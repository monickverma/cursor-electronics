"""
Stage 1 Task 1.2 — the generator registry and dispatch.

Dispatch is deterministic and keyed on declared envelopes rather than on a
model's judgement, per the formal-verification report's finding that an LLM
adds nothing to solver choice at these tiers. These tests pin that, and pin
the thing the registry exists to protect: **every refusal is kept**, because
§4.5 makes the out-of-envelope log the generator backlog and "nothing accepted
this" is a far weaker entry than the set of reasons.
"""

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from generators.protocol import EnvelopeDecision, GridSpec, PortContract
from generators.rc_lowpass import RCLowPassGenerator
from generators.registry import (
    DispatchResult,
    GeneratorRegistry,
    Refusal,
    default_registry,
)

PORTS = (PortContract(name="P", direction="input"),)


def intent(function="low_pass_filter", **targets) -> IntentIR:
    return IntentIR(
        requirements={
            "function": function,
            "targets": targets or {"cutoff_hz": 1000},
            "constraints": {"supply_v": 5},
        },
        provenance=Provenance(producer=Producer.FORM),
    )


class _Stub:
    """Minimal conforming generator with a scriptable envelope."""

    version = "1.0.0"

    def __init__(self, name, function="low_pass_filter", accept=True, reason="nope", raises=None):
        self.name = name
        self.function = function
        self._accept = accept
        self._reason = reason
        self._raises = raises

    def envelope(self, intent):
        if self._raises:
            raise self._raises
        return EnvelopeDecision.accept(PORTS) if self._accept else EnvelopeDecision.refuse(self._reason)

    def generate(self, intent):
        raise NotImplementedError

    def predict(self, intent, box=None):
        raise NotImplementedError

    def grid(self):
        return GridSpec(axes={"cutoff_hz": [10.0, 1000.0]}, units={"cutoff_hz": "Hz"})

    def dependency_closure(self, requirement_path):
        return frozenset()


class TestRegistration:
    def test_registers_a_conforming_generator(self):
        r = GeneratorRegistry()
        r.register(_Stub("a"))
        assert len(r) == 1
        assert r.by_name("a") is not None

    def test_rejects_a_non_conforming_generator_and_names_the_gaps(self):
        class Broken:
            name = "broken"
            version = "1.0.0"
            function = "low_pass_filter"
            # no envelope/generate/predict/grid/dependency_closure

        with pytest.raises(TypeError) as exc:
            GeneratorRegistry().register(Broken())
        assert "envelope" in str(exc.value) and "predict" in str(exc.value)

    def test_duplicate_names_rejected(self):
        # A design records which generator built it, so names must be unique.
        r = GeneratorRegistry()
        r.register(_Stub("a"))
        with pytest.raises(ValueError, match="already registered"):
            r.register(_Stub("a"))

    def test_registration_order_is_preserved(self):
        r = GeneratorRegistry()
        r.register(_Stub("first"))
        r.register(_Stub("second"))
        assert [g.name for g in r.generators] == ["first", "second"]


class TestCatalogue:
    def test_functions_are_derived_from_the_installed_generators(self):
        r = GeneratorRegistry()
        r.register(_Stub("a", function="low_pass_filter"))
        r.register(_Stub("b", function="voltage_divider"))
        assert r.functions() == ("low_pass_filter", "voltage_divider")

    def test_functions_are_deduplicated_in_first_seen_order(self):
        r = GeneratorRegistry()
        r.register(_Stub("a", function="low_pass_filter"))
        r.register(_Stub("b", function="low_pass_filter"))
        assert r.functions() == ("low_pass_filter",)

    def test_for_function_selects_the_right_generators(self):
        r = GeneratorRegistry()
        r.register(_Stub("a", function="low_pass_filter"))
        r.register(_Stub("b", function="voltage_divider"))
        assert [g.name for g in r.for_function("voltage_divider")] == ["b"]

    def test_default_registry_installs_the_real_generator(self):
        r = default_registry()
        # Stage 3: the five Phase 1 templates, in registration order.
        assert r.functions() == (
            "low_pass_filter", "voltage_divider", "led_indicator",
            "temperature_humidity_sensor", "modbus_rtu_master",
        )
        assert isinstance(r.by_name("rc_lowpass"), RCLowPassGenerator)
        assert [g.name for g in r.generators] == [
            "rc_lowpass", "voltage_divider", "led_indicator", "dht22_node", "rs485_node",
        ]


class TestDispatch:
    def test_dispatches_to_the_accepting_generator(self):
        r = GeneratorRegistry()
        r.register(_Stub("no", accept=False))
        r.register(_Stub("yes", accept=True))
        result = r.dispatch(intent())
        assert result.accepted
        assert result.generator.name == "yes"

    def test_every_refusal_is_collected_not_just_the_first(self):
        # The backlog entry is the set of reasons. "Nothing accepted this"
        # cannot tell "widen an envelope" from "author a generator".
        r = GeneratorRegistry()
        r.register(_Stub("a", accept=False, reason="cutoff_hz out of range"))
        r.register(_Stub("b", accept=False, reason="does not build band-pass"))
        result = r.dispatch(intent())

        assert not result.accepted
        assert len(result.refusals) == 2
        assert Refusal("a", "cutoff_hz out of range") in result.refusals
        assert "does not build band-pass" in result.refusal_summary()

    def test_refusals_are_kept_even_when_one_generator_accepts(self):
        # A request answered by a narrow generator should not hide that a
        # broader one turned it down.
        r = GeneratorRegistry()
        r.register(_Stub("narrow", accept=False, reason="too wide for me"))
        r.register(_Stub("broad", accept=True))
        result = r.dispatch(intent())
        assert result.accepted and len(result.refusals) == 1

    def test_first_registered_wins_and_the_overlap_is_surfaced(self):
        # Not an error, but a catalogue smell: the day the two disagree about
        # a design is not the day to discover they overlap.
        r = GeneratorRegistry()
        r.register(_Stub("first", accept=True))
        r.register(_Stub("second", accept=True))
        result = r.dispatch(intent())
        assert result.generator.name == "first"
        assert result.is_ambiguous
        assert result.also_accepted == ("second",)

    def test_unambiguous_dispatch_is_not_flagged(self):
        r = GeneratorRegistry()
        r.register(_Stub("only", accept=True))
        assert not r.dispatch(intent()).is_ambiguous

    def test_a_generator_that_raises_becomes_a_refusal_not_a_crash(self):
        # envelope() is contracted never to raise. One that does anyway must
        # not take the whole catalogue down with it.
        r = GeneratorRegistry()
        r.register(_Stub("bad", raises=RuntimeError("boom")))
        r.register(_Stub("good", accept=True))
        result = r.dispatch(intent())

        assert result.accepted and result.generator.name == "good"
        assert "RuntimeError: boom" in result.refusals[0].reason
        assert "contracted never to raise" in result.refusals[0].reason

    def test_refusals_are_hashable(self):
        # Defining __eq__ sets __hash__ to None. Deduplicating refusals by
        # reason is the obvious thing to do when ranking the backlog, so the
        # type has to survive being put in a set.
        a, b = Refusal("g", "reason"), Refusal("g", "reason")
        assert len({a, b}) == 1
        assert {a: 1}[b] == 1

    def test_empty_registry_refuses_legibly(self):
        result = GeneratorRegistry().dispatch(intent())
        assert not result.accepted
        assert result.refusal_summary() == "no generators are registered"

    def test_dispatch_is_deterministic(self):
        r = default_registry()
        i = intent()
        first = r.dispatch(i)
        second = r.dispatch(i)
        assert first.generator.name == second.generator.name

    def test_real_registry_refuses_an_unbuilt_function_with_a_usable_reason(self):
        result = default_registry().dispatch(intent(function="band_pass_filter"))
        assert not result.accepted
        assert "band_pass_filter" in result.refusal_summary()

    def test_real_registry_accepts_an_in_envelope_intent(self):
        result = default_registry().dispatch(intent(cutoff_hz=1000))
        assert result.accepted
        assert result.decision.ports
