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

**X6 is derived, never remembered.** If the design's own netlist contains an
`R_MCU_` element, every behavioural claim's model gains `mcu_as_100R` and
cites D2; `R_PIN_` adds `mcu_pin_thevenin`. A generator cannot forget to say so.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from core.ir_schema import CircuitIR, SignalType, ValidationRule
from core.ir_validator import validate_ir
from generators.netlist.models import MODEL_MCU_PIN, MODEL_MCU_SUPPLY
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

class ValidationCoverage(BaseModel):
    """EVIDENCE_CLASSES §5, revised `validation_coverage`. Three numbers, never fused."""

    model_config = ConfigDict(frozen=True)

    claims: Tuple[Claim, ...]
    coverage_le_g2: float
    grade_floor: Optional[str]
    open_defeaters: Tuple[str, ...]
    not_assessed: Tuple[str, ...]
    out_of_scope: Tuple[str, ...]

    @classmethod
    def summarise(cls, claims: Sequence[Claim]) -> "ValidationCoverage":
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
        )

    @property
    def failures(self) -> Tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.verdict == Verdict.FAILS.value)


# ── X6: models derived from the netlist ──────────────────────────────────────

def netlist_models(circuit: CircuitIR) -> Tuple[str, ...]:
    """MCU models the design's own netlist uses. Read from the netlist text."""
    from generators.netlist.spice import SpiceNetlistGenerator

    netlist = SpiceNetlistGenerator().generate(circuit)
    models = []
    if "\nR_MCU_" in netlist:
        models.append(MODEL_MCU_SUPPLY)
    if "\nR_PIN_" in netlist:
        models.append(MODEL_MCU_PIN)
    return tuple(models)


def _with_models(claim: Claim, models: Sequence[str], extra_defeaters: Sequence[str]) -> Claim:
    """Add derived model names and defeaters to a behavioural claim."""
    if claim.scope is None:
        return claim
    parts = claim.scope.model.split("+")
    for model in models:
        if model not in parts:
            parts.append(model)
    defeaters = list(claim.defeaters)
    for d in list(extra_defeaters) + (["D2"] if models else []):
        if d not in defeaters:
            defeaters.append(d)
    data = claim.model_dump()
    data["scope"] = claim.scope.model_copy(update={"model": "+".join(parts)})
    data["defeaters"] = tuple(defeaters)
    if data["verdict"] == Verdict.HOLDS.value and any(REGISTER[d].is_open for d in defeaters):
        data["verdict"] = Verdict.HOLDS_DEFEASIBLE.value
    return Claim.model_validate(data)


# ── X8: the rule catalogue as claims ─────────────────────────────────────────

_RULE_SENTENCES = {
    "no_floating_nodes": "every node has at least two connections, counting declared ports",
    "voltage_ratings_ok": "every part's rated supply voltage covers the circuit's supply",
    "i2c_pullups_present": "every I2C line has a pull-up to a supply rail",
    "rs485_termination_present": "the RS-485 A/B pair is terminated with 100–150 ohm",
    "rs485_bias_resistors": "RS-485 A is biased to VCC and B to GND",
    "pwm_pin_valid": "every PWM signal uses an Arduino Uno PWM-capable pin",
}


def _rule_claims(circuit: CircuitIR, ports: Sequence[str]) -> List[Claim]:
    from validation.rule_engine import HardwareRuleEngine

    structural = validate_ir(circuit)
    engine = HardwareRuleEngine()
    node_types = {n.type for n in circuit.nodes}
    scope = ClaimScope(parameters="nominal", model="design_graph")
    rows: List[Claim] = []

    def row(rule: str, holds: bool, applicable: bool, detail: Optional[str]) -> None:
        method, extra = _IMPLEMENTED[rule]
        if not applicable:
            rows.append(Claim(
                id=f"rule.{rule}", claim=_RULE_SENTENCES[rule], kind=Kind.ANALYTIC,
                verdict=Verdict.NOT_APPLICABLE, critical=False, detail=detail,
            ))
            return
        rows.append(graded(
            f"rule.{rule}", _RULE_SENTENCES[rule], holds, method, scope,
            defeaters=extra, detail=detail,
        ))

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


# ── Assessment ───────────────────────────────────────────────────────────────

def assess(generator: Any, intent: Any, circuit: CircuitIR) -> ValidationCoverage:
    """
    Every claim for one realised design. Deterministic, no simulator, no model.

    `generator.claims(intent)` supplies the physics; this adds what no
    generator may be trusted to remember — MCU models from the netlist (X6),
    D5 for a model-written specification, D9 for a generator outside the M1
    matrix — and the full rule catalogue (X8).
    """
    from validation.grid_adapters import M1_COVERED

    produce: Optional[Callable] = getattr(generator, "claims", None)
    physics: List[Claim] = list(produce(intent)) if callable(produce) else []

    extra: List[str] = []
    producer = getattr(getattr(intent, "provenance", None), "producer", None)
    if getattr(producer, "value", producer) == "llm":
        extra.append("D5")
    if generator.name not in M1_COVERED:
        extra.append("D9")

    models = netlist_models(circuit)
    physics = [_with_models(c, models, extra) for c in physics]

    decision = generator.envelope(intent)
    ports = tuple(p.name for p in decision.ports) if decision.accepted else ()
    rows = physics + _rule_claims(circuit, ports) + _accounting_rows(
        physics, getattr(generator, "not_applicable_rules", {}) or {}
    )
    return ValidationCoverage.summarise(rows)
