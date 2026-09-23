"""
Stage 2 — the patch route, end to end through FastAPI. `api/routes/patch.py`.

What this file pins, each from decisions.md [2026-09-21] X2 + X4:

- a patch re-derives the design through the same gate as a fresh request
- **a refused patch keeps v(n)** — nothing is written (item 9)
- a no-op patch is not a version (item 5)
- a design with no stored requirement is a 409, not a guess (item 1)
- `ops` patches with zero model calls; `command` with exactly one (item 8)
- an uncited operation is refused with the whole patch (item 7)
- every patched request produces a *valid* request-log row — the Stage 1
  ratchet requires `intent_ir` and `generator` alongside a `circuit_id`
- history reads as requirements; Phase 1 rows are shown as legacy (item 13)

The database is replaced by an in-memory store at the route's own seams
(`api.routes.patch.get_design`, …), so these run without Postgres. The
persistence itself is covered where it lives; what matters here is which
writes happen, in what order, and which do not happen at all.
"""

import asyncio
import copy
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

import api.routes.patch as patch_route
from ai.intent_patcher import IntentPatchError, PatchFailure, ProposedPatch
from api.routes.auth import get_current_user
from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp
from db.models import get_db
from generators.rc_lowpass import VERSION as RC_VERSION, RCLowPassGenerator
from generators.realize import realize
from main import app
from middleware.rate_limit import limiter
from observability.request_log import RequestLogger

USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"


class _Store:
    """The slice of the database the patch route touches."""

    def __init__(self):
        self.designs = {}
        self.patches = []
        self.outputs = []
        self.writes = []

    def add_design(self, intent=None, user=USER, legacy=False):
        intent = intent or IntentIR(
            requirements={
                "function": "low_pass_filter",
                "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
                "constraints": {"supply_v": 5, "source_impedance_ohm": 50},
            },
            provenance=Provenance(producer=Producer.FORM),
        )
        ir = realize(RCLowPassGenerator(), intent)
        self.designs[ir.circuit_id] = SimpleNamespace(
            circuit_id=ir.circuit_id,
            user_id=user,
            version=ir.version,
            ir_json=ir.model_dump(mode="json"),
            intent_ir=None if legacy else intent.model_dump(mode="json"),
            annotations=[],
        )
        return ir.circuit_id

    # The route's seams, with the route's signatures.
    async def get_design(self, db, circuit_id):
        return self.designs.get(circuit_id)

    async def update_design_revision(self, db, circuit_id, ir, intent_ir, expected_version):
        # The same predicate as the real UPDATE: write only if the stored
        # design is still the version the patch was computed from.
        d = self.designs[circuit_id]
        if d.version != expected_version:
            return False
        self.writes.append("revision")
        d.ir_json, d.intent_ir, d.version = ir.model_dump(mode="json"), intent_ir, ir.version
        return True

    async def update_design_annotations(self, db, circuit_id, annotations):
        self.writes.append("annotations")
        self.designs[circuit_id].annotations = annotations

    async def record_patch(self, db, **row):
        self.writes.append("patch")
        self.patches.append(SimpleNamespace(created_at=datetime(2026, 9, 21), **row))

    async def save_output(self, db, *args):
        self.writes.append("output")
        self.outputs.append(args)

    async def list_patches(self, db, circuit_id):
        return [p for p in self.patches if p.circuit_id == circuit_id]


@pytest.fixture
def env(monkeypatch):
    store = _Store()
    for seam in ("get_design", "update_design_revision", "update_design_annotations",
                 "record_patch", "save_output", "list_patches"):
        monkeypatch.setattr(patch_route, seam, getattr(store, seam))

    jobs = []
    monkeypatch.setattr(patch_route.run_simulation, "apply_async", lambda **kw: jobs.append(kw))

    rows = []

    async def capture(self, row):
        rows.append(row)
        return True

    monkeypatch.setattr(RequestLogger, "record", capture)

    user = {"id": USER}
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user["id"])
    app.dependency_overrides[get_db] = lambda: None
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield SimpleNamespace(client=TestClient(app), store=store, rows=rows, jobs=jobs, user=user)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


def ops(*items):
    return {"ops": [dict(op=o, path=p, **({"value": v[0]} if v else {})) for o, p, *v in items]}


def fake_patcher(monkeypatch, proposal=None, error=None):
    calls = []

    class Fake:
        def __init__(self, catalogue=()):
            pass

        def propose(self, intent, command, parts):
            calls.append((command, parts))
            if error:
                raise error
            return proposal

    monkeypatch.setattr(patch_route, "IntentPatcher", Fake)
    return calls


# ── The happy path ───────────────────────────────────────────────────────────

class TestRequirementPatch:
    def test_ops_patch_produces_the_next_revision(self, env):
        cid = env.store.add_design()
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["version"] == 2 and body["circuit_id"] == cid
        assert body["changes"] == ["targets.cutoff_hz: 1000 → 2000"]
        assert body["intent_ir"]["revision"] == 2
        assert body["ir"]["constraints"]["cutoff_hz"] == 2000
        assert body["generator"] == f"rc_lowpass@{RC_VERSION}"
        assert any(line.startswith("cutoff_hz: ") for line in body["predict_delta"])
        assert body["locality"]["ok"] is True

    def test_the_revision_is_persisted_with_its_history_row(self, env):
        cid = env.store.add_design()
        env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        assert env.store.writes[:2] == ["revision", "patch"]
        assert env.store.designs[cid].intent_ir["requirements"]["targets"]["cutoff_hz"] == 2000
        row = env.store.patches[0]
        assert row.patch_json["schema"] == "intent_patch/1"
        assert row.patch_json["readable"] == ["targets.cutoff_hz: 1000 → 2000"]
        assert row.patch_json["from_requirements"]["targets"]["cutoff_hz"] == 1000
        assert (row.from_version, row.to_version) == (1, 2)

    def test_the_simulation_job_is_tied_to_the_revision(self, env):
        cid = env.store.add_design()
        body = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000))).json()
        assert body["simulation_job_id"]
        assert env.store.patches[0].patch_json["simulation_job_id"] == body["simulation_job_id"]
        assert env.jobs[0]["task_id"] == body["simulation_job_id"]

    def test_the_log_row_is_valid_and_says_patched(self, env):
        cid = env.store.add_design()
        env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        row = env.rows[-1]
        assert row.outcome == "patched"
        assert row.circuit_id == cid and row.generator == f"rc_lowpass@{RC_VERSION}"
        assert row.intent_ir["revision"] == 2
        assert row.api_calls == 0
        assert not (row.error or "").startswith("log_row_invalid")


# ── What must not be written ─────────────────────────────────────────────────

class TestNothingIsWrittenUnlessTheRevisionIsGood:
    def test_a_refused_patch_keeps_v_n(self, env):
        cid = env.store.add_design()
        before = dict(vars(env.store.designs[cid]))
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2_000_000)))
        assert res.status_code == 422
        detail = res.json()["detail"]
        assert detail["error"] == "out_of_envelope"
        assert detail["kept_version"] == 1
        assert detail["requested_changes"] == ["targets.cutoff_hz: 1000 → 2000000"]
        assert env.store.writes == []
        assert vars(env.store.designs[cid]) == before
        assert env.rows[-1].outcome == "refused" and env.rows[-1].refusal_reason

    @pytest.mark.parametrize("value", ["12", True, -12])
    def test_a_supply_that_is_not_a_voltage_is_refused_not_defaulted(self, env, value):
        # Before rc_lowpass 0.2.1 "12" was built at the 5 V default and True
        # at 1 V. A patch is the easiest way to send such a value.
        cid = env.store.add_design()
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/constraints/supply_v", value)))
        assert res.status_code == 422
        detail = res.json()["detail"]
        assert detail["error"] == "out_of_envelope" and detail["kept_version"] == 1
        assert any("constraints.supply_v" in r["reason"] for r in detail["refusals"])
        assert env.store.writes == []

    def test_an_invalid_patch_keeps_v_n(self, env):
        cid = env.store.add_design()
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/intent_id", "x")))
        assert res.status_code == 422
        assert res.json()["detail"]["error"] == "invalid_patch"
        assert env.store.writes == []

    def test_a_no_op_patch_is_not_a_version(self, env):
        cid = env.store.add_design()
        for body in (ops(), ops(("replace", "/targets/cutoff_hz", 1000))):
            res = env.client.post(f"/design/{cid}/patch", json=body)
            assert res.status_code == 200
            assert res.json()["version"] == 1 and res.json()["changes"] == []
        assert env.store.writes == []
        assert env.jobs == []

    def test_a_design_without_a_requirement_is_409_not_a_guess(self, env):
        cid = env.store.add_design(legacy=True)
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        assert res.status_code == 409
        assert res.json()["detail"]["error"] == "no_requirement_on_record"
        assert env.store.writes == []

    def test_someone_elses_design_is_403(self, env):
        cid = env.store.add_design(user=OTHER)
        assert env.client.post(f"/design/{cid}/patch", json=ops()).status_code == 403

    def test_an_unknown_design_is_404(self, env):
        assert env.client.post("/design/nope/patch", json=ops()).status_code == 404

    @pytest.mark.parametrize("body", [
        {},
        {"command": "   "},
        {"command": "make it 2 kHz", "ops": []},
    ])
    def test_exactly_one_of_command_or_ops(self, env, body):
        cid = env.store.add_design()
        assert env.client.post(f"/design/{cid}/patch", json=body).status_code == 422


# ── Two patches in flight ────────────────────────────────────────────────────

class TestConcurrentPatches:
    """
    Found by the Stage 2 verification: two patches computed from the same v(n)
    both returned 200 as "v2", history got two 1 → 2 rows, and the second
    silently discarded the first while its user was told it had landed. The
    revision write is now conditional on the version the patch was computed
    from (`crud.update_design_revision`).
    """

    def test_a_stale_revision_is_409_and_writes_nothing(self, env, monkeypatch):
        cid = env.store.add_design()
        real_get = env.store.get_design

        async def moved_on(db, circuit_id):
            # The patch reads v1; by the time it writes, v2 has landed.
            snapshot = copy.deepcopy(await real_get(db, circuit_id))
            env.store.designs[circuit_id].version = 2
            return snapshot

        monkeypatch.setattr(patch_route, "get_design", moved_on)
        res = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert detail["error"] == "version_conflict" and detail["expected_version"] == 1
        assert env.store.writes == [] and env.store.patches == [] and env.jobs == []
        assert env.rows[-1].error.startswith("version_conflict")

    def test_of_two_patches_in_flight_one_lands_and_one_is_refused(self, env, monkeypatch):
        cid = env.store.add_design()
        real_get = env.store.get_design

        async def snapshot_read(db, circuit_id):
            # A SELECT returns a snapshot and costs a round trip — long enough
            # for both requests to read v1 before either writes.
            snapshot = copy.deepcopy(await real_get(db, circuit_id))
            await asyncio.sleep(0.05)
            return snapshot

        monkeypatch.setattr(patch_route, "get_design", snapshot_read)

        async def both():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await asyncio.gather(
                    client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000))),
                    client.post(f"/design/{cid}/patch", json=ops(("replace", "/constraints/supply_v", 12))),
                )

        results = asyncio.run(both())
        assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
        won = next(r for r in results if r.status_code == 200).json()
        lost = next(r for r in results if r.status_code == 409).json()["detail"]
        assert lost["error"] == "version_conflict"
        # One revision, recorded once, and it is the one the winner was told about.
        assert [(p.from_version, p.to_version) for p in env.store.patches] == [(1, 2)]
        assert env.store.patches[0].patch_json["readable"] == won["changes"]
        assert env.store.designs[cid].intent_ir == won["intent_ir"]

    @pytest.mark.parametrize("rowcount, written", [(1, True), (0, False)])
    def test_the_real_update_carries_the_version_predicate(self, rowcount, written):
        # The fake store above enforces the predicate; this pins that the real
        # statement does, and that it leaves annotations alone.
        from sqlalchemy.dialects import postgresql
        from db import crud

        captured = {}

        class _Session:
            async def execute(self, stmt):
                captured["stmt"] = stmt.compile(dialect=postgresql.dialect())
                return SimpleNamespace(rowcount=rowcount)

        ir = realize(RCLowPassGenerator(), IntentIR(
            requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}},
            provenance=Provenance(producer=Producer.FORM),
        ))
        result = asyncio.run(crud.update_design_revision(
            _Session(), ir.circuit_id, ir, intent_ir={}, expected_version=7,
        ))
        assert result is written
        sql, params = str(captured["stmt"]), captured["stmt"].params
        where = sql.split("WHERE", 1)[1]
        assert "circuit_designs.version = " in where and 7 in params.values()
        assert "annotations" not in sql


# ── The command path ─────────────────────────────────────────────────────────


class _ScriptedClient:
    """A model that returns one fixed tool call — for driving the real IntentPatcher."""

    def __init__(self, tool_input):
        block = SimpleNamespace(type="tool_use", input=tool_input)
        self.messages = SimpleNamespace(
            create=lambda **kw: SimpleNamespace(content=[block], stop_reason="tool_use")
        )

class TestCommandPath:
    def test_one_model_call_and_the_citations_come_back(self, env, monkeypatch):
        calls = fake_patcher(monkeypatch, ProposedPatch(
            [PatchOp(op="replace", path="/targets/cutoff_hz", value=2000)], ["cutoff to 2 kHz"], "",
        ))
        cid = env.store.add_design()
        res = env.client.post(f"/design/{cid}/patch", json={"command": "Set the cutoff to 2 kHz"})
        assert res.status_code == 200, res.text
        assert res.json()["citations"] == ["cutoff to 2 kHz"]
        assert len(calls) == 1
        assert {p["id"] for p in calls[0][1]} == {"R1", "C1"}   # told the part ids
        assert env.rows[-1].api_calls == 1
        assert env.store.patches[0].prompted_by == "Set the cutoff to 2 kHz"

    def test_an_uncited_operation_is_refused_and_logged_with_evidence(self, env, monkeypatch):
        fake_patcher(monkeypatch, error=IntentPatchError(
            "operation 1 cites 'nothing'", raw={"operations": ["…"]},
            kind=PatchFailure.UNCITED_OPERATION,
        ))
        cid = env.store.add_design()
        res = env.client.post(f"/design/{cid}/patch", json={"command": "Set the cutoff to 2 kHz"})
        assert res.status_code == 422
        assert res.json()["detail"]["kind"] == "uncited_operation"
        assert env.store.writes == []
        assert env.rows[-1].error.startswith("intent_patch_failed[uncited_operation]")

    def test_the_patchers_own_pin_form_lands_on_a_design_with_no_pins(self, env, monkeypatch):
        # The patcher's prompt tells the model to emit `add
        # /constraints/pinned/<id>`. A design that was never pinned has no
        # pinned map, and until the Stage 2 verification that operation failed
        # with "/constraints/pinned does not exist" — each half was tested,
        # never the two together. Real patcher, scripted model, real apply and
        # realize.
        monkeypatch.setattr("ai.intent_patcher.make_client", lambda: _ScriptedClient({"operations": [
            {"op": "add", "path": "/constraints/pinned/R1", "value": "4.7k", "because": "use the 4.7k"},
        ]}))
        cid = env.store.add_design(intent=IntentIR(
            requirements={
                "function": "low_pass_filter",
                "targets": {"cutoff_hz": 720, "tolerance_pct": 5},
                "constraints": {"supply_v": 5},
            },
            provenance=Provenance(producer=Producer.FORM),
        ))
        res = env.client.post(f"/design/{cid}/patch", json={"command": "Use the 4.7k resistor I have"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["changes"] == ['constraints.pinned.R1: (unset) → "4.7k"']
        assert body["version"] == 2
        r1 = next(c for c in body["ir"]["components"] if c["id"] == "R1")
        assert r1["value"] == "4700"


# ── Annotations and history ──────────────────────────────────────────────────

class TestAnnotationsAndHistory:
    def test_annotations_survive_a_patch_and_orphans_are_reported(self, env):
        cid = env.store.add_design()
        res = env.client.put(f"/design/{cid}/annotations", json={"annotations": [
            {"id": "c1", "kind": "comment", "anchor": {"kind": "component", "id": "C1"}, "text": "X7R"},
            {"id": "u7", "kind": "comment", "anchor": {"kind": "component", "id": "U7"}, "text": "?"},
        ]})
        assert res.status_code == 200
        assert [a["id"] for a in res.json()["orphaned"]] == ["u7"]

        body = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000))).json()
        assert [a["id"] for a in body["annotations"]["attached"]] == ["c1"]
        assert [a["id"] for a in body["annotations"]["orphaned"]] == ["u7"]
        assert {a["id"] for a in env.store.designs[cid].annotations} == {"c1", "u7"}

    def test_annotations_appear_in_the_schematic_and_leave_the_design_alone(self, env):
        cid = env.store.add_design()
        before = dict(env.store.designs[cid].ir_json)
        res = env.client.put(f"/design/{cid}/annotations", json={"annotations": [
            {"id": "c1", "kind": "comment", "anchor": {"kind": "component", "id": "C1"}, "text": "X7R only"},
            {"id": "u7", "kind": "comment", "anchor": {"kind": "component", "id": "U7"}, "text": "gone"},
        ]})
        body = res.json()
        assert "note: X7R only" in body["schematic"]
        assert "ORPHANED note on component U7" in body["schematic"]
        # The drawing is re-rendered and stored; the design is not touched.
        assert env.store.writes == ["annotations", "output"]
        assert env.store.outputs[-1][1] == "schematic"
        assert env.store.designs[cid].ir_json == before and body["version"] == env.store.designs[cid].version

        patched = env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000))).json()
        assert "note: X7R only" in patched["schematic"]

    def test_a_bad_annotation_is_422(self, env):
        cid = env.store.add_design()
        res = env.client.put(f"/design/{cid}/annotations", json={"annotations": [
            {"id": "x", "kind": "pinned_part", "anchor": {"kind": "design"}, "text": "no"},
        ]})
        assert res.status_code == 422

    def test_history_reads_as_requirements_and_marks_legacy_rows(self, env):
        cid = env.store.add_design()
        env.store.patches.append(SimpleNamespace(
            circuit_id=cid, from_version=0, to_version=1, prompted_by="Change R1",
            patch_json={"changes": [{"component_id": "R1", "field": "value", "new_value": "4.7k"}]},
            created_at=datetime(2026, 6, 2),
        ))
        env.client.post(f"/design/{cid}/patch", json=ops(("replace", "/targets/cutoff_hz", 2000)))
        history = env.client.get(f"/design/{cid}/history").json()
        assert history["patchable"] is True and history["current_version"] == 2
        kinds = [e["kind"] for e in history["entries"]]
        assert kinds == ["legacy_circuit_patch", "requirement_patch"]
        assert history["entries"][1]["changes"] == ["targets.cutoff_hz: 1000 → 2000"]


# ── The prerequisite: generate stores the requirement ────────────────────────

class TestGenerateStoresTheRequirement:
    """
    The council's first prerequisite for X2: until Stage 2 the IntentIR lived
    only in `request_log`, so there was nothing on the design to patch.
    """

    def test_the_intent_is_saved_with_the_design_and_ids_agree(self, env, monkeypatch):
        import api.routes.design as design_route

        intent = IntentIR(
            requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000, "tolerance_pct": 5}},
            provenance=Provenance(producer=Producer.LLM, model="m", prompt_hash="p"),
        )

        class _Producer:
            def __init__(self, registry):
                pass

            def produce(self, prompt):
                return intent

        saved = {}

        async def save_design(db, ir, user_id, intent_ir=None, annotations=None):
            saved.update(ir=ir, intent_ir=intent_ir)

        async def save_output(*args):
            pass

        monkeypatch.setattr(design_route, "IntentProducer", _Producer)
        monkeypatch.setattr(design_route, "save_design", save_design)
        monkeypatch.setattr(design_route, "save_output", save_output)
        monkeypatch.setattr(design_route.ExplanationEngine, "explain", lambda self, ir, v: "")
        monkeypatch.setattr(design_route.run_simulation, "apply_async", lambda **kw: None)

        res = env.client.post("/design/generate", json={"prompt": "1 kHz low-pass"})
        assert res.status_code == 201, res.text
        assert saved["intent_ir"]["intent_id"] == intent.intent_id
        assert saved["ir"].circuit_id == res.json()["circuit_id"]
        assert saved["ir"].generator == f"rc_lowpass@{RC_VERSION}"
        # Regenerating from the stored requirement reproduces the stored design.
        again = realize(RCLowPassGenerator(), IntentIR.model_validate(saved["intent_ir"]))
        assert again.model_dump(mode="json") == saved["ir"].model_dump(mode="json")
