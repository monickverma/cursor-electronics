"""
Properties: what is proved, in a form a person can sign. Stage 4.

A generator declares a `PropertySpec` — a quantity named in netlist terms, a
relation, and bounds — and the compiler resolves it against one design into a
`Statement`: the spec plus the exact box every part ranges over. The
statement's **English** is generated from that structure by template, never by
a model, so the sentence signed is guaranteed to be the formula proved. Its
**hash** covers both, and is what sign-off pins and the refine loop freezes.

Bounds are exact decimal strings in SI units. `outward()` rounds a predicted
band *away* from its interior to the figures the English shows, so a property
is never tighter than what the user reads.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from fractions import Fraction
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

Relation = Literal["le", "ge", "within"]


class BenchElement(BaseModel):
    """A test-bench element the property adds: a load, a far-end terminator, a probe."""

    model_config = ConfigDict(frozen=True)

    line: str                      # SPICE line at its nominal value
    describe: str                  # as a condition: "a 100 kΩ load on VOUT"
    tolerance: Optional[str] = None  # relative, e.g. "0.01" → box around nominal
    lo: Optional[str] = None       # or an explicit box
    hi: Optional[str] = None
    #: With a box, the element reads as a range instead: "every <label> from
    #: a to b (<basis>)".
    label: Optional[str] = None    # "far-end terminator"
    basis: Optional[str] = None    # "1%, at the other end of the bus"

    @property
    def name(self) -> str:
        return self.line.split()[0]


class PropertySpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str                     # "the voltage at VOUT"
    quantity: str                  # see prover.QUANTITIES
    relation: Relation
    lo: Optional[str] = None
    hi: Optional[str] = None
    units: str                     # V, A, W, Hz, ohm, s
    bench: Tuple[BenchElement, ...] = ()
    #: The Stage 3 claim this re-derives from the netlist, if any.
    re_derives: Optional[str] = None
    #: The bound is a datasheet or standard figure (a rating, a threshold) —
    #: the claim carries D7 because that figure is unverified.
    datasheet_bound: bool = False

    @model_validator(mode="after")
    def _bounds(self) -> "PropertySpec":
        need_lo = self.relation in ("ge", "within")
        need_hi = self.relation in ("le", "within")
        if need_lo != (self.lo is not None) or need_hi != (self.hi is not None):
            raise ValueError(f"property {self.id}: bounds do not match relation {self.relation}")
        if self.lo is not None and self.hi is not None and Fraction(self.lo) > Fraction(self.hi):
            raise ValueError(f"property {self.id}: lo > hi")
        return self


class Variable(BaseModel):
    """One part's value, and the box it ranges over."""

    model_config = ConfigDict(frozen=True)

    element: str
    label: str                     # "R1", "U1 pin resistance", "cable capacitance"
    lo: str
    hi: str
    nominal: str
    units: str
    basis: str                     # "1% resistor", "datasheet 15–40 Ω", "bench"


class Statement(BaseModel):
    """A property resolved against one design. Frozen; its hash is what is signed."""

    model_config = ConfigDict(frozen=True)

    spec: PropertySpec
    variables: Tuple[Variable, ...]
    conditions: Tuple[str, ...]    # fixed facts: "VCC_5V at 5 V"
    english: str
    uses_pi: bool = False
    #: A transcendental (π, ln 9, the diode's logarithm) enters as a rational
    #: bracket — D8's doubt, answered by proof/brackets.py.
    bracketed: bool = False
    datasheet: bool = False        # a bound or box comes from a datasheet table (D7)
    mcu_models: Tuple[str, ...] = ()

    @property
    def hash(self) -> str:
        return statement_hash(self)


def statement_hash(statement: "Statement") -> str:
    payload = {
        "spec": statement.spec.model_dump(mode="json"),
        "variables": [v.model_dump(mode="json") for v in statement.variables],
        "conditions": list(statement.conditions),
        "english": statement.english,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def set_hash(statements: List[Statement]) -> str:
    """The hash of a design's whole property set — what one sign-off covers."""
    joined = "\n".join(sorted(s.hash for s in statements))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ── Numbers for people ───────────────────────────────────────────────────────

_PREFIX = [(Fraction(10) ** 9, "G"), (Fraction(10) ** 6, "M"), (Fraction(10) ** 3, "k"), (Fraction(1), ""),
           (Fraction(1, 10**3), "m"), (Fraction(1, 10**6), "µ"), (Fraction(1, 10**9), "n"), (Fraction(1, 10**12), "p")]
_UNIT = {"ohm": "Ω"}


def si(value: Fraction | str, units: str, digits: int = 4, rounding: str = "nearest") -> str:
    """
    A value with an SI prefix. `rounding` is "up" or "down" where the direction
    matters: a part's range in a signed sentence is rounded **inward** (its low
    end up, its high end down), so the English never claims a wider domain
    than the proof covered.
    """
    v = Fraction(value)
    unit = _UNIT.get(units, units)
    if v == 0:
        return f"0 {unit}"
    scale, prefix = next(((s, p) for s, p in _PREFIX if abs(v) >= s), _PREFIX[-1])
    scaled = v / scale
    exponent = math.floor(math.log10(abs(float(scaled)))) - digits + 1
    quantum = Fraction(10) ** exponent
    steps = scaled / quantum
    if rounding == "up":
        n = -((-steps.numerator) // steps.denominator)
    elif rounding == "down":
        n = steps.numerator // steps.denominator
    else:
        n = round(steps)
    shown = Decimal(n) * Decimal(10) ** exponent
    text = format(shown.normalize(), "f") if shown != 0 else "0"
    return f"{text} {prefix}{unit}"


def outward(lo: Optional[float], hi: Optional[float], digits: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """Round a band away from its interior to `digits` significant figures."""
    def rounded(x: float, rounding) -> str:
        if x == 0:
            return "0"
        exponent = math.floor(math.log10(abs(x))) - digits + 1
        quantum = Decimal(1).scaleb(exponent)
        value = (Decimal(repr(x)) / quantum).to_integral_value(rounding=rounding) * quantum
        return format(value.normalize(), "f")

    # Nudged outward first by a part in 10⁹: a predicted corner computed in
    # floating point may sit a hair inside the exact one, and rounding it to
    # three figures must not land the bound on the wrong side of it.
    return (
        rounded(lo * (1 - 1e-9) if lo > 0 else lo * (1 + 1e-9), ROUND_FLOOR) if lo is not None else None,
        rounded(hi * (1 + 1e-9) if hi > 0 else hi * (1 - 1e-9), ROUND_CEILING) if hi is not None else None,
    )


def exact(value: float, exponent: int = 0) -> str:
    """
    A float's shortest decimal times 10^exponent, written out — exact(5.0, -6)
    is "0.000005". For datasheet limits and unit changes, which must not pick
    up binary noise on the way (270 * 1e-12 is 2.7000000000000004e-10).
    """
    return format(Decimal(repr(value)).scaleb(exponent).normalize(), "f")


def back_translate(spec: PropertySpec, variables: List[Variable], conditions: List[str]) -> str:
    """The sentence a person signs. Built from the structure, nothing else."""
    ranged = {v.element.lower() for v in variables}
    ranges = [
        f"{v.label} from {si(v.lo, v.units, 5, 'up')} to {si(v.hi, v.units, 5, 'down')} ({v.basis})"
        for v in variables
    ]
    parts: List[str] = []
    if ranges:
        parts.append("For every " + "; every ".join(ranges))
    # A bench element with a box is already a range above; one without is a condition.
    context = list(conditions) + [b.describe for b in spec.bench if b.name.lower() not in ranged]
    if context:
        parts.append(("with " if ranges else "With ") + ", ".join(context))
    lead = ", ".join(parts)
    if spec.relation == "within":
        claim = f"{spec.label} stays between {si(spec.lo, spec.units)} and {si(spec.hi, spec.units)}"
    elif spec.relation == "le":
        claim = f"{spec.label} never exceeds {si(spec.hi, spec.units)}"
    else:
        claim = f"{spec.label} never falls below {si(spec.lo, spec.units)}"
    sentence = f"{lead}, {claim}." if lead else f"{claim[0].upper()}{claim[1:]}."
    return sentence[0].upper() + sentence[1:]
