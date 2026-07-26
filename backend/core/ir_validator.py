"""
Cross-field IR validation that Pydantic field_validators cannot do
(they only see their own field, not the full IR object).
Called before any downstream compiler or simulation runs.
"""

from dataclasses import dataclass, field
from typing import List

from .ir_schema import CircuitIR, SignalType


@dataclass
class IRValidationError:
    field_path: str
    message: str
    severity: str = "critical"  # critical | warning


@dataclass
class IRValidationResult:
    errors: List[IRValidationError] = field(default_factory=list)
    warnings: List[IRValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, path: str, msg: str) -> None:
        self.errors.append(IRValidationError(field_path=path, message=msg))

    def add_warning(self, path: str, msg: str) -> None:
        self.warnings.append(IRValidationError(field_path=path, message=msg, severity="warning"))


def validate_ir(ir: CircuitIR) -> IRValidationResult:
    result = IRValidationResult()

    component_ids = {c.id for c in ir.components}
    node_ids = {n.id for n in ir.nodes}

    # Rule: every connection references existing component and node
    for i, conn in enumerate(ir.connections):
        if conn.component_id not in component_ids:
            result.add_error(
                f"connections[{i}].component_id",
                f"References component '{conn.component_id}' which does not exist in components list"
            )
        if conn.node_id not in node_ids:
            result.add_error(
                f"connections[{i}].node_id",
                f"References node '{conn.node_id}' which does not exist in nodes list"
            )

    # Rule: no orphan nodes (every node has at least 2 connections)
    node_connection_count: dict[str, int] = {}
    for conn in ir.connections:
        node_connection_count[conn.node_id] = node_connection_count.get(conn.node_id, 0) + 1

    for node in ir.nodes:
        count = node_connection_count.get(node.id, 0)
        if count == 0:
            result.add_error(
                f"nodes.{node.id}",
                f"Node '{node.id}' has no connections — it is orphaned and will cause simulation failure"
            )
        elif count == 1:
            result.add_warning(
                f"nodes.{node.id}",
                f"Node '{node.id}' has only 1 connection — floating nodes cause undefined behavior"
            )

    # Rule: component voltage ratings must exceed supply voltage
    supply_voltage = ir.constraints.get("supply_voltage", 5.0)
    for comp in ir.components:
        if comp.supply_voltage_max is not None and comp.supply_voltage_max < supply_voltage:
            result.add_error(
                f"components.{comp.id}.supply_voltage_max",
                f"{comp.id} ({comp.part_number}) rated for max {comp.supply_voltage_max}V "
                f"but supply is {supply_voltage}V — this component will be damaged"
            )

    # Rule: I2C nodes must have pull-ups defined
    i2c_nodes = [n for n in ir.nodes if n.type in (SignalType.I2C_SDA, SignalType.I2C_SCL)]
    for node in i2c_nodes:
        # Check if a resistor connects this node to a power node
        has_pullup = False
        power_node_ids = {n.id for n in ir.nodes if n.type == SignalType.POWER}
        for comp in ir.components:
            if comp.type.value == "resistor":
                comp_nodes = {
                    c.node_id for c in ir.connections if c.component_id == comp.id
                }
                if node.id in comp_nodes and comp_nodes & power_node_ids:
                    has_pullup = True
                    break
        if not has_pullup:
            result.add_error(
                f"nodes.{node.id}",
                f"I2C node '{node.id}' has no pull-up resistor to VCC. "
                f"I2C is open-drain and requires pull-ups on both SDA and SCL."
            )

    return result
