"""
The live-price cache against a real PostgreSQL. `tests/test_pricing.py` replaces
the cache with an in-memory stand-in at `price_view`'s seams; this file does
not. The startup migration, `get_price_quotes`, `put_price_quotes` (an
`INSERT … ON CONFLICT DO UPDATE`) and `price_view`'s default path all run
against a real server, and every assertion reads back through a fresh session.

Auto-skipped unless TEST_DATABASE_URL names a database, as in
`test_postgres_signoff.py` (which says how to set one up with docker compose).
It writes only rows under its own source name and deletes them afterwards.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL not set")

SOURCE = "test-price-cache"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


async def _with_session(work):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from db.migrations import apply_migrations

    engine = create_async_engine(_URL, poolclass=NullPool, future=True)
    try:
        assert await apply_migrations(engine), "the startup migrations must apply"
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await work(session)
            await session.commit()
            return result
    finally:
        await engine.dispose()


async def _clean(session):
    from sqlalchemy import delete

    from db.models import PriceQuote

    await session.execute(delete(PriceQuote).where(PriceQuote.source.in_([SOURCE, "mouser-test"])))


def _quote(pn, found=True, price=0.01, at=NOW):
    from pricing.quotes import PriceBreak, Quote

    return Quote(source=SOURCE, part_number=pn, found=found, fetched_at=at, currency="USD" if found else None,
                 breaks=(PriceBreak(quantity=1, unit_price=price),) if found else ()).model_dump(mode="json")


def test_the_cache_stores_reads_back_and_upserts():
    from db.crud import get_price_quotes, put_price_quotes

    async def write_first(session):
        await _clean(session)
        await put_price_quotes(session, SOURCE, {"RC0402FR-0710KL": _quote("RC0402FR-0710KL"),
                                                 "MAX485ECSA": _quote("MAX485ECSA", found=False)})

    async def read(session):
        return await get_price_quotes(session, SOURCE, ["RC0402FR-0710KL", "MAX485ECSA", "NOT-THERE"])

    async def write_again(session):
        later = NOW + timedelta(hours=30)
        await put_price_quotes(session, SOURCE, {"RC0402FR-0710KL": _quote("RC0402FR-0710KL", price=0.02, at=later)})

    try:
        _run(_with_session(write_first))
        first = _run(_with_session(read))
        assert set(first) == {"RC0402FR-0710KL", "MAX485ECSA"}
        assert first["MAX485ECSA"]["found"] is False
        _run(_with_session(write_again))
        again = _run(_with_session(read))
        assert again["RC0402FR-0710KL"]["breaks"][0]["unit_price"] == 0.02, "a newer answer replaces the older"
        assert again["MAX485ECSA"]["found"] is False, "an upsert touches only its own row"
    finally:
        _run(_with_session(_clean))


def test_price_view_uses_the_real_cache_by_default():
    import httpx

    from pricing import live, mouser

    def answer(request):
        parts = [{"ManufacturerPartNumber": "RC0402FR-0710KL", "MouserPartNumber": "603-RC0402FR-0710KL",
                  "Min": "1", "Mult": "1", "AvailabilityInStock": "10",
                  "PriceBreaks": [{"Quantity": 1, "Price": "$0.0100", "Currency": "USD"}]}]
        return httpx.Response(200, json={"Errors": [], "SearchResults": {"Parts": parts}})

    view = {"rows": [{"id": "R1", "part_number": "RC0402FR-0710KL", "quantity": 1, "price_known": False,
                      "unit_price": None, "currency": None, "price_source": "unknown"}], "substitutes": []}
    original = mouser.SOURCE
    mouser.SOURCE = "mouser-test"            # never mix test rows with real cached quotes
    try:
        async def priced(session):
            await _clean(session)
            return await live.price_view(session, view, api_key="test-key", cache_hours=24, now=NOW,
                                         client_factory=lambda: httpx.AsyncClient(
                                             transport=httpx.MockTransport(answer)))
        out = _run(_with_session(priced))
        assert out["rows"][0]["live"]["unit_price"] == 0.01 and out["live_pricing"]["error"] is None
        assert out["live_pricing"]["cache_error"] is None, out["live_pricing"]["cache_error"]

        async def stored(session):
            from db.crud import get_price_quotes
            return await get_price_quotes(session, "mouser-test", ["RC0402FR-0710KL"])
        assert _run(_with_session(stored))["RC0402FR-0710KL"]["found"] is True
    finally:
        mouser.SOURCE = original
        _run(_with_session(_clean))
