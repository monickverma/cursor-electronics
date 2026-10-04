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
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


# ── Behaviour (M2) ───────────────────────────────────────────────────────────
#
# A closed vocabulary, compiled into the sketch by a template. A rule reads one
# block's measurement and sets another block's output; nothing else is
# expressible, so nothing else can reach the firmware.

#: What a block can be read for: quantity → (lowest, highest, units) the sensor reports.
READS: Mapping[str, Mapping[str, Tuple[float, float, str]]] = {
    "temperature_humidity_sensor": {"temperature_c": (-40.0, 80.0, "°C"), "humidity_pct": (0.0, 100.0, "%")},
}
#: What a block's output can be set to. `blink` is 2 Hz (a buzzer beeps); `heartbeat` a short flash each second.
SETS: Mapping[str, Tuple[str, ...]] = {
    "led_indicator": ("on", "off", "blink", "heartbeat"),
    "load_switch": ("on", "off", "blink", "heartbeat"),
}


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    block: str
    reads: str
    op: Literal[">", "<", ">=", "<="]
    value: float


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    block: str
    set: str


class Rule(BaseModel):
    """`when` + `then` (+ optional `else`), or `always`. Later rules override earlier ones."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    when: Optional[Condition] = None
    then: Optional[Action] = None
    otherwise: Optional[Action] = Field(default=None, alias="else")
    always: Optional[Action] = None

    @model_validator(mode="after")
    def _shape(self) -> "Rule":
        if self.always is not None:
            if self.when or self.then or self.otherwise:
                raise ValueError("a rule is either `always`, or `when` + `then` (+ `else`) — not both")
        elif self.when is None or self.then is None:
            raise ValueError("a rule needs `when` and `then`, or `always`")
        return self

    def actions(self) -> Tuple[Action, ...]:
        return tuple(a for a in (self.then, self.otherwise, self.always) if a is not None)


class Project(BaseModel):
    """A board and the blocks on it. The board's MCU is the project's, never a block's."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: str = ""                               # the sentence, when there is one
    mcu: str = DEFAULT_TARGET
    #: The rail budget for the whole board, mA (M4); the boards' USB default when absent.
    supply_current_ma: Optional[float] = Field(default=None, gt=0)
    blocks: Tuple[Block, ...]
    behaviour: Tuple[Rule, ...] = ()

    @model_validator(mode="after")
    def _behaviour_names_real_things(self) -> "Project":
        """Every rule reads a quantity its block reports, and sets an output its block has — refused by name."""
        functions = {b.id: b.function for b in self.blocks}
        problems: List[str] = []
        for n, rule in enumerate(self.behaviour, 1):
            if rule.when is not None:
                c = rule.when
                offered = READS.get(functions.get(c.block, ""), {})
                if c.block not in functions:
                    problems.append(f"rule {n} reads block {c.block!r}, which the project does not have")
                elif c.reads not in offered:
                    problems.append(f"rule {n}: block {c.block!r} ({functions[c.block]}) cannot be read for "
                                    f"{c.reads!r}; it offers {sorted(offered) or 'nothing'}")
                else:
                    lo, hi, units = offered[c.reads]
                    if not lo <= c.value <= hi:
                        problems.append(f"rule {n}: {c.value:g} {units} is outside what {c.block!r} reports "
                                        f"({lo:g}–{hi:g} {units}), so the rule could never change")
            for a in rule.actions():
                if a.block not in functions:
                    problems.append(f"rule {n} sets block {a.block!r}, which the project does not have")
                elif a.set not in SETS.get(functions[a.block], ()):
                    offered = SETS.get(functions[a.block], ())
                    problems.append(f"rule {n}: block {a.block!r} ({functions[a.block]}) cannot be set to "
                                    f"{a.set!r}; it takes {list(offered) or 'nothing — it is not an output'}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

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
    default: Any           # Target → the generator's own default pin
    net: str               # the net the generator puts on that pin


def _switch_default(target: Target) -> str:
    from generators.load_switch import default_pin

    return default_pin(target)


#: The block functions that take one MCU pin, and how each generator is told
#: which. A function absent here is not composable yet and is refused by name.
SLOTS: Mapping[str, Slot] = {
    "led_indicator": Slot("gpio_pin", "output", lambda t: t.defaults.get("led"), "LED_CTRL"),
    "temperature_humidity_sensor": Slot("data_pin", "bidirectional", lambda t: t.defaults.get("dht_data"),
                                        "DHT22_DATA"),
    "load_switch": Slot("gpio_pin", "output", _switch_default, "SW_CTRL"),
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
        default = target.pin(slot.default(target))
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
    project: Project


def project_json(project: Project) -> Dict[str, Any]:
    """The project as stored on its circuit (`constraints.project`), `else` spelled as written."""
    return project.model_dump(mode="json", by_alias=True, exclude_none=True)


def project_circuit_id(project: Project) -> str:
    canonical = json.dumps(project_json(project), sort_keys=True, separators=(",", ":"))
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
                     "blocks": {b.id: c.constraints for b, _, c in realized},
                     # Everything the firmware (M2) and the board claims (M4) are rebuilt from.
                     "project": project_json(project)},
        simulation_spec=SimulationSpec(analyses=analyses, expected_outputs=expected) if analyses else None,
        validation_rules=rules,
    )
    board = check_design(circuit)
    if board and not all(holds for holds, _ in board.values()):
        raise CompositionRefused([detail for holds, detail in board.values() if not holds])
    return Composition(circuit=circuit, blocks=tuple(results), project=project)


# ── Board-level claims (M4) ──────────────────────────────────────────────────

def _relabel(text: str, mapping: Mapping[str, str]) -> str:
    """A block's part and net names as the board numbers them, in one pass (R1→R2 and R2→R3 together)."""
    moved = {old: new for old, new in mapping.items() if old != new}
    if not moved or not text:
        return text
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(moved, key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: moved[m.group(1)], text)


def board_coverage(composition: Composition, registry: Optional[GeneratorRegistry] = None) -> Dict[str, Any]:
    """
    The board's `validation_coverage`, in the shape every single design has.

    Every block's own claims and proofs, unchanged in verdict, grade and
    defeaters, relabelled with the board's part and net names and prefixed
    with the block id; and the board's own claims: the shared rail against its
    budget, and the pin rules over the whole assignment. Each block's claims
    hold with the rail held at its nominal voltage (the netlist's ideal
    source), so how far one block's current moves another's rail is a row of
    its own, *not assessed*, never folded into a pass.
    """
    from generators.arduino_parts import DEFAULT_RAIL_BUDGET_MA, mcu_rail_ma
    from generators.protocol import ClaimScope
    from generators.registry import default_registry
    from validation.claims import Claim, Kind, PropertyView, ValidationCoverage, Verdict, graded

    registry = registry or default_registry()
    project, board = composition.project, composition.circuit
    target = TARGETS[project.mcu]
    claims: List[Any] = []
    properties: List[Any] = []
    for b in composition.blocks:
        mapping = {**b.nets, **b.parts}
        coverage = b.circuit.validation_coverage or {}
        for row in coverage.get("claims", ()):
            row = dict(row)
            row["id"] = f"{b.id}.{row['id']}"
            row["claim"] = f"[{b.id}] " + _relabel(row["claim"], mapping)
            if row.get("detail"):
                row["detail"] = _relabel(row["detail"], mapping)
            claims.append(Claim.model_validate(row))
        for view in coverage.get("properties", ()):
            view = dict(view)
            view["id"] = f"{b.id}.{view['id']}"
            view["english"] = f"[{b.id}] " + _relabel(view["english"], mapping)
            properties.append(PropertyView.model_validate(view))

    # The shared rail: the MCU's model once, plus each block's own share of its port's worst case.
    supply = board.constraints.get("supply_voltage") or target.logic_v
    mcu_ma = mcu_rail_ma(supply, target.mcu_part)
    budget = project.supply_current_ma or DEFAULT_RAIL_BUDGET_MA
    shares: Dict[str, float] = {}
    for b in composition.blocks:
        block = next(x for x in project.blocks if x.id == b.id)
        decision = registry.by_name(b.generator.split("@")[0]).envelope(_block_intent(project, block, b.pin))
        port = next(p for p in decision.ports if p.name == "VCC")
        shares[b.id] = port.current_draw_a.hi * 1000 - mcu_ma
    total = mcu_ma + sum(shares.values())
    claims.append(graded(
        "board.rail_current",
        f"the shared {target.rail_node} rail draws at most {total:.4g} mA of its {budget:g} mA budget",
        total <= budget, "sound_enclosure",
        ClaimScope(parameters="tolerance_box", model=f"mna_ideal+mcu_as_{supply / mcu_ma * 1000:g}R",
                   measures=(f"i(V_{target.rail_node})",)),
        detail=f"MCU model {mcu_ma:.0f} mA + " + " + ".join(f"{k} ≤ {v:.3g} mA" for k, v in shares.items()),
        defeaters=("D1", "D2"), covers=("power_supply_adequate",)))
    pins = check_design(board) or {}
    claims.append(graded(
        "board.pin_rules",
        "every pin on the board is valid, used once, and off the strapping and console pins: "
        + ", ".join(f"{b.id} on {b.pin}" for b in composition.blocks),
        all(holds for holds, _ in pins.values()), "exact_graph_check",
        ClaimScope(parameters="nominal", model="design_graph"), defeaters=(),
        detail="; ".join(detail for _, detail in pins.values())))
    claims.append(Claim(
        id="board.rail_interaction", kind=Kind.ANALYTIC, verdict=Verdict.NOT_ASSESSED, grade="G7",
        critical=False,
        claim=f"one block's load current moving the {target.rail_node} rail that another block's claims assume",
        detail=f"every block's claims hold with the rail held at {supply:g} V (an ideal source); the regulator's "
               f"and the wiring's resistance are not modelled, so droop under the {total:.3g} mA total is "
               f"not assessed"))
    coverage = ValidationCoverage.summarise(claims, properties=properties).model_dump(mode="json")
    # What the UI shows of a board (M4): its blocks, where each sits, and what it is told to do.
    coverage["blocks"] = [{"id": b.id, "function": b.function, "generator": b.generator, "pin": b.pin,
                           "parts": sorted(set(b.parts.values()) - {"U1"})} for b in composition.blocks]
    coverage["behaviour"] = [_rule_text(r, project) for r in project.behaviour]
    return coverage


def _rule_text(rule: Rule, project: Project) -> str:
    if rule.always is not None:
        return f"always: {rule.always.block} {rule.always.set}"
    c = rule.when
    function = next(b.function for b in project.blocks if b.id == c.block)
    text = f"when {c.block} {c.reads} {c.op} {c.value:g} {READS[function][c.reads][2]}: {rule.then.block} {rule.then.set}"
    return text + (f", else {rule.otherwise.block} {rule.otherwise.set}" if rule.otherwise else "")


def project_from_intent(intent: IntentIR, sentence: str = "") -> Project:
    """The Project an IntentIR with `function: project` asks for (M4, the front door)."""
    req = intent.requirements
    constraints = req.get("constraints") or {}
    extra = {"supply_current_ma": constraints["supply_current_ma"]} if "supply_current_ma" in constraints else {}
    return Project.model_validate({
        "intent": sentence, "mcu": constraints.get("mcu", DEFAULT_TARGET), **extra,
        "blocks": req.get("blocks") or [], "behaviour": req.get("behaviour") or [],
    })


def compose_intent(registry: GeneratorRegistry, intent: IntentIR, sentence: str = "") -> Composition:
    """
    `compose()` for a stored design: the circuit stamped from the intent's
    lineage, as `realize()` stamps a single design, and carrying the board's
    coverage. Raises `CompositionRefused`, a malformed project included, by name.
    """
    from generators.realize import design_circuit_id

    try:
        project = project_from_intent(intent, sentence)
    except ValueError as exc:
        raise CompositionRefused([str(exc)]) from exc
    composed = compose(registry, project)
    circuit = composed.circuit.model_copy(update={"circuit_id": design_circuit_id(intent),
                                                  "version": intent.revision})
    stamped = Composition(circuit=circuit, blocks=composed.blocks, project=project)
    coverage = board_coverage(stamped, registry)
    return Composition(circuit=circuit.model_copy(update={"validation_coverage": coverage}),
                       blocks=composed.blocks, project=project)
