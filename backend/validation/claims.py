"""
Claim objects and `validation_coverage`. EVIDENCE_CLASSES.md §3–§5; Stage 3.

Every design carries a statement of which properties hold, over which
parameter ranges, under which model — or says plainly that it was not checked.
A claim has four independent fields and a verdict:

- `kind`   — analytic (true of the model by mathematics), empirical (measured),
             or projected (not yet an artifact)
- `grade`  — G0 (proof-checked) … G7 (asserted). **Derived from `method`**
             through one table, never typed per claim: a hand-assigned G1 is a G7.
- `scope`  — what it quantifies over, including the **model**
- `defeaters` — recorded doubts, by ID from `validation/defeaters.py`

**A claim with an open defeater is defeasible**, and its verdict says so:
`holds_defeasible`, never plain `holds`. The model validator enforces it.

**Nothing is averaged** (§5). `ValidationCoverage` reports three numbers side by
side — `coverage_le_g2`, `grade_floor`, `open_defeaters` — and never fuses them.

**What was not checked is printed** (§4, and amendment X8). Every
`ValidationRule` is accounted for on every design: run and graded; not
applicable, with the reason; covered by a generator's physics claim; declared
out of scope; or **not assessed**, as a visible, critical row graded G7. The
set is the catalogue minus what was actually checked — never the rules that
happened to run — so a design that checks less cannot look better verified.

**X6 is derived, never remembered — and since [2026-09-24], per claim.** A
claim cites D2 only where the real MCU can reach it: its quantity depends on
an MCU model element (`mcu_as_<R>R`, `mcu_pin_thevenin`; decided by symbolic
nodal analysis, `proof/dependence.py`), it measures a node an unmodelled MCU
pin sits on (`mcu_pin_load`), or it takes as given a node state an MCU pin sets
(`mcu_pin_state`) — or, where a resistor of the design holds that node to a
rail, one the pin reaches only through its load (`mcu_pin_load`, since
[2026-09-25]). What a claim measures comes from its declaration
(`ClaimScope.measures`) or from the proof that re-derives it. A claim that
declares nothing keeps the netlist-wide rule — every MCU model in the netlist,
and D2 — so a generator can narrow D2 only by saying what it measures, never
by forgetting to.

**Stage 4: proofs count once a person has signed them.** A generator's
`properties(intent)` are proved from the design's own netlist
(`proof/prover.py`) and appear as `proof.<id>` rows, each with the English
sentence that was proved. Until the property set is signed — its hash in
`IntentIR.signed_off.properties_hash` — those rows are shown and do not move
the floor. Signed, they are critical; the design stops carrying D5; and a
Stage 3 claim a signed proof re-derives at an equal or better grade is kept
visible but no longer critical. A refuted proof is critical either way: a
certified counterexample is never advisory.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from core.ir_schema import CircuitIR, ComponentType, SignalType, ValidationRule
from core.ir_validator import validate_ir
from generators.netlist.models import (
    MODEL_LED,
    MODEL_MCU_PIN,
    MODEL_MCU_PIN_LOAD,
    MODEL_MCU_PIN_STATE,
    mcu_supply_model,
)
from generators.protocol import ClaimScope
from validation.defeaters import REGISTER

GRADES = ("G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7")

#: The one place a grade comes from. EVIDENCE_CLASSES §3.2.
METHOD_GRADE: Dict[str, str] = {
    "proof_checked": "G0",
    "z3_unsat": "G1",
    "monotone_corners": "G1",       # exact when monotone in every argument
    "closed_form": "G1",            # exact at the declared (nominal) scope
    "exact_graph_check": "G1",      # exhaustive over the design as written
    "sound_enclosure": "G2",
    "certificate": "G3",
    "bounded_model_check": "G4",
    "ngspice_nominal": "G5",
    "sampled": "G6",
    "asserted": "G7",
}

#: v2 §3's declared out-of-scope list, printed on every design.
OUT_OF_SCOPE: Tuple[Tuple[str, str], ...] = (
    ("rf_gt_100mhz", "RF above 100 MHz"),
    ("emi_emc", "EMI / EMC"),
    ("thermal", "thermal behaviour, including operating temperature range"),
    ("manufacturing_yield", "manufacturing yield"),
    ("switching_converters", "switching converters"),
)

#: Rules with an implementation. Each maps to how it is checked and the extra
#: defeaters its check depends on.
_IMPLEMENTED: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    ValidationRule.NO_FLOATING_NODES.value: ("exact_graph_check", ()),
    ValidationRule.VOLTAGE_RATINGS_OK.value: ("exact_graph_check", ("D7",)),
    ValidationRule.I2C_PULLUPS_PRESENT.value: ("exact_graph_check", ()),
    ValidationRule.RS485_TERMINATION_PRESENT.value: ("exact_graph_check", ()),
    ValidationRule.RS485_BIAS_RESISTORS.value: ("exact_graph_check", ()),
    ValidationRule.PWM_PIN_VALID.value: ("exact_graph_check", ("D7",)),
    # Stage 5: against the board's pin table, which is datasheet data.
    ValidationRule.PIN_ASSIGNMENT_VALID.value: ("exact_graph_check", ("D7",)),
    ValidationRule.PERIPHERAL_CONFLICT_FREE.value: ("exact_graph_check", ("D7",)),
    ValidationRule.STRAPPING_PINS_SAFE.value: ("exact_graph_check", ("D7",)),
}

#: Rules declared out of scope rather than unimplemented.
_OUT_OF_SCOPE_RULES = {ValidationRule.OPERATING_TEMP_RANGE.value: "thermal"}

#: Everything else in the catalogue has no implementation. A generator must
#: account for each of these — covered by one of its claims, or not applicable
#: with a reason — or it is printed as not assessed.
UNIMPLEMENTED_RULES: Tuple[str, ...] = tuple(
    r.value for r in ValidationRule
    if r.value not in _IMPLEMENTED and r.value not in _OUT_OF_SCOPE_RULES
)


class Kind(str, Enum):
    ANALYTIC = "analytic"
    EMPIRICAL = "empirical"
    PROJECTED = "projected"


class Verdict(str, Enum):
    HOLDS = "holds"
    HOLDS_DEFEASIBLE = "holds_defeasible"
    FAILS = "fails"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"
    OUT_OF_SCOPE = "out_of_scope"


class Claim(BaseModel):
    """One row of EVIDENCE_CLASSES Table A."""

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    id: str
    claim: str
    kind: Kind
    verdict: Verdict
    method: Optional[str] = None
    grade: Optional[str] = None
    scope: Optional[ClaimScope] = None
    defeaters: Tuple[str, ...] = ()
    #: Whether the weakest-link floor looks at this row. A design is as proven
    #: as its worst *critical* claim.
    critical: bool = True
    #: The numbers behind the verdict, in words.
    detail: Optional[str] = None
    #: ValidationRule ids this claim discharges (X8).
    covers: Tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "Claim":
        unknown = [d for d in self.defeaters if d not in REGISTER]
        if unknown:
            raise ValueError(f"claim {self.id} cites unregistered defeaters {unknown}")
        if self.method is not None:
            expected = METHOD_GRADE.get(self.method)
            if expected is None:
                raise ValueError(f"claim {self.id}: unknown method {self.method!r}")
            if self.grade != expected:
                raise ValueError(
                    f"claim {self.id}: grade {self.grade} does not follow from method "
                    f"{self.method!r} ({expected}) — grades are derived, never typed"
                )
        if self.verdict in (Verdict.HOLDS.value, Verdict.HOLDS_DEFEASIBLE.value, Verdict.FAILS.value):
            if self.method is None or self.scope is None:
                raise ValueError(f"claim {self.id} has a verdict but no method or scope")
        has_open = any(REGISTER[d].is_open for d in self.defeaters)
        if self.verdict == Verdict.HOLDS.value and has_open:
            raise ValueError(
                f"claim {self.id} cites open defeaters {list(self.defeaters)} and so is "
                f"defeasible — its verdict must be holds_defeasible, not holds"
            )
        if self.verdict == Verdict.NOT_ASSESSED.value and self.grade != "G7":
            raise ValueError(f"claim {self.id}: a not-assessed row is G7 (EVIDENCE_CLASSES Table A)")
        return self


def graded(
    id: str,
    claim: str,
    holds: bool,
    method: str,
    scope: ClaimScope,
    defeaters: Iterable[str] = ("D1",),
    detail: Optional[str] = None,
    kind: Kind = Kind.ANALYTIC,
    critical: bool = True,
    covers: Iterable[str] = (),
) -> Claim:
    """A checked claim, with its grade looked up and its verdict made honest."""
    cited = tuple(dict.fromkeys(defeaters))
    if holds:
        # `.get`, not `[]`: an unregistered ID must reach Claim's validator and
        # be refused by name, not surface here as a bare KeyError.
        open_cited = any(REGISTER[d].is_open for d in cited if d in REGISTER)
        verdict = Verdict.HOLDS_DEFEASIBLE if open_cited else Verdict.HOLDS
    else:
        verdict = Verdict.FAILS
    return Claim(
        id=id, claim=claim, kind=kind, verdict=verdict, method=method,
        grade=METHOD_GRADE[method], scope=scope, defeaters=cited,
        critical=critical, detail=detail, covers=tuple(covers),
    )


# ── Coverage ─────────────────────────────────────────────────────────────────

class PropertyView(BaseModel):
    """One Stage 4 property as a person sees it before signing: the sentence, and its fate."""

    model_config = ConfigDict(frozen=True)

    id: str
    english: str
    hash: str
    status: str                    # proven | refuted | unknown
    method: str
    grade: Optional[str] = None
    re_derives: Optional[str] = None
    counterexample: Optional[Dict[str, str]] = None


class ValidationCoverage(BaseModel):
    """EVIDENCE_CLASSES §5, revised `validation_coverage`. Three numbers, never fused."""

    model_config = ConfigDict(frozen=True)

    claims: Tuple[Claim, ...]
    coverage_le_g2: float
    grade_floor: Optional[str]
    open_defeaters: Tuple[str, ...]
    not_assessed: Tuple[str, ...]
    out_of_scope: Tuple[str, ...]
    #: Stage 4. The properties proved from the netlist, the hash of the set —
    #: what a sign-off must quote — and whether that set is signed.
    properties: Tuple[PropertyView, ...] = ()
    properties_hash: Optional[str] = None
    properties_signed: bool = False
    signed_by: Optional[str] = None

    @classmethod
    def summarise(
        cls,
        claims: Sequence[Claim],
        properties: Sequence[PropertyView] = (),
        properties_hash: Optional[str] = None,
        properties_signed: bool = False,
        signed_by: Optional[str] = None,
    ) -> "ValidationCoverage":
        critical = [
            c for c in claims
            if c.critical and c.verdict not in (Verdict.NOT_APPLICABLE.value, Verdict.OUT_OF_SCOPE.value)
        ]
        graded_rows = [c for c in critical if c.grade is not None]
        floor = max((c.grade for c in graded_rows), key=GRADES.index, default=None)
        good = [c for c in critical if c.grade is not None and GRADES.index(c.grade) <= 2]
        cited = {d for c in claims for d in c.defeaters if REGISTER[d].is_open}
        return cls(
            claims=tuple(claims),
            coverage_le_g2=round(len(good) / len(critical), 4) if critical else 0.0,
            grade_floor=floor,
            open_defeaters=tuple(sorted(cited, key=lambda d: int(d[1:]))),
            not_assessed=tuple(c.id for c in claims if c.verdict == Verdict.NOT_ASSESSED.value),
            out_of_scope=tuple(c.id for c in claims if c.verdict == Verdict.OUT_OF_SCOPE.value),
            properties=tuple(properties),
            properties_hash=properties_hash,
            properties_signed=properties_signed,
            signed_by=signed_by,
        )

    @property
    def failures(self) -> Tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.verdict == Verdict.FAILS.value)


# ── X6: models derived from the netlist ──────────────────────────────────────

def _netlist_text(circuit: CircuitIR) -> str:
    from generators.netlist.spice import SpiceNetlistGenerator

    return SpiceNetlistGenerator().generate(circuit)


def netlist_models(circuit: CircuitIR, netlist: Optional[str] = None) -> Tuple[str, ...]:
    """
    Every MCU model the design's own netlist uses, read from the netlist text.
    The X6 rule, and the fallback for a claim that does not say what it measures.
    """
    netlist = _netlist_text(circuit) if netlist is None else netlist
    models = []
    for line in netlist.splitlines():
        if line.startswith("R_MCU_"):
            # Named from the value the netlist carries: `mcu_as_100R` on the Uno.
            model = mcu_supply_model(float(line.split()[3]))
            if model not in models:
                models.append(model)
    if "\nR_PIN_" in netlist:
        models.append(MODEL_MCU_PIN)
    return tuple(models)


def mcu_signal_nodes(circuit: CircuitIR) -> frozenset:
    """Nodes (lower case) an MCU signal pin is wired to — not its supply or ground pins."""
    mcus = {c.id for c in circuit.components if c.type == ComponentType.MICROCONTROLLER}
    kinds = {n.id: getattr(n.type, "value", n.type) for n in circuit.nodes}
    return frozenset(
        conn.node_id.lower() for conn in circuit.connections
        if conn.component_id in mcus and kinds.get(conn.node_id) not in (
            SignalType.POWER.value, SignalType.GROUND.value)
    )


def _pin_modelled(netlist: str) -> frozenset:
    """Nodes whose MCU pin the netlist models as a Thevenin source (`R_PIN_<node>`)."""
    return frozenset(line.split()[0][len("R_PIN_"):].lower()
                     for line in netlist.splitlines() if line.startswith("R_PIN_"))


#: Elements the netlist adds that are not parts of the design: the floating-node
#: tie-downs, the MCU and transceiver supply loads, the Thevenin pin model.
_NOT_DESIGN_PARTS = ("R_TIE_", "R_PIN_", "R_MCU_", "R_LOAD_")


def held_to_rail(circuit: CircuitIR, netlist: str) -> frozenset:
    """
    Nodes (lower case) a resistor of the design ties to ground or a supply
    rail — a pull-up or pull-down. Such a node keeps its state while the MCU
    pin on it is high-impedance, so the pin reaches it only through its load.
    """
    kinds = (SignalType.POWER.value, SignalType.GROUND.value)
    rails = {"0", "gnd"} | {n.id.lower() for n in circuit.nodes if getattr(n.type, "value", n.type) in kinds}
    held = set()
    for line in netlist.splitlines():
        fields = line.split()
        name = fields[0].upper() if fields else ""
        if len(fields) < 4 or not name.startswith("R_") or name.startswith(_NOT_DESIGN_PARTS):
            continue
        a, b = fields[1].lower(), fields[2].lower()
        if (a in rails) != (b in rails):
            held.add(b if a in rails else a)
    return frozenset(held)


Measure = Tuple[str, Tuple[str, ...]]      # (quantity, test-bench lines)


def derive_mcu_models(
    circuit: CircuitIR, netlist: str, measures: Sequence[Measure], assumes: Sequence[str] = ()
) -> Tuple[str, ...]:
    """
    The MCU models a claim rests on — empty if the real MCU cannot reach it.
    `brain/decisions.md` [2026-09-24] D1, D2, D7, D2's three routes:

    1. the quantity depends on an MCU model element (exact, symbolic);
    2. a measured node carries an MCU signal pin the netlist does not model;
    3. an assumed node is one an MCU pin is wired to: `mcu_pin_state` if
       nothing else holds it, `mcu_pin_load` if a resistor of the design holds
       it to a rail — the pin then reaches it only through its leakage
       ([2026-09-25], the RS-485 DE/RE pull-down). D2 stays either way.

    Raises `KeyError` / `ValueError` when a measure names something the
    netlist does not have; `assess` then falls back to the netlist-wide rule.
    """
    from proof.dependence import mcu_elements_reached, measured_nodes
    from proof.netlist import parse

    parsed = parse(netlist)
    models: List[str] = []

    def add(model: str) -> None:
        if model not in models:
            models.append(model)

    measured: set = set()
    for quantity, bench in measures:
        for name in mcu_elements_reached(netlist, quantity, bench):
            if name.upper().startswith("R_MCU_"):
                add(mcu_supply_model(float(parsed.element(name).value)))
            else:
                add(MODEL_MCU_PIN)
        measured |= measured_nodes(netlist, quantity, bench)
    signal = mcu_signal_nodes(circuit)
    if measured & (signal - _pin_modelled(netlist)):
        add(MODEL_MCU_PIN_LOAD)
    assumed = {a.lower() for a in assumes} & signal
    if assumed:
        held = held_to_rail(circuit, netlist)
        if assumed & held:
            add(MODEL_MCU_PIN_LOAD)
        if assumed - held:
            add(MODEL_MCU_PIN_STATE)
    return tuple(models)


def _is_mcu_model(name: str) -> bool:
    return name.startswith("mcu_")


def _with_models(
    claim: Claim, models: Sequence[str], extra_defeaters: Sequence[str], derived: bool = False,
    measures: Sequence[str] = (),
) -> Claim:
    """
    Set a behavioural claim's MCU models and D2, and add the extra defeaters.

    `derived`: `models` were derived for this claim from `measures`, so they
    replace whatever MCU models and D2 the generator wrote by hand, and the
    measures are recorded on the scope — a claim a proof re-derives says so.
    Otherwise they are the netlist-wide fallback, added to what is there — X6
    as it always was. A structural claim (`design_graph`) reads no electrical
    model at all.
    """
    if claim.scope is None:
        return claim
    parts = claim.scope.model.split("+")
    defeaters = list(claim.defeaters)
    scope_update: Dict[str, Any] = {}
    if claim.scope.model == "design_graph":
        models, derived = (), True
    elif derived and measures:
        scope_update["measures"] = tuple(measures)
    if derived:
        parts = [p for p in parts if not _is_mcu_model(p)]
        if not models:
            defeaters = [d for d in defeaters if d != "D2"]
    for model in models:
        if model not in parts:
            parts.append(model)
    for d in list(extra_defeaters) + (["D2"] if models else []):
        if d not in defeaters:
            defeaters.append(d)
    data = claim.model_dump()
    data["scope"] = claim.scope.model_copy(update={"model": "+".join(parts), **scope_update})
    data["defeaters"] = tuple(defeaters)
    if data["verdict"] in (Verdict.HOLDS.value, Verdict.HOLDS_DEFEASIBLE.value):
        open_now = any(REGISTER[d].is_open for d in defeaters)
        data["verdict"] = (Verdict.HOLDS_DEFEASIBLE if open_now else Verdict.HOLDS).value
    return Claim.model_validate(data)


# ── D7: the part figures a claim reads ───────────────────────────────────────

_PIN_RULES = (ValidationRule.PIN_ASSIGNMENT_VALID.value, ValidationRule.PERIPHERAL_CONFLICT_FREE.value,
              ValidationRule.STRAPPING_PINS_SAFE.value)


def _with_figures(claim: Claim, figures: Optional[Sequence[str]]) -> Claim:
    """
    D7 derived from the figures the claim reads (`data/figures.py`): cited
    while any is untrusted, dropped once all are. No figures — undeclared, or
    one without a record — leaves the claim's own D7 citation as it was.
    """
    if not figures or claim.scope is None:
        return claim
    from data.figures import FIGURES, untrusted

    if any(f not in FIGURES for f in figures):
        return claim
    doubtful = bool(untrusted(figures))
    defeaters = list(claim.defeaters)
    if doubtful and "D7" not in defeaters:
        defeaters.append("D7")
    elif not doubtful:
        defeaters = [d for d in defeaters if d != "D7"]
    data = claim.model_dump()
    data["scope"] = claim.scope.model_copy(update={"figures": tuple(dict.fromkeys(figures))})
    data["defeaters"] = tuple(defeaters)
    if data["verdict"] in (Verdict.HOLDS.value, Verdict.HOLDS_DEFEASIBLE.value):
        open_now = any(REGISTER[d].is_open for d in defeaters)
        data["verdict"] = (Verdict.HOLDS_DEFEASIBLE if open_now else Verdict.HOLDS).value
    return Claim.model_validate(data)


def _rating_figures(circuit: CircuitIR) -> Optional[Tuple[str, ...]]:
    """The rating each part's `supply_voltage_max` stands for. None if any has no record."""
    from data.figures import FIGURES
    from data.parts import passive_figures

    out = []
    for comp in circuit.components:
        if comp.supply_voltage_max is None:
            continue
        passive = passive_figures(comp.part_number)
        figure = f"{passive[0]}/voltage_max" if passive else f"{comp.part_number}/supply_voltage_max"
        if figure not in FIGURES:
            return None
        out.append(figure)
    return tuple(out) or None


def _pin_figures(circuit: CircuitIR) -> Optional[Tuple[str, ...]]:
    """The board's pin rows the design uses, and its console UART. None if a pin is not in the table."""
    from validation.pin_rules import assignments_of, design_target

    target = design_target(circuit)
    if target is None:
        return None
    out = []
    for assignment in assignments_of(circuit):
        pin = target.pin(assignment.pin)
        if pin is None:
            return None
        out.append(f"board:{target.id}/{pin.name}")
    return tuple(out) + (f"board:{target.id}/console_uart",)


# ── X8: the rule catalogue as claims ─────────────────────────────────────────

_RULE_SENTENCES = {
    "no_floating_nodes": "every node has at least two connections, counting declared ports",
    "voltage_ratings_ok": "every part's rated supply voltage covers the circuit's supply",
    "i2c_pullups_present": "every I2C line has a pull-up to a supply rail",
    "rs485_termination_present": "the RS-485 A/B pair is terminated with 100–150 ohm",
    "rs485_bias_resistors": "RS-485 A is biased to VCC and B to GND",
    "pwm_pin_valid": "every PWM signal uses an Arduino Uno PWM-capable pin",
    "pin_assignment_valid": "every MCU pin exists on the board, is not reserved, and can do what it is wired for",
    "peripheral_conflict_free": "no MCU pin carries two nets, and each hardware UART has one user and is not the console",
    "strapping_pins_safe": "nothing external is wired to a strapping pin",
}


def _rule_claims(circuit: CircuitIR, ports: Sequence[str]) -> List[Claim]:
    from validation.rule_engine import HardwareRuleEngine

    structural = validate_ir(circuit)
    engine = HardwareRuleEngine()
    node_types = {n.type for n in circuit.nodes}
    scope = ClaimScope(parameters="nominal", model="design_graph")
    rows: List[Claim] = []

    rating_figures = _rating_figures(circuit)
    pin_figures = _pin_figures(circuit)

    def row(rule: str, holds: bool, applicable: bool, detail: Optional[str]) -> None:
        method, extra = _IMPLEMENTED[rule]
        if not applicable:
            rows.append(Claim(
                id=f"rule.{rule}", claim=_RULE_SENTENCES[rule], kind=Kind.ANALYTIC,
                verdict=Verdict.NOT_APPLICABLE, critical=False, detail=detail,
            ))
            return
        claim = graded(f"rule.{rule}", _RULE_SENTENCES[rule], holds, method, scope,
                       defeaters=extra, detail=detail)
        figures = {"voltage_ratings_ok": rating_figures}.get(rule, pin_figures if rule in _PIN_RULES else None)
        rows.append(_with_figures(claim, figures) if figures else claim)

    # no_floating_nodes — a declared port is connected by definition: it is
    # where the next stage attaches. Without this every RC filter's IN fails.
    counts: Dict[str, int] = {}
    for conn in circuit.connections:
        counts[conn.node_id] = counts.get(conn.node_id, 0) + 1
    floating = sorted(
        n.id for n in circuit.nodes
        if counts.get(n.id, 0) + (1 if n.id in ports else 0) < 2
    )
    row("no_floating_nodes", not floating, True,
        f"floating: {floating}" if floating else "no node below two connections")

    ratings = [e for e in structural.errors if e.field_path.endswith(".supply_voltage_max")]
    row("voltage_ratings_ok", not ratings, True,
        "; ".join(e.message for e in ratings) or "all ratings at or above the supply")

    i2c = {SignalType.I2C_SDA.value, SignalType.I2C_SCL.value} & {getattr(t, "value", t) for t in node_types}
    i2c_errors = [e for e in structural.errors if "I2C" in e.message]
    row("i2c_pullups_present", not i2c_errors, bool(i2c),
        "; ".join(e.message for e in i2c_errors) or ("pull-ups present" if i2c else "no I2C lines"))

    has_rs485 = {"rs485_a", "rs485_b"} <= {getattr(t, "value", t) for t in node_types}
    for rule, handler in (
        ("rs485_termination_present", engine._check_rs485_termination),
        ("rs485_bias_resistors", engine._check_rs485_bias_resistors),
    ):
        result = type(structural)()
        handler(circuit, result)
        row(rule, not result.errors, has_rs485,
            "; ".join(e.message for e in result.errors + result.warnings)
            or ("present" if has_rs485 else "no RS-485 lines"))

    from validation.pin_rules import RULES as PIN_RULES, check_design

    pins = check_design(circuit)
    for rule in PIN_RULES:
        if pins is None:
            row(rule, True, False, "no microcontroller on this design")
        else:
            holds, detail = pins[rule]
            row(rule, holds, True, detail)

    has_pwm = SignalType.PWM.value in {getattr(t, "value", t) for t in node_types}
    result = type(structural)()
    engine._check_pwm_pin_valid(circuit, result)
    row("pwm_pin_valid", not result.errors, has_pwm and circuit.target_mcu == "arduino_uno",
        "; ".join(e.message for e in result.errors) or ("valid" if has_pwm else "no PWM signals"))
    return rows


def _accounting_rows(
    generator_claims: Sequence[Claim], not_applicable: Mapping[str, str]
) -> List[Claim]:
    covered = {rule: c.id for c in generator_claims for rule in c.covers}
    rows = []
    for rule in UNIMPLEMENTED_RULES:
        sentence = f"rule {rule} (no rule-engine implementation)"
        if rule in covered:
            rows.append(Claim(
                id=f"rule.{rule}", claim=sentence, kind=Kind.ANALYTIC,
                verdict=Verdict.NOT_APPLICABLE, critical=False,
                detail=f"covered by claim {covered[rule]}",
            ))
        elif rule in not_applicable:
            rows.append(Claim(
                id=f"rule.{rule}", claim=sentence, kind=Kind.ANALYTIC,
                verdict=Verdict.NOT_APPLICABLE, critical=False, detail=not_applicable[rule],
            ))
        else:
            rows.append(Claim(
                id=f"rule.{rule}", claim=sentence, kind=Kind.ANALYTIC,
                verdict=Verdict.NOT_ASSESSED, grade="G7",
                detail="not implemented, and no claim on this design discharges it",
            ))
    for rule, area in _OUT_OF_SCOPE_RULES.items():
        rows.append(Claim(
            id=f"rule.{rule}", claim=f"rule {rule}", kind=Kind.ANALYTIC,
            verdict=Verdict.OUT_OF_SCOPE, critical=False, detail=f"declared out of scope: {area}",
        ))
    for key, text in OUT_OF_SCOPE:
        rows.append(Claim(
            id=f"scope.{key}", claim=text, kind=Kind.ANALYTIC,
            verdict=Verdict.OUT_OF_SCOPE, critical=False, detail="declared out of scope (v2 §3)",
        ))
    return rows


# ── Stage 4: proofs ──────────────────────────────────────────────────────────

class _Proved(NamedTuple):
    spec: Any
    statement: Any                 # None when the property could not be compiled
    result: Any
    error: Optional[str] = None


def prove_properties(generator: Any, intent: Any, circuit: CircuitIR,
                     netlist: Optional[str] = None) -> List[_Proved]:
    """
    Every property the generator declares, proved from this design's netlist.
    A property the prover cannot compile — a netlist line it cannot read, a
    node that is not there — becomes a visible not-assessed row, never a
    failed generation and never a silent omission.
    """
    produce = getattr(generator, "properties", None)
    if not callable(produce):
        return []
    from proof.prover import check

    netlist = _netlist_text(circuit) if netlist is None else netlist
    out: List[_Proved] = []
    for spec in produce(intent):
        try:
            statement, _, result = check(circuit, spec, netlist)
        except (ValueError, KeyError, ArithmeticError) as exc:
            out.append(_Proved(spec, None, None, f"{type(exc).__name__}: {exc}"))
            continue
        out.append(_Proved(spec, statement, result))
    return out


def properties_hash(proved: Sequence[_Proved]) -> Optional[str]:
    """The hash one sign-off covers. None — unsignable — if any property failed to compile."""
    from proof.properties import set_hash

    if not proved or any(p.statement is None for p in proved):
        return None
    return set_hash([p.statement for p in proved])


def _proof_claim(p: _Proved, signed: bool, extra: Sequence[str], mcu_models: Sequence[str] = (),
                 assumes: Sequence[str] = ()) -> Claim:
    """
    One proof as a claim row. `mcu_models` are derived for this property
    (`derive_mcu_models`), not read off the netlist as a whole: the statement's
    own `mcu_models` lists every MCU element present, reachable or not.
    """
    if p.statement is None:
        return Claim(id=f"proof.{p.spec.id}", claim=_uncompiled_sentence(p.spec), kind=Kind.ANALYTIC,
                     verdict=Verdict.NOT_ASSESSED, grade="G7", critical=False,
                     detail=f"the prover could not compile this property ({p.error}); nothing about it "
                            f"is proved, and the property set cannot be signed")
    statement, result = p.statement, p.result
    quantity = statement.spec.quantity
    diode = quantity.startswith(("diode_current", "series_power"))
    model = "+".join(["netlist_mna"] + list(mcu_models) + ([MODEL_LED] if diode else []))
    scope = ClaimScope(parameters="tolerance_box", horizon="steady_state", model=model,
                       measures=(quantity,), assumes=tuple(assumes))
    defeaters = ["D1"]
    if mcu_models:
        defeaters.append("D2")
    if statement.datasheet:
        defeaters.append("D7")
    if statement.bracketed:
        defeaters.append("D8")      # eliminated: cited to show where it was answered
    defeaters += [d for d in extra if d not in defeaters]
    standing = "signed off" if signed else "awaiting sign-off: shown, not counted"
    if result.status == "unknown":
        return Claim(id=f"proof.{p.spec.id}", claim=statement.english, kind=Kind.ANALYTIC,
                     verdict=Verdict.NOT_ASSESSED, grade="G7", critical=signed,
                     detail=f"{result.detail} ({standing})")
    detail = result.detail
    if result.counterexample:
        detail += " at " + ", ".join(f"{k}={v}" for k, v in sorted(result.counterexample.items()))
    return graded(
        f"proof.{p.spec.id}", statement.english, result.status == "proven", result.method, scope,
        defeaters=defeaters, detail=f"{detail} ({standing})",
        # A certified counterexample is never advisory, signed or not.
        critical=signed or result.status == "refuted",
    )


def _uncompiled_sentence(spec: Any) -> str:
    bounds = {"le": f"at most {spec.hi}", "ge": f"at least {spec.lo}",
              "within": f"between {spec.lo} and {spec.hi}"}[spec.relation]
    return f"{spec.label} ({spec.quantity}) stays {bounds} {spec.units}"


def _supersede(physics: List[Claim], proved: Sequence[_Proved], proofs: Sequence[Claim]) -> List[Claim]:
    """Stage 3 claims a signed proof re-derives at an equal or better grade stop being critical."""
    by_target: Dict[str, List[Claim]] = {}
    for p, claim in zip(proved, proofs):
        if p.spec.re_derives:
            by_target.setdefault(p.spec.re_derives, []).append(claim)
    out = []
    for claim in physics:
        proofs_for = by_target.get(claim.id, [])
        if (proofs_for and claim.critical and claim.grade is not None
                and all(c.critical and c.verdict in (Verdict.HOLDS.value, Verdict.HOLDS_DEFEASIBLE.value)
                        for c in proofs_for)
                and max(GRADES.index(c.grade) for c in proofs_for) <= GRADES.index(claim.grade)):
            data = claim.model_dump()
            data["critical"] = False
            data["detail"] = ((claim.detail + "; ") if claim.detail else "") + \
                "superseded by " + ", ".join(c.id for c in proofs_for) + " (signed proofs)"
            claim = Claim.model_validate(data)
        out.append(claim)
    return out


# ── D1: bench evidence ───────────────────────────────────────────────────────

def _with_bench(generator: Any, circuit: CircuitIR, netlist: str, proved: Sequence[_Proved],
                physics: List[Claim], proofs: List[Claim]) -> Tuple[List[Claim], List[Claim]]:
    """
    A proof an agreeing bench record covers — this design, its netlist as
    measured, no disagreement anywhere in its family — and the Stage 3 claim it
    re-derives stop citing D1 (`validation/bench.py`). No records, no change.
    """
    from validation.bench import evidence_for

    covered = evidence_for(generator.name, circuit.target_mcu, netlist)
    if not covered:
        return physics, proofs
    by_claim: Dict[str, Any] = {}
    for p in proved:
        if p.spec.id in covered:
            by_claim[f"proof.{p.spec.id}"] = covered[p.spec.id]
            if p.spec.re_derives:
                by_claim[p.spec.re_derives] = covered[p.spec.id]

    def bench(claim: Claim) -> Claim:
        finding = by_claim.get(claim.id)
        if finding is None or "D1" not in claim.defeaters:
            return claim
        data = claim.model_dump()
        data["defeaters"] = tuple(d for d in claim.defeaters if d != "D1")
        data["detail"] = ((claim.detail + "; ") if claim.detail else "") +             f"bench record {finding.record} agrees: {finding.detail}"
        if data["verdict"] in (Verdict.HOLDS.value, Verdict.HOLDS_DEFEASIBLE.value):
            open_now = any(REGISTER[d].is_open for d in data["defeaters"])
            data["verdict"] = (Verdict.HOLDS_DEFEASIBLE if open_now else Verdict.HOLDS).value
        return Claim.model_validate(data)

    return [bench(c) for c in physics], [bench(c) for c in proofs]


# ── Assessment ───────────────────────────────────────────────────────────────

def assess(generator: Any, intent: Any, circuit: CircuitIR) -> ValidationCoverage:
    """
    Every claim for one realised design. Deterministic, no simulator, no model.

    `generator.claims(intent)` supplies the physics; this adds what no
    generator may be trusted to remember — MCU models from the netlist (X6),
    D5 for a model-written specification nobody has signed, D9 for a
    generator outside the M1 matrix — the full rule catalogue (X8), and the
    Stage 4 proofs of `generator.properties(intent)`.
    """
    from validation.grid_adapters import M1_COVERED

    produce: Optional[Callable] = getattr(generator, "claims", None)
    physics: List[Claim] = list(produce(intent)) if callable(produce) else []

    netlist = _netlist_text(circuit)
    proved = prove_properties(generator, intent, circuit, netlist)
    set_hash = properties_hash(proved)
    signature = getattr(intent, "signed_off", None)
    intact = getattr(intent, "is_intact", lambda: True)()
    signed = bool(set_hash) and signature is not None and intact and \
        getattr(signature, "properties_hash", None) == set_hash

    extra: List[str] = []
    producer = getattr(getattr(intent, "provenance", None), "producer", None)
    if getattr(producer, "value", producer) == "llm" and not signed:
        extra.append("D5")

    # D2 per claim. What a claim measures is its own declaration, else the
    # quantities of the proofs that re-derive it; what it assumes is its own,
    # and a proof inherits the assumptions of the claim it re-derives.
    fallback = netlist_models(circuit, netlist)
    assumed = {c.id: c.scope.assumes for c in physics if c.scope is not None}
    reads = {c.id: c.scope.figures for c in physics if c.scope is not None}
    via_proofs: Dict[str, List[Measure]] = {}
    for p in proved:
        if p.spec.re_derives:
            via_proofs.setdefault(p.spec.re_derives, []).append(
                (p.spec.quantity, tuple(b.line for b in p.spec.bench)))

    def mcu_models_for(measures: Sequence[Measure], assumes: Sequence[str]) -> Tuple[Tuple[str, ...], bool]:
        """(models, derived). Undeclared, or unreadable, falls back to the netlist-wide rule."""
        if not measures:
            return fallback, False
        try:
            return derive_mcu_models(circuit, netlist, measures, assumes), True
        except (KeyError, ValueError):
            return fallback, False

    proofs = []
    for p in proved:
        assumes = assumed.get(p.spec.re_derives or "", ())
        models, _ = mcu_models_for([(p.spec.quantity, tuple(b.line for b in p.spec.bench))], assumes)
        # D9 is a doubt about predict(); a proof is checked against the netlist
        # generate() emitted, so it does not inherit D9.
        # A proof reads the parts and the bound of the claim it re-derives.
        proofs.append(_with_figures(_proof_claim(p, signed, extra, models, assumes),
                                    reads.get(p.spec.re_derives or "", ())))
    if generator.name not in M1_COVERED:
        extra.append("D9")
    scoped = []
    for c in physics:
        declared = c.scope.measures if c.scope is not None else ()
        measures = [(q, ()) for q in declared] or via_proofs.get(c.id, [])
        models, derived = mcu_models_for(measures, c.scope.assumes if c.scope is not None else ())
        scoped.append(_with_figures(
            _with_models(c, models, extra, derived=derived, measures=tuple(dict.fromkeys(q for q, _ in measures))),
            c.scope.figures if c.scope is not None else ()))
    physics = _supersede(scoped, proved, proofs)

    decision = generator.envelope(intent)
    ports = tuple(p.name for p in decision.ports) if decision.accepted else ()
    physics, proofs = _with_bench(generator, circuit, netlist, proved, physics, proofs)
    rows = physics + proofs + _rule_claims(circuit, ports) + _accounting_rows(
        physics, getattr(generator, "not_applicable_rules", {}) or {}
    )
    views = [
        PropertyView(id=p.spec.id, english=c.claim, hash=p.statement.hash if p.statement else "",
                     status=p.result.status if p.result else "unknown",
                     method=p.result.method if p.result else "not_compiled", grade=c.grade,
                     re_derives=p.spec.re_derives, counterexample=p.result.counterexample if p.result else None)
        for p, c in zip(proved, proofs)
    ]
    return ValidationCoverage.summarise(
        rows, properties=views, properties_hash=set_hash, properties_signed=signed,
        signed_by=signature.by if signed else None,
    )
