"""
`GET /design/{id}/bom` — Stage 6. Rows priced only as themselves, with their
date; substitutes offered only after passing the original's checks, and
applied through the ordinary patch route.
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.routes.bom as bom_route
import api.routes.patch as patch_route
from api.routes.auth import get_current_user
from core.intent_ir import IntentIR, Producer, Provenance
from db.models import get_db
from generators.protocol import grid_of
from generators.realize import realize
from main import app
from middleware.rate_limit import limiter
from observability.request_log import RequestLogger
from validation.grid_adapters import ADAPTERS

USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"


class _Store:
    def __init__(self):
        self.designs = {}

    def add(self, name, board=None, user=USER, legacy=False, generator_tag=None):
        adapter = ADAPTERS[name].build(board)
        req = json.loads(json.dumps(dict(adapter.intent_for(next(iter(grid_of(adapter.generator, board).points())))
                                         .requirements)))
        intent = IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))
        ir = realize(adapter.generator, intent)
        if generator_tag:
            ir = ir.model_copy(update={"generator": generator_tag})
        self.designs[ir.circuit_id] = SimpleNamespace(
            circuit_id=ir.circuit_id, user_id=user, version=ir.version,
            ir_json=ir.model_dump(mode="json"),
            intent_ir=None if legacy else intent.model_dump(mode="json"), annotations=[],
        )
        return ir.circuit_id

    async def get_design(self, db, circuit_id):
        return self.designs.get(circuit_id)

    async def update_design_revision(self, db, circuit_id, ir, intent_ir, expected_version):
        d = self.designs[circuit_id]
        if d.version != expected_version:
            return False
        d.ir_json, d.intent_ir, d.version = ir.model_dump(mode="json"), intent_ir, ir.version
        return True

    async def record_patch(self, db, **row):
        pass

    async def save_output(self, db, *args):
        pass

    async def update_design_annotations(self, db, circuit_id, annotations):
        pass

    async def list_patches(self, db, circuit_id):
        return []


@pytest.fixture
def env(monkeypatch):
    store = _Store()
    monkeypatch.setattr(bom_route, "get_design", store.get_design)
    for seam in ("get_design", "update_design_revision", "update_design_annotations",
                 "record_patch", "save_output", "list_patches"):
        monkeypatch.setattr(patch_route, seam, getattr(store, seam))
    monkeypatch.setattr(patch_route.run_simulation, "apply_async", lambda **kw: None)

    async def no_firmware(*args, **kwargs):          # the compile gate is not what this tests
        from api.routes.firmware import FirmwareView

        return FirmwareView(status="unavailable", message="not built in this test")

    monkeypatch.setattr(patch_route, "firmware_view", no_firmware)

    async def capture(self, row):
        return True

    monkeypatch.setattr(RequestLogger, "record", capture)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER, email="t@example.com")
    app.dependency_overrides[get_db] = lambda: None
    was_enabled = limiter.enabled
    limiter.enabled = False
    yield SimpleNamespace(client=TestClient(app), store=store)
    limiter.enabled = was_enabled
    app.dependency_overrides.clear()


def test_rows_are_priced_as_themselves_and_dated(env):
    cid = env.store.add("rs485_node", "arduino_uno")
    body = env.client.get(f"/design/{cid}/bom").json()
    rows = {r["id"]: r for r in body["rows"]}
    assert rows["R1"]["part_number"] == "RC1206FR-07120RL" and rows["R1"]["price_known"] is False
    assert rows["R1"]["lcsc_pn"] is None and rows["R1"]["priced_as"] is None
    for row in body["rows"]:
        assert (row["price_asof"] is not None) == row["price_known"]
    assert "not enabled" in body["pricing"]


def test_substitutes_arrive_checked_and_the_terminator_is_refused_by_name(env):
    cid = env.store.add("rs485_node", "arduino_uno")
    body = env.client.get(f"/design/{cid}/bom").json()
    assert body["substitutes_unavailable"] is None
    assert {s["component_id"] for s in body["substitutes"]} == {"R2", "R3"}
    refused = {r["part_number"]: r["reason"] for r in body["rejected"] if r["component_id"] == "R1"}
    assert "62.5 mW rating" in refused["RC0402FR-07120RL"]


def test_a_substitute_is_applied_through_the_patch_route(env):
    cid = env.store.add("dht22_node", "arduino_uno")
    sub = next(s for s in env.client.get(f"/design/{cid}/bom").json()["substitutes"]
               if s["part_number"] == "RC0603FR-0710KL")
    assert sub["unit_price_usd"] is not None and sub["price_asof"] == "2026-07-25"
    response = env.client.post(f"/design/{cid}/patch", json={"ops": sub["ops"]})
    assert response.status_code == 200, response.text
    stored = env.store.designs[cid]
    r1 = next(c for c in stored.ir_json["components"] if c["id"] == "R1")
    assert (r1["part_number"], r1["package"]) == ("RC0603FR-0710KL", "0603")
    assert stored.version == 2
    # The re-derived design's BOM prices the new part as itself.
    rows = {r["id"]: r for r in env.client.get(f"/design/{cid}/bom").json()["rows"]}
    assert rows["R1"]["part_number"] == "RC0603FR-0710KL" and rows["R1"]["price_known"] is True


def test_a_design_without_a_requirement_gets_no_substitutes_and_is_told_why(env):
    cid = env.store.add("dht22_node", "arduino_uno", legacy=True)
    body = env.client.get(f"/design/{cid}/bom").json()
    assert body["substitutes"] == [] and "predates requirement patching" in body["substitutes_unavailable"]


def test_a_design_from_another_generator_version_is_not_checked_against_this_one(env):
    cid = env.store.add("dht22_node", "arduino_uno", generator_tag="dht22_node@0.0.1")
    body = env.client.get(f"/design/{cid}/bom").json()
    assert body["substitutes"] == [] and "Patch the design first" in body["substitutes_unavailable"]


def test_someone_elses_design_is_not_shown(env):
    cid = env.store.add("dht22_node", "arduino_uno", user=OTHER)
    assert env.client.get(f"/design/{cid}/bom").status_code == 403
    assert env.client.get("/design/no-such-design/bom").status_code == 404
