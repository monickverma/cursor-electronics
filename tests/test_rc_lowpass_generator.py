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
           source_impedance_ohm=50.0, pinned=None, **extra):
    targets = {"tolerance_pct": tolerance_pct}
    if cutoff is not None:
        targets["cutoff_hz"] = cutoff
    constraints = {"supply_v": supply_v, "source_impedance_ohm": source_impedance_ohm}
    if pinned is not None:
        constraints["pinned"] = pinned
    return _Intent(
        function=function,
        targets=targets,
        constraints=constraints,
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

    @pytest.mark.parametrize("supply", [-5.0, 0.0, float("inf"), float("nan")])
    def test_unusable_supply_is_refused_not_raised(self, supply):
        # envelope() is contracted never to raise. A negative or non-finite
        # supply reaches _ports() as Interval(lo=0, hi=supply), which Pydantic
        # rejects — turning a bad intent into a crash instead of a named
        # refusal, in the one method whose job is to say no cleanly.
        d = GEN.envelope(intent(cutoff=1000.0, supply_v=supply))
        assert d.accepted is False
        assert "rail voltage" in d.reason


class TestInputsAreReadStrictly:
    """
    0.2.1. Found by the Stage 2 verification: a requirement that was present
    but not a number was read as the default, and `True` was read as 1.
    `supply_v: "12"` built a 5 V design, `tolerance_pct: "1"` loosened to 5%,
    and `tolerance_pct: NaN` accepted every design because every comparison
    with NaN is false. A value that was written is honoured or refused by
    name — never replaced.
    """

    FIELDS = {
        "cutoff": "targets.cutoff_hz",
        "tolerance_pct": "targets.tolerance_pct",
        "supply_v": "constraints.supply_v",
        "source_impedance_ohm": "constraints.source_impedance_ohm",
    }

    @pytest.mark.parametrize("field", list(FIELDS))
    @pytest.mark.parametrize("value", [True, False, "12", "1 kHz", [5], {"v": 5},
                                       float("nan"), float("inf"), -5.0])
    def test_an_unusable_value_is_refused_by_name(self, field, value):
        d = GEN.envelope(intent(**{field: value}))
        assert d.accepted is False
        assert self.FIELDS[field] in d.reason, d.reason

    @pytest.mark.parametrize("field", ["cutoff", "tolerance_pct", "supply_v"])
    def test_zero_is_refused_where_it_means_nothing(self, field):
        d = GEN.envelope(intent(**{field: 0}))
        assert d.accepted is False and self.FIELDS[field] in d.reason

    def test_zero_source_impedance_is_an_ideal_source_and_is_accepted(self):
        assert GEN.envelope(intent(source_impedance_ohm=0)).accepted

    def test_a_string_supply_is_not_built_at_the_default(self):
        # The worst of the four: accepted, and silently a different circuit.
        d = GEN.envelope(intent(supply_v="12"))
        assert d.accepted is False
        assert "'12'" in d.reason and "not a number" in d.reason

    def test_a_nan_tolerance_no_longer_accepts_everything(self):
        assert not GEN.envelope(intent(tolerance_pct=float("nan"))).accepted

    def test_null_means_absent_and_takes_the_default(self):
        explicit = intent(tolerance_pct=5.0, supply_v=5.0, source_impedance_ohm=0.0)
        nulls = intent(tolerance_pct=None, supply_v=None, source_impedance_ohm=None)
        assert GEN.envelope(nulls).accepted
        assert GEN.generate(nulls).model_dump(exclude={"circuit_id"}) == \
            GEN.generate(explicit).model_dump(exclude={"circuit_id"})

    def test_ints_and_floats_are_the_same_number(self):
        a = GEN.generate(intent(cutoff=1000, supply_v=5, tolerance_pct=5))
        b = GEN.generate(intent(cutoff=1000.0, supply_v=5.0, tolerance_pct=5.0))
        assert a.model_dump(exclude={"circuit_id"}) == b.model_dump(exclude={"circuit_id"})


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

    @pytest.mark.parametrize("bad", [
        {"function": "band_pass_filter"},          # not what this generator builds
        {"cutoff": 2_000_000.0},                   # outside the declared envelope
        {"tolerance_pct": 0.1},                    # tighter than E96 can deliver
        {"supply_v": 100.0},                       # beyond every capacitor rating
    ])
    def test_predict_will_not_produce_a_claim_outside_the_envelope(self, bad):
        # predict() used to check only that a cutoff and a catalogue pair
        # existed, so a caller could get a confident band for an intent the
        # generator had already refused. A claim outside the declared envelope
        # is precisely what envelope() exists to prevent, and it would be
        # indistinguishable from a real one downstream.
        i = intent(**bad)
        assert GEN.envelope(i).accepted is False
        with pytest.raises(ValueError, match="refused intent"):
            GEN.predict(i)

    def test_predict_still_works_for_an_accepted_intent(self):
        assert GEN.predict(intent(cutoff=1000.0)).quantities["cutoff_hz"].nominal > 0


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

    def test_supply_change_can_reach_the_resistor(self):
        # Stage 0 declared {C1}: only the capacitor carries a rating. The
        # Stage 2 locality sweep showed that a supply above 16 V drops the
        # 100 nF part, picks another capacitor and re-snaps R1 around it.
        assert GEN.dependency_closure("constraints.supply_v") == frozenset({"R1", "C1"})
        at_5v = select_components(1_000.0, 5.0)
        at_20v = select_components(1_000.0, 20.0)
        assert at_5v.c_value != at_20v.c_value
        assert at_5v.ohms != at_20v.ohms

    def test_source_impedance_reaches_both_parts(self):
        # 0.2.3: a source too large for the closest pair swaps the capacitor to
        # raise R1, so the path can reach C1. A closure that is too narrow is
        # worse than a wide one, because it is believed.
        assert GEN.dependency_closure("constraints.source_impedance_ohm") == frozenset({"R1", "C1"})


class TestSourceIsSwamped:
    """
    0.2.3. A declared source that would move f_c past tolerance is swamped by
    a larger R1 — a smaller catalogue capacitor — and refused only when no
    pair manages it. Chosen over compensating R1 by R_s after a TypeSafe
    consultation: brain/decisions.md [2026-09-23].
    """

    @pytest.mark.parametrize("target", [10.0, 100.0, 1_000.0, 10_000.0, 100_000.0])
    @pytest.mark.parametrize("source", [0.0, 25.0, 50.0])
    def test_a_design_that_already_passed_is_unchanged(self, target, source):
        plain = select_components(target, 5.0)
        with_source = select_components(target, 5.0, None, None, source, 5.0)
        if source / (plain.ohms + source) <= 0.05:
            assert (with_source.ohms, with_source.c_value) == (plain.ohms, plain.c_value)

    def test_a_600_ohm_line_source_at_1khz_is_swamped(self):
        spec = intent(cutoff=1_000.0, source_impedance_ohm=600.0)
        assert GEN.envelope(spec).accepted
        parts = {c.id: c for c in GEN.generate(spec).components}
        plain = select_components(1_000.0, 5.0)
        assert parts["C1"].value != plain.c_value                 # a smaller capacitor…
        r1 = float(parts["R1"].value.rstrip("Ω"))
        assert r1 > plain.ohms                                     # …and a larger R1
        assert 600.0 / (r1 + 600.0) <= 0.05

    def test_a_source_nothing_can_swamp_is_refused_by_name(self):
        decision = GEN.envelope(intent(cutoff=1_000.0, source_impedance_ohm=10_000.0))
        assert not decision.accepted
        assert "lowers f_c" in decision.reason and "swamp" in decision.reason

    def test_nothing_is_swapped_around_a_pin(self):
        decision = GEN.envelope(intent(cutoff=1_000.0, source_impedance_ohm=600.0,
                                       pinned={"C1": "100n"}))
        assert not decision.accepted and "pinned" in decision.reason

    def test_a_nested_path_resolves_through_its_declared_prefix(self):
        assert GEN.dependency_closure("constraints.pinned.R1") == frozenset({"R1", "C1"})

    def test_cutoff_change_touches_both_passives(self):
        assert GEN.dependency_closure("targets.cutoff_hz") == frozenset({"R1", "C1"})

    def test_unknown_requirement_falls_back_to_everything(self):
        assert GEN.dependency_closure("something.new") == frozenset({"R1", "C1"})


# ── Pinned parts (0.2.0) ─────────────────────────────────────────────────────

class TestPinnedParts:
    """
    `constraints.pinned` — "use the part in my drawer". Stage 2 decision,
    item 6: a generator honours every pin or refuses naming it.
    """

    def _parts(self, ir):
        return {c.id: c for c in ir.components}

    def test_a_pinned_resistor_is_used_as_given(self):
        # 4.7 k is not an E96 value, so an unpinned run could never pick it.
        req = intent(cutoff=3_386.0, pinned={"R1": "4.7k"})
        assert GEN.envelope(req).accepted
        r1 = self._parts(GEN.generate(req))["R1"]
        assert float(r1.value) == 4_700.0
        assert "pinned" in r1.justification

    def test_the_capacitor_is_chosen_around_a_pinned_resistor(self):
        req = intent(cutoff=3_386.0, pinned={"R1": 4700})
        parts = self._parts(GEN.generate(req))
        assert parts["C1"].value == "10nF"   # 1/(2π·4.7k·10n) = 3386 Hz

    def test_a_pinned_capacitor_restricts_the_catalogue(self):
        req = intent(cutoff=1_000.0, pinned={"C1": "10nF"})
        parts = self._parts(GEN.generate(req))
        assert parts["C1"].value == "10nF"
        assert float(parts["R1"].value) == snap_to_e96(1 / (2 * math.pi * 1_000.0 * 10e-9))

    def test_pins_parse_the_way_the_netlist_reads_them(self):
        # Same parser as the SPICE generator, so "4k7" means 4700 in both.
        for spelling in ("4.7k", "4k7", "4700", 4700.0):
            req = intent(cutoff=3_386.0, pinned={"R1": spelling})
            assert float(self._parts(GEN.generate(req))["R1"].value) == 4_700.0

    def test_a_pin_the_target_cannot_tolerate_is_refused_with_numbers(self):
        decision = GEN.envelope(intent(cutoff=1_000.0, pinned={"R1": "4.7k"}))
        assert not decision.accepted
        assert "pinned pair" in decision.reason and "tolerance_pct" in decision.reason

    @pytest.mark.parametrize("pinned, fragment", [
        ({"L1": "10uH"}, "L1"),
        ({"R1": "banana"}, "not a resistance"),
        ({"R1": "100"}, "series window"),
        ({"C1": "3.3nF"}, "not in this generator's capacitor catalogue"),
        ({"C1": "1uF"}, "rated 6.3V"),
        ("R1=4.7k", "must map part ids"),
    ])
    def test_an_unhonourable_pin_is_refused_by_name(self, pinned, fragment):
        decision = GEN.envelope(intent(cutoff=1_000.0, supply_v=12.0, pinned=pinned))
        assert not decision.accepted
        assert fragment in decision.reason

    def test_envelope_never_raises_on_a_bad_pin(self):
        for pinned in ({"R1": None}, {"R1": True}, {"C1": ""}, {"R1": float("nan")}, {"R1": -1}):
            assert not GEN.envelope(intent(pinned=pinned)).accepted

    def test_predict_follows_the_pinned_parts(self):
        req = intent(cutoff=3_386.0, pinned={"R1": "4.7k"})
        band = GEN.predict(req).quantities["resistance_ohm"]
        assert band.nominal == 4_700.0

    def test_unpinned_output_is_what_0_1_0_produced(self):
        # The version bump is for the wider envelope, not for new output on an
        # old intent. Checked in full against a git checkout of 0.1.0 while
        # building (150 accepted intents, zero differences); this spot-checks
        # the justification text, which was restructured to carry the pin.
        parts = self._parts(GEN.generate(intent(cutoff=1_000.0)))
        assert ", nearest E96 (1%) value to the " in parts["R1"].justification
        assert "Chosen first because it puts R1 inside" in parts["C1"].justification
        assert "pinned" not in parts["R1"].justification + parts["C1"].justification


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
