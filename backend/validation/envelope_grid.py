"""
The CI envelope-grid harness. PHASE_2_PLAN_v2.md §5 Stage 0.

Two gates depend on this module:

  - *"RC low-pass ported; `predict()` matches ngspice across the declared
    grid"* — empirical, G5 ≤ 2%
  - *"Grid harness fails on a 5% injected error in `generate()`"* — G1

The second is the one that matters. `ARCHITECTURE_ASSURANCE_CASE.md` §7 ranks
**M1**, the seeded fault-injection matrix, as the highest-priority harness to
build, because it is the refutation of defeater **D-G**: *"a generator bug
makes `predict()` confidently wrong, and nothing catches it."* A grid that only
ever agrees proves nothing — agreement between two expressions of the same
formula is cheap. Agreement that **breaks** when the circuit is perturbed is
evidence.

So a grid run comes in two arms, and `GridReport` carries both: a control arm
on the unmutated generator, and mutated arms that must fail. A mutation
detector that reports failure unconditionally is as useless as a gate that
never fires, which is why `run_matrix` refuses to call a mutation "detected"
unless the control passed first.

**Why adapters instead of protocol methods.** Comparing `predict()` against a
simulator needs three circuit-class-specific things: how to turn a grid point
into an intent, how to read the realized component values back out of the
generated design, and how to measure the quantity in the simulator output. None
of those belong to the generator — they are CI infrastructure, and putting them
on the `Generator` contract would reopen a return type Task 0.2 deliberately
froze. They live in `GridAdapter`, one per generator, supplied by the caller.

**The comparison is against the nominal, not the band.** `predict()` returns a
band over component tolerance, and a simulated point falls inside it almost
regardless of whether the prediction is any good — for the RC filter the band
is ±10% wide because the capacitor is, so a 5% seeded fault lands comfortably
inside it and would go undetected. The gate is therefore the deviation from
`Interval.nominal`, which is the generator's prediction at its *intended*
parameter values. Band containment is recorded alongside as the weaker claim
it is.

That distinction is load-bearing for fault injection. An earlier draft read the
realized component values back out of the generated design and pinned
`predict()` to those — which would have made the mutated arm agree with itself
and left the harness blind to the fault it exists to catch. The claim under
test is what the generator says *from the intent*, compared against what the
design it produced actually does.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from core.ir_schema import CircuitIR, ComponentType
from generators.netlist.spice import _parse_farads, _parse_ohms
from generators.protocol import Generator, Interval

# Matches the criterion-11 gate and `tests/test_simulation_accuracy.py`. The
# 15% grader tolerance exists to absorb physical component spread; there is no
# physical component on either side of this comparison.
DEFAULT_TOLERANCE = 0.02


class GridPointResult(BaseModel):
    """One grid point, one quantity, one verdict."""

    model_config = ConfigDict(frozen=True)

    point: Dict[str, float]
    quantity: str
    predicted: Optional[Interval] = None
    measured: Optional[float] = None
    #: Deviation from `predicted.nominal` — the generator's claim at its
    #: intended parameter values. This is what the gate is applied to.
    error: Optional[float] = None
    #: Whether the measurement also fell inside the tolerance band. Recorded,
    #: never gated on: the band is wide enough to swallow a 5% fault.
    within_band: Optional[bool] = None
    passed: bool
    note: Optional[str] = None

    def describe(self) -> str:
        where = ", ".join(f"{k}={v:g}" for k, v in self.point.items())
        if self.note:
            return f"[{where}] {self.quantity}: {self.note}"
        return (
            f"[{where}] {self.quantity}: predicted {self.predicted.nominal:.6g}, "
            f"measured {self.measured:.6g}, error {self.error:.4%}, "
            f"in-band {self.within_band}"
        )


class GridReport(BaseModel):
    """The outcome of sweeping one generator's declared envelope."""

    model_config = ConfigDict(frozen=True)

    generator: str
    tolerance: float
    results: Sequence[GridPointResult] = Field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    @property
    def failures(self) -> List[GridPointResult]:
        return [r for r in self.results if not r.passed]

    @property
    def worst_error(self) -> float:
        errors = [r.error for r in self.results if r.error is not None]
        return max(errors) if errors else 0.0

    def summary(self) -> str:
        head = (
            f"{self.generator}: {len(self.results) - len(self.failures)}/"
            f"{len(self.results)} points within {self.tolerance:.0%}, "
            f"worst {self.worst_error:.4%}"
        )
        if self.passed:
            return head
        lines = [head] + [f"  FAIL {r.describe()}" for r in self.failures[:10]]
        if len(self.failures) > 10:
            lines.append(f"  … and {len(self.failures) - 10} more")
        return "\n".join(lines)


class GridAdapter:
    """
    The circuit-class-specific glue between a generator and a simulator.

    `intent_for`  — grid point (as the generator's `grid()` declares it) → intent
    `measure`     — generated design → measured quantities, by the same names
                    `predict()` uses. Returning a name `predict()` does not
                    produce, or omitting one it does, is how a harness silently
                    stops checking anything, so `run_grid` fails a point whose
                    two sides have no quantity in common.
    """

    def __init__(
        self,
        generator: Generator,
        intent_for: Callable[[Mapping[str, float]], Any],
        measure: Callable[[CircuitIR], Mapping[str, float]],
    ) -> None:
        self.generator = generator
        self.intent_for = intent_for
        self.measure = measure


def run_grid(
    adapter: GridAdapter, tolerance: float = DEFAULT_TOLERANCE
) -> GridReport:
    """
    Sweep one generator's declared envelope and compare `predict()` against the
    simulator at every point.

    A point that cannot be evaluated — refused by `envelope()`, or a quantity
    the simulator did not produce — is recorded as a **failure with a note**,
    never skipped. A harness that quietly drops the points it cannot handle
    reports a clean sweep over whatever happened to work.
    """
    generator = adapter.generator
    results: List[GridPointResult] = []

    for point in generator.grid().points():
        point = dict(point)
        intent = adapter.intent_for(point)

        decision = generator.envelope(intent)
        if not decision.accepted:
            results.append(GridPointResult(
                point=point, quantity="-", passed=False,
                note=f"envelope() refused its own declared grid point: {decision.reason}",
            ))
            continue

        try:
            ir = generator.generate(intent)
            # Deliberately unpinned: the claim under test is what the generator
            # predicts from the intent, not what can be read back out of the
            # design it produced. `.nominal` is that claim at the intended
            # parameter values.
            predicted = generator.predict(intent).quantities
            measured = adapter.measure(ir)
        except Exception as exc:  # noqa: BLE001 — a crash is a grid failure
            results.append(GridPointResult(
                point=point, quantity="-", passed=False,
                note=f"{type(exc).__name__}: {exc}",
            ))
            continue

        comparable = [q for q in measured if q in predicted]
        if not comparable:
            results.append(GridPointResult(
                point=point, quantity="-", passed=False,
                note=(
                    f"no quantity in common — predict() offers {sorted(predicted)}, "
                    f"measure() returned {sorted(measured)}"
                ),
            ))
            continue

        for quantity in comparable:
            value = measured[quantity]
            band = predicted[quantity]
            if value is None or not math.isfinite(value):
                results.append(GridPointResult(
                    point=point, quantity=quantity, predicted=band, passed=False,
                    note="simulator produced no finite measurement",
                ))
                continue
            denominator = abs(band.nominal) if band.nominal else 1.0
            error = abs(value - band.nominal) / denominator
            results.append(GridPointResult(
                point=point, quantity=quantity, predicted=band,
                measured=value, error=error, within_band=band.contains(value),
                passed=error <= tolerance,
            ))

    return GridReport(
        generator=f"{generator.name}@{generator.version}",
        tolerance=tolerance,
        results=tuple(results),
    )


# ── Fault injection ──────────────────────────────────────────────────────────
#
# M1's mutation arms. The perturbation is applied to `generate()` output and
# never to `predict()`: that is precisely defeater D-G's shape — the design
# drifts away from what the generator confidently predicts about it, and the
# question is whether anything notices.

#: Named mutation strengths, per ARCHITECTURE_ASSURANCE_CASE.md §7 M1.
MUTATIONS: Dict[str, float] = {
    "P5": 1.05,     # the stated Stage 0 gate — just above a 2% tolerance
    "P20": 1.20,
    "X10": 10.0,
}


def _format_value(component_type: ComponentType, value: float) -> str:
    """
    Re-emit a scaled value in a form the SPICE value parsers accept.

    Resistors use `.10g` rather than `.6g` deliberately: at six significant
    figures `%g` switches to scientific notation from 1 MΩ upward, producing
    `3.4e+06`, which `_parse_ohms` does not match. A mutation arm would then
    inject an unparseable value and "detect" a fault that was really a broken
    netlist — a false positive in the one harness whose job is to tell true
    detections from false ones. Caller-side round-tripping in
    `scale_component_value` is the backstop.
    """
    if component_type == ComponentType.CAPACITOR:
        for suffix, scale in (("uF", 1e-6), ("nF", 1e-9), ("pF", 1e-12)):
            if value >= scale:
                return f"{value / scale:.10g}{suffix}"
        return f"{value / 1e-12:.10g}pF"
    return f"{value:.10g}"


def scale_component_value(ir: CircuitIR, component_id: str, factor: float) -> CircuitIR:
    """
    Return a copy of `ir` with one passive's value scaled.

    Deep-copies rather than mutating: a mutation arm that corrupted the shared
    design would make every later arm meaningless, and the bug would look like
    a detection.
    """
    mutated = ir.model_copy(deep=True)
    target = next((c for c in mutated.components if c.id == component_id), None)
    if target is None:
        raise ValueError(f"no component {component_id!r} to mutate")

    if target.type == ComponentType.CAPACITOR:
        current = _parse_farads(target.value or "")
    elif target.type == ComponentType.RESISTOR:
        current = _parse_ohms(target.value or "")
    else:
        raise ValueError(f"{component_id} is a {target.type}, not a scalable passive")

    if current is None:
        raise ValueError(f"cannot parse {component_id} value {target.value!r}")

    wanted = current * factor
    target.value = _format_value(target.type, wanted)

    # Round-trip before handing it back. A value string the SPICE parsers
    # cannot read would make the mutation arm test a broken netlist rather
    # than a seeded fault, and it would look like a successful detection.
    parser = _parse_farads if target.type == ComponentType.CAPACITOR else _parse_ohms
    readback = parser(target.value)
    if readback is None or abs(readback - wanted) / abs(wanted or 1.0) > 1e-6:
        raise ValueError(
            f"mutated {component_id} to {target.value!r}, which the SPICE value "
            f"parser reads as {readback!r} rather than {wanted!r} — the fault "
            f"would not be the one that was seeded"
        )
    return mutated


class MutatedGenerator:
    """
    A generator whose `generate()` is wrong by a known factor while its
    `predict()` is untouched — a seeded D-G fault.

    Conforms to the `Generator` protocol by delegation, so the harness cannot
    tell it apart from the real thing. That is the point: if the grid passes
    this, the grid is not checking the design.
    """

    def __init__(self, inner: Generator, component_id: str, factor: float) -> None:
        self._inner = inner
        self.component_id = component_id
        self.factor = factor

    @property
    def name(self) -> str:
        return f"{self._inner.name}[{self.component_id}×{self.factor:g}]"

    @property
    def version(self) -> str:
        return self._inner.version

    def envelope(self, intent):
        return self._inner.envelope(intent)

    def generate(self, intent) -> CircuitIR:
        return scale_component_value(
            self._inner.generate(intent), self.component_id, self.factor
        )

    def predict(self, intent, box=None):
        return self._inner.predict(intent, box=box)

    def grid(self):
        return self._inner.grid()

    def dependency_closure(self, requirement_path: str):
        return self._inner.dependency_closure(requirement_path)


class MatrixReport(BaseModel):
    """Control arm plus mutation arms. The pair is the evidence, not either half."""

    model_config = ConfigDict(frozen=True)

    control: GridReport
    mutations: Dict[str, GridReport] = Field(default_factory=dict)

    @property
    def control_passed(self) -> bool:
        return self.control.passed

    @property
    def undetected(self) -> List[str]:
        """Mutation arms the grid failed to catch."""
        return [name for name, report in self.mutations.items() if report.passed]

    @property
    def passed(self) -> bool:
        """
        The harness is sound when the clean design passes **and** at least one
        seeded fault was run **and** every one of them was caught.

        Each condition rules out a different broken harness: one that always
        passes, one that always fails, and — the hole an earlier version left —
        one that ran no faults at all and reported soundness vacuously, which
        is the same mistake as a grid that skips the points it cannot evaluate.
        """
        return bool(self.mutations) and self.control_passed and not self.undetected

    def summary(self) -> str:
        lines = [f"control: {self.control.summary()}"]
        for name, report in self.mutations.items():
            verdict = "DETECTED" if not report.passed else "MISSED"
            lines.append(
                f"{name}: {verdict} — {len(report.failures)}/{len(report.results)} "
                f"points outside {report.tolerance:.0%}, worst {report.worst_error:.4%}"
            )
        return "\n".join(lines)


def run_matrix(
    adapter: GridAdapter,
    component_id: str,
    mutations: Optional[Mapping[str, float]] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> MatrixReport:
    """
    Run the control arm and each seeded fault. `ARCHITECTURE_ASSURANCE_CASE.md`
    §7 M1, in the one-generator form Stage 0 calls for; Stage 3 extends the
    same call across the generator library.
    """
    control = run_grid(adapter, tolerance)
    arms: Dict[str, GridReport] = {}
    for label, factor in (mutations or MUTATIONS).items():
        mutated = GridAdapter(
            generator=MutatedGenerator(adapter.generator, component_id, factor),
            intent_for=adapter.intent_for,
            measure=adapter.measure,
        )
        arms[label] = run_grid(mutated, tolerance)
    return MatrixReport(control=control, mutations=arms)
