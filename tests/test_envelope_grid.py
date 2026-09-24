"""
Task 0.4 — the CI envelope-grid harness and its fault-injection matrix.

Two Stage 0 gates land here:

  - *"RC low-pass ported; `predict()` matches ngspice across the declared
    grid"* — G5 ≤ 2%
  - *"Grid harness fails on a 5% injected error in `generate()`"* — G1

The second is the one worth having. This is **M1** in
`ARCHITECTURE_ASSURANCE_CASE.md` §7, and its refutation of defeater **D-G** —
*"a generator bug makes `predict()` confidently wrong, and nothing catches
it."* Agreement between two expressions of the same formula is cheap;
agreement that breaks when the design is perturbed is evidence.

`TestHarnessLogic` runs against a fake generator and a fake simulator, so the
harness's own behaviour is pinned deterministically and without infrastructure.
`TestRCEnvelopeGrid` and `TestFaultInjectionMatrix` run the real thing through
ngspice, and auto-skip when it is absent.

One result below is worth reading even when everything passes:
`test_band_containment_would_not_have_caught_the_fault` shows the 5% fault
sitting *inside* the tolerance band. That is why the gate is the deviation from
the nominal and not band containment — a harness built the obvious way would
report this fault as fine.
"""

import math

import pytest

from core.ir_schema import ComponentType
from generators.protocol import ClaimScope, GridSpec, Interval, Prediction  # noqa: F401
from generators.rc_lowpass import RCLowPassGenerator, select_components
from validation.envelope_grid import (
    DEFAULT_TOLERANCE,
    MUTATIONS,
    GridAdapter,
    MutatedGenerator,
    run_grid,
    run_matrix,
    scale_component_value,
)
from test_rc_lowpass_generator import intent
from test_simulation_accuracy import _skip_no_ngspice, interpolate_cutoff, run_ir


# ── Fakes, so the harness logic is testable without ngspice ──────────────────

class _FakeGenerator:
    """Predicts `value = 10 × x`. Generates nothing real."""

    name = "fake"
    version = "1.0.0"
    function = "fake_function"

    def __init__(self, grid_values=(1.0, 2.0, 3.0), refuse_at=None):
        self._values = grid_values
        self._refuse_at = refuse_at

    def envelope(self, intent):
        from generators.protocol import EnvelopeDecision, PortContract

        if self._refuse_at is not None and intent["x"] == self._refuse_at:
            return EnvelopeDecision.refuse(f"x={intent['x']} out of envelope")
        return EnvelopeDecision.accept((PortContract(name="P", direction="input"),))

    def generate(self, intent):
        return intent  # the "design" is just the point; the fake measure reads it

    def predict(self, intent, box=None):
        nominal = 10.0 * intent["x"]
        return Prediction(
            quantities={
                "value": Interval(
                    lo=nominal * 0.9, hi=nominal * 1.1, nominal=nominal, units="u"
                )
            },
            scope=ClaimScope(model="fake"),
        )

    def grid(self):
        return GridSpec(axes={"x": list(self._values)})

    def dependency_closure(self, requirement_path):
        return frozenset()


def _fake_adapter(generator, measure):
    return GridAdapter(
        generator=generator, intent_for=lambda point: dict(point), measure=measure
    )


class TestHarnessLogic:
    def test_clean_sweep_passes_every_point(self):
        report = _fake_adapter(_FakeGenerator(), lambda d: {"value": 10.0 * d["x"]})
        result = run_grid(report)
        assert result.passed
        assert len(result.results) == 3
        assert result.worst_error == 0.0

    def test_error_is_measured_from_the_nominal(self):
        # 3% high everywhere.
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": 10.3 * d["x"]}))
        assert not result.passed
        assert result.worst_error == pytest.approx(0.03)

    def test_within_tolerance_passes(self):
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": 10.15 * d["x"]}))
        assert result.passed and result.worst_error == pytest.approx(0.015)

    def test_band_containment_is_recorded_but_not_gated(self):
        # 5% off: inside the ±10% band, outside the 2% gate. The whole reason
        # the gate is not band containment.
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": 10.5 * d["x"]}))
        assert not result.passed
        assert all(r.within_band for r in result.results)

    def test_refused_grid_point_is_a_failure_not_a_skip(self):
        # A generator refusing a point from its own declared grid is a
        # contradiction. Skipping it would report a clean sweep over whatever
        # happened to work.
        gen = _FakeGenerator(refuse_at=2.0)
        result = run_grid(_fake_adapter(gen, lambda d: {"value": 10.0 * d["x"]}))
        assert not result.passed
        assert len(result.failures) == 1
        assert "refused its own declared grid point" in result.failures[0].note

    def test_generator_crash_is_a_failure_not_an_error(self):
        def boom(design):
            raise RuntimeError("simulator died")

        result = run_grid(_fake_adapter(_FakeGenerator(), boom))
        assert not result.passed
        assert all("RuntimeError: simulator died" in r.note for r in result.failures)

    def test_no_common_quantity_is_a_failure(self):
        # The silent-stop-checking case: a measure() that reports a name
        # predict() never produces would otherwise compare nothing at all.
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"other": 1.0}))
        assert not result.passed
        assert "no quantity in common" in result.failures[0].note

    def test_non_finite_measurement_is_a_failure(self):
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": math.nan}))
        assert not result.passed
        assert "no finite measurement" in result.failures[0].note

    def test_summary_names_the_failing_points(self):
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": 20.0 * d["x"]}))
        text = result.summary()
        assert "FAIL" in text and "x=1" in text

    def test_multi_output_rows_are_counted_as_checks_not_points(self):
        # run_grid appends one row per (point, quantity). Reporting rows as
        # "points" overstates the sweep for any generator whose measure()
        # returns more than one quantity — two quantities at one point read as
        # two points.
        class TwoOutputs(_FakeGenerator):
            def predict(self, intent, box=None):
                n = 10.0 * intent["x"]
                return Prediction(
                    quantities={
                        "value": Interval(lo=n * 0.9, hi=n * 1.1, nominal=n, units="u"),
                        "other": Interval(lo=n * 1.9, hi=n * 2.1, nominal=n * 2, units="u"),
                    },
                    scope=ClaimScope(model="fake"),
                )

        result = run_grid(_fake_adapter(
            TwoOutputs(), lambda d: {"value": 10.0 * d["x"], "other": 20.0 * d["x"]}
        ))
        assert len(result.results) == 6      # 3 points x 2 quantities
        assert result.point_count == 3
        assert "3 grid points" in result.summary()
        assert "6 checks" in result.summary()

    def test_report_identifies_the_generator_and_version(self):
        result = run_grid(_fake_adapter(_FakeGenerator(), lambda d: {"value": 10.0 * d["x"]}))
        assert result.generator == "fake@1.0.0"


# ── Mutation operators ───────────────────────────────────────────────────────

class TestScaleComponentValue:
    def test_scales_a_capacitor_and_stays_parseable(self):
        from generators.netlist.spice import _parse_farads

        ir = RCLowPassGenerator().generate(intent(cutoff=1000.0))
        original = _parse_farads(next(c for c in ir.components if c.id == "C1").value)
        mutated = scale_component_value(ir, "C1", 1.05)
        got = _parse_farads(next(c for c in mutated.components if c.id == "C1").value)
        assert got == pytest.approx(original * 1.05, rel=1e-4)

    def test_scales_a_resistor_and_stays_parseable(self):
        from generators.netlist.spice import _parse_ohms

        ir = RCLowPassGenerator().generate(intent(cutoff=1000.0))
        original = _parse_ohms(next(c for c in ir.components if c.id == "R1").value)
        mutated = scale_component_value(ir, "R1", 1.05)
        got = _parse_ohms(next(c for c in mutated.components if c.id == "R1").value)
        assert got == pytest.approx(original * 1.05, rel=1e-4)

    def test_does_not_mutate_the_original(self):
        # A mutation arm that corrupted the shared design would make every
        # later arm meaningless, and the bug would look like a detection.
        ir = RCLowPassGenerator().generate(intent(cutoff=1000.0))
        before = next(c for c in ir.components if c.id == "C1").value
        scale_component_value(ir, "C1", 2.0)
        assert next(c for c in ir.components if c.id == "C1").value == before

    @pytest.mark.parametrize("component_id,factor", [
        ("R1", 1.05), ("R1", 10.0), ("R1", 100.0), ("R1", 1000.0), ("R1", 0.001),
        ("C1", 1.05), ("C1", 10.0), ("C1", 1000.0), ("C1", 0.001),
    ])
    def test_scaled_values_stay_parseable_at_every_magnitude(self, component_id, factor):
        # At six significant figures `%g` switches to scientific notation from
        # 1 MΩ up — `3.4e+06`, which `_parse_ohms` does not match. A mutation
        # arm would then inject an unparseable value and "detect" a fault that
        # was really a broken netlist: a false positive in the one harness
        # whose job is telling true detections from false ones.
        from generators.netlist.spice import _parse_farads, _parse_ohms

        ir = RCLowPassGenerator().generate(intent(cutoff=100.0))
        parser = _parse_ohms if component_id == "R1" else _parse_farads
        before = parser(next(c for c in ir.components if c.id == component_id).value)

        mutated = scale_component_value(ir, component_id, factor)
        after = parser(next(c for c in mutated.components if c.id == component_id).value)

        assert after is not None
        assert after == pytest.approx(before * factor, rel=1e-6)

    def test_megohm_resistor_does_not_become_scientific_notation(self):
        # The specific regression: 3.4 MΩ must not format as "3.4e+06".
        from generators.netlist.spice import _parse_ohms
        from validation.envelope_grid import _format_value

        text = _format_value(ComponentType.RESISTOR, 3_400_000.0)
        assert "e+" not in text
        assert _parse_ohms(text) == pytest.approx(3_400_000.0)

    def test_unknown_component_rejected(self):
        ir = RCLowPassGenerator().generate(intent(cutoff=1000.0))
        with pytest.raises(ValueError, match="no component"):
            scale_component_value(ir, "R99", 1.05)

    def test_mutated_generator_leaves_predict_untouched(self):
        # The seeded fault is D-G's exact shape: the design drifts, the claim
        # does not. A mutation that moved both would test nothing.
        base = RCLowPassGenerator()
        mutated = MutatedGenerator(base, "C1", 1.05)
        i = intent(cutoff=1000.0)
        assert (
            mutated.predict(i).quantities["cutoff_hz"].nominal
            == base.predict(i).quantities["cutoff_hz"].nominal
        )

    def test_mutated_generator_still_satisfies_the_protocol(self):
        from generators.protocol import Generator

        assert isinstance(MutatedGenerator(RCLowPassGenerator(), "C1", 1.05), Generator)


# ── The real grid, through ngspice ───────────────────────────────────────────

def _rc_adapter():
    def measure(ir):
        supply = ir.constraints["supply_voltage"]
        points = run_ir(ir).ac_points
        crossing = interpolate_cutoff(points, "out", supply / math.sqrt(2.0))
        return {"cutoff_hz": crossing if crossing is not None else math.nan}

    return GridAdapter(
        generator=RCLowPassGenerator(),
        intent_for=lambda point: intent(cutoff=point["cutoff_hz"]),
        measure=measure,
    )


@_skip_no_ngspice
class TestRCEnvelopeGrid:
    def test_clean_grid_passes_within_two_percent(self):
        report = run_grid(_rc_adapter())
        assert report.passed, report.summary()
        assert len(report.results) == 7

    def test_worst_deviation_is_print_precision(self):
        # Both sides are the same mathematics, so anything above noise here
        # means the netlist generator and predict() have diverged.
        report = run_grid(_rc_adapter())
        assert report.worst_error < 1e-4, report.summary()


@_skip_no_ngspice
class TestFaultInjectionMatrix:
    """M1. The control arm and the seeded faults are the evidence together."""

    def test_five_percent_fault_is_detected(self):
        # The stated Stage 0 gate.
        report = run_matrix(_rc_adapter(), "C1", {"P5": MUTATIONS["P5"]})
        assert report.control_passed, report.control.summary()
        assert not report.mutations["P5"].passed, (
            "a 5% capacitor error went undetected — the grid is not checking "
            "the design it was given"
        )

    def test_full_matrix_catches_every_seeded_fault(self):
        report = run_matrix(_rc_adapter(), "C1")
        assert report.passed, report.summary()
        assert report.undetected == []
        assert set(report.mutations) == set(MUTATIONS)

    def test_faults_on_the_resistor_are_caught_too(self):
        # Both passives set the cutoff. A harness watching only one of them
        # would miss half the ways generate() can be wrong.
        report = run_matrix(_rc_adapter(), "R1", {"P5": 1.05})
        assert report.passed, report.summary()

    def test_a_matrix_with_no_seeded_faults_is_not_sound(self):
        # The third way to build a broken detector, after "always passes" and
        # "always fails": run no faults at all and report soundness vacuously.
        # Reachable through the API now that `{}` is honoured rather than
        # being swapped for the defaults — previously this could only be
        # constructed by hand, which meant the guard was untestable in situ.
        report = run_matrix(_rc_adapter(), "C1", {})
        assert report.mutations == {}
        assert report.control_passed
        assert report.undetected == []
        assert not report.passed, "a matrix that seeded nothing reported itself sound"

    def test_explicit_empty_mutations_is_not_treated_as_unspecified(self):
        assert run_matrix(_rc_adapter(), "C1", {}).mutations == {}
        assert set(run_matrix(_rc_adapter(), "C1", None).mutations) == set(MUTATIONS)

    def test_control_arm_is_required_for_the_matrix_to_pass(self):
        # A detector that fails everything is not a detector. `passed` is only
        # true when the clean design passes *and* every fault is caught.
        report = run_matrix(_rc_adapter(), "C1", {"P5": 1.05})
        assert report.control_passed and report.passed
        broken = report.model_copy(
            update={"control": report.mutations["P5"]}  # a failing control arm
        )
        assert not broken.passed

    def test_band_containment_would_not_have_caught_the_fault(self):
        # The finding that decided the harness design. A 5% capacitor error
        # moves the cutoff well inside the ±10% tolerance band, so a grid gated
        # on band containment would have called this design fine.
        report = run_matrix(_rc_adapter(), "C1", {"P5": 1.05})
        failures = report.mutations["P5"].failures
        assert failures, "the 5% fault was not detected at all"
        assert all(r.within_band for r in failures), (
            "expected the seeded fault to sit inside the tolerance band — if it "
            "no longer does, the band tightened and this test has lost its point"
        )
        assert all(r.error > DEFAULT_TOLERANCE for r in failures)

    def test_fault_moves_the_cutoff_in_the_right_direction(self):
        # A bigger capacitor lowers the cutoff. Detection for the wrong reason
        # is still a broken harness.
        report = run_matrix(_rc_adapter(), "C1", {"P20": 1.20})
        for r in report.mutations["P20"].results:
            assert r.measured < r.predicted.nominal
