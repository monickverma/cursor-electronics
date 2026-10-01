"""
The Phase 2 LLM paths, against the live model. Stages 1–4 test them with
scripted clients; this file sends real prompts.

- **Prompt → IntentIR** (`ai/intent_producer.py`): one plain-English request
  per generator must reach that generator, realise, and prove every property —
  and, written by a model, carry D5 until a person signs the properties.
- **Out of catalogue**: a request no generator builds is refused, never bent
  into one that fits (amendment X5's guard).
- **Command → patch** (`ai/intent_patcher.py`): "2 kHz" becomes a cited
  operation; "double the cutoff" is refused until a value is stated.
- **End to end** (also needs TEST_DATABASE_URL): generate → sign-off → patch
  through the real routes and a real PostgreSQL.

Auto-skipped unless ANTHROPIC_API_KEY is set, like `test_ai_layer.py`. Each
run costs model calls — roughly a dozen.
"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest

API_KEY_PRESENT = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
pytestmark = pytest.mark.skipif(not API_KEY_PRESENT, reason="ANTHROPIC_API_KEY not set — live API tests skipped")

from ai.intent_patcher import IntentPatcher, IntentPatchError  # noqa: E402
from ai.intent_producer import IntentProducer  # noqa: E402
from core.intent_ir import IntentIR, Producer, Provenance  # noqa: E402
from core.intent_patch import apply_patch  # noqa: E402
from generators.realize import realize  # noqa: E402
from generators.registry import default_registry  # noqa: E402

REGISTRY = default_registry()

PROMPTS = {
    "rc_lowpass": "A passive RC low-pass filter with a 1 kHz cutoff, within 5%, on a 5 V supply.",
    "voltage_divider": "A resistor voltage divider that gives 3.3 V from a 5 V supply.",
    "led_indicator": "Drive a red indicator LED at 10 mA from an Arduino Uno GPIO pin on a 5 V supply.",
    "dht22_node": ("An Arduino Uno reading a DHT22 temperature and humidity sensor on a 5 V supply, "
                   "with 2 metres of cable to the sensor."),
    "rs485_node": "An Arduino Uno acting as a Modbus RTU master over RS-485 using a MAX485 transceiver at 5 V.",
}


@pytest.fixture(scope="module")
def producer():
    return IntentProducer(REGISTRY)


@pytest.mark.parametrize("expected", list(PROMPTS))
def test_a_plain_request_reaches_its_generator_and_is_proved(producer, expected):
    intent = producer.produce(PROMPTS[expected])
    assert intent.provenance.producer == "llm" or intent.provenance.producer == Producer.LLM
    assert intent.is_answerable, intent.open_questions()
    dispatch = REGISTRY.dispatch(intent)
    assert dispatch.accepted, dispatch.refusal_summary()
    assert dispatch.generator.name == expected
    design = realize(dispatch.generator, intent)
    coverage = design.validation_coverage
    assert coverage["properties"] and all(p["status"] == "proven" for p in coverage["properties"])
    assert not [c["id"] for c in coverage["claims"] if c["verdict"] == "fails"]
    # A model wrote the specification: D5 stands until a person signs.
    assert "D5" in coverage["open_defeaters"]
    signed = realize(dispatch.generator, intent.sign_off("live@example.com",
                                                         properties_hash=coverage["properties_hash"]))
    assert signed.validation_coverage["properties_signed"] is True
    assert "D5" not in signed.validation_coverage["open_defeaters"]


def test_a_request_outside_the_catalogue_is_refused_not_bent(producer):
    intent = producer.produce("A buck converter that steps 12 V down to 3.3 V at 2 A.")
    dispatch = REGISTRY.dispatch(intent)
    assert not dispatch.accepted
    assert all(r.reason for r in dispatch.refusals)
    assert intent.requirements["function"] not in REGISTRY.functions()


def _rc_intent():
    return IntentIR(requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
                                  "constraints": {"supply_v": 5}},
                    provenance=Provenance(producer=Producer.FORM))


def test_a_stated_value_becomes_a_cited_operation():
    intent = _rc_intent()
    parts = [{"id": c.id, "type": c.type, "value": c.value}
             for c in realize(REGISTRY.dispatch(intent).generator, intent).components]
    proposal = IntentPatcher(REGISTRY.functions()).propose(intent, "make the cutoff 2 kHz", parts)
    assert [(o.op, o.path, o.value) for o in proposal.ops] == [("replace", "/targets/cutoff_hz", 2000)]
    assert any("2 kHz" in c or "2kHz" in c for c in proposal.citations)
    outcome = apply_patch(intent, list(proposal.ops))
    design = realize(REGISTRY.dispatch(outcome.intent).generator, outcome.intent)
    assert all(p["status"] == "proven" for p in design.validation_coverage["properties"])


def test_a_relative_request_is_refused_until_a_value_is_stated():
    # Refused means nothing to apply: either the citation guard raises, or the
    # patcher returns no operations and asks for the value (what it does live).
    intent = _rc_intent()
    try:
        proposal = IntentPatcher(REGISTRY.functions()).propose(intent, "double the cutoff", [])
    except IntentPatchError:
        return
    assert proposal.ops == () and proposal.note_to_user


# ── End to end through the routes and a real database ───────────────────────

_DB = os.environ.get("TEST_DATABASE_URL", "").strip()


@pytest.mark.skipif(not _DB, reason="TEST_DATABASE_URL not set")
def test_generate_sign_off_and_patch_end_to_end(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    import api.routes.design as design_route
    import api.routes.patch as patch_route
    import db.models as models
    from api.routes.auth import get_current_user
    from db.models import User, get_db
    from main import app
    from middleware.rate_limit import limiter

    engine = create_async_engine(_DB, poolclass=NullPool, future=True)

    async def make_user():
        async with AsyncSession(engine, expire_on_commit=False) as s:
            u = User(email=f"live-{uuid.uuid4()}@example.com", hashed_password="x")
            s.add(u)
            await s.commit()
            return SimpleNamespace(id=u.id, email=u.email)

    async def real_db():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    user = asyncio.run(make_user())
    monkeypatch.setattr(models, "engine", engine)
    for route in (design_route, patch_route):
        monkeypatch.setattr(route.run_simulation, "apply_async", lambda **kw: None)
    app.dependency_overrides[get_db] = real_db
    app.dependency_overrides[get_current_user] = lambda: user
    was = limiter.enabled
    limiter.enabled = False
    try:
        client = TestClient(app)
        res = client.post("/design/generate", json={"prompt": PROMPTS["voltage_divider"]})
        assert res.status_code == 201, res.text
        body = res.json()
        cid, coverage = body["circuit_id"], body["validation_coverage"]
        assert coverage["properties"] and "D5" in coverage["open_defeaters"]

        signed = client.post(f"/design/{cid}/sign-off", json={"properties_hash": coverage["properties_hash"]})
        assert signed.status_code == 200, signed.text
        assert "D5" not in signed.json()["validation_coverage"]["open_defeaters"]

        patched = client.post(f"/design/{cid}/patch", json={"command": "change the output voltage to 1.8 V"})
        assert patched.status_code == 200, patched.text
        p = patched.json()
        assert p["version"] == 2 and p["intent_ir"]["signed_off"] is None
        assert p["intent_ir"]["requirements"]["targets"]["vout_v"] == 1.8
        assert all(x["status"] == "proven" for x in p["validation_coverage"]["properties"])
    finally:
        limiter.enabled = was
        app.dependency_overrides.clear()

        async def cleanup():
            async with AsyncSession(engine) as s:
                await s.execute(delete(User).where(User.id == user.id))
                await s.commit()
            await engine.dispose()
        asyncio.run(cleanup())
