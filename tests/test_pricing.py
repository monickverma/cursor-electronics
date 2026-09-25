"""
Live distributor pricing — Mouser, optional. `brain/decisions.md` [2026-09-25].

A part is priced only as itself; a quote is dated and in its own currency;
the cache is PostgreSQL's; a failure falls back visibly; the key never
appears in a log line or an answer; and nothing that validates reads a price.
No test here reaches the network: every request goes to a mock transport.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from db.migrations import MIGRATIONS, is_safe
from db.models import PriceQuote
from pricing import live, mouser
from pricing.quotes import PriceBreak, Quote, key, parse_count, parse_price, totals

BACKEND = Path(__file__).parent.parent / "backend"
SCHEMA_SQL = BACKEND / "db" / "schema.sql"
KEY = "sk-mouser-TEST-5f3a9c"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def _part(mpn, price="$0.10", currency="USD", stock="12345", mouser_pn=None, breaks=None, minimum="1"):
    return {
        "ManufacturerPartNumber": mpn, "MouserPartNumber": mouser_pn or f"603-{mpn}", "Manufacturer": "Maker",
        "PriceBreaks": breaks if breaks is not None else [{"Quantity": 1, "Price": price, "Currency": currency}],
        "AvailabilityInStock": stock, "Availability": f"{stock} In Stock", "Min": minimum, "Mult": "1",
        "ProductDetailUrl": f"https://www.mouser.com/ProductDetail/{mpn}",
    }


class _Mouser:
    """A mock Mouser: answers from a catalogue, records what it was asked."""

    def __init__(self, catalogue=None, status=200, errors=None, raise_exc=None):
        self.catalogue, self.status, self.errors, self.raise_exc = catalogue or {}, status, errors, raise_exc
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_exc:
            raise self.raise_exc
        if self.status != 200:
            return httpx.Response(self.status, json={})
        body = json.loads(request.content)
        asked = body["SearchByPartRequest"]["mouserPartNumber"].split("|")
        parts = [p for pn in asked for p in self.catalogue.get(pn.upper(), [])]
        return httpx.Response(200, json={"Errors": self.errors or [],
                                         "SearchResults": {"NumberOfResult": len(parts), "Parts": parts}})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def _fetch(mock, part_numbers):
    async def run():
        async with mock.client() as client:
            return await mouser.fetch(part_numbers, KEY, client, NOW)
    return asyncio.run(run())


# ── Prices as the distributor formats them ────────────────────────────────────

@pytest.mark.parametrize("text, value", [
    ("$0.10", 0.10), ("$1,234.56", 1234.56), ("6,85 €", 6.85), ("0,069 €", 0.069),
    ("1.234,56 €", 1234.56), ("₹8.50", 8.50), ("1'234.50 CHF", 1234.50), ("£0.0412", 0.0412),
    ("1,234,567", 1234567.0), (0.25, 0.25), ("", None), ("Quote", None), (None, None),
])
def test_parse_price_reads_every_locale_mouser_answers_in(text, value):
    assert parse_price(text) == value


@pytest.mark.parametrize("text, value", [
    ("12345", 12345), ("12,345 In Stock", 12345), ("1.234 auf Lager", 1234), ("None", None), (None, None), (7, 7),
])
def test_parse_count(text, value):
    assert parse_count(text) == value


def test_price_for_takes_the_break_at_or_below_the_quantity():
    q = Quote(source="mouser", part_number="X", found=True, fetched_at=NOW, currency="USD",
              breaks=(PriceBreak(quantity=10, unit_price=0.05), PriceBreak(quantity=1, unit_price=0.10),
                      PriceBreak(quantity=100, unit_price=0.02)))
    assert q.price_for(1).unit_price == 0.10 and q.price_for(50).unit_price == 0.05
    assert q.price_for(1000).unit_price == 0.02
    only_reel = Quote(source="mouser", part_number="X", found=True, fetched_at=NOW, currency="USD",
                      breaks=(PriceBreak(quantity=5000, unit_price=0.001),))
    assert only_reel.price_for(1).quantity == 5000


def test_key_is_trimmed_and_case_blind():
    assert key("  rc0402fr-0710kl ") == key("RC0402FR-0710KL") == "RC0402FR-0710KL"


def test_totals_are_per_currency_never_converted():
    rows = [
        {"price_known": True, "unit_price": 0.10, "currency": "USD", "quantity": 1, "price_source": "static"},
        {"price_known": True, "unit_price": 6.85, "currency": "EUR", "quantity": 2, "price_source": "mouser"},
        {"price_known": True, "unit_price": 0.05, "currency": "USD", "quantity": 1, "price_source": "mouser"},
        {"price_known": False, "unit_price": None, "currency": None, "quantity": 1, "price_source": "unknown"},
    ]
    by = {t["currency"]: t for t in totals(rows)}
    assert set(by) == {"USD", "EUR"}
    assert by["USD"]["amount"] == pytest.approx(0.15) and by["USD"]["sources"] == ["static", "mouser"]
    assert by["EUR"]["amount"] == pytest.approx(13.70) and by["EUR"]["rows"] == 1


# ── The Mouser request and its answer ─────────────────────────────────────────

def test_fetch_asks_for_exact_part_numbers_ten_to_a_request():
    mock = _Mouser()
    parts = [f"RC0402FR-07{i}KL" for i in range(23)] + ["RC0402FR-070KL"]      # one repeated
    quotes = _fetch(mock, parts)
    assert len(mock.requests) == 3 and len(quotes) == 23
    first = mock.requests[0]
    assert first.method == "POST" and first.url.path == "/api/v1/search/partnumber"
    assert first.url.params["apiKey"] == KEY
    body = json.loads(first.content)["SearchByPartRequest"]
    assert body["partSearchOptions"] == "Exact" and len(body["mouserPartNumber"].split("|")) == 10


def test_batches_skip_what_cannot_be_asked():
    assert mouser.batches(["A", "A", " ", "B|C", "D"]) == [["A", "D"]]


def test_fetch_prices_a_part_only_as_itself():
    # An "Exact" search still returns the lead-free variant; it is another orderable part.
    mock = _Mouser({"MAX485ECSA": [_part("MAX485ECSA+", "$3.21")],
                    "RC0402FR-0710KL": [_part("RC0402FR-0710KL", "$0.10")]})
    quotes = _fetch(mock, ["MAX485ECSA", "RC0402FR-0710KL"])
    assert quotes["MAX485ECSA"].found is False
    ok = quotes["RC0402FR-0710KL"]
    assert ok.found and ok.currency == "USD" and ok.breaks[0].unit_price == 0.10
    assert ok.distributor_pn == "603-RC0402FR-0710KL" and ok.stock == 12345 and ok.fetched_at == NOW


def test_quote_from_reads_a_non_us_account_and_prefers_a_stocked_listing():
    listings = [
        _part("CL05B104KO5NNNC", "0,012 €", "EUR", stock="0", mouser_pn="187-B"),
        _part("CL05B104KO5NNNC", "0,009 €", "EUR", stock="80000", mouser_pn="187-A"),
    ]
    q = mouser.quote_from("CL05B104KO5NNNC", listings, NOW)
    assert (q.distributor_pn, q.currency, q.breaks[0].unit_price, q.listings) == ("187-A", "EUR", 0.009, 2)


@pytest.mark.parametrize("mock, words", [
    (_Mouser(status=429), "rate limit"),
    (_Mouser(status=503), "HTTP 503"),
    (_Mouser(raise_exc=httpx.ReadTimeout("slow")), "in time"),
    (_Mouser(raise_exc=httpx.ConnectError("down")), "could not be reached"),
    (_Mouser(errors=[{"Code": "Invalid", "Message": f"Invalid unique identifier {KEY}."}]), "Invalid"),
])
def test_fetch_failures_say_why_and_never_carry_the_key(mock, words):
    with pytest.raises(mouser.MouserUnavailable) as caught:
        _fetch(mock, ["RC0402FR-0710KL"])
    assert words in str(caught.value) and KEY not in str(caught.value)
    assert "api.mouser.com" not in str(caught.value)


def test_redact_removes_the_key_from_any_text():
    assert mouser.redact(f"https://api.mouser.com/x?apiKey={KEY}&y=1") == \
        "https://api.mouser.com/x?apiKey=REDACTED&y=1"


def test_httpx_log_lines_never_show_the_key(caplog):
    caplog.set_level(logging.DEBUG, logger="httpx")
    _fetch(_Mouser({"RC0402FR-0710KL": [_part("RC0402FR-0710KL")]}), ["RC0402FR-0710KL"])
    assert "HTTP Request" in caplog.text, "httpx no longer logs requests; this test proves nothing"
    assert KEY not in caplog.text and "apiKey=REDACTED" in caplog.text


# ── The BOM view ──────────────────────────────────────────────────────────────

def _view():
    rows = [
        {"id": "R1", "part_number": "RC0402FR-0710KL", "quantity": 1, "price_known": True, "unit_price": 0.001,
         "currency": "USD", "unit_price_usd": 0.001, "price_source": "part_number", "price_asof": "2026-07-25",
         "price_note": "static catalogue price, recorded in the repository on 2026-07-25"},
        {"id": "U2", "part_number": "MAX485ECSA", "quantity": 1, "price_known": True, "unit_price": 1.2,
         "currency": "USD", "unit_price_usd": 1.2, "price_source": "part_number", "price_asof": "2026-07-25",
         "price_note": "static"},
        {"id": "U9", "part_number": "NOT-IN-CATALOGUE", "quantity": 1, "price_known": False, "unit_price": None,
         "currency": None, "unit_price_usd": 0.0, "price_source": "unknown", "price_asof": None, "price_note": None},
    ]
    return {"rows": rows, "substitutes": [{"component_id": "R1", "part_number": "RC0402JR-0710KL"}]}


class _Cache:
    def __init__(self, stored=None):
        self.stored, self.puts = dict(stored or {}), []

    async def get(self, db, source, keys):
        return {k: v for k, v in self.stored.items() if k in keys}

    async def put(self, db, source, quotes):
        self.puts.append(dict(quotes))
        self.stored.update(quotes)


def _price(view, mock=None, cache=None, api_key=KEY):
    cache = cache or _Cache()

    def factory():
        if mock is None:
            raise AssertionError("no request may be made")
        return mock.client()

    out = asyncio.run(live.price_view(None, view, api_key=api_key, cache_hours=24, client_factory=factory,
                                      now=NOW, get_cached=cache.get, put_cached=cache.put))
    return out, cache


def test_price_view_without_a_key_changes_nothing_and_asks_nobody():
    view, cache = _price(_view(), mock=None, api_key="")
    assert view["live_pricing"]["enabled"] is False and "no MOUSER_API_KEY" in view["pricing"]
    assert [r["price_source"] for r in view["rows"]] == ["part_number", "part_number", "unknown"]
    assert all(r["live"] is None for r in view["rows"]) and cache.puts == []


def test_price_view_lays_live_quotes_over_the_rows_dated_and_in_their_currency():
    mock = _Mouser({"RC0402FR-0710KL": [_part("RC0402FR-0710KL", "0,009 €", "EUR")],
                    "RC0402JR-0710KL": [_part("RC0402JR-0710KL", "0,007 €", "EUR")]})
    view, cache = _price(_view(), mock)
    rows = {r["id"]: r for r in view["rows"]}
    r1 = rows["R1"]
    assert (r1["price_source"], r1["currency"], r1["unit_price"]) == ("mouser", "EUR", 0.009)
    assert r1["price_asof"] == NOW.isoformat() and r1["unit_price_usd"] == 0.001, "the static price stays"
    assert "catalogue price" in r1["price_note"] and "2026-07-25" in r1["price_note"]
    # MAX485ECSA is not listed under that exact number: it keeps its static price.
    assert rows["U2"]["price_source"] == "part_number" and rows["U2"]["live"] is None
    assert "MAX485ECSA" in view["pricing"]
    assert {t["currency"] for t in view["totals"]} == {"USD", "EUR"}
    assert view["substitutes"][0]["live"]["unit_price"] == 0.007
    assert len(cache.puts) == 1 and cache.stored["MAX485ECSA"]["found"] is False, "not listed is cached"
    assert KEY not in json.dumps(view)


def test_price_view_uses_a_fresh_cached_quote_and_refetches_a_stale_one():
    fresh = Quote(source="mouser", part_number="RC0402FR-0710KL", found=True, fetched_at=NOW - timedelta(hours=2),
                  currency="USD", breaks=(PriceBreak(quantity=1, unit_price=0.02),)).model_dump(mode="json")
    stale = Quote(source="mouser", part_number="MAX485ECSA", found=False,
                  fetched_at=NOW - timedelta(hours=30)).model_dump(mode="json")
    other = Quote(source="mouser", part_number="NOT-IN-CATALOGUE", found=False,
                  fetched_at=NOW - timedelta(hours=1)).model_dump(mode="json")
    sub = Quote(source="mouser", part_number="RC0402JR-0710KL", found=False,
                fetched_at=NOW - timedelta(hours=1)).model_dump(mode="json")
    cache = _Cache({"RC0402FR-0710KL": fresh, "MAX485ECSA": stale, "NOT-IN-CATALOGUE": other,
                    "RC0402JR-0710KL": sub})
    mock = _Mouser({"MAX485ECSA": [_part("MAX485ECSA", "$2.50")]})
    view, cache = _price(_view(), mock, cache)
    asked = [json.loads(r.content)["SearchByPartRequest"]["mouserPartNumber"] for r in mock.requests]
    assert asked == ["MAX485ECSA"], "only the stale quote is asked again"
    rows = {r["id"]: r for r in view["rows"]}
    assert rows["R1"]["unit_price"] == 0.02 and rows["U2"]["unit_price"] == 2.50
    assert view["live_pricing"]["from_cache"] == 3 and view["live_pricing"]["fetched"] == 1


def test_price_view_falls_back_visibly_and_caches_no_failure():
    view, cache = _price(_view(), _Mouser(status=429))
    assert all(r["live"] is None for r in view["rows"]) and cache.puts == []
    assert "rate limit" in view["pricing"] and view["live_pricing"]["error"]
    assert [r["price_source"] for r in view["rows"]] == ["part_number", "part_number", "unknown"]


def test_price_view_survives_a_cache_that_cannot_be_read_or_written():
    class Broken(_Cache):
        async def get(self, db, source, keys):
            raise ConnectionError("database down")

        async def put(self, db, source, quotes):
            raise ConnectionError("database down")

    mock = _Mouser({"RC0402FR-0710KL": [_part("RC0402FR-0710KL", "$0.02")]})
    view, _ = _price(_view(), mock, Broken())
    rows = {r["id"]: r for r in view["rows"]}
    assert rows["R1"]["price_source"] == "mouser", "Mouser still answered; the row is live"
    assert view["live_pricing"]["cache_error"] and view["live_pricing"]["error"] is None
    assert "could not be read" in view["pricing"]


def test_price_view_asks_again_for_a_cached_row_it_cannot_read():
    cache = _Cache({"RC0402FR-0710KL": {"source": "mouser", "shape": "from an older version"}})
    mock = _Mouser({"RC0402FR-0710KL": [_part("RC0402FR-0710KL", "$0.02")]})
    view, cache = _price(_view(), mock, cache)
    assert {r["id"]: r for r in view["rows"]}["R1"]["unit_price"] == 0.02
    assert cache.stored["RC0402FR-0710KL"]["found"] is True


def test_price_view_keeps_static_prices_when_mouser_answers_in_an_unexpected_shape():
    class Odd(_Mouser):
        def handler(self, request):
            self.requests.append(request)
            return httpx.Response(200, json={"Errors": [], "SearchResults": {"Parts": [
                {"ManufacturerPartNumber": "RC0402FR-0710KL", "PriceBreaks": "not a list"}]}})

    view, cache = _price(_view(), Odd())
    assert all(r["live"] is None for r in view["rows"]) and cache.puts == []
    assert "could not be read" in view["live_pricing"]["error"]
    assert [r["price_source"] for r in view["rows"]] == ["part_number", "part_number", "unknown"]


def test_live_fields_need_a_price_and_a_currency():
    no_currency = Quote(source="mouser", part_number="X", found=True, fetched_at=NOW,
                        breaks=(PriceBreak(quantity=1, unit_price=1.0),))
    no_breaks = Quote(source="mouser", part_number="X", found=True, fetched_at=NOW, currency="USD")
    assert live.live_fields(no_currency, 1) is None and live.live_fields(no_breaks, 1) is None


def test_apply_notes_a_minimum_order_above_the_quantity():
    view = _view()
    quote = Quote(source="mouser", part_number="RC0402FR-0710KL", found=True, fetched_at=NOW, currency="USD",
                  breaks=(PriceBreak(quantity=10000, unit_price=0.0008),), min_order=10000, distributor_pn="603-X")
    live.apply(view, {"RC0402FR-0710KL": quote})
    assert "minimum order 10000" in view["rows"][0]["price_note"]


# ── Where pricing may and may not reach ───────────────────────────────────────

def test_nothing_that_validates_imports_pricing():
    for folder in ("validation", "proof", "generators"):
        for path in (BACKEND / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                assert not any(n == "pricing" or n.startswith("pricing.") for n in names), path


def test_the_price_cache_table_is_one_shape_everywhere():
    found = [s for s in MIGRATIONS if "price_quotes" in s]
    assert len(found) == 1 and is_safe(found[0])
    body = found[0].split("(", 1)[1].rsplit(")", 1)[0]
    in_migration = {part.split()[0] for part in body.split(",") if part.strip()} - {"PRIMARY", "part_number)"}
    block = SCHEMA_SQL.read_text(encoding="utf-8").split("CREATE TABLE price_quotes (", 1)[1].split(");", 1)[0]
    in_schema = {line.split()[0] for line in block.splitlines()
                 if line.strip() and not line.strip().startswith(("--", "PRIMARY"))}
    assert in_schema == in_migration == set(PriceQuote.__table__.columns.keys())
    assert {c.name for c in PriceQuote.__table__.primary_key.columns} == {"source", "part_number"}
