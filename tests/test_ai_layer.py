"""
Week 5 — AI layer tests.

Tests that require ANTHROPIC_API_KEY are auto-skipped when the key is absent.
Unit tests (DesignSpec, error formatting) run without the key.

What is verified:
- DesignSpec extracts fields correctly from the tool_use dict
- IntentParser.parse (live): 5 prompt phrasings → valid DesignSpec fields
- (CircuitReasoner coverage removed 2026-09-21 with the module — Stage 1 Task 1.5)
- ExplanationEngine.explain (live): returns non-empty consequential text
"""

import os

import pytest
from pydantic import ValidationError

from ai.explainer import ExplanationEngine
from ai.intent_parser import DesignSpec, IntentParser
from ai.patcher import CircuitPatcher, PatchResult
from core.ir_schema import ApplicationClass, CircuitIR

API_KEY_PRESENT = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
requires_api = pytest.mark.skipif(
    not API_KEY_PRESENT,
    reason="ANTHROPIC_API_KEY not set — live API tests skipped",
)


# ── DesignSpec unit tests (no API) ────────────────────────────────────────────

class TestDesignSpec:
    def test_required_fields(self):
        spec = DesignSpec({
            "intent": "Temperature sensor with RS-485 output",
            "application_class": "modbus_rtu",
        })
        assert spec.intent == "Temperature sensor with RS-485 output"
        assert spec.application_class == "modbus_rtu"

    def test_defaults_applied_when_missing(self):
        spec = DesignSpec({"intent": "LED blink", "application_class": "hobby_arduino"})
        assert spec.safety_class == "general"
        assert spec.target_mcu is None
        assert spec.constraints == {}
        assert spec.use_rs485 is False
        assert spec.has_relay is False

    def test_constraints_populated(self):
        spec = DesignSpec({
            "intent": "Temp sensor",
            "application_class": "hobby_arduino",
            "constraints": {"threshold_temp_celsius": 40, "supply_voltage": 5.0},
        })
        assert spec.constraints["threshold_temp_celsius"] == 40

    def test_use_rs485_true(self):
        spec = DesignSpec({
            "intent": "Modbus sensor",
            "application_class": "modbus_rtu",
            "use_rs485": True,
        })
        assert spec.use_rs485 is True



@requires_api
class TestIntentParserLive:
    """5 prompt phrasings → DesignSpec with expected fields."""

    @pytest.mark.parametrize("prompt,expected_app,expected_sensor", [
        (
            "Build a temperature and humidity sensor that alerts above 40 degrees Celsius",
            "hobby_arduino", "dht22",
        ),
        (
            "I need a Modbus RTU RS-485 master to poll two slave devices at 9600 baud",
            "modbus_rtu", None,
        ),
        (
            "Simple LED blink circuit for an Arduino Uno",
            "hobby_arduino", None,
        ),
        (
            "HVAC controller that reads a temperature sensor and controls a relay",
            "hvac_control", None,
        ),
        (
            "Warehouse temperature monitoring with RS-485 Modbus RTU interface",
            "modbus_rtu", None,
        ),
    ])
    def test_parse_returns_expected_application_class(self, prompt, expected_app, expected_sensor):
        parser = IntentParser()
        spec = parser.parse(prompt)
        assert spec.application_class == expected_app, (
            f"Expected app={expected_app}, got {spec.application_class!r} for prompt: {prompt!r}"
        )
        if expected_sensor:
            assert spec.primary_sensor is not None
            assert expected_sensor in spec.primary_sensor.lower()

    def test_rs485_prompt_sets_use_rs485(self):
        spec = IntentParser().parse("RS-485 Modbus RTU master for industrial sensors")
        assert spec.use_rs485 is True

    def test_threshold_constraint_extracted(self):
        spec = IntentParser().parse(
            "Temperature sensor that triggers a relay when temperature exceeds 40 degrees"
        )
        threshold = spec.constraints.get("threshold_temp_celsius")
        assert threshold is not None, "threshold_temp_celsius should be extracted"
        assert float(threshold) == pytest.approx(40, abs=1)


class TestPatchResultUnit:
    def test_stores_changes_list(self):
        result = PatchResult({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"}
        ]})
        assert len(result.changes) == 1
        assert result.changes[0]["component_id"] == "R1"

    def test_empty_changes_stored(self):
        result = PatchResult({"changes": []})
        assert result.changes == []

    def test_note_to_user_stored(self):
        result = PatchResult({
            "changes": [],
            "note_to_user": "Cannot swap sensor type without redesigning the circuit",
        })
        assert "sensor" in result.note_to_user.lower()

    def test_note_defaults_to_empty_string(self):
        result = PatchResult({"changes": []})
        assert result.note_to_user == ""

    def test_apply_to_updates_component_value(self, ir_dht22):
        result = PatchResult({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"}
        ]})
        patched = result.apply_to(ir_dht22)
        r1 = next(c for c in patched.components if c.id == "R1")
        assert r1.value == "4.7k"

    def test_apply_to_increments_version(self, ir_dht22):
        result = PatchResult({"changes": []})
        patched = result.apply_to(ir_dht22)
        assert patched.version == ir_dht22.version + 1

    def test_apply_to_does_not_mutate_original(self, ir_dht22):
        original_value = next(c for c in ir_dht22.components if c.id == "R1").value
        PatchResult({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"}
        ]}).apply_to(ir_dht22)
        # Original IR is unchanged
        assert next(c for c in ir_dht22.components if c.id == "R1").value == original_value

    def test_apply_to_ignores_unknown_component_id(self, ir_dht22):
        result = PatchResult({"changes": [
            {"component_id": "NONEXISTENT_XYZ", "field": "value", "new_value": "10k"}
        ]})
        patched = result.apply_to(ir_dht22)  # must not raise
        assert patched is not None


@requires_api
class TestPatcherLive:
    def test_change_resistor_value_returns_patch(self, ir_dht22):
        result = CircuitPatcher().patch(ir_dht22, "Change R1 to 4.7k instead of 10k")
        assert isinstance(result, PatchResult)
        assert len(result.changes) > 0

    def test_patch_targets_r1_for_pullup_change(self, ir_dht22):
        result = CircuitPatcher().patch(ir_dht22, "Use a 4.7k pull-up resistor instead of 10k")
        comp_ids = [c["component_id"] for c in result.changes]
        assert "R1" in comp_ids

    def test_patch_apply_produces_valid_pydantic_model(self, ir_dht22):
        result = CircuitPatcher().patch(ir_dht22, "Change R1 value to 4.7k")
        patched = result.apply_to(ir_dht22)
        assert isinstance(patched, CircuitIR)


@requires_api
class TestExplanationEngineLive:
    def test_explanation_is_non_empty_string(self, ir_dht22):
        explainer = ExplanationEngine()
        text = explainer.explain(ir_dht22)
        assert isinstance(text, str) and len(text) > 100

    def test_explanation_mentions_all_component_ids(self, ir_dht22):
        explainer = ExplanationEngine()
        text = explainer.explain(ir_dht22)
        for comp in ir_dht22.components:
            assert comp.id in text, f"Explanation missing component {comp.id}"

    def test_explanation_references_part_numbers(self, ir_modbus):
        explainer = ExplanationEngine()
        text = explainer.explain(ir_modbus)
        assert "MAX485" in text or "485" in text
