"""
Mouser Search API — exact manufacturer part numbers, ten to a request.

`POST https://api.mouser.com/api/v1/search/partnumber?apiKey=<key>` with
`{"SearchByPartRequest": {"mouserPartNumber": "A|B|…", "partSearchOptions": "Exact"}}`.
The answer lists `SearchResults.Parts[]`, each with `ManufacturerPartNumber`,
`MouserPartNumber`, `PriceBreaks[{Quantity, Price, Currency}]` and stock, and
an `Errors` list. Limits: 30 requests a minute, 1000 a day, per key.

**A listing is used only when its manufacturer part number equals the one
asked for** — the Stage 6 rule. An "Exact" search still returns variants
(`MAX485ECSA+` for `MAX485ECSA`); a variant is another orderable part.

**The key never leaves this module except in the request.** Mouser takes it in
the query string, so httpx's own log line for the request is redacted here,
and no error message built here carries a URL.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import httpx

from pricing.quotes import PriceBreak, Quote, key, parse_count, parse_price

SOURCE = "mouser"
API_URL = "https://api.mouser.com/api/v1/search/partnumber"
BATCH = 10
TIMEOUT = httpx.Timeout(8.0, connect=4.0)

_KEY_IN_TEXT = re.compile(r"(apiKey=)[^&\s\"'>]+", re.IGNORECASE)


def redact(text: str) -> str:
    return _KEY_IN_TEXT.sub(r"\1REDACTED", text)


def scrub(value: Any) -> Any:
    """`redact` over every string in a nested event — what Sentry is handed ([2026-10-01] #1)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(scrub(v) for v in value)
    return value


class _RedactApiKey(logging.Filter):
    """httpx logs every request's URL at INFO — with the key in it. Not here."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and "apikey=" in record.msg.lower():
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(str(a)) if "apikey=" in str(a).lower() else a for a in record.args)
        return True


for _name in ("httpx", "httpcore"):
    _logger = logging.getLogger(_name)
    if not any(isinstance(f, _RedactApiKey) for f in _logger.filters):
        _logger.addFilter(_RedactApiKey())


class MouserUnavailable(Exception):
    """Mouser could not answer. The message is safe to show: no URL, no key."""


#: Mouser's spec: each part number 3 to 40 characters. One outside it would
#: fail the whole request, and with it every part in the BOM.
PN_LENGTH = (3, 40)


def batches(part_numbers: Iterable[str]) -> List[List[str]]:
    """Distinct, queryable part numbers, ten to a request. A '|' would split one in two."""
    lo, hi = PN_LENGTH
    unique = list(dict.fromkeys(p.strip() for p in part_numbers
                                if p and "|" not in p and lo <= len(p.strip()) <= hi))
    return [unique[i:i + BATCH] for i in range(0, len(unique), BATCH)]


def _describe(errors: Sequence[Mapping[str, Any]]) -> str:
    first = errors[0] if errors else {}
    code = str(first.get("Code") or first.get("ResourceKey") or "error")[:40]
    message = str(first.get("Message") or "")[:160]
    return f"Mouser refused the request ({code}{': ' + message if message else ''})"


def _choose(listings: List[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Priced before unpriced, in stock before not, smallest minimum order, then by Mouser number."""
    def rank(p: Mapping[str, Any]):
        stock = parse_count(p.get("AvailabilityInStock")) or parse_count(p.get("Availability")) or 0
        return (not p.get("PriceBreaks"), stock <= 0, parse_count(p.get("Min")) or 1,
                str(p.get("MouserPartNumber") or ""))
    return sorted(listings, key=rank)[0]


def quote_from(part_number: str, listings: List[Mapping[str, Any]], fetched_at: datetime) -> Quote:
    if not listings:
        return Quote(source=SOURCE, part_number=part_number, found=False, fetched_at=fetched_at)
    chosen = _choose(listings)
    breaks, currency = [], None
    for b in chosen.get("PriceBreaks") or []:
        price, quantity = parse_price(b.get("Price"), b.get("Currency")), parse_count(b.get("Quantity"))
        if price is None or not quantity:
            continue
        breaks.append(PriceBreak(quantity=quantity, unit_price=price))
        if currency is None and b.get("Currency"):
            currency = str(b["Currency"]).strip().upper() or None
    stock = parse_count(chosen.get("AvailabilityInStock"))
    if stock is None:
        stock = parse_count(chosen.get("Availability"))
    return Quote(
        source=SOURCE, part_number=part_number, found=True, fetched_at=fetched_at,
        currency=currency, breaks=tuple(breaks), stock=stock,
        distributor_pn=chosen.get("MouserPartNumber"), manufacturer=chosen.get("Manufacturer"),
        min_order=parse_count(chosen.get("Min")), order_multiple=parse_count(chosen.get("Mult")),
        product_url=chosen.get("ProductDetailUrl"), listings=len(listings),
    )


async def fetch(part_numbers: Iterable[str], api_key: str, client: httpx.AsyncClient,
                fetched_at: datetime) -> Dict[str, Quote]:
    """
    One quote per part number asked for, keyed by `quotes.key`. Raises
    `MouserUnavailable` on any failure — a partial answer is not stored.
    """
    out: Dict[str, Quote] = {}
    for batch in batches(part_numbers):
        body = {"SearchByPartRequest": {"mouserPartNumber": "|".join(batch), "partSearchOptions": "Exact"}}
        try:
            response = await client.post(API_URL, params={"apiKey": api_key}, json=body, timeout=TIMEOUT)
        except httpx.TimeoutException:
            raise MouserUnavailable("Mouser did not answer in time") from None
        except httpx.HTTPError as exc:
            raise MouserUnavailable(f"Mouser could not be reached ({type(exc).__name__})") from None
        if response.status_code == 429:
            raise MouserUnavailable("Mouser's rate limit was reached (30 requests a minute, 1000 a day)")
        if response.status_code >= 400:
            raise MouserUnavailable(f"Mouser answered HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise MouserUnavailable("Mouser's answer was not JSON") from None
        errors = data.get("Errors") or []
        if errors:
            message = _describe(errors)
            raise MouserUnavailable(redact(message.replace(api_key, "REDACTED") if api_key else message))
        parts = (data.get("SearchResults") or {}).get("Parts") or []
        for pn in batch:
            exact = [p for p in parts if key(str(p.get("ManufacturerPartNumber") or "")) == key(pn)]
            out[key(pn)] = quote_from(pn, exact, fetched_at)
    return out
