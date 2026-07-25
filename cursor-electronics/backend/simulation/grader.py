"""Grade simulation output against the IR's expected_outputs with 15% tolerance.

The 15% tolerance matches the CLAUDE.md accuracy gate:
  "ngspice output must be within 15% of bench measurement."
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.ir_schema import CircuitIR
from simulation.parser import SimulationData


_TOLERANCE = 0.15  # 15% — must match CLAUDE.md accuracy gate


@dataclass
class GradeResult:
    passed: bool
    failures: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class SimulationGrader:
    """Compares SimulationData against ir.simulation_spec.expected_outputs."""

    def grade(self, ir: CircuitIR, data: SimulationData) -> GradeResult:
        if not ir.simulation_spec or not ir.simulation_spec.expected_outputs:
            return GradeResult(passed=True, notes=["No expected outputs defined — skipped"])

        failures: List[str] = []
        for node_id, expected in ir.simulation_spec.expected_outputs.items():
            actual = self._find_value(ir, data, node_id)
            if actual is None:
                failures.append(f"Node '{node_id}' not found in simulation output")
            elif not _within_tolerance(actual, expected):
                pct = (
                    abs(actual - expected) / abs(expected) * 100
                    if expected != 0
                    else float("inf")
                )
                failures.append(
                    f"Node '{node_id}': expected {expected}V, got {actual:.4f}V "
                    f"({pct:.1f}% error, tolerance ±{_TOLERANCE * 100:.0f}%)"
                )

        return GradeResult(passed=len(failures) == 0, failures=failures)

    def _find_value(
        self, ir: CircuitIR, data: SimulationData, node_id: str
    ) -> Optional[float]:
        node_lower = node_id.lower()

        # DC operating point
        if node_lower in data.dc_voltages:
            return data.dc_voltages[node_lower]

        # AC sweep: evaluate at the cutoff frequency from constraints
        if data.ac_points:
            cutoff = ir.constraints.get("cutoff_hz") or ir.constraints.get(
                "cutoff_frequency"
            )
            if cutoff is not None:
                _, values = min(data.ac_points, key=lambda x: abs(x[0] - cutoff))
                if node_lower in values:
                    return values[node_lower]

        return None


def _within_tolerance(actual: float, expected: float) -> bool:
    if expected == 0:
        return abs(actual) < 1e-3
    return abs(actual - expected) / abs(expected) <= _TOLERANCE
