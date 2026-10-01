"""
Stage 4 sign-off against a real PostgreSQL. `tests/test_sign_off.py` replaces
the database with an in-memory store at the route's seams; this file does not.
The routes, `get_db`, `crud` and the conditional UPDATE all run against a real
server, and every assertion about what was stored reads it back through a
fresh connection — as a restarted server would.

Auto-skipped unless TEST_DATABASE_URL names a database with the project schema,
in the same spirit as `test_request_log.py`. To run it:

    docker compose up -d db
    docker compose exec db createdb -U circuitos_user circuitos_test
    docker compose exec db psql -U circuitos_user -d circuitos_test \\
        -f /docker-entrypoint-initdb.d/schema.sql
    TEST_DATABASE_URL=postgresql+asyncpg://circuitos_user:circuitos_pass@localhost:5432/circuitos_test \\
        pytest tests/test_postgres_signoff.py

A separate database, so nothing here touches development data.
"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest

_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL not set")

if _URL:
    from fastapi.testclient import TestClient
    from sqlalchemy import delete, func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    import api.routes.patch as patch_route
    import db.models as models
    from api.routes.auth import get_current_user
    from core.intent_ir import IntentIR, Producer, Provenance
    from core.ir_schema import CircuitIR
    from db.crud import save_design, update_design_revision
    from db.migrations import apply_migrations
    from db.models import CircuitDesign, PatchHistory, User, get_db
    from generators.realize import canonical_json, realize, same_design
    from generators.voltage_divider import VoltageDividerGenerator
    from main import app
    from middleware.rate_limit import limiter

GEN = None if not _URL else VoltageDividerGenerator()


def _engine():
    # NullPool: TestClient runs the app on its own event loop, and a pooled
    # asyncpg connection may not cross loops.
    return create_async_engine(_URL, poolclass=NullPool, future=True)


def _run(coro):
    return asyncio.run(coro)


def _intent():
    return IntentIR(requirements={"function": "voltage_divider", "targets": {"vout_v": 3.3},
                                  "constraints": {"supply_v": 5}},
                    provenance=Provenance(producer=Producer.LLM, model="test-model"))


async def _seed(intent):
    engine = _engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as s:
            user = User(email=f"signoff-{uuid.uuid4()}@example.com", hashed_password="x")
            s.add(user)
            await s.flush()
            ir = realize(GEN, intent)
            await save_design(s, ir, str(user.id), intent_ir=intent.model_dump(mode="json"))
            await s.commit()
            return SimpleNamespace(id=user.id, email=user.email), ir
    finally:
        await engine.dispose()


async def _row(circuit_id):
    engine = _engine()
    try:
        async with AsyncSession(engine) as s:
            d = (await s.execute(select(CircuitDesign).where(CircuitDesign.circuit_id == circuit_id))).scalar_one()
            patches = (await s.execute(select(func.count()).select_from(PatchHistory)
                                       .where(PatchHistory.circuit_id == circuit_id))).scalar_one()
            return SimpleNamespace(version=d.version, ir_json=d.ir_json, intent_ir=d.intent_ir,
                                   updated_at=d.updated_at, patches=patches)
    finally:
        await engine.dispose()


async def _drop_user(user_id):
    engine = _engine()
    try:
        async with AsyncSession(engine) as s:
            await s.execute(delete(User).where(User.id == user_id))   # designs cascade
            await s.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _schema():
    async def migrate():
        engine = _engine()
        try:
            await apply_migrations(engine)
        finally:
            await engine.dispose()
    _run(migrate())


@pytest.fixture
def env(monkeypatch):
    engine = _engine()

    async def real_db():
        # The shape of db.models.get_db, pointed at the test database.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # The request logger writes through db.models.engine: keep it off dev data.
    monkeypatch.setattr(models, "engine", engine)
    monkeypatch.setattr(patch_route.run_simulation, "apply_async", lambda **kw: None)
    user, ir = _run(_seed(_intent()))
    app.dependency_overrides[get_db] = real_db
    app.dependency_overrides[get_current_user] = lambda: user
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield SimpleNamespace(client=TestClient(app), user=user, ir=ir,
                          shown=ir.validation_coverage["properties_hash"])
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()
    _run(_drop_user(user.id))
    _run(engine.dispose())


class TestSignOffOnPostgres:
    def test_the_signature_is_stored_and_survives_a_restart(self, env):
        res = env.client.post(f"/design/{env.ir.circuit_id}/sign-off", json={"properties_hash": env.shown})
        assert res.status_code == 200, res.text
        row = _run(_row(env.ir.circuit_id))                       # a fresh connection
        assert row.version == 1
        assert row.intent_ir["signed_off"]["by"] == env.user.email
        assert row.intent_ir["signed_off"]["properties_hash"] == env.shown
        coverage = row.ir_json["validation_coverage"]
        assert coverage["properties_signed"] is True and coverage["grade_floor"] == "G1"
        assert "D5" not in coverage["open_defeaters"]             # an LLM-written spec, now signed
        # "After a restart": rebuild everything from what the database holds.
        intent = IntentIR.model_validate(row.intent_ir)
        rebuilt = realize(GEN, intent)
        assert rebuilt.validation_coverage["properties_signed"] is True
        assert same_design(rebuilt, CircuitIR.model_validate(row.ir_json))

    def test_a_hash_the_user_was_not_shown_writes_nothing(self, env):
        before = _run(_row(env.ir.circuit_id))
        res = env.client.post(f"/design/{env.ir.circuit_id}/sign-off", json={"properties_hash": "0" * 64})
        assert res.status_code == 409 and res.json()["detail"]["error"] == "properties_changed"
        after = _run(_row(env.ir.circuit_id))
        assert after.intent_ir["signed_off"] is None
        assert canonical_json(CircuitIR.model_validate(after.ir_json)) == \
            canonical_json(CircuitIR.model_validate(before.ir_json))
        assert after.updated_at == before.updated_at

    def test_signing_twice_writes_once(self, env):
        env.client.post(f"/design/{env.ir.circuit_id}/sign-off", json={"properties_hash": env.shown})
        first = _run(_row(env.ir.circuit_id))
        res = env.client.post(f"/design/{env.ir.circuit_id}/sign-off", json={"properties_hash": env.shown})
        assert res.status_code == 200
        assert _run(_row(env.ir.circuit_id)).updated_at == first.updated_at

    def test_a_patch_after_sign_off_stores_an_unsigned_revision_and_its_history(self, env):
        env.client.post(f"/design/{env.ir.circuit_id}/sign-off", json={"properties_hash": env.shown})
        res = env.client.post(f"/design/{env.ir.circuit_id}/patch",
                              json={"ops": [{"op": "replace", "path": "/targets/vout_v", "value": 1.8}]})
        assert res.status_code == 200, res.text
        row = _run(_row(env.ir.circuit_id))
        assert row.version == 2 and row.patches == 1
        assert row.intent_ir["signed_off"] is None and row.intent_ir["revision"] == 2
        assert row.ir_json["validation_coverage"]["properties_signed"] is False
        assert row.ir_json["validation_coverage"]["properties_hash"] != env.shown


class TestTheConditionalUpdateOnPostgres:
    def test_a_stale_version_writes_nothing(self, env):
        async def attempt():
            engine = _engine()
            try:
                async with AsyncSession(engine) as s:
                    ok = await update_design_revision(s, env.ir.circuit_id, env.ir, intent_ir={"stale": True},
                                                      expected_version=7)
                    await s.commit()
                    return ok
            finally:
                await engine.dispose()

        assert _run(attempt()) is False
        assert _run(_row(env.ir.circuit_id)).intent_ir.get("stale") is None

    def test_of_two_writers_racing_from_one_version_exactly_one_lands(self, env):
        """
        The race `crud.update_design_revision` exists for. Writer 1 updates and
        holds the row lock; writer 2's UPDATE blocks on it; writer 1 commits;
        under READ COMMITTED writer 2 re-checks the version predicate against
        the committed row and matches nothing.
        """
        intent = _intent()
        v2 = realize(GEN, intent.with_requirements({**intent.requirements, "targets": {"vout_v": 1.8}}))

        async def race():
            engine = _engine()
            try:
                async with AsyncSession(engine) as s1, AsyncSession(engine) as s2:
                    ok1 = await update_design_revision(s1, env.ir.circuit_id, v2, {"writer": 1}, expected_version=1)
                    second = asyncio.create_task(
                        update_design_revision(s2, env.ir.circuit_id, v2, {"writer": 2}, expected_version=1))
                    await asyncio.sleep(0.5)
                    blocked = not second.done()
                    await s1.commit()
                    ok2 = await second
                    await s2.commit()
                    return ok1, blocked, ok2
            finally:
                await engine.dispose()

        ok1, blocked, ok2 = _run(race())
        assert ok1 and blocked and not ok2
        row = _run(_row(env.ir.circuit_id))
        assert row.intent_ir == {"writer": 1} and row.version == 2
