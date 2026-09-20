"""
Task 0.3 — the RC low-pass generator, and the Stage 0 gate it has to clear.

PHASE_2_PLAN_v2.md Stage 0: *"RC low-pass ported; `predict()` matches ngspice
across the declared grid — empirical, G5 ≤ 2%."*

The gate lives in `TestPredictAgainstNgspice`. Everything above it pins the
pieces the gate depends on, because a comparison whose inputs are wrong can
agree with ngspice and still be meaningless.

Two things this file is careful about:

**It compares like with like.** `predict()` returns a band over the tolerance
box, and ngspice simulates one nominal netlist. Checking that the simulated
point falls inside a ±10% band would pass on almost any prediction — the band
is wide because the capacitor is. So the gate pins the box to the exact
component values the netlist uses, via degenerate intervals, and compares point
against point. The band is asserted separately, against the worked example in
the formal-verification report.

**It has a negative control.** A gate that only ever passes tests nothing —
the same reasoning that put the injected-5%-error check in
`tests/test_simulation_accuracy.py`. `test_gate_rejects_a_mismatched_prediction`
perturbs the circuit and asserts the unperturbed prediction now fails.

The ngspice harness is reused from `tests/test_simulation_accuracy.py` rather
than rebuilt, per the task note in `plan/current_phase.md`.
"""

import math

import pytest
from pydantic import ValidationError

from core.ir_schema import ComponentType
from core.ir_validator import validate_ir
from generators.protocol import (
    ClaimScope,
    Generator,
    Interval,
    conformance_gaps,
)
from generators.rc_lowpass import (
    C_TOLERANCE,
    MAX_CUTOFF_HZ,
    MIN_CUTOFF_HZ,
    R_TOLERANCE,
    RCLowPassGenerator,
    cutoff_hz,
    select_components,
    snap_to_e96,
)
from test_simulation_accuracy import (
    TOLERANCE,
    _skip_no_ngspice,
    interpolate_cutoff,
    run_ir,
)


class _Intent:
    """Stands in for Stage 1's IntentIR — only `requirements`, per IntentLike."""

    def __init__(self, **requirements):
        self._requirements = requirements

    @property
    def requirements(self):
        return self._requirements


def intent(cutoff=1000.0, tolerance_pct=5.0, supply_v=5.0, function="low_pass_filter",
           source_impedance_ohm=50.0, **extra):
    targets = {"tolerance_pct": tolerance_pct}
    if cutoff is not None:
        targets["cutoff_hz"] = cutoff
    return _Intent(
        function=function,
        targets=targets,
        constraints={"supply_v": supply_v, "source_impedance_ohm": source_impedance_ohm},
        preferences={"package": "0402"},
        **extra,
    )


GEN = RCLowPassGenerator()


# ── Conformance ──────────────────────────────────────────────────────────────

class TestConformance:
    def test_satisfies_the_generator_protocol(self):
        assert isinstance(GEN, Generator)

    def test_no_contract_gaps(self):
        assert conformance_gaps(GEN) == []

    def test_name_and_version_are_declared(self):
        assert GEN.name == "rc_lowpass"
        assert GEN.version.count(".") == 2  # semver — half the determinism contract


# ── The arithmetic the rest of the file trusts ───────────────────────────────

class TestClosedForm:
    def test_cutoff_matches_the_shipping_reference_design(self):
        # IR_003: R=1590, C=100nF → ~1000.7 Hz. Same number the criterion-11
        # harness uses, so the two files cannot silently disagree.
        assert cutoff_hz(1590, 100e-9) == pytest.approx(1000.7, rel=1e-3)

    def test_snap_picks_the_logarithmically_nearest_e96_value(self):
        # 1591.55 sits between E96 neighbours 1580 and 1620. By absolute
        # distance 1580 wins by 11.5 Ω; in log space, which is how the series
        # is actually spaced, it wins by more. Either way the answer is 1580 —
        # this pins that it is not 1590, which is not an E96 value at all.
        assert snap_to_e96(1591.55) == 1580.0

    def test_snap_is_exact_on_a_series_value(self):
        assert snap_to_e96(1000.0) == 1000.0
        assert snap_to_e96(4750.0) == 4750.0

    def test_e24_values_are_not_assumed_to_be_e96_values(self):
        # 4.7k is the familiar E24/E12 value and is *not* in E96 — the nearest
        # 1% parts are 4.64k and 4.75k. A generator that assumed otherwise
        # would emit a part number nobody stocks at that tolerance.
        assert snap_to_e96(4700.0) == 4750.0

    def test_snap_rejects_non_positive(self):
        with pytest.raises(ValueError):
            snap_to_e96(0.0)

    def test_selection_is_deterministic(self):
        first = select_components(1000.0, 5.0)
        second = select_components(1000.0, 5.0)
        assert (first.ohms, first.farads) == (second.ohms, second.farads)

    def test_selection_keeps_the_series_resistor_in_range(self):
        for target in (100.0, 1_000.0, 10_000.0, 100_000.0):
            sel = select_components(target, 5.0)
            assert sel is not None
            assert 1_000.0 <= sel.ohms <= 100_000.0


# ── envelope() ───────────────────────────────────────────────────────────────

class TestEnvelope:
    def test_accepts_an_in_range_intent(self):
        decision = GEN.envelope(intent(cutoff=1000.0))
        assert decision.accepted is True

    def test_acceptance_carries_the_interface_contract(self):
        ports = GEN.envelope(intent()).ports
        assert {p.name for p in ports} == {"IN", "OUT", "GND"}

    def test_input_impedance_is_the_series_resistor_band(self):
        # What an upstream stage sees. Stage 3 composition checks this against
        # the neighbouring block's output impedance.
        port = next(p for p in GEN.envelope(intent()).ports if p.name == "IN")
        sel = select_components(1000.0, 5.0)
        assert port.impedance_ohm.nominal == pytest.approx(sel.ohms)

    def test_passive_filter_draws_no_supply_current(self):
        port = next(p for p in GEN.envelope(intent()).ports if p.name == "OUT")
        assert port.current_draw_a.hi == 0.0

    def test_refuses_a_function_it_does_not_build(self):
        d = GEN.envelope(intent(function="band_pass_filter"))
        assert d.accepted is False
        assert "band_pass_filter" in d.reason

    def test_refuses_a_missing_cutoff_and_says_it_is_underdetermined(self):
        # Distinct from out-of-envelope: Stage 1 turns this into a question,
        # not a refusal, so the reason has to distinguish the two.
        d = GEN.envelope(intent(cutoff=None))
        assert d.accepted is False
        assert "underdetermined" in d.reason

    @pytest.mark.parametrize("target", [1.0, 2_000_000.0])
    def test_refuses_outside_the_declared_envelope(self, target):
        d = GEN.envelope(intent(cutoff=target))
        assert d.accepted is False
        assert "outside declared envelope" in d.reason

    def test_refusal_names_the_offending_value_and_the_bound(self):
        # §4.5 makes the refusal log the generator backlog. A reason that does
        # not name the value cannot be ranked or acted on.
        reason = GEN.envelope(intent(cutoff=2_000_000.0)).reason
        assert "2e+06" in reason or "2000000" in reason
        assert f"{MAX_CUTOFF_HZ:g}" in reason

    def test_refuses_when_the_supply_exceeds_every_capacitor_rating(self):
        d = GEN.envelope(intent(cutoff=1000.0, supply_v=100.0))
        assert d.accepted is False
        assert "supply_v=100" in d.reason

    def test_refuses_when_e96_cannot_meet_the_requested_tolerance(self):
        # 1 kHz selects 3400 Ω with 47 nF and achieves ~996 Hz — a 0.4% error,
        # the best the catalogue and E96 can do. Asking for 0.1% is a real
        # boundary of this generator, not a bug, and it must be refused rather
        # than silently delivered.
        d = GEN.envelope(intent(cutoff=1000.0, tolerance_pct=0.1))
        assert d.accepted is False
        assert "tolerance_pct" in d.reason

    def test_envelope_never_raises_on_a_junk_intent(self):
        d = GEN.envelope(_Intent())
        assert d.accepted is False and d.reason


# ── predict() ────────────────────────────────────────────────────────────────

class TestPredict:
    def test_returns_a_band_over_the_tolerance_box(self):
        band = GEN.predict(intent()).quantities["cutoff_hz"]
        assert not band.is_point
        assert band.contains(band.nominal)

    def test_band_reproduces_the_research_report_worked_example(self):
        # The formal-verification report works this by hand: R ∈ [1574, 1606] Ω
        # with C ∈ [90, 110] nF gives "roughly 900 to 1,125 Hz". Reproducing a
        # published number is worth more than reproducing my own arithmetic.
        box = {
            "R": Interval(lo=1574.0, hi=1606.0, nominal=1590.0, units="ohm"),
            "C": Interval(lo=90e-9, hi=110e-9, nominal=100e-9, units="F"),
        }
        band = GEN.predict(intent(), box=box).quantities["cutoff_hz"]
        assert band.lo == pytest.approx(900.7, rel=1e-3)
        assert band.hi == pytest.approx(1123.3, rel=1e-3)

    def test_band_edges_are_opposite_corners(self):
        # f_c is monotone decreasing in both R and C, so the extremes are the
        # corners. This is what makes `method` monotone_corners and the claim
        # exact rather than sampled.
        p = GEN.predict(intent())
        r, c = p.quantities["resistance_ohm"], p.quantities["capacitance_f"]
        band = p.quantities["cutoff_hz"]
        assert band.hi == pytest.approx(cutoff_hz(r.lo, c.lo))
        assert band.lo == pytest.approx(cutoff_hz(r.hi, c.hi))

    def test_capacitor_dominates_the_spread(self):
        # 10% part against a 1% part. The generator says so in C1's
        # justification; this is the assertion behind that sentence.
        p = GEN.predict(intent())
        r, c = p.quantities["resistance_ohm"], p.quantities["capacitance_f"]
        r_spread = (r.hi - r.lo) / r.nominal
        c_spread = (c.hi - c.lo) / c.nominal
        assert c_spread == pytest.approx(2 * C_TOLERANCE)
        assert r_spread == pytest.approx(2 * R_TOLERANCE)
        assert c_spread > 5 * r_spread

    def test_method_is_recorded_as_exact(self):
        assert GEN.predict(intent()).method == "monotone_corners"

    def test_scope_declares_the_model(self):
        # EVIDENCE_CLASSES §3.3 — a claim without a named model is how a G1
        # proof over an unvalidated model gets read as ground truth.
        scope = GEN.predict(intent()).scope
        assert scope.model == "mna_ideal"
        assert scope.parameters == "tolerance_box"
        assert scope.horizon == "steady_state"

    def test_partial_box_pins_only_the_axis_it_names(self):
        # An earlier version discarded any box that did not name both axes, so
        # a caller pinning R alone silently got the full tolerance band back.
        sel = select_components(1000.0, 5.0)
        full = GEN.predict(intent()).quantities["cutoff_hz"]
        pinned = GEN.predict(
            intent(), box={"R": Interval.at(sel.ohms, "ohm")}
        ).quantities["cutoff_hz"]

        assert (pinned.lo, pinned.hi) != (full.lo, full.hi), "partial box was ignored"
        # R pinned, C still ±10% — the band narrows to the capacitor's spread.
        assert pinned.hi / pinned.lo == pytest.approx(
            (1 + C_TOLERANCE) / (1 - C_TOLERANCE)
        )

    def test_unknown_box_parameter_is_rejected(self):
        # A typo is otherwise indistinguishable from a deliberate omission.
        with pytest.raises(ValueError, match="unknown parameters"):
            GEN.predict(intent(), box={"Rs": Interval.at(1000.0, "ohm")})

    def test_degenerate_box_gives_a_point_and_says_so(self):
        sel = select_components(1000.0, 5.0)
        box = {"R": Interval.at(sel.ohms, "ohm"), "C": Interval.at(sel.farads, "F")}
        p = GEN.predict(intent(), box=box)
        assert p.quantities["cutoff_hz"].is_point
        assert p.scope.parameters == "nominal"

    def test_attenuation_at_cutoff_is_minus_three_db(self):
        band = GEN.predict(intent()).quantities["attenuation_at_cutoff_db"]
        assert band.nominal == pytest.approx(-3.0103, abs=1e-4)

    def test_output_at_cutoff_is_vin_over_root_two(self):
        band = GEN.predict(intent(supply_v=5.0)).quantities["vout_at_cutoff_v"]
        assert band.nominal == pytest.approx(5.0 / math.sqrt(2.0))

    def test_predict_refuses_an_intent_envelope_would_refuse(self):
        with pytest.raises(ValueError):
            GEN.predict(intent(cutoff=None))


# ── generate() ───────────────────────────────────────────────────────────────

class TestGenerate:
    def test_produces_a_structurally_valid_ir(self):
        result = validate_ir(GEN.generate(intent()))
        assert result.errors == [], result.errors

    def test_has_one_resistor_and_one_capacitor(self):
        ir = GEN.generate(intent())
        types = {c.id: c.type for c in ir.components}
        assert types == {"R1": ComponentType.RESISTOR, "C1": ComponentType.CAPACITOR}

    def test_records_the_requested_cutoff_in_constraints(self):
        assert GEN.generate(intent(cutoff=3300.0)).constraints["cutoff_hz"] == 3300.0

    def test_sweeps_two_decades_either_side_of_cutoff(self):
        analysis = GEN.generate(intent(cutoff=1000.0)).simulation_spec.analyses[0]
        assert analysis.type == "ac_sweep"
        assert analysis.f_start < 100.0 < 10_000.0 < analysis.f_stop

    def test_capacitor_rating_covers_the_supply(self):
        ir = GEN.generate(intent(supply_v=5.0))
        cap = next(c for c in ir.components if c.id == "C1")
        assert cap.supply_voltage_max >= 5.0

    def test_justifications_are_consequential_not_descriptive(self):
        # The product differentiator, per PRODUCT_MASTER Part 12: every
        # sentence should answer "what breaks if this is wrong". Same class of
        # assertion tests/test_explainer.py makes on the explanation layer.
        ir = GEN.generate(intent())
        r1 = next(c for c in ir.components if c.id == "R1")
        assert "Raising R lowers the cutoff" in r1.justification
        assert "loading error" in r1.justification

    def test_flags_the_part_number_as_needing_a_stock_check(self):
        # The code is encoded from Yageo's series scheme, which is real; that
        # this exact SKU is stocked is not something this generator knows.
        r1 = next(c for c in GEN.generate(intent()).components if c.id == "R1")
        assert "stock check" in r1.justification

    def test_deterministic_modulo_circuit_id(self):
        # v2 §4.1 wants byte-identical output for the same intent and version.
        # `CircuitIR.circuit_id` defaults to a fresh uuid4, so full byte
        # identity is blocked until Task 2.3 derives it. Everything this
        # generator controls is already reproducible, and this test is what
        # will still be here to prove it when 2.3 lands.
        a = GEN.generate(intent(cutoff=2200.0)).model_dump(mode="json")
        b = GEN.generate(intent(cutoff=2200.0)).model_dump(mode="json")
        a.pop("circuit_id")
        b.pop("circuit_id")
        assert a == b


# ── grid() and dependency_closure() ──────────────────────────────────────────

class TestGridAndLocality:
    def test_grid_spans_three_decades(self):
        points = [p["cutoff_hz"] for p in GEN.grid().points()]
        assert min(points) == 100.0 and max(points) == 100_000.0
        assert len(points) >= 5  # a single point passes on a decade-scaling bug

    def test_every_grid_point_is_inside_the_declared_envelope(self):
        for point in GEN.grid().points():
            assert MIN_CUTOFF_HZ <= point["cutoff_hz"] <= MAX_CUTOFF_HZ
            assert GEN.envelope(intent(cutoff=point["cutoff_hz"])).accepted

    def test_supply_change_cannot_touch_the_resistor(self):
        # Only the capacitor carries a voltage rating. A conservative closure
        # would be sound and would make the Stage 2 locality check vacuous.
        assert GEN.dependency_closure("constraints.supply_v") == frozenset({"C1"})

    def test_cutoff_change_touches_both_passives(self):
        assert GEN.dependency_closure("targets.cutoff_hz") == frozenset({"R1", "C1"})

    def test_unknown_requirement_falls_back_to_everything(self):
        assert GEN.dependency_closure("something.new") == frozenset({"R1", "C1"})


# ── The Stage 0 gate ─────────────────────────────────────────────────────────

@_skip_no_ngspice
class TestPredictAgainstNgspice:
    """
    The G5 ≤ 2% gate. `predict()` is pinned to the exact component values the
    netlist carries, so this compares a closed-form point against a simulated
    point — not a point against a band it would trivially fall inside.
    """

    def _measure(self, ir, supply_v=5.0):
        points = run_ir(ir).ac_points
        measured = interpolate_cutoff(points, "out", supply_v / math.sqrt(2.0))
        assert measured is not None, "no -3dB crossing found in the sweep"
        return measured

    def _predicted_point(self, target):
        sel = select_components(target, 5.0)
        box = {"R": Interval.at(sel.ohms, "ohm"), "C": Interval.at(sel.farads, "F")}
        return GEN.predict(intent(cutoff=target), box=box).quantities["cutoff_hz"]

    @pytest.mark.parametrize("target", [100.0, 330.0, 1_000.0, 3_300.0, 10_000.0, 33_000.0, 100_000.0])
    def test_predict_matches_ngspice_across_the_declared_grid(self, target):
        ir = GEN.generate(intent(cutoff=target))
        measured = self._measure(ir)
        predicted = self._predicted_point(target)
        error = predicted.relative_error(measured)
        assert error <= TOLERANCE, (
            f"predict() and ngspice disagree at cutoff_hz={target:g}: "
            f"predicted {predicted.nominal:.3f} Hz, measured {measured:.3f} Hz, "
            f"relative error {error:.4%} exceeds the {TOLERANCE:.0%} gate"
        )

    def test_simulated_point_lies_inside_the_tolerance_band(self):
        # The weaker claim, asserted separately so it cannot be mistaken for
        # the gate above. It says the band is not wrong, not that it is tight.
        ir = GEN.generate(intent(cutoff=1_000.0))
        measured = self._measure(ir)
        assert GEN.predict(intent(cutoff=1_000.0)).quantities["cutoff_hz"].contains(measured)

    def test_gate_rejects_a_mismatched_prediction(self):
        # Negative control. A gate that only ever passes tests nothing — the
        # same argument behind the injected-5%-error check in
        # tests/test_simulation_accuracy.py, and 5% is deliberately the size
        # used here too. A large error would prove only that the gate catches
        # large errors; the question worth answering is whether a 2% gate is
        # sharp enough to catch one barely above it.
        #
        # The perturbation is computed from the selected capacitor rather than
        # hardcoded, so it stays a 5% error if the catalogue or the selection
        # rule ever changes.
        sel = select_components(1_000.0, 5.0)
        ir = GEN.generate(intent(cutoff=1_000.0))
        cap = next(c for c in ir.components if c.id == "C1")
        cap.value = f"{sel.farads * 1.05 * 1e9:.6g}nF"

        measured = self._measure(ir)
        predicted = self._predicted_point(1_000.0)
        error = predicted.relative_error(measured)

        assert error > TOLERANCE, (
            f"a 5% capacitor error moved the measured cutoff to {measured:.3f} Hz "
            f"against a predicted {predicted.nominal:.3f} Hz — a {error:.4%} "
            f"deviation that the {TOLERANCE:.0%} gate did not catch. The gate is "
            f"not sharp enough to be worth having."
        )
        # And it fails for the right reason: a bigger capacitor lowers cutoff.
        assert measured < predicted.nominal
