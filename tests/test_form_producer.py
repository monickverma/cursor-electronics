"""
Stage 1 Task 1.3 — the form producer.

The Stage 1 gate: *"Form produces valid IntentIR for all five generators, 0 API
calls."* One generator is installed, so the claim this file actually supports
is "for every installed generator" — the count follows the library, and Stage 3
adds the rest.

What the tests are really protecting is §4.2's two consequences: the system is
**provably LLM-optional**, and the catalogue is **derived** from what is
installed rather than maintained beside it.
"""

import pytest

from ai.form_producer import FormProducer, FormSpec
from core.intent_ir import IntentIR, Producer
from generators.protocol import EnvelopeDecision, GridSpec, IntentLike, PortContract
from generators.registry import GeneratorRegistry, default_registry


class _Stub:
    version = "1.0.0"

    def __init__(self, name, function, axes):
        self.name = name
        self.function = function
        self._axes = axes

    def envelope(self, intent):
        return EnvelopeDecision.accept((PortContract(name="P", direction="input"),))

    def generate(self, intent):
        raise NotImplementedError

    def predict(self, intent, box=None):
        raise NotImplementedError

    def grid(self):
        return GridSpec(axes=self._axes, units={k: "Hz" for k in self._axes})

    def dependency_closure(self, requirement_path):
        return frozenset()


class TestCatalogueIsDerived:
    def test_catalogue_comes_from_the_installed_generators(self):
        # A hand-maintained "what we support" list is the stale-copy failure
        # this project keeps hitting, one layer out. Here it is not expressible.
        producer = FormProducer()
        assert tuple(s.function for s in producer.catalogue()) == default_registry().functions()
        # Stage 3: all five Phase 1 templates are back in coverage.
        assert len(producer.catalogue()) == 5

    def test_field_ranges_come_from_the_declared_grid(self):
        spec = FormProducer().spec_for("low_pass_filter")
        cutoff = next(f for f in spec.fields if f.name == "cutoff_hz")
        assert (cutoff.minimum, cutoff.maximum) == (100.0, 100_000.0)
        assert cutoff.units == "Hz"

    def test_grid_derived_ranges_are_marked_as_ci_exercised(self):
        # The grid is what CI sweeps; the envelope may accept beyond it.
        # Showing grid bounds is conservative, and the flag says which is which
        # rather than leaving the reader to assume the bounds are hard limits.
        spec = FormProducer().spec_for("low_pass_filter")
        cutoff = next(f for f in spec.fields if f.name == "cutoff_hz")
        supply = next(f for f in spec.fields if f.name == "supply_v")
        assert cutoff.exercised_in_ci is True
        assert supply.exercised_in_ci is False

    def test_ranges_union_across_generators_sharing_a_function(self):
        # One covering 10-100 Hz and another 100 Hz-100 kHz means the function
        # is offered across both; dispatch decides which takes a request.
        registry = GeneratorRegistry()
        registry.register(_Stub("low", "low_pass_filter", {"cutoff_hz": [10.0, 100.0]}))
        registry.register(_Stub("high", "low_pass_filter", {"cutoff_hz": [100.0, 100_000.0]}))
        spec = FormProducer(registry).spec_for("low_pass_filter")
        cutoff = next(f for f in spec.fields if f.name == "cutoff_hz")
        assert (cutoff.minimum, cutoff.maximum) == (10.0, 100_000.0)
        assert set(spec.generators) == {"low", "high"}

    def test_a_grid_axis_shadowing_a_universal_field_appears_once(self):
        # Two fields with the same name meant build() keyed by name and kept
        # the last, routing the value into the wrong section and losing the
        # declared range. The generator's own declaration wins: it is the one
        # that knows the range it sweeps.
        registry = GeneratorRegistry()
        registry.register(_Stub("c", "thing", {"supply_v": [1.0, 50.0]}))
        spec = FormProducer(registry).spec_for("thing")

        names = [f.name for f in spec.fields]
        assert names.count("supply_v") == 1
        supply = next(f for f in spec.fields if f.name == "supply_v")
        assert supply.section == "targets"
        assert (supply.minimum, supply.maximum) == (1.0, 50.0)

    def test_unknown_function_names_what_is_available(self):
        with pytest.raises(ValueError, match="low_pass_filter"):
            FormProducer().spec_for("band_pass_filter")

    def test_targets_constraints_and_preferences_stay_separated(self):
        # A form that flattened them would let a preference silently become a
        # target, and predict() is only ever checked against targets.
        spec = FormProducer().spec_for("low_pass_filter")
        sections = {f.name: f.section for f in spec.fields}
        assert sections["cutoff_hz"] == "targets"
        assert sections["supply_v"] == "constraints"


class TestProducesValidIntent:
    def test_builds_a_valid_intent_with_zero_api_calls(self, monkeypatch):
        # §4.2's claim is that the form needs no model. If this ever starts
        # calling one, "provably LLM-optional" quietly stops being true.
        import ai.client

        monkeypatch.setattr(
            ai.client, "make_client",
            lambda *a, **k: pytest.fail("the form producer made an API call"),
        )
        intent = FormProducer().build("low_pass_filter", {
            "cutoff_hz": 1000, "supply_v": 5, "tolerance_pct": 5,
        })
        assert isinstance(intent, IntentIR)
        assert intent.is_answerable

    def test_records_form_provenance(self):
        intent = FormProducer().build("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5})
        assert intent.provenance.producer == Producer.FORM
        assert intent.provenance.model is None

    def test_result_satisfies_the_generator_protocol(self):
        intent = FormProducer().build("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5})
        assert isinstance(intent, IntentLike)

    def test_every_installed_generator_accepts_a_form_built_intent(self):
        # The Stage 1 gate, scoped to what is installed.
        registry = default_registry()
        producer = FormProducer(registry)
        for spec in producer.catalogue():
            # Values from the generator's own first grid point, which CI
            # sweeps, plus a 5 V rail where the grid does not set one.
            generator = registry.for_function(spec.function)[0]
            values = dict(next(iter(generator.grid().points())))
            values.setdefault("supply_v", 5)
            intent = producer.build(spec.function, values)
            assert intent.is_answerable, (spec.function, intent.open_questions())
            assert registry.dispatch(intent).accepted, (spec.function, registry.dispatch(intent).refusal_summary())

    def test_form_built_intent_drives_a_real_generation(self):
        registry = default_registry()
        intent = FormProducer(registry).build(
            "low_pass_filter", {"cutoff_hz": 3300, "supply_v": 5}
        )
        result = registry.dispatch(intent)
        ir = result.generator.generate(intent)
        prediction = result.generator.predict(intent)

        assert ir.constraints["cutoff_hz"] == 3300
        assert prediction.quantities["cutoff_hz"].contains(3319.878)


class TestIncompleteInput:
    def test_missing_required_field_becomes_a_question_not_an_error(self):
        # Stage 1 gate: underdetermined non-empty -> ask, never generate. A
        # half-filled form is a question to put back, not a failure.
        intent = FormProducer().build("low_pass_filter", {"supply_v": 5})
        assert not intent.is_answerable
        assert "targets.cutoff_hz" in intent.open_questions()

    def test_optional_fields_do_not_become_questions(self):
        intent = FormProducer().build("low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5})
        assert intent.open_questions() == []

    def test_explicit_none_is_treated_as_unanswered(self):
        intent = FormProducer().build(
            "low_pass_filter", {"cutoff_hz": None, "supply_v": 5}
        )
        assert "targets.cutoff_hz" in intent.open_questions()
        assert "cutoff_hz" not in intent.requirements["targets"]

    def test_unknown_field_is_rejected_in_strict_mode(self):
        # A typo landing in requirements would be read by no generator and
        # would look like the user never asked for it.
        with pytest.raises(ValueError, match="does not take"):
            FormProducer().build("low_pass_filter", {"cutof_hz": 1000, "supply_v": 5})

    def test_unknown_field_becomes_a_preference_when_not_strict(self):
        intent = FormProducer().build(
            "low_pass_filter", {"cutoff_hz": 1000, "supply_v": 5, "colour": "red"},
            strict=False,
        )
        assert intent.requirements["preferences"]["colour"] == "red"
