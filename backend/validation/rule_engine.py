"""
Hardware rule engine — deterministic checks for circuit-type-specific rules.
Runs after ir_validator.py (structural validation) and before simulation.
Only evaluates rules listed in ir.validation_rules.
"""

import re
from typing import Optional, Set

from core.ir_schema import CircuitIR, SignalType, ValidationRule
from core.ir_validator import IRValidationResult


_ARDUINO_UNO_PWM_PINS: Set[str] = {"3", "5", "6", "9", "10", "11"}
_RS485_TERMINATION_MIN_OHM = 100.0
_RS485_TERMINATION_MAX_OHM = 150.0


def _parse_ohms(value: str) -> Optional[float]:
    """Parse a component value string into ohms. Returns None if not a resistance."""
    v = value.strip().upper()
    # "120R", "150R", "560R", plain digits like "120"
    m = re.match(r'^(\d+(?:\.\d+)?)R?$', v)
    if m and not any(v.endswith(suffix) for suffix in ("F", "H", "HZ")):
        return float(m.group(1))
    # "10K", "1K59", "5K1"
    m = re.match(r'^(\d+(?:\.\d+)?)K(\d*)$', v)
    if m:
        integer = float(m.group(1))
        frac_str = m.group(2)
        frac = float(frac_str) / (10 ** len(frac_str)) if frac_str else 0.0
        return (integer + frac) * 1000.0
    return None


class HardwareRuleEngine:
    """Deterministic hardware rule checks keyed to ValidationRule enum values."""

    _HANDLERS = {
        ValidationRule.RS485_TERMINATION_PRESENT: "_check_rs485_termination",
        ValidationRule.RS485_BIAS_RESISTORS: "_check_rs485_bias_resistors",
        ValidationRule.PWM_PIN_VALID: "_check_pwm_pin_valid",
    }

    def run(self, ir: CircuitIR) -> IRValidationResult:
        result = IRValidationResult()
        for rule in ir.validation_rules:
            handler_name = self._HANDLERS.get(rule)
            if handler_name:
                getattr(self, handler_name)(ir, result)
        return result

    # ── RS-485 termination ────────────────────────────────────────────────────

    def _check_rs485_termination(self, ir: CircuitIR, result: IRValidationResult) -> None:
        rs485_a_ids = {n.id for n in ir.nodes if n.type == SignalType.RS485_A}
        rs485_b_ids = {n.id for n in ir.nodes if n.type == SignalType.RS485_B}

        if not rs485_a_ids or not rs485_b_ids:
            return  # No RS-485 nodes present — rule does not apply

        for comp in ir.components:
            if comp.type.value != "resistor":
                continue
            comp_nodes = {c.node_id for c in ir.connections if c.component_id == comp.id}
            if not (comp_nodes & rs485_a_ids and comp_nodes & rs485_b_ids):
                continue
            # A resistor bridges A and B lines — validate its value if declared
            if comp.value is not None:
                ohms = _parse_ohms(comp.value)
                if ohms is not None and not (
                    _RS485_TERMINATION_MIN_OHM <= ohms <= _RS485_TERMINATION_MAX_OHM
                ):
                    result.add_warning(
                        f"components.{comp.id}.value",
                        f"{comp.id} bridges RS-485 A/B lines but its value ({comp.value}) is "
                        f"outside the 100–150Ω termination range. Typical value is 120Ω.",
                    )
            return  # Termination resistor found

        result.add_error(
            "rs485_termination",
            "RS-485 bus has no termination resistor between the A and B lines. "
            "Without 120Ω termination, signal reflections cause communication errors "
            "at baud rates above ~19200.",
        )

    # ── RS-485 bus bias resistors ─────────────────────────────────────────────

    def _check_rs485_bias_resistors(self, ir: CircuitIR, result: IRValidationResult) -> None:
        rs485_a_ids = {n.id for n in ir.nodes if n.type == SignalType.RS485_A}
        rs485_b_ids = {n.id for n in ir.nodes if n.type == SignalType.RS485_B}
        power_ids = {n.id for n in ir.nodes if n.type == SignalType.POWER}
        gnd_ids = {n.id for n in ir.nodes if n.type == SignalType.GROUND}

        if not rs485_a_ids or not rs485_b_ids:
            return

        a_bias_ok = b_bias_ok = False
        for comp in ir.components:
            if comp.type.value != "resistor":
                continue
            comp_nodes = {c.node_id for c in ir.connections if c.component_id == comp.id}
            if comp_nodes & rs485_a_ids and comp_nodes & power_ids:
                a_bias_ok = True
            if comp_nodes & rs485_b_ids and comp_nodes & gnd_ids:
                b_bias_ok = True

        if not a_bias_ok:
            result.add_error(
                "rs485_bias.A",
                "RS-485 A-line has no pull-up bias resistor to VCC. When all transmitters "
                "are tri-stated the bus floats and receivers see undefined data.",
            )
        if not b_bias_ok:
            result.add_error(
                "rs485_bias.B",
                "RS-485 B-line has no pull-down bias resistor to GND. When all transmitters "
                "are tri-stated the bus floats and receivers see undefined data.",
            )

    # ── PWM pin validity ──────────────────────────────────────────────────────

    def _check_pwm_pin_valid(self, ir: CircuitIR, result: IRValidationResult) -> None:
        if ir.target_mcu != "arduino_uno":
            return  # Rule scoped to Arduino Uno only

        mcu_ids = {c.id for c in ir.components if c.type.value == "microcontroller"}
        pwm_node_ids = {n.id for n in ir.nodes if n.type == SignalType.PWM}

        for conn in ir.connections:
            if conn.component_id not in mcu_ids or conn.node_id not in pwm_node_ids:
                continue
            pin_num = conn.pin.lstrip("Dd")
            if pin_num not in _ARDUINO_UNO_PWM_PINS:
                result.add_error(
                    f"connections.{conn.component_id}.{conn.pin}",
                    f"Pin {conn.pin} on {conn.component_id} carries a PWM signal but Arduino Uno "
                    f"only supports PWM on pins 3, 5, 6, 9, 10, 11. "
                    f"Pin {conn.pin} outputs DC — this will silently produce wrong behavior.",
                )
