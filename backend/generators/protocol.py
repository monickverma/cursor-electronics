"""
The `Generator` contract. PHASE_2_PLAN_v2.md §5 Stage 0.

A generator is the unit Phase 2 is built out of: it declares what it can do,
produces a design deterministically, and predicts that design's behaviour in
closed form. Three methods, and the plan is emphatic that the *return types*
are what matter here — `ARCHITECTURE_ASSURANCE_CASE.md` §8.1 puts adding the
interface-contract fields first precisely because "its only near-term cost is
adding the fields to the `envelope()` return type before five generators
calcify it."

So this module is deliberately front-loaded. Several fields below are unused
in Stage 0 and exist because adding them in Stage 2 or Stage 3 would mean
editing every generator written before then:

  - `PortContract`      — composition, §4 of the assurance case (Stage 3+)
  - `ClaimScope`        — claim objects, EVIDENCE_CLASSES §3.3 (Stage 3)
  - `Generator.grid`    — the CI envelope grid (Task 0.4, next)
  - `dependency_closure`— the locality property, v2 §4.1 (Stage 2)

Two invariants are enforced here rather than left to convention, because both
are stated as G1 gates and a G1 claim that depends on everyone remembering is
not G1:

1. **A refusal carries a named reason.** v2 Stage 0: *"`envelope()` refuses
   out-of-range intents with a named reason."* The reason is not an error
   message — §4.5 makes the refusal log the generator backlog, so the reason
   is the specification for the next generator. `EnvelopeDecision` cannot be
   constructed as a refusal without one.

2. **An acceptance carries its ports.** If the interface contract were
   optional it would be skipped, and the composition work in Stage 3 would
   start by editing all five generators — the exact cost this task exists to
   avoid.

On the input type: v2 schedules the concrete `IntentIR` schema in Stage 1,
while scheduling this protocol in Stage 0. `IntentLike` resolves that ordering
— it captures only what a generator reads, so Stage 1's model satisfies it
structurally with no change here and no pre-empting of Task 1.1.
"""

from __future__ import annotations

import math
from itertools import product
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.ir_schema import CircuitIR


# ── What a generator reads from an intent ────────────────────────────────────

@runtime_checkable
class IntentLike(Protocol):
    """
    The slice of IntentIR a generator touches. v2 §6 gives the full schema and
    Stage 1 Task 1.1 builds it; a generator only ever reads `requirements`, so
    typing against that keeps Stage 0 unblocked without freezing Stage 1's
    model prematurely.
    """

    @property
    def requirements(self) -> Mapping[str, Any]:
        """`function`, `targets`, `constraints`, `preferences` — v2 §6."""
        ...


# ── Value types ──────────────────────────────────────────────────────────────

class Interval(BaseModel):
    """
    A quantity over a range, not a point.

    This type is the whole of amendment X1 in one place. A nominal ngspice run
    reports a number; `predict()` reports the band that number is in for every
    component value inside tolerance. One is a measurement of a point, the
    other is a statement about the box — G5 against G1 in EVIDENCE_CLASSES §3.2.
    """

    model_config = ConfigDict(frozen=True)

    lo: float
    hi: float
    nominal: float
    units: str

    @model_validator(mode="after")
    def _ordered(self) -> "Interval":
        # NaN is already rejected by the ordering checks below (every
        # comparison against it is False), but infinities are not: they satisfy
        # both and would sail through. An unbounded prediction is never a real
        # answer — it means a divide-by-zero upstream — and it must not reach a
        # claim object looking like one.
        for field, value in (("lo", self.lo), ("hi", self.hi), ("nominal", self.nominal)):
            if math.isinf(value):
                raise ValueError(
                    f"interval {field}={value} is not finite — an unbounded "
                    "quantity is a symptom of a degenerate parameter, not a claim"
                )
        if self.lo > self.hi:
            raise ValueError(f"interval lo={self.lo} exceeds hi={self.hi}")
        if not (self.lo <= self.nominal <= self.hi):
            raise ValueError(
                f"nominal={self.nominal} lies outside [{self.lo}, {self.hi}] — "
                "a nominal value outside its own tolerance band is a bug in the "
                "generator, not a wide interval"
            )
        return self

    @classmethod
    def at(cls, value: float, units: str) -> "Interval":
        """A degenerate interval. Used for a single grid point in CI."""
        return cls(lo=value, hi=value, nominal=value, units=units)

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    @property
    def is_point(self) -> bool:
        return self.lo == self.hi

    def relative_error(self, measured: float) -> float:
        """
        Fractional distance from `measured` to this interval — 0.0 when inside.

        The Stage 0 gate is "`predict()` matches ngspice across the declared
        grid, ≤2%", and the honest reading of "matches" for a band is that the
        simulated point falls inside it. A point inside a wide band is not
        evidence of a tight prediction, which is why `width` is reported
        alongside this in the grid harness rather than folded into it.
        """
        if self.contains(measured):
            return 0.0
        edge = self.lo if measured < self.lo else self.hi
        denominator = abs(edge) if edge != 0 else 1.0
        return abs(measured - edge) / denominator


class ClaimScope(BaseModel):
    """
    What a prediction quantifies over. EVIDENCE_CLASSES.md §3.3.

    "A claim without `scope` is not a claim. *'The cutoff is 1 kHz'* is
    meaningless; *'f_c ∈ [850, 1150] Hz for all R ∈ [1574, 1606] Ω and
    C ∈ [90, 110] nF under `mna_ideal`'* is a claim."

    `model` is why this is required rather than nice-to-have. Amendment X6
    turns the MCU-as-100Ω assumption from a buried convention into a declared
    field, and defeater D2 hangs off it. An undeclared model is how a G1 proof
    gets presented as ground truth.
    """

    model_config = ConfigDict(frozen=True)

    parameters: str = "tolerance_box"   # nominal | tolerance_box | declared_envelope
    horizon: str = "steady_state"       # steady_state | bounded:T | unbounded
    model: str                          # mna_ideal, mcu_as_100R, shockley_diode, …
    inputs: str = "single_stimulus"     # single_stimulus | input_set


class PortContract(BaseModel):
    """
    One port of a generated block, and what it promises electrically.

    `ARCHITECTURE_ASSURANCE_CASE.md` §4: per-block proofs do not compose into a
    board claim on their own, but they do once each block declares its
    interface — composition then becomes algebraic side conditions checked
    between adjacent blocks. That capability exists only for an architecture
    with declared per-block contracts, which is the point of carrying these
    fields from the first generator onward.

    Grade: none. This is a design proposal until two generators share a rail
    and defeater D-E is actually tested.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    direction: str                      # input | output | bidirectional | power | ground
    impedance_ohm: Optional[Interval] = None
    current_draw_a: Optional[Interval] = None
    voltage_range_v: Optional[Interval] = None


# ── envelope() ───────────────────────────────────────────────────────────────

class EnvelopeDecision(BaseModel):
    """
    Whether this generator will take the job.

    Hard and deterministic by design. v2 §4.1 rejects the research report's
    selective-prediction proposal for exactly this reason: a confidence
    threshold needs a calibration set and drifts when the model changes, while
    a declared range does not.
    """

    model_config = ConfigDict(frozen=True)

    accepted: bool
    reason: Optional[str] = None
    ports: Sequence[PortContract] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _reason_and_ports(self) -> "EnvelopeDecision":
        if not self.accepted and not (self.reason or "").strip():
            raise ValueError(
                "a refusal requires a reason — §4.5 makes the out-of-envelope "
                "log the generator backlog, and an unexplained refusal is a "
                "backlog entry nobody can act on"
            )
        if self.accepted and not self.ports:
            raise ValueError(
                "an acceptance requires at least one PortContract — the "
                "interface contract is mandatory from the first generator so "
                "that composition work does not begin by editing all of them"
            )
        return self

    @classmethod
    def accept(cls, ports: Sequence[PortContract]) -> "EnvelopeDecision":
        return cls(accepted=True, ports=tuple(ports))

    @classmethod
    def refuse(cls, reason: str) -> "EnvelopeDecision":
        return cls(accepted=False, reason=reason)


# ── predict() ────────────────────────────────────────────────────────────────

class Prediction(BaseModel):
    """
    Closed-form behaviour of a design, over a parameter box.

    Amendment X1 ([2026-09-20] in decisions.md) makes this the per-request
    source of numerical truth, with ngspice moved to CI as the regression check
    that guards it. `method` records how the numbers were obtained so a claim
    can later be graded honestly — a monotone-corner evaluation and a z3 UNSAT
    are both exact, a midpoint evaluation is not, and EVIDENCE_CLASSES §3.2
    grades them differently.
    """

    model_config = ConfigDict(frozen=True)

    quantities: Dict[str, Interval]
    scope: ClaimScope
    method: str = "closed_form"

    @model_validator(mode="after")
    def _non_empty(self) -> "Prediction":
        if not self.quantities:
            raise ValueError(
                "a prediction with no quantities is not a prediction — return "
                "a refusal from envelope() instead of an empty result"
            )
        return self


# ── The CI envelope grid ─────────────────────────────────────────────────────

class GridSpec(BaseModel):
    """
    The parameter grid a generator declares for CI. Consumed by Task 0.4.

    Declared by the generator rather than chosen by the harness, because the
    generator is what knows where its envelope ends. A harness that picks its
    own points tests the generator where it is comfortable.
    """

    model_config = ConfigDict(frozen=True)

    axes: Dict[str, Sequence[float]]
    units: Dict[str, str] = Field(default_factory=dict)
    #: Which requirement section each axis lives in. Stage 3: the form producer
    #: had put every axis in `targets`, which would have made a divider's input
    #: rail a target. Absent axes default to `targets`, as before.
    sections: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _non_empty(self) -> "GridSpec":
        if not self.axes:
            raise ValueError("a grid needs at least one axis")
        for name, values in self.axes.items():
            if not values:
                raise ValueError(f"grid axis {name!r} has no values")
        for name, section in self.sections.items():
            if name not in self.axes:
                raise ValueError(f"sections names {name!r}, which is not an axis")
            if section not in ("targets", "constraints", "preferences"):
                raise ValueError(f"axis {name!r} is placed in unknown section {section!r}")
        return self

    def section_of(self, axis: str) -> str:
        return self.sections.get(axis, "targets")

    def points(self) -> Iterator[Dict[str, float]]:
        """Cartesian product of the axes, in declaration order."""
        names = list(self.axes)
        for combo in product(*(self.axes[n] for n in names)):
            yield dict(zip(names, combo))

    @property
    def size(self) -> int:
        n = 1
        for values in self.axes.values():
            n *= len(values)
        return n


# ── The protocol ─────────────────────────────────────────────────────────────

@runtime_checkable
class Generator(Protocol):
    """
    Structural, not inherited. A generator is anything with these members.

    Determinism (v2 §4.1): `generate()` must be a pure function of
    `(intent, version)`. Same intent and same version produce a byte-identical
    CircuitIR, which is what lets Stage 2 patch by regeneration without
    destroying anything.

    Known obstacle, carried in `plan/current_phase.md` Task 2.3: today
    `CircuitIR.circuit_id` defaults to a fresh `uuid4()` per instantiation, so
    byte-identity is unreachable until that id is derived from the intent and
    the generator version. Implementations should not work around it locally.
    """

    @property
    def name(self) -> str:
        """Stable identifier, e.g. `rc_lowpass`."""
        ...

    @property
    def function(self) -> str:
        """
        The `requirements.function` value this generator serves, e.g.
        `low_pass_filter`.

        Added in Stage 1 and not in Stage 0, deliberately and with the cost
        acknowledged: §4.2 makes the form producer derive its fields from the
        registry so that the form *is* the envelope catalogue, and a catalogue
        cannot be built from generators that do not say what they build.
        Probing `envelope()` with candidate functions would work and would be
        worse — it makes the catalogue depend on refusal messages.

        One generator exists, so this costs one edit today. That is the same
        argument Task 0.2 used for front-loading the other fields, and this is
        the last cheap moment to apply it.
        """
        ...

    @property
    def version(self) -> str:
        """
        Semver. Half of the determinism contract, and recorded on the design —
        v2 §6 gives CircuitIR a `generator` field of name + version. Bump it
        whenever `generate()` output changes for an unchanged intent.
        """
        ...

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        """Accept with ports, or refuse with a named reason. Never raises."""
        ...

    def generate(self, intent: IntentLike) -> CircuitIR:
        """
        Deterministic. Callers must call `envelope()` first; behaviour on a
        refused intent is undefined by this contract.
        """
        ...

    def predict(
        self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None
    ) -> Prediction:
        """
        Closed-form behaviour. With `box` omitted, evaluates over the intent's
        own tolerance box. With `box` supplied, evaluates over that instead —
        which is how the CI harness pins a single grid point, by passing
        degenerate intervals built with `Interval.at`.
        """
        ...

    def grid(self) -> GridSpec:
        """The declared envelope grid for CI. Task 0.4."""
        ...

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        """
        Component ids a change to `requirement_path` may touch. Stage 2's
        locality property asserts the CircuitIR diff is a subset of this.

        A conservative implementation returns every component id and is always
        sound — it just makes the locality check vacuous. Narrow it when the
        generator actually knows better; `conservative_closure()` is the
        honest default until then.
        """
        ...


# ── Helpers ──────────────────────────────────────────────────────────────────

def conservative_closure(ir: CircuitIR) -> FrozenSet[str]:
    """
    Every component. Sound but vacuous — a locality check against this passes
    unconditionally, which is the right default for a generator that has not
    yet worked out its real dependencies, and the wrong one to leave in place.
    """
    return frozenset(c.id for c in ir.components)


_REQUIRED_ATTRIBUTES = ("name", "version", "function")
_REQUIRED_METHODS = ("envelope", "generate", "predict", "grid", "dependency_closure")
_REQUIRED_MEMBERS = _REQUIRED_ATTRIBUTES + _REQUIRED_METHODS


def conformance_gaps(candidate: Any) -> List[str]:
    """
    Which parts of the contract `candidate` is missing, by name.

    `isinstance(x, Generator)` answers yes or no; the registry in Stage 1 has
    to tell an author *what* is missing, and a test asserting a specific gap is
    worth more than one asserting a bare False.

    The method members are checked for callability, not merely for presence. A
    plain `hasattr` check disagreed with `isinstance` on an object that had
    every name bound to a non-callable — this function reported no gaps while
    the protocol check correctly refused it, which is the worst possible
    combination for whoever is reading the error.
    """
    gaps = [m for m in _REQUIRED_ATTRIBUTES if not hasattr(candidate, m)]
    for method in _REQUIRED_METHODS:
        if not callable(getattr(candidate, method, None)):
            gaps.append(method)
    return gaps
