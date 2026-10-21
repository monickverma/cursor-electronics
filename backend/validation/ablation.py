"""
Component ablation: take each part out, or short it, and see what notices.

The M1 matrix (`envelope_grid.py`) asks whether a 5% drift in one part is
caught. Ablation asks the coarser question topology optimisation asks of a
structure: *which parts does the design actually need?* For every component of
a realised design, two faults:

  - **open** — the part and its connections are gone (a part left off the
    board, a cracked joint). The SPICE generator ties any node left floating
    to ground through 1 GΩ, so the netlist still solves.
  - **short** — a two-terminal part becomes 1 mΩ between the same nodes (a
    solder bridge, a failed-short capacitor).

Each fault is judged twice, by two witnesses that must not be confused:

  - **ngspice** — the adapter's measurement on the faulted design, against the
    unfaulted one. This is the physics.
  - **the claims** — `assess()` on the faulted design, against the unfaulted
    one. This is what Circuit OS would tell the user.

The interesting rows are where they disagree. ngspice moves and no claim flips
means the claims did not look at that part (physics claims are written from
the intent, not read from the circuit, so only proofs and rules can react).
Neither moves means the part is redundant *in what is modelled* — a bypass
capacitor is the expected case, since nothing here simulates supply noise.
That is a statement about the model, never about the board.
"""

from __future__ import annotations

import math
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel

from core.ir_schema import CircuitIR, ComponentType, Connection

Fault = Literal["open", "short"]

#: A change in a measured quantity larger than this counts as "ngspice noticed".
#: The grader's 15% tolerance: a smaller move would pass the simulation gate anyway.
MOVED = 0.15

_SHORT_OHMS = "0.001"


class NotTwoTerminal(ValueError):
    """A short was asked of a part that has no single pair of terminals."""


def open_component(ir: CircuitIR, component_id: str) -> CircuitIR:
    """A deep copy of `ir` with one part and all its connections removed."""
    faulted = ir.model_copy(deep=True)
    if not any(c.id == component_id for c in faulted.components):
        raise ValueError(f"no component {component_id!r} to open")
    faulted.components = [c for c in faulted.components if c.id != component_id]
    faulted.connections = [k for k in faulted.connections if k.component_id != component_id]
    return faulted


def short_component(ir: CircuitIR, component_id: str) -> CircuitIR:
    """
    A deep copy of `ir` with a two-terminal part replaced by 1 mΩ.

    Refuses anything with more or fewer than two distinct nodes: shorting a
    transistor or an MCU has no single meaning, and guessing one would report
    a fault nobody seeded.
    """
    faulted = ir.model_copy(deep=True)
    target = next((c for c in faulted.components if c.id == component_id), None)
    if target is None:
        raise ValueError(f"no component {component_id!r} to short")
    nodes = list(dict.fromkeys(k.node_id for k in faulted.connections if k.component_id == component_id))
    if len(nodes) != 2:
        raise NotTwoTerminal(f"{component_id} touches {len(nodes)} nodes; a short needs exactly two")
    # The part keeps its id, confidence and justification; only what SPICE reads changes.
    faulted.components = [c for c in faulted.components if c.id != component_id] + [
        target.model_copy(update={"type": ComponentType.RESISTOR, "part_number": "ABLATION_SHORT",
                                  "value": _SHORT_OHMS})
    ]
    faulted.connections = [k for k in faulted.connections if k.component_id != component_id] + [
        Connection(component_id=component_id, pin="A", node_id=nodes[0]),
        Connection(component_id=component_id, pin="B", node_id=nodes[1]),
    ]
    return faulted


class AblationRow(BaseModel):
    component: str
    kind: str
    fault: Fault
    #: quantity -> (baseline, faulted); NaN where ngspice gave nothing
    measured: Dict[str, Tuple[float, float]] = {}
    #: claim id -> (baseline verdict, faulted verdict), only the ones that changed
    flipped: Dict[str, Tuple[str, str]] = {}
    note: Optional[str] = None

    @property
    def physics_moved(self) -> bool:
        for before, after in self.measured.values():
            if not math.isfinite(after) and math.isfinite(before):
                return True
            if math.isfinite(before) and math.isfinite(after):
                if abs(after - before) / (abs(before) or 1.0) > MOVED:
                    return True
        return False

    @property
    def caught_by(self) -> List[str]:
        """
        Claims that now say *fails*. A claim that weakens (holds → holds_defeasible,
        usually because the stand-in short has no rating) or falls silent
        (→ not_assessed, the proof could not compile) did not tell anyone anything.
        """
        return [cid for cid, (before, after) in self.flipped.items()
                if after == "fails" and before != "fails"]

    @property
    def silenced(self) -> List[str]:
        return [cid for cid, (before, after) in self.flipped.items()
                if after in ("not_assessed", "absent") and before.startswith("holds")]

    @property
    def verdict(self) -> str:
        if self.note:
            return "not evaluated"
        moved, caught = self.physics_moved, bool(self.caught_by)
        if moved and caught:
            return "needed, and caught"
        if moved:
            return "needed, NOT caught"          # the gap this harness exists to find
        if caught:
            return "caught, physics unchanged"   # a rule, not the measured quantity
        return "unused in the model"


class AblationReport(BaseModel):
    generator: str
    point: Dict[str, float]
    baseline: Dict[str, float]
    rows: List[AblationRow]

    def summary(self) -> str:
        lines = [f"{self.generator} at {self.point}",
                 "  baseline: " + ", ".join(f"{q}={v:.4g}" for q, v in self.baseline.items())]
        for r in self.rows:
            moves = ", ".join(f"{q} {b:.4g}->{a:.4g}" for q, (b, a) in r.measured.items())
            tail = (f"  | fails: {', '.join(r.caught_by)}" if r.caught_by else "") + \
                   (f"  | silenced: {', '.join(r.silenced)}" if r.silenced else "")
            lines.append(f"  {r.component:<4} {r.kind:<16} {r.fault:<5} {r.verdict:<26} "
                         + (r.note or moves) + tail)
        return "\n".join(lines)


def _verdicts(generator, intent, circuit: CircuitIR) -> Dict[str, str]:
    from validation.claims import assess

    return {c.id: str(getattr(c.verdict, "value", c.verdict)) for c in assess(generator, intent, circuit).claims}


def _measure(adapter, circuit: CircuitIR) -> Dict[str, float]:
    try:
        return dict(adapter.measure(circuit))
    except Exception:  # noqa: BLE001 — a netlist ngspice cannot solve is a result, not a crash
        return {}


def _middle_point(generator, board) -> Dict[str, float]:
    from validation.envelope_grid import grid_of

    points = [dict(p) for p in grid_of(generator, board).points()]
    return points[len(points) // 2]


def run_ablation(adapter_name: str, board: Optional[str] = None,
                 point: Optional[Dict[str, float]] = None) -> AblationReport:
    """Open and short every part of one generator's design at one grid point."""
    from validation.grid_adapters import ADAPTERS

    adapter = ADAPTERS[adapter_name].build(board)
    generator = adapter.generator
    point = point or _middle_point(generator, board)
    intent = adapter.intent_for(point)
    circuit = generator.generate(intent)

    baseline = _measure(adapter, circuit)
    if not baseline:
        raise RuntimeError(f"{adapter_name}: the unfaulted design gives no measurement — nothing to compare")
    base_verdicts = _verdicts(generator, intent, circuit)

    rows: List[AblationRow] = []
    for comp in circuit.components:
        kind = str(getattr(comp.type, "value", comp.type))
        for fault, apply in (("open", open_component), ("short", short_component)):
            try:
                faulted = apply(circuit, comp.id)
            except NotTwoTerminal:
                continue            # not a two-terminal part; nothing to report
            except ValueError as exc:
                rows.append(AblationRow(component=comp.id, kind=kind, fault=fault, note=str(exc)))
                continue
            after = _measure(adapter, faulted)
            measured = {q: (v, after.get(q, math.nan)) for q, v in baseline.items()}
            try:
                verdicts = _verdicts(generator, intent, faulted)
            except Exception as exc:  # noqa: BLE001 — a proof that cannot compile is reported
                rows.append(AblationRow(component=comp.id, kind=kind, fault=fault, measured=measured,
                                        note=f"assess() failed: {type(exc).__name__}: {exc}"[:160]))
                continue
            flipped = {cid: (base_verdicts.get(cid, "absent"), v)
                       for cid, v in verdicts.items() if base_verdicts.get(cid) != v}
            flipped.update({cid: (v, "absent") for cid, v in base_verdicts.items() if cid not in verdicts})
            rows.append(AblationRow(component=comp.id, kind=kind, fault=fault,
                                    measured=measured, flipped=flipped))

    return AblationReport(generator=f"{generator.name}@{generator.version}", point=point,
                          baseline=baseline, rows=rows)
