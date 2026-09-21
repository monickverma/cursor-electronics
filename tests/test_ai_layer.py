"""
Week 5 — AI layer tests.

Tests that require ANTHROPIC_API_KEY are auto-skipped when the key is absent.
Unit tests (DesignSpec, error formatting) run without the key.

What is verified:
- DesignSpec extracts fields correctly from the tool_use dict
- IntentParser.parse (live): 5 prompt phrasings → valid DesignSpec fields
- (CircuitReasoner coverage removed 2026-09-21 with the module — Stage 1 Task 1.5)
- (CircuitPatcher coverage removed 2026-09-21 with the module — Stage 2, X4;
   the IntentIR patcher is covered by tests/test_intent_patcher.py)
- ExplanationEngine.explain (live): returns non-empty consequential text
"""

import os

import pytest
from pydantic import ValidationError

from ai.explainer import ExplanationEngine
from ai.intent_parser import DesignSpec, IntentParser
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
