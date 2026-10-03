"""
Composition — several blocks on one board. `COMPOSITION_PLAN.md` M1;
`brain/decisions.md` [2026-10-03].

A project is a board plus a list of blocks, each block a request one existing
generator already serves ("temperature_humidity_sensor", "led_indicator").
The composer never designs a circuit itself. It:

1. allocates each block's MCU pin on the shared board — a pin the request
   names, else the board's default for that role, else the first free pin
   the board's table allows — and checks the whole assignment with
   `validation/pin_rules.py`, so two blocks never meet on one pin;
2. hands each block, with its pin, to its own generator through the
   registry and `realize()`, so every block keeps its own envelope, proofs
   and claims, unchanged;
3. merges the block circuits into one CircuitIR: one MCU (U1), one bypass
   capacitor (C1), one rail and one ground; every other part renumbered,
   and every other net kept, prefixed with its block id only where two
   blocks would otherwise share a name.

What it does **not** claim (M4): anything about the board as a whole — the
shared rail's total current, or one block's load moving another's rail. The
composite carries no `validation_coverage`; each block's claims stay on that
block (`Composition.blocks[*].circuit`), and hold on the stated side condition
that the shared rail stays in range.

A block function without a pin slot below is refused by name, as is any
block its generator refuses. Every refusal is collected before raising.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.intent_ir import IntentIR, Producer, Provenance
from core.ir_schema import CircuitIR, ComponentType, Connection, SignalType, SimulationAnalysis, SimulationSpec
from data.mcu_targets import DEFAULT_TARGET, TARGETS, Target
from generators.realize import CIRCUIT_ID_NAMESPACE, RefusedIntent, realize
from generators.registry import GeneratorRegistry
from validation.pin_rules import Assignment, check_assignment, check_design

VERSION = "0.1.0"
NAME = "compose"


# ── The request ──────────────────────────────────────────────────────────────

class Block(BaseModel):
    """One block: what one existing generator is asked for, as IntentIR sections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")
    function: str
    targets: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    """A board and the blocks on it. The board's MCU is the project's, never a block's."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: str = ""                               # the sentence, when there is one
    mcu: str = DEFAULT_TARGET
    blocks: Tuple[Block, ...]

    @field_validator("blocks")
    @classmethod
    def _blocks(cls, v: Tuple[Block, ...]) -> Tuple[Block, ...]:
        if len(v) < 1:
            raise ValueError("a project needs at least one block")
        ids = [b.id for b in v]
        if len(ids) != len(set(ids)):
            raise ValueError(f"block ids must be unique; got {ids}")
        return v

    @field_validator("mcu")
    @classmethod
    def _board(cls, v: str) -> str:
        if v not in TARGETS:
            raise ValueError(f"mcu must be one of {sorted(TARGETS)}; got {v!r}")
        return v


# ── Pin slots ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Slot:
    preference: str        # the preference the generator reads its pin from
    role: str              # pin_rules role
    default: str           # key into Target.defaults
    net: str               # the net the generator puts on that pin


#: The block functions that take one MCU pin, and how each generator is told
#: which. A function absent here is not composable yet and is refused by name.
SLOTS: Mapping[str, Slot] = {
    "led_indicator": Slot("gpio_pin", "output", "led", "LED_CTRL"),
    "temperature_humidity_sensor": Slot("data_pin", "bidirectional", "dht_data", "DHT22_DATA"),
}


class CompositionRefused(Exception):
    """The project cannot be built; `reasons` names every block that failed and why."""

    def __init__(self, reasons: Sequence[str]) -> None:
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


def _free_for_gpio(target: Target, name: str) -> bool:
    pin = target.pins[name]
    if pin.reserved or pin.strapping:
        return False
    return not any(unit == target.console_uart for unit, _ in pin.uart)


def allocate_pins(target: Target, blocks: Sequence[Block]) -> Dict[str, str]:
    """Block id → pin. Requested pins first, then defaults, then the first free pin, in table order."""
    taken: Dict[str, str] = {}
    out: Dict[str, str] = {}
    reasons: List[str] = []

    def claim(block: Block, name: str) -> None:
        out[block.id] = name
        taken[name] = block.id

    for block in blocks:                               # requested pins: never moved
        slot = SLOTS[block.function]
        asked = block.preferences.get(slot.preference)
        if asked is None:
            continue
        pin = target.pin(asked)
        if pin is None:
            reasons.append(f"{block.id}: {target.board} has no pin {asked!r}")
        elif pin.name in taken:
            reasons.append(f"{block.id}: {pin.name} is already {taken[pin.name]}'s pin")
        elif any(unit == target.console_uart for unit, _ in pin.uart):
            reasons.append(f"{block.id}: {pin.name} carries the USB console ({target.console_uart}); "
                           f"a load on it disturbs uploads and the serial monitor")
        else:
            claim(block, pin.name)

    for block in blocks:
        if block.id in out or any(r.startswith(f"{block.id}:") for r in reasons):
            continue
        slot = SLOTS[block.function]
        default = target.pin(target.defaults.get(slot.default))
        candidates = ([default.name] if default else []) + list(target.pins)
        for name in candidates:
            if name in taken or not _free_for_gpio(target, name):
                continue
            if check_assignment(target, [Assignment(name, slot.role, slot.net)]):
                continue
            claim(block, name)
            break
        else:
            reasons.append(f"{block.id}: no free pin on the {target.board} can take a {slot.role} line")

    if reasons:
        raise CompositionRefused(reasons)
    findings = check_assignment(target, [Assignment(out[b.id], SLOTS[b.function].role, b.id) for b in blocks])
    if findings:
        raise CompositionRefused([f.message for f in findings])
    return out


# ── The result ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BlockResult:
    id: str
    function: str
    generator: str                     # name@version
    pin: str
    #: block part id → board part id, and block net → board net
    parts: Mapping[str, str]
    nets: Mapping[str, str]
    #: the block as its own generator realised it, claims and proofs included
    circuit: CircuitIR


@dataclass(frozen=True)
class Composition:
    circuit: CircuitIR
    blocks: Tuple[BlockResult, ...]


def project_circuit_id(project: Project) -> str:
    canonical = json.dumps(project.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return str(uuid.uuid5(CIRCUIT_ID_NAMESPACE, "project:" + canonical))


def _block_intent(project: Project, block: Block, pin: str) -> IntentIR:
    constraints = dict(block.constraints)
    if constraints.get("mcu", project.mcu) != project.mcu:
        raise CompositionRefused([f"{block.id}: asks for {constraints['mcu']!r}, but the board is {project.mcu!r}"])
    constraints["mcu"] = project.mcu
    preferences = {**block.preferences, SLOTS[block.function].preference: pin}
    return IntentIR(
        intent_id=str(uuid.uuid5(CIRCUIT_ID_NAMESPACE, f"{project_circuit_id(project)}/{block.id}")),
        requirements={"function": block.function, "targets": dict(block.targets),
                      "constraints": constraints, "preferences": preferences},
        provenance=Provenance(producer=Producer.FORM),
    )


def _prefix(part_id: str) -> str:
    return re.match(r"[A-Za-z]+", part_id).group(0)


def _is_bypass(circuit: CircuitIR, part_id: str, shared: set) -> bool:
    part = next(c for c in circuit.components if c.id == part_id)
    nets = {c.node_id for c in circuit.connections if c.component_id == part_id}
    return part.type == ComponentType.CAPACITOR.value and nets <= shared and len(nets) == 2


def compose(registry: GeneratorRegistry, project: Project) -> Composition:
    """The board for `project`, deterministic for the same project. Raises `CompositionRefused`."""
    target = TARGETS[project.mcu]
    unknown = [f"{b.id}: {b.function!r} is not composable yet — composable blocks are {sorted(SLOTS)}"
               for b in project.blocks if b.function not in SLOTS]
    if unknown:
        raise CompositionRefused(unknown)
    pins = allocate_pins(target, project.blocks)

    realized: List[Tuple[Block, str, CircuitIR]] = []
    reasons: List[str] = []
    for block in project.blocks:
        intent = _block_intent(project, block, pins[block.id])
        dispatch = registry.dispatch(intent)
        if not dispatch.accepted:
            reasons.append(f"{block.id}: {dispatch.refusal_summary()}")
            continue
        try:
            realized.append((block, f"{dispatch.generator.name}@{dispatch.generator.version}",
                             realize(dispatch.generator, intent)))
        except RefusedIntent as exc:
            reasons.append(f"{block.id}: {exc.reason}")
    if reasons:
        raise CompositionRefused(reasons)

    # Shared nets: every block's power and ground nodes. Same board, so same names.
    shared = {n.id for _, _, c in realized for n in c.nodes if n.type in (SignalType.POWER.value, SignalType.GROUND.value)}
    seen: Dict[str, int] = {}
    for _, _, c in realized:
        for n in c.nodes:
            if n.id not in shared:
                seen[n.id] = seen.get(n.id, 0) + 1

    first = realized[0][2]
    mcu = next(c for c in first.components if c.type == ComponentType.MICROCONTROLLER.value)
    components = [mcu.model_copy(update={"justification": f"{target.board} MCU shared by "
                                         f"{len(realized)} blocks — " + "; ".join(
                                             f"{b.id}: " + next(c.justification for c in circuit.components
                                                                if c.type == ComponentType.MICROCONTROLLER.value)
                                             for b, _, circuit in realized)})]
    nodes = {n.id: n for n in first.nodes if n.id in shared}
    connections: List[Connection] = []
    counters: Dict[str, int] = {"U": 1}
    bypass_id: Optional[str] = None
    results: List[BlockResult] = []
    rules: List[str] = []
    expected: Dict[str, float] = {}
    descriptions: List[str] = []
    other_analyses: List[SimulationAnalysis] = []

    for block, tag, circuit in realized:
        nets = {n.id: (n.id if n.id in shared or seen[n.id] == 1 else f"{block.id.upper()}_{n.id}")
                for n in circuit.nodes}
        parts: Dict[str, str] = {}
        bypasses: set = set()
        for part in circuit.components:
            if part.type == ComponentType.MICROCONTROLLER.value:
                if part.part_number != mcu.part_number:
                    raise CompositionRefused([f"{block.id}: built for {part.part_number}, the board is {mcu.part_number}"])
                parts[part.id] = mcu.id
                continue
            if _is_bypass(circuit, part.id, shared):
                bypasses.add(part.id)
                if bypass_id is None:
                    counters["C"] = counters.get("C", 0) + 1
                    bypass_id = f"C{counters['C']}"
                    components.append(part.model_copy(update={"id": bypass_id, "justification": (
                        f"{part.value or ''} bypass across the shared rail at the MCU's supply pin, one for the "
                        f"board: every block's generator places one, and on one board they are the same part. "
                        f"Without it switching noise couples into every line on the board.").strip()}))
                    connections += [c.model_copy(update={"component_id": bypass_id, "node_id": nets[c.node_id]})
                                    for c in circuit.connections if c.component_id == part.id]
                parts[part.id] = bypass_id
                continue
            prefix = _prefix(part.id)
            counters[prefix] = counters.get(prefix, 0) + 1
            parts[part.id] = f"{prefix}{counters[prefix]}"
            components.append(part.model_copy(update={"id": parts[part.id]}))

        for n in circuit.nodes:
            nodes.setdefault(nets[n.id], n.model_copy(update={"id": nets[n.id]}))
        for c in circuit.connections:
            if c.component_id == mcu.id and c.node_id in shared and any(
                    x.component_id == mcu.id and x.pin == c.pin for x in connections):
                continue                               # the MCU's own supply pins, once
            if c.component_id in bypasses:
                continue                               # the one bypass is already wired
            connections.append(c.model_copy(update={"component_id": parts[c.component_id],
                                                    "node_id": nets[c.node_id]}))

        rules += [r for r in circuit.validation_rules if r not in rules]
        if circuit.simulation_spec:
            for a in circuit.simulation_spec.analyses:
                if a.type == "dc_op":
                    descriptions.append(f"{block.id}: {a.description}")
                else:
                    other_analyses.append(a)
            expected.update({nets[k]: v for k, v in circuit.simulation_spec.expected_outputs.items()})
        results.append(BlockResult(id=block.id, function=block.function, generator=tag, pin=pins[block.id],
                                   parts=parts, nets=nets, circuit=circuit))

    analyses = ([SimulationAnalysis(type="dc_op", description="; ".join(descriptions))] if descriptions else []) \
        + other_analyses
    circuit = CircuitIR(
        circuit_id=project_circuit_id(project),
        version=1,
        intent=project.intent or " + ".join(c.intent for _, _, c in realized),
        generator=f"{NAME}@{VERSION}",
        application_class=first.application_class,
        target_mcu=project.mcu,
        components=components,
        nodes=list(nodes.values()),
        connections=connections,
        constraints={"supply_voltage": first.constraints.get("supply_voltage"),
                     "blocks": {b.id: c.constraints for b, _, c in realized}},
        simulation_spec=SimulationSpec(analyses=analyses, expected_outputs=expected) if analyses else None,
        validation_rules=rules,
    )
    board = check_design(circuit)
    if board and not all(holds for holds, _ in board.values()):
        raise CompositionRefused([detail for holds, detail in board.values() if not holds])
    return Composition(circuit=circuit, blocks=tuple(results))
