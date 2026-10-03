"""
Composition M2–M4 (`COMPOSITION_PLAN.md`, `brain/decisions.md` [2026-10-03]).

M2 — behaviour: a closed vocabulary, checked against the blocks by name, and
compiled into one sketch that builds under the compile gate on every board.
M3 — the load switch as a block: the room monitor's alarm, proved as itself.
M4 — the front door: a project is an IntentIR, the board carries claims of its
own (rail budget, pin rules) beside every block's, rail interaction is shown
not assessed, and POST /design/generate returns the board.
"""

import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai.form_producer import FormProducer
from core.intent_ir import IntentIR, Producer, Provenance, Requirements
from generators.compose import CompositionRefused, Project, compose, compose_intent
from generators.firmware.composite import composite_project, render
from generators.firmware.project import project_for
from generators.realize import design_circuit_id, realize
from generators.registry import default_registry

ROOT = Path(__file__).resolve().parent.parent
ROOM = json.loads((ROOT / "docs" / "projects" / "room_monitor.json").read_text(encoding="utf-8"))
BOARDS = ("arduino_uno", "esp32_devkitc", "blackpill_f411ce")


@pytest.fixture(scope="module")
def registry():
    return default_registry()


def room(mcu="arduino_uno", **changes):
    return Project.model_validate({**ROOM, "mcu": mcu, **changes})


def project_intent(spec=ROOM, **constraints):
    return IntentIR(requirements={"function": "project", "targets": {}, "preferences": {},
                                  "constraints": {"mcu": spec.get("mcu", "arduino_uno"), **constraints},
                                  "blocks": spec["blocks"], "behaviour": spec.get("behaviour", [])},
                    provenance=Provenance(producer=Producer.FORM))


# ── M2: behaviour ────────────────────────────────────────────────────────────

class TestBehaviourIsAClosedVocabulary:
    @pytest.mark.parametrize("rule, fragment", [
        ({"when": {"block": "nobody", "reads": "temperature_c", "op": ">", "value": 30},
          "then": {"block": "alarm", "set": "on"}}, "does not have"),
        ({"when": {"block": "status", "reads": "temperature_c", "op": ">", "value": 30},
          "then": {"block": "alarm", "set": "on"}}, "cannot be read"),
        ({"when": {"block": "climate", "reads": "pressure_hpa", "op": ">", "value": 30},
          "then": {"block": "alarm", "set": "on"}}, "cannot be read"),
        ({"when": {"block": "climate", "reads": "temperature_c", "op": ">", "value": 300},
          "then": {"block": "alarm", "set": "on"}}, "could never change"),
        ({"always": {"block": "climate", "set": "on"}}, "not an output"),
        ({"always": {"block": "alarm", "set": "scream"}}, "cannot be set to 'scream'"),
        ({"when": {"block": "climate", "reads": "temperature_c", "op": ">", "value": 30}}, "needs `when` and `then`"),
        ({"always": {"block": "alarm", "set": "on"}, "then": {"block": "alarm", "set": "off"}}, "not both"),
    ])
    def test_a_rule_naming_what_is_not_there_is_refused_by_name(self, rule, fragment):
        with pytest.raises(ValidationError, match=re.escape(fragment)):
            room(behaviour=[rule])

    def test_else_is_spelled_as_written_and_kept(self, registry):
        stored = compose(registry, room()).circuit.constraints["project"]
        assert stored["behaviour"][0]["else"] == {"block": "alarm", "set": "off"}
        assert Project.model_validate(stored) == room()


class TestTheBoardsFirmware:
    def test_one_sketch_drives_the_pins_the_composer_allocated(self, registry):
        composition = compose(registry, room())
        sketch = render(composition)
        pins = {b.id: b.pin for b in composition.blocks}
        assert pins == {"climate": "D2", "alarm": "D8", "status": "D13"}
        assert "DHT dht_climate(2, DHT22);" in sketch
        assert "const int OUT_PINS[2] = { 8, 13 };" in sketch
        assert "climate_ok && (climate_temperature_c > 30.0f)" in sketch
        assert "next[1] = MODE_HEARTBEAT;" in sketch

    def test_deterministic_and_ascii(self, registry):
        a, b = composite_project(compose(registry, room())), composite_project(compose(registry, room()))
        assert a.files == b.files and a.hash == b.hash
        assert all(ord(ch) < 128 for line in a.source.splitlines() if "Serial" in line for ch in line)

    def test_a_stored_board_rebuilds_the_same_firmware(self, registry):
        composition = compose_intent(registry, project_intent(), ROOM["intent"])
        rebuilt = project_for(composition.circuit)
        assert rebuilt.source == render(composition)

    @pytest.mark.skipif(shutil.which("pio") is None and shutil.which("platformio") is None,
                        reason="PlatformIO not installed")
    @pytest.mark.parametrize("mcu", BOARDS)
    def test_it_compiles_on_every_board(self, registry, mcu):
        from generators.firmware.compile_gate import compile_project

        result = compile_project(composite_project(compose(registry, room(mcu))))
        assert result.status == "passed", result.log[-2000:]


# ── M3: the load switch as a block ───────────────────────────────────────────

class TestTheAlarm:
    def test_the_room_monitor_has_one_mcu_and_a_switched_buzzer(self, registry):
        board = compose(registry, room()).circuit
        assert [c.id for c in board.components] == ["U1", "U2", "R1", "C1", "Q1", "R2", "J1", "D1", "LED1", "R3"]
        q = {c.pin: c.node_id for c in board.connections if c.component_id == "Q1"}
        assert q == {"B": "SW_BASE", "C": "SW_LOAD", "E": "GND"}

    def test_the_alarm_is_proved_as_itself(self, registry):
        intent = IntentIR(requirements={"function": "load_switch", "targets": {"load_current_ma": 30},
                                        "constraints": {"mcu": "arduino_uno", "load_inductive": True},
                                        "preferences": {}},
                          provenance=Provenance(producer=Producer.FORM))
        alone = realize(registry.dispatch(intent).generator, intent).validation_coverage
        alarm = next(b for b in compose(registry, room()).blocks if b.id == "alarm").circuit.validation_coverage
        assert alarm["properties_hash"] == alone["properties_hash"]
        assert {p["status"] for p in alarm["properties"]} == {"proven"}


# ── M4: the front door ───────────────────────────────────────────────────────

class TestAProjectIsARequirement:
    def test_only_a_project_carries_blocks(self):
        with pytest.raises(ValidationError, match="only function 'project'"):
            Requirements.model_validate({"function": "led_indicator", "blocks": [{"id": "a"}]})
        with pytest.raises(ValidationError, match="names its blocks"):
            Requirements.model_validate({"function": "project"})

    def test_the_form_asks_each_blocks_missing_fields(self):
        intent = FormProducer().build_project([{"id": "alarm", "function": "load_switch"},
                                               {"id": "climate", "function": "temperature_humidity_sensor"}])
        assert intent.underdetermined == ["blocks.alarm.targets.load_current_ma",
                                          "blocks.climate.constraints.cable_length_m"]
        assert not intent.is_answerable

    def test_the_form_builds_the_room_monitor(self, registry):
        intent = FormProducer().build_project(ROOM["blocks"], ROOM["behaviour"], mcu="arduino_uno")
        assert intent.is_answerable
        assert compose_intent(registry, intent).circuit.circuit_id == design_circuit_id(intent)

    def test_an_unknown_block_function_is_refused_by_the_composer(self, registry):
        spec = {**ROOM, "blocks": [*ROOM["blocks"], {"id": "screen", "function": "oled_display"}]}
        with pytest.raises(CompositionRefused, match="screen: 'oled_display' is not composable yet"):
            compose_intent(registry, project_intent(spec))


class TestTheBoardsClaims:
    @pytest.fixture(scope="class")
    def coverage(self, registry):
        return compose_intent(registry, project_intent(), ROOM["intent"]).circuit.validation_coverage

    def test_every_block_claim_is_there_and_named_for_the_board(self, coverage):
        ids = {c["id"] for c in coverage["claims"]}
        assert {"climate.dht.rise_time", "alarm.sw.saturation", "alarm.sw.flyback", "status.led.current_band"} <= ids
        rows = {c["id"]: c for c in coverage["claims"]}
        # The alarm's base resistor is its R1, the board's R2; the LED's R1 is the board's R3.
        assert "R2" in rows["alarm.sw.resistor_dissipation"]["claim"]
        assert "R3" in rows["status.led.resistor_dissipation"]["claim"]

    def test_the_board_claims_its_rail_and_its_pins(self, coverage):
        rows = {c["id"]: c for c in coverage["claims"]}
        assert rows["board.rail_current"]["verdict"] == "holds_defeasible"
        assert rows["board.rail_current"]["grade"] == "G2"
        assert rows["board.pin_rules"]["verdict"] == "holds"

    def test_rail_interaction_is_shown_not_assessed(self, coverage):
        assert coverage["not_assessed"] == ["board.rail_interaction"]
        assert coverage["grade_floor"] == "G2"

    def test_nothing_fails_and_the_ui_gets_the_blocks(self, coverage):
        assert not [c["id"] for c in coverage["claims"] if c["verdict"] == "fails"]
        assert [b["id"] for b in coverage["blocks"]] == ["climate", "alarm", "status"]
        assert coverage["behaviour"][1] == "always: status heartbeat"
        assert coverage["properties_hash"] is None          # a board is not signed as one set (yet)

    def test_a_budget_the_board_exceeds_fails_its_rail_claim(self, registry):
        coverage = compose_intent(registry, project_intent(supply_current_ma=60)).circuit.validation_coverage
        rows = {c["id"]: c for c in coverage["claims"]}
        assert rows["board.rail_current"]["verdict"] == "fails"


class TestGenerateRoute:
    def test_the_room_monitor_sentence_returns_the_board(self, monkeypatch):
        from fastapi.testclient import TestClient

        from api.routes import design as design_route
        from api.routes.auth import get_current_user
        from db.models import get_db
        from main import app
        from middleware.rate_limit import limiter
        from observability.request_log import RequestLogger

        intent = project_intent()

        class _Producer:
            def __init__(self, registry):
                pass

            def produce(self, prompt):
                return intent

        saved, rows = {}, []

        async def save_design(db, ir, user_id, intent_ir=None, annotations=None):
            saved.update(ir=ir, intent_ir=intent_ir)

        async def save_output(*args):
            pass

        async def no_firmware(db, ir):
            return SimpleNamespace(firmware=None, model_dump=lambda **kw: {"status": "unavailable"})

        async def capture(self, row):
            rows.append(row)
            return True

        monkeypatch.setattr(design_route, "IntentProducer", _Producer)
        monkeypatch.setattr(design_route, "save_design", save_design)
        monkeypatch.setattr(design_route, "save_output", save_output)
        monkeypatch.setattr(design_route, "firmware_view", no_firmware)
        monkeypatch.setattr(design_route.ExplanationEngine, "explain", lambda self, ir, v: "")
        monkeypatch.setattr(design_route.run_simulation, "apply_async", lambda **kw: None)
        monkeypatch.setattr(RequestLogger, "record", capture)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u-compose")
        app.dependency_overrides[get_db] = lambda: None
        was_enabled, limiter.enabled = limiter.enabled, False
        try:
            res = TestClient(app).post("/design/generate", json={"prompt": ROOM["intent"]})
        finally:
            limiter.enabled = was_enabled
            app.dependency_overrides.clear()
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["intent"] == ROOM["intent"]
        assert body["circuit_id"] == design_circuit_id(intent)
        assert saved["ir"].generator.startswith("compose@")
        assert [b["id"] for b in body["validation_coverage"]["blocks"]] == ["climate", "alarm", "status"]
        assert "Q1" in body["schematic"] and len(body["bom"]) == 10
        assert rows and rows[-1].generator.startswith("compose@")


class TestTheLLMProducerRecordsAProject:
    """The model writes the project as a requirement; code decides what to ask, and never retries it."""

    def _producer(self, payloads, monkeypatch):
        from ai.intent_producer import IntentProducer

        calls = []

        class _Messages:
            def create(self, **kwargs):
                calls.append(kwargs)
                payload = payloads.pop(0)
                block = SimpleNamespace(type="tool_use", input=payload)
                return SimpleNamespace(content=[block], stop_reason="tool_use")

        monkeypatch.setattr("ai.intent_producer.make_client", lambda: SimpleNamespace(messages=_Messages()))
        return IntentProducer(default_registry()), calls

    def test_the_room_monitor_is_one_call_and_answerable(self, monkeypatch):
        payload = {"function": "project", "constraints": {"mcu": "arduino_uno"},
                   "blocks": ROOM["blocks"], "behaviour": ROOM["behaviour"]}
        producer, calls = self._producer([payload], monkeypatch)
        intent = producer.produce(ROOM["intent"])
        assert len(calls) == 1 and intent.is_answerable
        assert intent.requirements["blocks"] == ROOM["blocks"]
        assert "PROJECTS" in calls[0]["messages"][0]["content"]

    def test_a_missing_load_current_is_asked_only_if_the_model_says_so(self, monkeypatch):
        blocks = [{"id": "alarm", "function": "load_switch"}, *ROOM["blocks"][:1]]
        claimed = {"function": "project", "constraints": {"mcu": "arduino_uno"}, "blocks": blocks,
                   "underdetermined": ["blocks.alarm.targets.load_current_ma", "blocks.alarm.targets.colour"]}
        producer, _ = self._producer([claimed], monkeypatch)
        assert producer.produce("buzzer and a DHT22").underdetermined == ["blocks.alarm.targets.load_current_ma"]

    def test_a_project_is_not_retried(self, monkeypatch):
        payload = {"function": "project", "constraints": {"mcu": "arduino_uno"},
                   "blocks": [{"id": "screen", "function": "oled_display"}]}
        producer, calls = self._producer([payload], monkeypatch)
        producer.produce("an OLED")
        assert len(calls) == 1
