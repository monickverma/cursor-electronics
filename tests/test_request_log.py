"""
Tests for §4.5 request instrumentation.

Stage 0 gate: "Every request produces a complete log row — analytic, G1
(schema-enforced)." G1 means the claim holds for every point in the declared
space, not for a sample — so these tests assert that an incomplete row cannot
be *constructed*, and that the middleware emits a row on every exit path
including the ones nobody remembers: exceptions, 4xx, and handlers that never
mention instrumentation at all.

No database is required. The logger's Postgres path is exercised through its
failure branch, which is the branch that must not lose data.
"""

import asyncio
import json
import os

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from middleware.instrumentation import RequestLogMiddleware
from observability.request_log import (
    LOG_SCHEMA_VERSION,
    Outcome,
    RequestLogContext,
    RequestLogger,
    RequestLogRow,
    log_ctx,
    prompt_hash,
)


# ── prompt_hash ───────────────────────────────────────────────────────────────

class TestPromptHash:
    def test_prompt_hash_is_stable(self):
        assert prompt_hash("RC filter 1kHz") == prompt_hash("RC filter 1kHz")

    def test_prompt_hash_ignores_surrounding_whitespace(self):
        # The §4.4 cache key must treat a trailing newline as the same prompt,
        # or the cache never hits for anyone who pasted their text.
        assert prompt_hash("RC filter 1kHz") == prompt_hash("  RC filter 1kHz\n")

    def test_prompt_hash_differs_for_different_prompts(self):
        assert prompt_hash("RC filter 1kHz") != prompt_hash("RC filter 2kHz")

    def test_prompt_hash_is_sha256_hex(self):
        assert len(prompt_hash("x")) == 64
        int(prompt_hash("x"), 16)  # raises if not hex


# ── RequestLogRow: completeness is enforced at construction ───────────────────

class TestRequestLogRowSchemaEnforcement:
    def test_minimal_row_is_valid(self):
        row = RequestLogRow(route="GET /design/list", outcome=Outcome.COMPLETED, latency_ms=12)
        assert row.schema_version == LOG_SCHEMA_VERSION
        assert row.api_calls == 0
        assert row.request_id and row.created_at

    def test_route_is_required(self):
        with pytest.raises(ValidationError):
            RequestLogRow(outcome=Outcome.COMPLETED, latency_ms=1)

    def test_latency_is_required(self):
        with pytest.raises(ValidationError):
            RequestLogRow(route="POST /design/generate", outcome=Outcome.COMPLETED)

    def test_negative_latency_rejected(self):
        with pytest.raises(ValidationError):
            RequestLogRow(route="r", outcome=Outcome.COMPLETED, latency_ms=-1)

    def test_unknown_field_rejected(self):
        # extra="forbid": a typo'd field name must fail loudly rather than
        # silently write a row missing the data someone thought they logged.
        with pytest.raises(ValidationError):
            RequestLogRow(route="r", outcome=Outcome.COMPLETED, latency_ms=1, promt_hash="x")

    def test_refusal_requires_a_reason(self):
        with pytest.raises(ValidationError):
            RequestLogRow(
                route="POST /design/generate",
                outcome=Outcome.REFUSED,
                latency_ms=5,
                prompt_hash="a" * 64,
            )

    def test_refusal_requires_a_prompt_hash(self):
        with pytest.raises(ValidationError):
            RequestLogRow(
                route="POST /design/generate",
                outcome=Outcome.REFUSED,
                latency_ms=5,
                refusal_reason="cutoff_hz 2 MHz outside declared envelope",
            )

    def test_valid_refusal_row(self):
        row = RequestLogRow(
            route="POST /design/generate",
            outcome=Outcome.REFUSED,
            latency_ms=5,
            prompt_hash="a" * 64,
            refusal_reason="cutoff_hz 2 MHz outside declared envelope",
        )
        assert row.outcome == Outcome.REFUSED.value
        assert row.refusal_reason

    def test_circuit_id_requires_prompt_hash(self):
        # A design that exists came from a prompt. Without the pair the row
        # cannot join back to anything and the cache key is unusable.
        with pytest.raises(ValidationError):
            RequestLogRow(
                route="POST /design/generate",
                outcome=Outcome.COMPLETED,
                latency_ms=900,
                circuit_id="c-1",
            )

    def test_plain_read_route_needs_no_prompt_hash(self):
        # The requirement keys on what the request did, not which route it hit.
        row = RequestLogRow(route="GET /design/list", outcome=Outcome.COMPLETED, latency_ms=3)
        assert row.prompt_hash is None

    def test_failed_row_needs_no_prompt_hash(self):
        # A request that died before its body was read has no prompt to record,
        # and must still produce a row.
        row = RequestLogRow(route="POST /design/generate", outcome=Outcome.FAILED, latency_ms=2)
        assert row.outcome == Outcome.FAILED.value


# ── RequestLogContext ─────────────────────────────────────────────────────────

class TestRequestLogContext:
    def test_default_outcome_is_failed(self):
        # Pessimistic by default: a request that dies before any handler code
        # runs should read as a failure without anyone having set it.
        assert RequestLogContext(route="r").outcome == Outcome.FAILED

    def test_count_api_call_accumulates(self):
        ctx = RequestLogContext(route="r")
        ctx.count_api_call()
        ctx.count_api_call(2)
        assert ctx.api_calls == 3

    def test_refuse_sets_outcome_and_reason(self):
        ctx = RequestLogContext(route="r")
        ctx.refuse("no generator accepts supply_v=48")
        assert ctx.outcome == Outcome.REFUSED
        assert ctx.refusal_reason == "no generator accepts supply_v=48"

    def test_complete_sets_outcome_and_circuit_id(self):
        ctx = RequestLogContext(route="r")
        ctx.complete(circuit_id="abc")
        assert ctx.outcome == Outcome.COMPLETED
        assert ctx.circuit_id == "abc"

    def test_to_row_carries_every_field(self):
        ctx = RequestLogContext(route="POST /design/generate")
        ctx.prompt_hash = "b" * 64
        ctx.user_id = "u1"
        ctx.generator = "rc_lowpass@1.0.0"
        ctx.underdetermined = ["supply_v"]
        ctx.intent_ir = {"requirements": {"function": "low_pass_filter"}}
        ctx.count_api_call()
        ctx.complete(circuit_id="c1")

        row = ctx.to_row(latency_ms=1234)

        assert row.route == "POST /design/generate"
        assert row.latency_ms == 1234
        assert row.api_calls == 1
        assert row.user_id == "u1"
        assert row.circuit_id == "c1"
        assert row.generator == "rc_lowpass@1.0.0"
        assert row.underdetermined == ["supply_v"]
        assert row.intent_ir == {"requirements": {"function": "low_pass_filter"}}

    def test_log_ctx_returns_throwaway_when_uninstrumented(self):
        class Bare:
            pass

        ctx = log_ctx(Bare())
        assert isinstance(ctx, RequestLogContext)
        ctx.count_api_call()  # must not raise


# ── RequestLogger: the failure branch is the one that matters ────────────────

class TestRequestLogger:
    def test_record_falls_back_to_jsonl_when_db_unreachable(self, tmp_path):
        # No database in this test run, so _write_db raises — which is exactly
        # the path under test. "Data not logged is gone permanently" (§4.5),
        # so an unreachable Postgres must not mean a lost row.
        logger = RequestLogger(fallback_path=tmp_path / "fallback.jsonl")
        row = RequestLogRow(route="POST /design/generate", outcome=Outcome.FAILED, latency_ms=7)

        reached_db = asyncio.run(logger.record(row))

        assert reached_db is False
        written = logger.read_fallback()
        assert len(written) == 1
        assert written[0]["route"] == "POST /design/generate"
        assert written[0]["request_id"] == row.request_id

    def test_record_never_raises(self, tmp_path):
        # A directory where the file should be: opening it for append fails.
        bad = tmp_path / "fallback.jsonl"
        bad.mkdir()
        logger = RequestLogger(fallback_path=bad)
        row = RequestLogRow(route="r", outcome=Outcome.FAILED, latency_ms=1)

        assert asyncio.run(logger.record(row)) is False  # must not raise

    def test_fallback_path_is_redirected_away_from_the_source_tree(self):
        # The suite has no database, so every request a test makes through the
        # app falls back to this file. Left at its default it accumulates
        # inside backend/observability/ run after run — conftest.py redirects
        # it, and this is what notices if that stops happening.
        import observability.request_log as module

        assert "backend" not in str(module._FALLBACK_PATH).replace("\\", "/").split("/")[:-1], (
            f"request-log sidecar would be written into the source tree at "
            f"{module._FALLBACK_PATH}"
        )

    def test_read_fallback_empty_when_no_file(self, tmp_path):
        assert RequestLogger(fallback_path=tmp_path / "nope.jsonl").read_fallback() == []

    def test_read_fallback_skips_corrupt_lines(self, tmp_path):
        path = tmp_path / "fallback.jsonl"
        good = RequestLogRow(route="r", outcome=Outcome.FAILED, latency_ms=1)
        path.write_text(
            json.dumps(good.model_dump(), default=str) + "\n{ not json\n",
            encoding="utf-8",
        )
        assert len(RequestLogger(fallback_path=path).read_fallback()) == 1

    def test_fallback_rows_are_json_round_trippable(self, tmp_path):
        # The sidecar is a replay source. A row that cannot be read back is a
        # row that was not really kept.
        logger = RequestLogger(fallback_path=tmp_path / "f.jsonl")
        row = RequestLogRow(
            route="POST /design/generate",
            outcome=Outcome.REFUSED,
            latency_ms=11,
            prompt_hash="c" * 64,
            refusal_reason="out of envelope",
            intent_ir={"requirements": {"targets": {"cutoff_hz": 2_000_000}}},
        )
        logger.write_fallback(row)

        replayed = RequestLogRow(**logger.read_fallback()[0])
        assert replayed.model_dump() == row.model_dump()


# ── Middleware: a row on every exit path ─────────────────────────────────────

# ── Postgres round trip ──────────────────────────────────────────────────────
#
# Auto-skipped unless TEST_DATABASE_URL names a reachable database with the
# request_log table, in the same spirit as the ngspice and arduino-cli skips.
# To run it:
#
#   docker compose up -d db
#   TEST_DATABASE_URL=postgresql+asyncpg://circuitos_user:circuitos_pass@localhost:5432/circuitos \
#       pytest tests/test_request_log.py -k Postgres
#
# Note that `schema.sql` only runs on a *fresh* volume, so an existing database
# needs the request_log DDL applied by hand — there is no migration tool in
# this repo.

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
_skip_no_postgres = pytest.mark.skipif(
    not _TEST_DB_URL, reason="TEST_DATABASE_URL not set"
)


@_skip_no_postgres
class TestPostgresRoundTrip:
    """
    The write path. Everything else in this file exercises the failure branch,
    which is the branch that must not lose data — this is the branch that must
    actually store it.
    """

    def _run(self, tmp_path):
        import db.models as models
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        engine = create_async_engine(_TEST_DB_URL, future=True)
        original = models.engine
        models.engine = engine  # _write_db imports this at call time

        logger = RequestLogger(fallback_path=tmp_path / "fb.jsonl")
        row = RequestLogRow(
            route="POST /design/generate",
            outcome=Outcome.REFUSED,
            latency_ms=1234,
            api_calls=1,
            prompt_hash=prompt_hash("buck converter 48V"),
            refusal_reason="no generator declares an envelope covering switching converters",
            intent_ir={"requirements": {"targets": {"cutoff_hz": 2_000_000}}},
            underdetermined=["source_impedance_ohm"],
            generator="rc_lowpass@0.1.0",
            user_id="u-1",
            status_code=200,
        )

        async def go():
            first = await logger.record(row)
            async with AsyncSession(engine) as session:
                stored = (
                    await session.execute(
                        select(models.RequestLog).where(
                            models.RequestLog.request_id == row.request_id
                        )
                    )
                ).scalar_one()
                # Detach before the session closes so attributes stay readable.
                session.expunge(stored)
            duplicate = await logger.record(row)  # same primary key
            await engine.dispose()
            return first, stored, duplicate

        try:
            return asyncio.run(go()), logger, row
        finally:
            models.engine = original

    def test_row_reaches_postgres_and_reads_back_intact(self, tmp_path):
        (reached, stored, duplicate), logger, row = self._run(tmp_path)

        assert reached is True, "record() did not reach Postgres"
        assert stored.outcome == "refused"  # enum stored as its value, not repr
        assert stored.latency_ms == 1234
        assert stored.api_calls == 1
        assert stored.created_at.tzinfo is not None, "timestamp lost its timezone"
        assert stored.intent_ir == {"requirements": {"targets": {"cutoff_hz": 2_000_000}}}
        assert stored.underdetermined == ["source_impedance_ohm"]
        assert stored.generator == "rc_lowpass@0.1.0"
        assert stored.schema_version == LOG_SCHEMA_VERSION

        # A genuine database error — duplicate primary key — must fall back
        # rather than raise. The resilience contract, against a real database
        # rather than a simulated failure.
        assert duplicate is False
        assert len(logger.read_fallback()) == 1


class _CapturingLogger(RequestLogger):
    """Collects rows instead of writing them."""

    def __init__(self):
        super().__init__()
        self.rows = []

    async def record(self, row):
        self.rows.append(row)
        return True


class TestRequestLogMiddleware:
    def _client(self):
        logger = _CapturingLogger()
        app = FastAPI()
        app.add_middleware(RequestLogMiddleware, logger=logger)

        from fastapi import Request

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/quiet")
        async def quiet():
            return {"ok": True}

        @app.get("/boom")
        async def boom():
            raise RuntimeError("kaboom")

        @app.get("/teapot")
        async def teapot():
            raise HTTPException(418, detail="no")

        @app.post("/generate")
        async def generate(request: Request):
            ctx = log_ctx(request)
            ctx.prompt_hash = prompt_hash("RC filter 1kHz")
            ctx.count_api_call()
            ctx.complete(circuit_id="c-42")
            return {"ok": True}

        @app.post("/refuse")
        async def refuse(request: Request):
            ctx = log_ctx(request)
            ctx.prompt_hash = prompt_hash("buck converter 48V")
            ctx.refuse("no generator declares an envelope covering switching converters")
            return {"refused": True}

        return TestClient(app, raise_server_exceptions=False), logger

    def test_successful_request_logs_one_row(self):
        client, logger = self._client()
        client.get("/quiet")
        assert len(logger.rows) == 1
        assert logger.rows[0].outcome == Outcome.COMPLETED.value
        assert logger.rows[0].status_code == 200

    def test_health_is_not_logged(self):
        client, logger = self._client()
        client.get("/health")
        assert logger.rows == []

    def test_handler_exception_still_logs_a_row(self):
        # The gate is "every request", and an unhandled exception is the path
        # most likely to be missed by hand-placed record() calls.
        client, logger = self._client()
        client.get("/boom")
        assert len(logger.rows) == 1
        assert logger.rows[0].outcome == Outcome.FAILED.value
        assert "RuntimeError: kaboom" in logger.rows[0].error

    def test_http_error_logs_a_failed_row(self):
        client, logger = self._client()
        client.get("/teapot")
        assert len(logger.rows) == 1
        assert logger.rows[0].status_code == 418
        assert logger.rows[0].outcome == Outcome.FAILED.value

    def test_handler_enrichment_reaches_the_row(self):
        client, logger = self._client()
        client.post("/generate")
        row = logger.rows[0]
        assert row.outcome == Outcome.COMPLETED.value
        assert row.circuit_id == "c-42"
        assert row.api_calls == 1
        assert row.prompt_hash == prompt_hash("RC filter 1kHz")

    def test_refusal_is_recorded_with_its_reason(self):
        # The refusal log is the generator backlog (§4.5), so the reason has
        # to survive the round trip, not just the fact of refusal.
        client, logger = self._client()
        client.post("/refuse")
        row = logger.rows[0]
        assert row.outcome == Outcome.REFUSED.value
        assert "switching converters" in row.refusal_reason

    def test_latency_is_recorded(self):
        client, logger = self._client()
        client.get("/quiet")
        assert logger.rows[0].latency_ms >= 0

    def test_every_request_gets_a_distinct_row(self):
        client, logger = self._client()
        client.get("/quiet")
        client.get("/boom")
        client.post("/generate")
        assert len({r.request_id for r in logger.rows}) == 3

    def test_inconsistent_context_still_produces_a_row(self):
        # A handler that sets circuit_id without a prompt_hash builds an
        # invalid row. That is an instrumentation bug, and the middleware must
        # report it rather than drop the request silently.
        logger = _CapturingLogger()
        app = FastAPI()
        app.add_middleware(RequestLogMiddleware, logger=logger)

        from fastapi import Request

        @app.post("/bad")
        async def bad(request: Request):
            log_ctx(request).complete(circuit_id="c-1")  # no prompt_hash
            return {"ok": True}

        TestClient(app, raise_server_exceptions=False).post("/bad")

        assert len(logger.rows) == 1
        assert logger.rows[0].outcome == Outcome.FAILED.value
        assert "log_row_invalid" in logger.rows[0].error
