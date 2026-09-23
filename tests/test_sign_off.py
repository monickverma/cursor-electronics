"""
Stage 4 — sign-off. A proved property counts only once a person has agreed to
it in words, and what they agree to is frozen.

Gate (PHASE_2_PLAN_v2.md §5 Stage 4, G1): *every property back-translated and
signed off before it counts.* Pinned here in two places:

- `validation/claims.py::assess` — unsigned proofs are shown and are not
  critical; a signature on exactly this property set makes them critical,
  retires the Stage 3 claims they re-derive, and removes D5
- `POST /design/{id}/sign-off` — the client quotes the hash of what it
  displayed; anything else is a 409 and nothing is signed

Design record: `brain/decisions.md` [2026-09-23] item 5.
"""

import copy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.routes.patch as patch_route
from ai.form_producer import FormProducer
from api.routes.auth import get_current_user
from core.intent_ir import IntentIR, Producer, Provenance
from db.models import get_db
from generators.realize import realize
from generators.registry import default_registry
from main import app
from middleware.rate_limit import limiter
from proof.properties import PropertySpec
from validation.claims import GRADES, ValidationCoverage, assess

REGISTRY = default_registry()
FORMS = FormProducer(REGISTRY)
USER = "00000000-0000-0000-0000-000000000001"
EMAIL = "signer@example.com"


def divider_intent(producer=Producer.FORM):
    requirements = {"function": "voltage_divider", "targets": {"vout_v": 3.3}, "constraints": {"supply_v": 5}}
    provenance = (Provenance(producer=Producer.LLM, model="claude-test") if producer == Producer.LLM
                  else Provenance(producer=producer))
    return IntentIR(requirements=requirements, provenance=provenance)


def coverage_of(intent) -> ValidationCoverage:
    g = REGISTRY.dispatch(intent).generator
    return assess(g, intent, realize(g, intent).model_copy(update={"validation_coverage": None}))


def rows(coverage, prefix):
    return {c.id: c for c in coverage.claims if c.id.startswith(prefix)}


# ── assess(): what a signature changes ───────────────────────────────────────

class TestUnsignedProofsDoNotCount:
    def test_proofs_are_shown_but_not_critical(self):
        coverage = coverage_of(divider_intent())
        proofs = rows(coverage, "proof.")
        assert set(proofs) == {"proof.divider.vout", "proof.divider.r1_power", "proof.divider.r2_power"}
        assert all(not c.critical for c in proofs.values())
        assert all("awaiting sign-off" in c.detail for c in proofs.values())
        assert coverage.properties_signed is False and coverage.signed_by is None

    def test_the_floor_ignores_unsigned_proofs(self):
        coverage = coverage_of(divider_intent())
        without = ValidationCoverage.summarise([c for c in coverage.claims if not c.id.startswith("proof.")])
        assert coverage.grade_floor == without.grade_floor == "G2"

    def test_each_property_is_shown_with_its_sentence_and_hash(self):
        coverage = coverage_of(divider_intent())
        assert [p.id for p in coverage.properties] == ["divider.vout", "divider.r1_power", "divider.r2_power"]
        for view, claim in zip(coverage.properties, rows(coverage, "proof.").values()):
            assert view.english == claim.claim and len(view.hash) == 64
        assert coverage.properties_hash and len(coverage.properties_hash) == 64


class TestASignatureOnExactlyTheseProperties:
    def signed(self, intent):
        return intent.sign_off(EMAIL, properties_hash=coverage_of(intent).properties_hash)

    def test_signed_proofs_are_critical_and_raise_the_divider_to_g1(self):
        coverage = coverage_of(self.signed(divider_intent()))
        assert coverage.properties_signed and coverage.signed_by == EMAIL
        assert all(c.critical for c in rows(coverage, "proof.").values())
        # Stage 3 bounded dissipation by interval arithmetic (G2); the signed
        # proof decides it exactly, so the G2 row stops setting the floor.
        dissipation = rows(coverage, "divider.")["divider.resistor_dissipation"]
        assert not dissipation.critical and "superseded by" in dissipation.detail
        assert coverage.grade_floor == "G1"

    def test_the_led_floor_stays_g2(self):
        intent = FORMS.build("led_indicator", {"led_current_ma": 10, "supply_v": 5})
        coverage = coverage_of(intent.sign_off(EMAIL, properties_hash=coverage_of(intent).properties_hash))
        assert coverage.properties_signed
        # R1's dissipation is proved through a current bound: sound, not
        # complete. The proof is G2, so the Stage 3 G2 row it re-derives is
        # superseded by another G2 — and the floor does not move.
        assert rows(coverage, "proof.")["proof.led.r1_power"].grade == "G2"
        assert coverage.grade_floor == "G2"

    def test_a_signature_on_other_properties_is_no_signature(self):
        intent = divider_intent().sign_off(EMAIL, properties_hash="0" * 64)
        coverage = coverage_of(intent)
        assert not coverage.properties_signed
        assert all(not c.critical for c in rows(coverage, "proof.").values())

    def test_a_stage_1_signature_on_the_json_alone_does_not_count(self):
        coverage = coverage_of(divider_intent().sign_off(EMAIL))
        assert not coverage.properties_signed

    def test_signing_removes_d5_from_a_model_written_specification(self):
        llm = divider_intent(Producer.LLM)
        assert "D5" in coverage_of(llm).open_defeaters
        coverage = coverage_of(self.signed(llm))
        assert "D5" not in coverage.open_defeaters
        assert all("D5" not in c.defeaters for c in coverage.claims)

    def test_an_edit_drops_the_signature(self):
        signed = self.signed(divider_intent())
        edited = signed.with_requirements({**signed.requirements,
                                           "targets": {"vout_v": 1.8}})
        assert edited.signed_off is None
        assert not coverage_of(edited).properties_signed

    def test_signing_does_not_change_the_design(self):
        intent = divider_intent()
        g = REGISTRY.dispatch(intent).generator
        before, after = realize(g, intent), realize(g, self.signed(intent))
        assert before.model_dump(exclude={"validation_coverage"}) == after.model_dump(exclude={"validation_coverage"})
        assert self.signed(intent).revision == intent.revision


class TestARefutationIsNeverAdvisory:
    def test_a_refuted_proof_is_critical_even_unsigned(self, monkeypatch):
        intent = divider_intent()
        g = REGISTRY.dispatch(intent).generator
        impossible = PropertySpec(id="divider.impossible", label="the voltage at VOUT", quantity="v(vout)",
                                  relation="within", lo="3.3", hi="3.3", units="V")
        monkeypatch.setattr(type(g), "properties", lambda self, it: [impossible])
        coverage = assess(g, intent, g.generate(intent))
        row = rows(coverage, "proof.")["proof.divider.impossible"]
        assert row.verdict == "fails" and row.critical
        assert row in coverage.failures
        assert "counterexample" in row.detail


class TestAPropertyThatCannotBeCompiled:
    def test_it_is_a_visible_row_and_the_set_is_unsignable(self, monkeypatch):
        intent = divider_intent()
        g = REGISTRY.dispatch(intent).generator
        broken = PropertySpec(id="divider.nowhere", label="the voltage at a node the design lacks",
                              quantity="v(nowhere)", relation="le", hi="5", units="V")
        monkeypatch.setattr(type(g), "properties", lambda self, it: [broken])
        circuit = realize(g, intent)          # generation does not fail
        coverage = circuit.validation_coverage
        row = next(c for c in coverage["claims"] if c["id"] == "proof.divider.nowhere")
        assert row["verdict"] == "not_assessed" and row["grade"] == "G7"
        assert "could not compile" in row["detail"]
        assert coverage["properties_hash"] is None and coverage["properties"][0]["status"] == "unknown"


def test_grades_order_is_the_one_the_floor_uses():
    assert GRADES.index("G1") < GRADES.index("G2")


# ── The route ────────────────────────────────────────────────────────────────

class _Store:
    def __init__(self):
        self.designs, self.writes = {}, []

    def add(self, intent=None, user=USER, legacy=False):
        intent = intent or divider_intent()
        ir = realize(REGISTRY.dispatch(intent).generator, intent)
        self.designs[ir.circuit_id] = SimpleNamespace(
            circuit_id=ir.circuit_id, user_id=user, version=ir.version,
            ir_json=ir.model_dump(mode="json"),
            intent_ir=None if legacy else intent.model_dump(mode="json"),
            annotations=[],
        )
        return ir.circuit_id

    async def get_design(self, db, circuit_id):
        return self.designs.get(circuit_id)

    async def update_design_revision(self, db, circuit_id, ir, intent_ir, expected_version):
        d = self.designs[circuit_id]
        if d.version != expected_version:
            return False
        self.writes.append("revision")
        d.ir_json, d.intent_ir, d.version = ir.model_dump(mode="json"), intent_ir, ir.version
        return True


@pytest.fixture
def env(monkeypatch):
    store = _Store()
    monkeypatch.setattr(patch_route, "get_design", store.get_design)
    monkeypatch.setattr(patch_route, "update_design_revision", store.update_design_revision)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER, email=EMAIL)
    app.dependency_overrides[get_db] = lambda: None
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield SimpleNamespace(client=TestClient(app), store=store)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


def shown(store, cid):
    return store.designs[cid].ir_json["validation_coverage"]["properties_hash"]


class TestSignOffRoute:
    def test_signing_the_hash_shown_makes_the_proofs_count(self, env):
        cid = env.store.add()
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": shown(env.store, cid)})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["signed_by"] == EMAIL and body["version"] == 1
        assert body["validation_coverage"]["properties_signed"] is True
        assert body["validation_coverage"]["grade_floor"] == "G1"
        stored = env.store.designs[cid]
        assert env.store.writes == ["revision"] and stored.version == 1
        assert stored.intent_ir["signed_off"]["properties_hash"] == shown(env.store, cid)
        assert stored.ir_json["validation_coverage"]["properties_signed"] is True

    def test_a_hash_the_user_was_not_shown_is_409_and_signs_nothing(self, env):
        cid = env.store.add()
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": "f" * 64})
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert detail["error"] == "properties_changed" and detail["current_hash"] == shown(env.store, cid)
        assert env.store.writes == [] and env.store.designs[cid].intent_ir["signed_off"] is None

    def test_a_design_with_no_stored_requirement_is_409(self, env):
        cid = env.store.add(legacy=True)
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": shown(env.store, cid)})
        assert res.status_code == 409 and res.json()["detail"]["error"] == "no_requirement_on_record"

    def test_a_design_built_by_another_generator_version_is_409(self, env):
        cid = env.store.add()
        env.store.designs[cid].ir_json["generator"] = "voltage_divider@0.0.1"
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": shown(env.store, cid)})
        assert res.status_code == 409 and res.json()["detail"]["error"] == "generator_changed"
        assert env.store.writes == []

    def test_a_design_that_moved_while_being_signed_is_409(self, env, monkeypatch):
        cid = env.store.add()
        real_get = env.store.get_design

        async def moved_on(db, circuit_id):
            snapshot = copy.deepcopy(await real_get(db, circuit_id))
            env.store.designs[circuit_id].version = 2
            return snapshot

        monkeypatch.setattr(patch_route, "get_design", moved_on)
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": shown(env.store, cid)})
        assert res.status_code == 409 and res.json()["detail"]["error"] == "version_conflict"
        assert env.store.writes == []

    def test_signing_twice_is_idempotent(self, env):
        cid = env.store.add()
        h = shown(env.store, cid)
        first = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": h})
        second = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": h})
        assert first.status_code == second.status_code == 200
        assert env.store.writes == ["revision"]
        assert second.json()["validation_coverage"] == first.json()["validation_coverage"]

    def test_someone_elses_design_is_403(self, env):
        cid = env.store.add(user="00000000-0000-0000-0000-000000000002")
        res = env.client.post(f"/design/{cid}/sign-off", json={"properties_hash": shown(env.store, cid)})
        assert res.status_code == 403
