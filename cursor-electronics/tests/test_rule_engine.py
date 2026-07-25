"""
Week 3 — HardwareRuleEngine tests.

What is verified:
- rs485_termination_present: PASS (IR_005), FAIL (missing R1), WARN (wrong value)
- rs485_bias_resistors:      PASS (IR_005), FAIL (missing A-line bias), FAIL (missing B-line bias),
                             FAIL (both missing → 2 errors)
- pwm_pin_valid:             PASS (valid pin D9), FAIL (invalid pin D4), FAIL (two bad pins),
                             SKIP (non-Uno target)
- Integration:               rules not in validation_rules are never run;
                             IR with no RS-485 nodes skips RS-485 checks silently
"""

import pytest

from core.ir_examples import IR_001, IR_005
from core.ir_schema import (
    ApplicationClass, CircuitIR, Component, ComponentType,
    Connection, Node, SignalType, ValidationRule,
)
from validation.rule_engine import HardwareRuleEngine


# ── Helpers ───────────────────────────────────────────────────────────────────

def _modbus_without(*component_ids: str) -> CircuitIR:
    """Return IR_005 with the named components (and their connections) removed."""
    return IR_005.model_copy(update={
        "components": [c for c in IR_005.components if c.id not in component_ids],
        "connections": [c for c in IR_005.connections if c.component_id not in component_ids],
    })


def _pwm_ir(pin: str, target_mcu: str = "arduino_uno") -> CircuitIR:
    """Minimal IR with an MCU pin wired to a PWM-typed node."""
    return CircuitIR(
        intent="Test PWM pin validity",
        application_class=ApplicationClass.HOBBY_ARDUINO,
        target_mcu=target_mcu,
        components=[
            Component(
                id="U1", type=ComponentType.MICROCONTROLLER,
                part_number="ATmega328P-PU", manufacturer="Microchip", package="DIP-28",
                supply_voltage_min=1.8, supply_voltage_max=5.5, current_draw_ma=50,
                confidence=0.97,
                justification="Arduino Uno MCU used for PWM pin validity test. "
                              "Only PWM-capable pins 3,5,6,9,10,11 supported.",
            ),
        ],
        nodes=[
            Node(id="VCC_5V", voltage_nominal=5.0, type=SignalType.POWER),
            Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
            Node(id="PWM_OUT", type=SignalType.PWM),
        ],
        connections=[
            Connection(component_id="U1", pin="VCC", node_id="VCC_5V", direction="input"),
            Connection(component_id="U1", pin="GND", node_id="GND", direction="input"),
            Connection(component_id="U1", pin=f"D{pin}", node_id="PWM_OUT", direction="output"),
        ],
        constraints={"supply_voltage": 5.0},
        validation_rules=[ValidationRule.PWM_PIN_VALID],
    )


# ── RS-485 termination ────────────────────────────────────────────────────────

class TestRS485Termination:

    def test_modbus_ir_passes(self, ir_modbus):
        result = HardwareRuleEngine().run(ir_modbus)
        termination_errors = [e for e in result.errors if "termination" in e.field_path]
        assert termination_errors == []

    def test_missing_termination_resistor_fails(self):
        # Remove R1 (the 120Ω resistor bridging RS485_A to RS485_B)
        ir = _modbus_without("R1")
        result = HardwareRuleEngine().run(ir)
        assert not result.is_valid
        assert any("termination" in e.field_path for e in result.errors)

    def test_wrong_value_termination_adds_warning_not_error(self):
        # Replace R1's value with a non-120Ω value (e.g., 10k)
        modified_components = []
        for c in IR_005.components:
            if c.id == "R1":
                modified_components.append(c.model_copy(update={"value": "10k"}))
            else:
                modified_components.append(c)
        ir = IR_005.model_copy(update={"components": modified_components})
        result = HardwareRuleEngine().run(ir)
        assert result.is_valid, "Wrong value should warn, not error"
        assert any("termination" in w.message.lower() or "100" in w.message for w in result.warnings)

    def test_no_rs485_nodes_skips_check_silently(self, ir_dht22):
        # IR_001 has no RS-485 nodes — rule should not produce any errors
        # (though RS485_TERMINATION_PRESENT is not in IR_001's rules, we call directly)
        ir = ir_dht22.model_copy(update={
            "validation_rules": ir_dht22.validation_rules + [ValidationRule.RS485_TERMINATION_PRESENT]
        })
        result = HardwareRuleEngine().run(ir)
        assert result.is_valid

    def test_rule_not_in_validation_rules_is_not_run(self):
        # IR_005 without RS485_TERMINATION_PRESENT in its rules should not be checked
        ir = IR_005.model_copy(update={
            "components": [c for c in IR_005.components if c.id != "R1"],
            "connections": [c for c in IR_005.connections if c.component_id != "R1"],
            "validation_rules": [
                r for r in IR_005.validation_rules
                if r != ValidationRule.RS485_TERMINATION_PRESENT
            ],
        })
        result = HardwareRuleEngine().run(ir)
        # No termination check ran, so no termination error
        assert not any("termination" in e.field_path for e in result.errors)


# ── RS-485 bias resistors ─────────────────────────────────────────────────────

class TestRS485BiasResistors:

    def test_modbus_ir_passes(self, ir_modbus):
        result = HardwareRuleEngine().run(ir_modbus)
        bias_errors = [e for e in result.errors if "bias" in e.field_path]
        assert bias_errors == []

    def test_missing_a_line_bias_fails(self):
        # Remove R2 (A-line pull-up to VCC)
        ir = _modbus_without("R2")
        result = HardwareRuleEngine().run(ir)
        assert not result.is_valid
        assert any("bias.A" in e.field_path for e in result.errors)
        assert not any("bias.B" in e.field_path for e in result.errors)

    def test_missing_b_line_bias_fails(self):
        # Remove R3 (B-line pull-down to GND)
        ir = _modbus_without("R3")
        result = HardwareRuleEngine().run(ir)
        assert not result.is_valid
        assert any("bias.B" in e.field_path for e in result.errors)
        assert not any("bias.A" in e.field_path for e in result.errors)

    def test_missing_both_bias_resistors_produces_two_errors(self):
        ir = _modbus_without("R2", "R3")
        result = HardwareRuleEngine().run(ir)
        bias_errors = [e for e in result.errors if "bias" in e.field_path]
        assert len(bias_errors) == 2


# ── PWM pin validity ──────────────────────────────────────────────────────────

class TestPWMPinValid:

    @pytest.mark.parametrize("pin", ["3", "5", "6", "9", "10", "11"])
    def test_valid_pwm_pins_pass(self, pin):
        result = HardwareRuleEngine().run(_pwm_ir(pin))
        assert result.is_valid, f"Pin D{pin} should be a valid PWM pin on Arduino Uno"

    def test_invalid_pwm_pin_4_fails(self):
        result = HardwareRuleEngine().run(_pwm_ir("4"))
        assert not result.is_valid
        assert any("D4" in e.field_path for e in result.errors)

    def test_invalid_pwm_pin_7_fails(self):
        result = HardwareRuleEngine().run(_pwm_ir("7"))
        assert not result.is_valid
        assert any("D7" in e.field_path for e in result.errors)

    def test_non_uno_target_skips_pwm_check(self):
        # ESP32 target — rule should not run even on non-PWM Uno pin numbers
        result = HardwareRuleEngine().run(_pwm_ir("4", target_mcu="esp32"))
        assert result.is_valid

    def test_multiple_invalid_pwm_pins_all_flagged(self):
        # Build IR with two MCU pins on PWM nodes — both invalid
        ir = CircuitIR(
            intent="Test multiple invalid PWM pins",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            target_mcu="arduino_uno",
            components=[
                Component(
                    id="U1", type=ComponentType.MICROCONTROLLER,
                    part_number="ATmega328P-PU", manufacturer="Microchip", package="DIP-28",
                    supply_voltage_min=1.8, supply_voltage_max=5.5, current_draw_ma=50,
                    confidence=0.97,
                    justification="Uno MCU used to test that all invalid PWM pins are flagged "
                                  "individually, not just the first one found.",
                ),
            ],
            nodes=[
                Node(id="VCC_5V", voltage_nominal=5.0, type=SignalType.POWER),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
                Node(id="PWM_A", type=SignalType.PWM),
                Node(id="PWM_B", type=SignalType.PWM),
            ],
            connections=[
                Connection(component_id="U1", pin="VCC", node_id="VCC_5V", direction="input"),
                Connection(component_id="U1", pin="GND", node_id="GND", direction="input"),
                Connection(component_id="U1", pin="D4", node_id="PWM_A", direction="output"),
                Connection(component_id="U1", pin="D7", node_id="PWM_B", direction="output"),
            ],
            constraints={"supply_voltage": 5.0},
            validation_rules=[ValidationRule.PWM_PIN_VALID],
        )
        result = HardwareRuleEngine().run(ir)
        pwm_errors = [e for e in result.errors if "pwm" in e.field_path.lower() or "D4" in e.field_path or "D7" in e.field_path]
        assert len(pwm_errors) == 2


# ── Integration ───────────────────────────────────────────────────────────────

class TestRuleEngineIntegration:

    def test_dht22_ir_has_no_rule_engine_errors(self, ir_dht22):
        # IR_001 has no RS-485 or PWM rules — engine should return clean result
        result = HardwareRuleEngine().run(ir_dht22)
        assert result.is_valid

    def test_modbus_ir_passes_all_its_rules(self, ir_modbus):
        result = HardwareRuleEngine().run(ir_modbus)
        assert result.is_valid, f"IR_005 should pass all its rules. Errors: {result.errors}"

    def test_engine_returns_clean_result_for_empty_rules_list(self):
        ir = IR_001.model_copy(update={"validation_rules": []})
        result = HardwareRuleEngine().run(ir)
        assert result.is_valid
        assert result.errors == []
        assert result.warnings == []
