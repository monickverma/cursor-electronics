"""
Live prices laid over a BOM view — cached quotes first, Mouser for the rest.

`brain/decisions.md` [2026-09-25]. Called by `GET /design/{id}/bom` after the
view is built; nothing else calls it, so generation, patching and validation
never wait on a distributor, and a price never decides a claim.

- No `MOUSER_API_KEY`: the view is returned as it was built — static prices,
  each with the date it was recorded — and says live pricing is off.
- A cached quote younger than `PRICE_CACHE_HOURS` is used as it is; the rest
  are asked of Mouser, ten to a request, and stored (PostgreSQL, never memory).
- Mouser failing leaves those rows static and the view says why; a failed
  request is never cached, so the next view asks again.
- A live price replaces a row's price only when Mouser listed that exact part
  number with a price and a currency. The static price stays on the row
  (`unit_price_usd`) and in the note.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

from pricing import mouser
from pricing.quotes import Quote, key, totals

ClientFactory = Callable[[], httpx.AsyncClient]


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=mouser.TIMEOUT)


async def _rollback(db: Any) -> None:
    """A failed cache statement must not fail the request's commit."""
    try:
        if db is not None and hasattr(db, "rollback"):
            await db.rollback()
    except Exception:                             # noqa: BLE001
        pass


def live_fields(quote: Quote, quantity: int) -> Optional[Dict[str, Any]]:
    """What a row shows for a live quote; None if it cannot price the row."""
    if not quote.found or not quote.currency:
        return None
    chosen = quote.price_for(quantity)
    if chosen is None:
        return None
    return {
        "source": quote.source,
        "distributor_pn": quote.distributor_pn,
        "currency": quote.currency,
        "unit_price": chosen.unit_price,
        "price_break": chosen.quantity,
        "breaks": [b.model_dump() for b in quote.breaks],
        "stock": quote.stock,
        "min_order": quote.min_order,
        "order_multiple": quote.order_multiple,
        "product_url": quote.product_url,
        "fetched_at": quote.fetched_at.isoformat(),
    }


def _note(live: Dict[str, Any], quantity: int, static_note: Optional[str]) -> str:
    stock = "stock not stated" if live["stock"] is None else f"{live['stock']:,} in stock"
    parts = [f"Mouser {live['distributor_pn'] or ''} quote fetched {live['fetched_at'][:16].replace('T', ' ')} UTC, "
             f"in {live['currency']}, at the {live['price_break']}-piece break; {stock}"]
    if live["min_order"] and live["min_order"] > quantity:
        parts.append(f"minimum order {live['min_order']}")
    if static_note:
        parts.append(f"catalogue price: {static_note}")
    return "; ".join(parts)


def apply(view: Dict[str, Any], quotes: Dict[str, Quote]) -> None:
    """Lay the quotes over the view's rows and substitutes, in place."""
    for row in view["rows"]:
        quote = quotes.get(key(row.get("part_number") or ""))
        live = live_fields(quote, row.get("quantity", 1)) if quote else None
        row["live"] = live
        if live is None:
            continue
        row["price_note"] = _note(live, row.get("quantity", 1), row.get("price_note"))
        row.update(unit_price=live["unit_price"], currency=live["currency"], price_known=True,
                   price_source=live["source"], price_asof=live["fetched_at"])
    for sub in view.get("substitutes", []):
        quote = quotes.get(key(sub.get("part_number") or ""))
        sub["live"] = live_fields(quote, 1) if quote else None
    view["totals"] = list(totals(view["rows"]))


async def price_view(
    db: Any, view: Dict[str, Any], *, api_key: str, cache_hours: float,
    client_factory: Optional[ClientFactory] = None, now: Optional[datetime] = None,
    get_cached: Optional[Callable] = None, put_cached: Optional[Callable] = None,
) -> Dict[str, Any]:
    """The view with live prices where they could be had, and a sentence saying which."""
    from db.crud import get_price_quotes, put_price_quotes

    get_cached = get_cached or get_price_quotes
    client_factory = client_factory or _default_client
    put_cached = put_cached or put_price_quotes
    view.setdefault("totals", list(totals(view["rows"])))
    wanted: List[str] = [r["part_number"] for r in view["rows"] if r.get("part_number")]
    wanted += [s["part_number"] for s in view.get("substitutes", []) if s.get("part_number")]
    status = {"enabled": bool(api_key.strip()), "source": mouser.SOURCE, "requested": len(set(map(key, wanted))),
              "quoted": 0, "from_cache": 0, "fetched": 0, "error": None, "cache_error": None}
    view["live_pricing"] = status
    if not status["enabled"]:
        view["pricing"] = ("Static catalogue prices, each with the date it was recorded. Live Mouser pricing is off: "
                           "no MOUSER_API_KEY is set.")
        for row in view["rows"]:
            row.setdefault("live", None)
        return view

    # Pricing is never the reason a BOM fails: the cache and the distributor
    # each fall back to the static prices, and the view says which failed.
    now = now or datetime.now(timezone.utc)
    fresh_after = now - timedelta(hours=cache_hours)
    keys = sorted(set(map(key, wanted)))
    quotes: Dict[str, Quote] = {}
    try:
        stored_quotes = await get_cached(db, mouser.SOURCE, keys)
    except Exception as exc:                      # noqa: BLE001 — the cache is an optimisation
        stored_quotes = {}
        status["cache_error"] = f"The price cache could not be read ({type(exc).__name__})."
        await _rollback(db)
    for k, stored in stored_quotes.items():
        try:
            quote = Quote.model_validate(stored)
        except ValueError:                        # a row this code no longer reads: ask again
            continue
        if quote.fetched_at >= fresh_after:
            quotes[k] = quote
    status["from_cache"] = len(quotes)
    missing = [pn for pn in dict.fromkeys(wanted) if key(pn) not in quotes]
    if missing:
        try:
            async with client_factory() as client:
                fetched = await mouser.fetch(missing, api_key, client, now)
        except mouser.MouserUnavailable as exc:
            status["error"] = str(exc)
        except Exception as exc:                  # noqa: BLE001 — an answer of a shape not expected
            status["error"] = f"Mouser's answer could not be read ({type(exc).__name__})"
        else:
            quotes.update(fetched)
            status["fetched"] = len(fetched)
            try:
                await put_cached(db, mouser.SOURCE, {k: q.model_dump(mode="json") for k, q in fetched.items()})
            except Exception as exc:              # noqa: BLE001 — shown now, asked again next time
                status["cache_error"] = " ".join(filter(None, (
                    status["cache_error"], f"The quotes could not be cached ({type(exc).__name__}).")))
                await _rollback(db)
    apply(view, quotes)
    live_rows = [r for r in view["rows"] if r.get("live")]
    status["quoted"] = len(live_rows)
    said = (f"Live Mouser prices on {len(live_rows)} of {len(view['rows'])} rows, each with the time it was "
            f"fetched; the others keep the static catalogue price and the date it was recorded.")
    if status["error"]:
        said += f" {status['error']}; those rows are not live."
    if status["cache_error"]:
        said += f" {status['cache_error']}"
    unlisted = [q.part_number for q in quotes.values() if not q.found]
    if unlisted:
        said += (" Mouser does not list " + ", ".join(sorted(unlisted)[:6])
                 + (" …" if len(unlisted) > 6 else "") + " under that exact part number.")
    view["pricing"] = said
    return view
