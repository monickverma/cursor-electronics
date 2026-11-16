"""
The saved-designs harness: reopening a design, listing designs, projects.

 - `GET /design/{id}` re-derives every output from the stored CircuitIR with the
   same compilers that made them. Its module calls no model and reaches none
   (tests/test_llm_cannot_write_circuit_ir.py holds it to that).
 - Only the owner can open or file a design; a project belongs to its owner.
 - Filing a design under a project touches nothing about the design.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.routes.design as design_route
import api.routes.library as library_route
import api.routes.projects as projects_route
from api.routes.auth import get_current_user
from api.routes.firmware import FirmwareView
from core.intent_ir import IntentIR, Producer, Provenance
from core.ir_schema import CircuitIR
from db.models import get_db
from generators.bom.compiler import BOMCompiler
from generators.protocol import grid_of
from generators.realize import realize
from generators.schematic.kicad import KiCadSchematicGenerator
from main import app
from middleware.rate_limit import limiter
from validation.grid_adapters import ADAPTERS

USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
WHEN = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class _Store:
    def __init__(self):
        self.designs: dict[str, SimpleNamespace] = {}
        self.projects: dict[str, SimpleNamespace] = {}
        self.sim_jobs: dict[str, str] = {}

    def add(self, name="rc_lowpass", board=None, user=USER, legacy=False):
        adapter = ADAPTERS[name].build(board)
        point = next(iter(grid_of(adapter.generator, board).points()))
        req = json.loads(json.dumps(dict(adapter.intent_for(point).requirements)))
        intent = IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))
        ir = realize(adapter.generator, intent)
        self.designs[ir.circuit_id] = SimpleNamespace(
            circuit_id=ir.circuit_id, user_id=user, version=ir.version, intent=ir.intent,
            application_class=str(ir.application_class), target_mcu=ir.target_mcu,
            simulation_passed=None, project_id=None, created_at=WHEN, updated_at=WHEN,
            ir_json=ir.model_dump(mode="json"),
            intent_ir=None if legacy else intent.model_dump(mode="json"),
        )
        return ir.circuit_id

    # design seams
    async def get_design(self, db, circuit_id):
        return self.designs.get(circuit_id)

    async def list_user_designs(self, db, user_id):
        return [d for d in self.designs.values() if d.user_id == user_id]

    async def latest_simulation_job(self, db, circuit_id):
        return self.sim_jobs.get(circuit_id)

    async def set_design_project(self, db, circuit_id, project_id):
        self.designs[circuit_id].project_id = project_id

    # project seams
    async def list_user_projects(self, db, user_id):
        return [p for p in self.projects.values() if p.user_id == user_id]

    async def create_project(self, db, user_id, name):
        project = SimpleNamespace(id=str(uuid.uuid4()), user_id=user_id, name=name, created_at=WHEN)
        self.projects[project.id] = project
        return project

    async def get_project(self, db, project_id):
        return self.projects.get(project_id)

    async def rename_project(self, db, project_id, name):
        self.projects[project_id].name = name


@pytest.fixture
def env(monkeypatch):
    store = _Store()
    monkeypatch.setattr(design_route, "list_user_designs", store.list_user_designs)
    for seam in ("get_design", "latest_simulation_job", "set_design_project"):
        monkeypatch.setattr(library_route, seam, getattr(store, seam))
    for seam in ("list_user_projects", "create_project", "get_project", "rename_project"):
        monkeypatch.setattr(projects_route, seam, getattr(store, seam))

    async def not_built(db, ir):                      # the compile gate is not what this tests
        return FirmwareView(status="unavailable", message="not built in this test")

    monkeypatch.setattr(library_route, "firmware_view", not_built)

    # Opening a design must never reach a model.
    def no_model(*args, **kwargs):
        raise AssertionError("open_design constructed a model client")

    monkeypatch.setattr(design_route, "IntentProducer", no_model)
    monkeypatch.setattr(design_route, "ExplanationEngine", no_model)

    who = SimpleNamespace(id=USER, email="t@example.com")
    app.dependency_overrides[get_current_user] = lambda: who
    app.dependency_overrides[get_db] = lambda: None
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield SimpleNamespace(client=TestClient(app), store=store, who=who)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


# ── Reopening ────────────────────────────────────────────────────────────────

def test_open_design_recompiles_every_output_from_the_stored_ir(env):
    cid = env.store.add("rc_lowpass")
    stored = CircuitIR.model_validate(env.store.designs[cid].ir_json)

    res = env.client.get(f"/design/{cid}")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["circuit_id"] == cid and body["version"] == stored.version
    assert body["intent"] == stored.intent
    # The same compilers, the same input: byte-identical outputs.
    assert body["schematic"] == KiCadSchematicGenerator().generate(stored)
    assert body["bom"] == json.loads(json.dumps(BOMCompiler().compile(stored), default=str))
    assert body["ir"] == stored.model_dump(mode="json")
    assert body["validation_coverage"] == stored.validation_coverage
    assert set(body["validation"]) == {"passed", "errors", "warnings"}
    # The explanation is left to its own route ("writing" sends the client there); the firmware
    # goes through the gate.
    assert body["explanation"] == "" and body["explanation_status"] == "writing"
    assert body["firmware"] is None and body["firmware_build"]["status"] == "unavailable"
    assert body["patchable"] is True and body["simulation_job_id"] is None


def test_open_design_carries_the_last_simulation_and_legacy_designs_are_read_only(env):
    cid = env.store.add("voltage_divider", legacy=True)
    env.store.sim_jobs[cid] = "job-123"
    body = env.client.get(f"/design/{cid}").json()
    assert body["simulation_job_id"] == "job-123"
    assert body["patchable"] is False


def test_only_the_owner_opens_a_design(env):
    mine = env.store.add("rc_lowpass")
    theirs = env.store.add("voltage_divider", user=OTHER)
    assert env.client.get(f"/design/{mine}").status_code == 200
    assert env.client.get(f"/design/{theirs}").status_code == 403
    assert env.client.get("/design/no-such-design").status_code == 404


def test_list_is_still_reachable_and_says_where_each_design_is_filed(env):
    # `/design/list` must not be captured by `/design/{circuit_id}`.
    cid = env.store.add("rc_lowpass")
    env.store.add("voltage_divider", user=OTHER)
    rows = env.client.get("/design/list").json()
    assert [r["circuit_id"] for r in rows] == [cid]
    assert rows[0]["project_id"] is None and rows[0]["updated_at"] == WHEN.isoformat()


# ── Projects ─────────────────────────────────────────────────────────────────

def test_a_project_is_named_listed_and_renamed_by_its_owner(env):
    made = env.client.post("/projects", json={"name": "  Greenhouse   controller "})
    assert made.status_code == 201
    project = made.json()
    assert project["name"] == "Greenhouse controller"          # whitespace collapsed
    assert [p["id"] for p in env.client.get("/projects").json()] == [project["id"]]

    renamed = env.client.put(f"/projects/{project['id']}", json={"name": "Greenhouse v2"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Greenhouse v2"
    assert env.store.projects[project["id"]].name == "Greenhouse v2"


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_a_project_needs_a_usable_name(env, name):
    assert env.client.post("/projects", json={"name": name}).status_code == 422
    assert env.store.projects == {}


def test_a_project_is_its_owners_alone(env):
    theirs = SimpleNamespace(id=str(uuid.uuid4()), user_id=OTHER, name="Not mine", created_at=WHEN)
    env.store.projects[theirs.id] = theirs
    assert env.client.get("/projects").json() == []
    assert env.client.put(f"/projects/{theirs.id}", json={"name": "Mine now"}).status_code == 403
    assert theirs.name == "Not mine"
    assert env.client.put(f"/projects/{uuid.uuid4()}", json={"name": "x"}).status_code == 404


def test_filing_a_design_moves_it_and_changes_nothing_else(env):
    cid = env.store.add("rc_lowpass")
    before = json.dumps(env.store.designs[cid].ir_json, sort_keys=True)
    project = env.client.post("/projects", json={"name": "Filters"}).json()

    filed = env.client.put(f"/design/{cid}/project", json={"project_id": project["id"]})
    assert filed.status_code == 200 and filed.json() == {"circuit_id": cid, "project_id": project["id"]}
    assert env.client.get("/design/list").json()[0]["project_id"] == project["id"]
    assert env.client.get(f"/design/{cid}").json()["project_id"] == project["id"]
    # The design is the same design.
    assert json.dumps(env.store.designs[cid].ir_json, sort_keys=True) == before
    assert env.store.designs[cid].version == 1

    unfiled = env.client.put(f"/design/{cid}/project", json={"project_id": None})
    assert unfiled.status_code == 200 and env.store.designs[cid].project_id is None


def test_a_design_cannot_be_filed_under_someone_elses_project_or_by_someone_else(env):
    mine = env.store.add("rc_lowpass")
    theirs = env.store.add("voltage_divider", user=OTHER)
    foreign = SimpleNamespace(id=str(uuid.uuid4()), user_id=OTHER, name="Not mine", created_at=WHEN)
    env.store.projects[foreign.id] = foreign
    own = env.client.post("/projects", json={"name": "Mine"}).json()

    assert env.client.put(f"/design/{mine}/project", json={"project_id": foreign.id}).status_code == 403
    assert env.client.put(f"/design/{theirs}/project", json={"project_id": own["id"]}).status_code == 403
    assert env.client.put(f"/design/{mine}/project", json={"project_id": str(uuid.uuid4())}).status_code == 404
    assert env.store.designs[mine].project_id is None and env.store.designs[theirs].project_id is None
