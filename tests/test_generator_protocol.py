"""
Tests for the Generator contract — Task 0.2, PHASE_2_PLAN_v2.md §5 Stage 0.

Two of these assertions correspond to stated G1 gates and are the reason the
invariants live in validators rather than in a docstring:

  - "`envelope()` refuses out-of-range intents with a named reason" — a
    refusal without one cannot be constructed.
  - the interface contract is mandatory on acceptance, so that composition
    work in Stage 3 does not begin by editing every generator written before it.

The rest pin the value types the five generators will be built against.
"""

import pytest
from pydantic import ValidationError

from core.ir_examples import IR_003
from generators.protocol import (
    ClaimScope,
    EnvelopeDecision,
    Generator,
    GridSpec,
    IntentLike,
    Interval,
    PortContract,
    Prediction,
    conformance_gaps,
    conservative_closure,
)


# ── Stubs ─────────────────────────────────────────────────────────────────────

class _Intent:
    """Stands in for Stage 1's IntentIR. v2 §6 shape, only what a generator reads."""

    def __init__(self, **requirements):
        self._requirements = requirements or {
            "function": "low_pass_filter",
            "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
            "constraints": {"supply_v": 5, "source_impedance_ohm": 50},
            "preferences": {"package": "0603"},
        }

    @property
    def requirements(self):
        return self._requirements


_PORTS = (
    PortContract(name="vin", direction="input",
                 impedance_ohm=Interval(lo=1574, hi=1606, nominal=1590, units="ohm")),
    PortContract(name="vout", direction="output"),
)


class _ConformingGenerator:
    name = "rc_lowpass"
    version = "0.1.0"
    function = "low_pass_filter"

    def envelope(self, intent):
        hz = intent.requirements.get("targets", {}).get("cutoff_hz", 0)
        if not 10 <= hz <= 100_000:
            return EnvelopeDecision.refuse(
                f"cutoff_hz={hz} outside declared envelope 10 Hz – 100 kHz"
            )
        return EnvelopeDecision.accept(_PORTS)

    def generate(self, intent):
        return IR_003

    def predict(self, intent, box=None):
        return Prediction(
            quantities={"cutoff_hz": Interval(lo=900.0, hi=1125.0, nominal=1000.7, units="Hz")},
            scope=ClaimScope(model="mna_ideal"),
            method="monotone_corners",
        )

    def grid(self):
        return GridSpec(axes={"cutoff_hz": [100.0, 1000.0, 10000.0]}, units={"cutoff_hz": "Hz"})

    def dependency_closure(self, requirement_path):
        return conservative_closure(IR_003)


class _MissingPredict:
    name = "broken"
    version = "0.1.0"
    function = "low_pass_filter"

    def envelope(self, intent):
        return EnvelopeDecision.refuse("nope")

    def generate(self, intent):
        return IR_003

    def grid(self):
        return GridSpec(axes={"x": [1.0]})

    def dependency_closure(self, requirement_path):
        return frozenset()


# ── Interval ─────────────────────────────────────────────────────────────────

class TestInterval:
    def test_valid_interval(self):
        iv = Interval(lo=900, hi=1125, nominal=1000.7, units="Hz")
        assert iv.contains(1000.7)
        assert not iv.contains(1200)

    def test_lo_above_hi_rejected(self):
        with pytest.raises(ValidationError):
            Interval(lo=10, hi=1, nominal=5, units="Hz")

    def test_nominal_outside_band_rejected(self):
        # A nominal outside its own tolerance band is a generator bug. Catching
        # it here is cheaper than explaining a nonsensical claim later.
        with pytest.raises(ValidationError):
            Interval(lo=900, hi=1100, nominal=1500, units="Hz")

    def test_at_builds_a_point(self):
        iv = Interval.at(1000.0, "Hz")
        assert iv.is_point and iv.contains(1000.0)

    def test_relative_error_zero_inside_band(self):
        iv = Interval(lo=900, hi=1125, nominal=1000, units="Hz")
        assert iv.relative_error(1100) == 0.0

    def test_relative_error_measured_from_nearest_edge(self):
        iv = Interval(lo=900, hi=1000, nominal=950, units="Hz")
        assert iv.relative_error(1020) == pytest.approx(0.02)
        assert iv.relative_error(882) == pytest.approx(0.02)

    def test_interval_is_frozen(self):
        iv = Interval(lo=1, hi=2, nominal=1.5, units="V")
        with pytest.raises(ValidationError):
            iv.lo = 0

    @pytest.mark.parametrize("kwargs", [
        {"lo": float("inf"), "hi": float("inf"), "nominal": float("inf")},
        {"lo": 0.0, "hi": float("inf"), "nominal": 1.0},
        {"lo": float("-inf"), "hi": 1.0, "nominal": 0.0},
    ])
    def test_infinite_interval_rejected(self, kwargs):
        # Infinities satisfy both ordering checks and would otherwise reach a
        # claim object looking like an answer. An unbounded quantity means a
        # divide-by-zero upstream, not a wide band.
        with pytest.raises(ValidationError):
            Interval(units="Hz", **kwargs)

    def test_nan_interval_rejected(self):
        with pytest.raises(ValidationError):
            Interval(lo=float("nan"), hi=1.0, nominal=1.0, units="Hz")

    def test_at_rejects_infinity(self):
        with pytest.raises(ValidationError):
            Interval.at(float("inf"), "Hz")


# ── ClaimScope ───────────────────────────────────────────────────────────────

class TestClaimScope:
    def test_model_is_required(self):
        # EVIDENCE_CLASSES §3.3: an undeclared model is how a G1 proof over an
        # unvalidated model gets presented as ground truth. X6 and defeater D2
        # both hang off this field.
        with pytest.raises(ValidationError):
            ClaimScope()

    def test_defaults_are_the_conservative_reading(self):
        scope = ClaimScope(model="mna_ideal")
        assert scope.parameters == "tolerance_box"
        assert scope.horizon == "steady_state"
        assert scope.inputs == "single_stimulus"

    def test_mcu_model_is_expressible(self):
        assert ClaimScope(model="mcu_as_100R").model == "mcu_as_100R"


# ── EnvelopeDecision — the two G1 invariants ─────────────────────────────────

class TestEnvelopeDecision:
    def test_refusal_requires_a_reason(self):
        with pytest.raises(ValidationError):
            EnvelopeDecision(accepted=False)

    def test_refusal_with_blank_reason_rejected(self):
        with pytest.raises(ValidationError):
            EnvelopeDecision(accepted=False, reason="   ")

    def test_refuse_helper_carries_the_reason(self):
        d = EnvelopeDecision.refuse("cutoff_hz=2e6 outside declared envelope")
        assert d.accepted is False
        assert "2e6" in d.reason

    def test_acceptance_requires_ports(self):
        # If the interface contract were optional it would be skipped, and the
        # composition work in Stage 3 would start by editing all five generators.
        with pytest.raises(ValidationError):
            EnvelopeDecision(accepted=True)

    def test_accept_helper_carries_ports(self):
        d = EnvelopeDecision.accept(_PORTS)
        assert d.accepted is True
        assert [p.name for p in d.ports] == ["vin", "vout"]

    def test_port_contract_carries_the_three_declared_fields(self):
        p = PortContract(
            name="vcc",
            direction="power",
            impedance_ohm=Interval(lo=0.1, hi=0.5, nominal=0.2, units="ohm"),
            current_draw_a=Interval(lo=0.04, hi=0.06, nominal=0.05, units="A"),
            voltage_range_v=Interval(lo=4.75, hi=5.25, nominal=5.0, units="V"),
        )
        assert p.impedance_ohm and p.current_draw_a and p.voltage_range_v


# ── Prediction ───────────────────────────────────────────────────────────────

class TestPrediction:
    def test_prediction_requires_scope(self):
        with pytest.raises(ValidationError):
            Prediction(quantities={"cutoff_hz": Interval.at(1000, "Hz")})

    def test_empty_prediction_rejected(self):
        with pytest.raises(ValidationError):
            Prediction(quantities={}, scope=ClaimScope(model="mna_ideal"))

    def test_prediction_is_a_band_not_a_point(self):
        # The whole of X1 in one assertion: predict() states something about
        # every component value in tolerance, not about one nominal run.
        p = _ConformingGenerator().predict(_Intent())
        band = p.quantities["cutoff_hz"]
        assert not band.is_point
        assert band.contains(1000.7)

    def test_method_is_recorded(self):
        p = _ConformingGenerator().predict(_Intent())
        assert p.method == "monotone_corners"


# ── GridSpec ─────────────────────────────────────────────────────────────────

class TestGridSpec:
    def test_points_are_the_cartesian_product(self):
        g = GridSpec(axes={"r": [1.0, 2.0], "c": [10.0, 20.0, 30.0]})
        points = list(g.points())
        assert len(points) == 6 == g.size
        assert {"r": 1.0, "c": 30.0} in points

    def test_empty_grid_rejected(self):
        with pytest.raises(ValidationError):
            GridSpec(axes={})

    def test_axis_with_no_values_rejected(self):
        with pytest.raises(ValidationError):
            GridSpec(axes={"r": []})


# ── Conformance ──────────────────────────────────────────────────────────────

class TestConformance:
    def test_conforming_generator_satisfies_the_protocol(self):
        assert isinstance(_ConformingGenerator(), Generator)

    def test_conforming_generator_has_no_gaps(self):
        assert conformance_gaps(_ConformingGenerator()) == []

    def test_non_conforming_generator_fails(self):
        assert not isinstance(_MissingPredict(), Generator)

    def test_gaps_name_what_is_missing(self):
        # A registry that says "not a Generator" makes the author guess. The
        # gap list is what Stage 1 dispatch will surface.
        assert conformance_gaps(_MissingPredict()) == ["predict"]

    def test_gaps_agree_with_isinstance_on_non_callable_members(self):
        # A hasattr-only check reported no gaps for this object while
        # isinstance correctly refused it — the worst combination for whoever
        # reads the registry's error in Stage 1.
        class AllNames:
            name = version = function = None
            envelope = generate = predict = grid = dependency_closure = None

        candidate = AllNames()
        assert not isinstance(candidate, Generator)
        assert conformance_gaps(candidate) != []
        assert set(conformance_gaps(candidate)) == {
            "envelope", "generate", "predict", "grid", "dependency_closure",
        }

    def test_arbitrary_object_is_not_a_generator(self):
        assert not isinstance(object(), Generator)
        assert set(conformance_gaps(object())) == {
            "name", "version", "function", "envelope", "generate", "predict",
            "grid", "dependency_closure",
        }

    def test_intent_stub_satisfies_intent_like(self):
        assert isinstance(_Intent(), IntentLike)


# ── Behaviour of a conforming generator ──────────────────────────────────────

class TestGeneratorBehaviour:
    def test_in_envelope_intent_is_accepted_with_ports(self):
        d = _ConformingGenerator().envelope(_Intent())
        assert d.accepted and d.ports

    def test_out_of_envelope_intent_is_refused_with_a_named_reason(self):
        intent = _Intent(function="low_pass_filter", targets={"cutoff_hz": 2_000_000})
        d = _ConformingGenerator().envelope(intent)
        assert d.accepted is False
        assert "outside declared envelope" in d.reason

    def test_refusal_reason_is_specific_enough_to_be_a_backlog_entry(self):
        # §4.5: the out-of-envelope log is the generator backlog. A reason that
        # does not name the offending value cannot be ranked or acted on.
        intent = _Intent(function="low_pass_filter", targets={"cutoff_hz": 2_000_000})
        reason = _ConformingGenerator().envelope(intent).reason
        assert "2000000" in reason.replace("_", "") or "2e" in reason.lower()

    def test_grid_is_declared_by_the_generator(self):
        assert _ConformingGenerator().grid().size == 3

    def test_conservative_closure_covers_every_component(self):
        closure = _ConformingGenerator().dependency_closure("targets.cutoff_hz")
        assert closure == frozenset(c.id for c in IR_003.components)
        assert len(closure) > 0
