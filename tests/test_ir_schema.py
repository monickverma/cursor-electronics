"""
IR schema tests — 20+ cases covering valid and invalid inputs.
Every example IR must pass. Every invalid IR must be rejected with a clear error.
"""

import pytest
from pydantic import ValidationError

from core.ir_schema import (
    ApplicationClass, CircuitIR, Component, ComponentType,
    Connection, Node, SafetyClass, SignalType, ValidationRule,
)
from core.ir_examples import ALL_EXAMPLES, IR_001, IR_003, IR_005
from core.ir_validator import validate_ir


# ─── All 5 example IRs must instantiate cleanly ────────────────────────────

class TestExampleIRsValid:
    def test_all_examples_instantiate(self):
        assert len(ALL_EXAMPLES) == 5
        for ir in ALL_EXAMPLES:
            assert isinstance(ir, CircuitIR)

    def test_example_circuit_ids_unique(self):
        ids = [ir.circuit_id for ir in ALL_EXAMPLES]
        assert len(ids) == len(set(ids)), "Example IRs must have unique circuit_ids"

    def test_ir001_component_count(self):
        assert len(IR_001.components) == 4

    def test_ir005_has_rs485_nodes(self, ir_modbus):
        node_types = {n.type for n in ir_modbus.nodes}
        assert SignalType.RS485_A in node_types
        assert SignalType.RS485_B in node_types

    def test_ir003_has_simulation_spec(self, ir_rc_filter):
        assert ir_rc_filter.simulation_spec is not None
        assert ir_rc_filter.simulation_spec.analyses[0].type == "ac_sweep"

    def test_all_examples_pass_ir_validation(self):
        for ir in ALL_EXAMPLES:
            result = validate_ir(ir)
            assert result.is_valid, (
                f"IR {ir.circuit_id} failed validation: "
                + "; ".join(e.message for e in result.errors)
            )


# ─── Component validation ───────────────────────────────────────────────────

class TestComponentValidation:
    def _base_component(self, **overrides):
        defaults = {
            "id": "R1", "type": ComponentType.RESISTOR,
            "part_number": "RC0402FR-0710KL", "manufacturer": "Yageo",
            "package": "0402", "value": "10k", "supply_voltage_max": 50.0,
            "confidence": 0.99,
            "justification": "10kΩ pull-up required by DHT22 datasheet section 4.2",
        }
        defaults.update(overrides)
        return Component(**defaults)

    def test_valid_component(self):
        comp = self._base_component()
        assert comp.id == "R1"

    def test_confidence_must_be_0_to_1(self):
        with pytest.raises(ValidationError):
            self._base_component(confidence=1.5)

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValidationError):
            self._base_component(confidence=-0.1)

    def test_justification_too_short_rejected(self):
        with pytest.raises(ValidationError):
            self._base_component(justification="too short")

    def test_justification_empty_rejected(self):
        with pytest.raises(ValidationError):
            self._base_component(justification="")

    def test_sensor_type_optional_defaults_none(self):
        comp = self._base_component()
        assert comp.sensor_type is None

    def test_sensor_type_can_be_set(self):
        comp = self._base_component(
            type=ComponentType.SENSOR,
            part_number="DHT22", sensor_type="dht22",
            justification="DHT22 digital temp/humidity sensor with 10kΩ pull-up required"
        )
        assert comp.sensor_type == "dht22"


# ─── Connection and node validation ────────────────────────────────────────

class TestCrossFieldValidation:
    def _minimal_ir(self, extra_components=None, extra_nodes=None, extra_connections=None):
        components = [
            Component(
                id="R1", type=ComponentType.RESISTOR,
                part_number="RC0402FR-0710KL", manufacturer="Yageo",
                package="0402", value="10k", supply_voltage_max=50.0,
                confidence=0.99,
                justification="Pull-up resistor, minimum 20 char justification here",
            )
        ] + (extra_components or [])
        nodes = [
            Node(id="VCC", voltage_nominal=5.0, type=SignalType.POWER),
            Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
            Node(id="SIG", type=SignalType.DIGITAL),
        ] + (extra_nodes or [])
        connections = [
            Connection(component_id="R1", pin="A", node_id="VCC"),
            Connection(component_id="R1", pin="B", node_id="SIG"),
            Connection(component_id="R1", pin="GND", node_id="GND"),  # prevents orphan-node error
        ] + (extra_connections or [])
        return CircuitIR(
            intent="test circuit",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            components=components, nodes=nodes, connections=connections,
            constraints={"supply_voltage": 5.0},
            validation_rules=[ValidationRule.NO_FLOATING_NODES],
        )

    def test_valid_minimal_ir(self):
        ir = self._minimal_ir()
        result = validate_ir(ir)
        # SIG has only 1 connection — should be a warning, not error
        assert not any(e.severity == "critical" for e in result.errors)

    def test_nonexistent_component_id_in_connection(self):
        ir = self._minimal_ir(
            extra_connections=[Connection(component_id="NONEXISTENT", pin="A", node_id="GND")]
        )
        result = validate_ir(ir)
        assert not result.is_valid
        assert any("NONEXISTENT" in e.message for e in result.errors)

    def test_nonexistent_node_id_in_connection(self):
        ir = self._minimal_ir(
            extra_connections=[Connection(component_id="R1", pin="C", node_id="MISSING_NODE")]
        )
        result = validate_ir(ir)
        assert not result.is_valid
        assert any("MISSING_NODE" in e.message for e in result.errors)

    def test_duplicate_component_ids_rejected(self):
        comp = Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-0710KL", manufacturer="Yageo",
            package="0402", value="10k", supply_voltage_max=50.0,
            confidence=0.99,
            justification="Duplicate ID component — should be rejected by validator",
        )
        with pytest.raises(ValidationError):
            CircuitIR(
                intent="test", application_class=ApplicationClass.HOBBY_ARDUINO,
                components=[comp, comp],  # same ID twice
                nodes=[Node(id="GND", type=SignalType.GROUND)],
                connections=[],
                validation_rules=[],
            )

    def test_voltage_rating_below_supply_caught(self):
        ir = self._minimal_ir(
            extra_components=[
                Component(
                    id="C1", type=ComponentType.CAPACITOR,
                    part_number="GRM033R60J104KE19D", manufacturer="Murata",
                    package="0201", value="100nF",
                    supply_voltage_max=3.0,  # rated 3V but supply is 5V — VIOLATION
                    confidence=0.99,
                    justification="Wrong voltage rating — intentional test violation here",
                )
            ],
            extra_connections=[
                Connection(component_id="C1", pin="+", node_id="VCC"),
                Connection(component_id="C1", pin="-", node_id="GND"),
            ]
        )
        result = validate_ir(ir)
        assert not result.is_valid
        assert any("C1" in e.message for e in result.errors)


# ─── Patch history ──────────────────────────────────────────────────────────

class TestPatchHistory:
    def test_patch_history_starts_empty(self):
        assert IR_001.patch_history == []

    def test_version_starts_at_1(self):
        assert IR_001.version == 1
