"""
Stage 1 Task 1.1 — the IntentIR schema.

`ARCHITECTURE_ASSURANCE_CASE.md` §2 rests the whole architecture on one
analytic claim: only this architecture materializes the requirement as an
artifact that exists before the design. These tests hold the artifact to what
that claim needs of it — that it is readable by the generators frozen in Task
0.2, that an incomplete specification cannot be signed, and that a signature
cannot survive an edit to the thing it signed.
"""

import pytest
from pydantic import ValidationError

from core.intent_ir import (
    SCHEMA_VERSION,
    IntentIR,
    Producer,
    Provenance,
    Requirements,
    SignOff,
)
from generators.protocol import IntentLike
from generators.rc_lowpass import RCLowPassGenerator

FORM = Provenance(producer=Producer.FORM)


def make(**overrides) -> IntentIR:
    payload = {
        "requirements": {
            "function": "low_pass_filter",
            "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
            "constraints": {"supply_v": 5, "source_impedance_ohm": 50},
            "preferences": {"package": "0402"},
        },
        "provenance": FORM,
    }
    payload.update(overrides)
    return IntentIR(**payload)


class TestSchema:
    def test_matches_the_shape_the_plan_specifies(self):
        intent = make()
        assert intent.schema_version == SCHEMA_VERSION == "2.0.0"
        assert intent.intent_id
        assert intent.underdetermined == []
        assert intent.signed_off is None

    def test_requirements_are_validated_even_though_stored_as_a_mapping(self):
        with pytest.raises(ValidationError):
            make(requirements={"targets": {"cutoff_hz": 1000}})  # no function

    def test_unknown_requirement_section_rejected(self):
        with pytest.raises(ValidationError):
            make(requirements={"function": "low_pass_filter", "targts": {}})

    def test_blank_function_rejected(self):
        with pytest.raises(ValidationError):
            Requirements(function="   ")

    def test_unknown_top_level_field_rejected(self):
        with pytest.raises(ValidationError):
            make(intnet_id="typo")

    def test_non_json_requirements_are_rejected_at_construction(self):
        # `requirements` is typed Any, so a set validates fine and then blows
        # up inside requirements_hash() — sign-off and the §4.4 cache key —
        # and again when the request log serialises the intent. Failing here
        # names the field; failing there is a bare TypeError from elsewhere.
        with pytest.raises(ValidationError, match="JSON-serialisable"):
            make(requirements={"function": "f", "targets": {"x": {1, 2}}})

    def test_intent_is_frozen(self):
        # An editable record makes property_hash meaningless and the Stage 2
        # patch chain unreadable.
        with pytest.raises(ValidationError):
            make().requirements = {}

    def test_provenance_is_required(self):
        with pytest.raises(ValidationError):
            IntentIR(requirements={"function": "low_pass_filter"})

    def test_llm_provenance_must_name_its_model(self):
        # Without it a later claim cannot be attributed or reproduced.
        with pytest.raises(ValidationError):
            Provenance(producer=Producer.LLM)
        assert Provenance(producer=Producer.LLM, model="some-model").model

    def test_form_provenance_needs_no_model(self):
        assert Provenance(producer=Producer.FORM).model is None


class TestGeneratorsCanReadIt:
    def test_satisfies_the_intent_like_protocol(self):
        # The Task 0.2 protocol types `requirements` as a Mapping. If this
        # stops holding, every generator needs editing — which is the cost
        # freezing the protocol early was meant to avoid.
        assert isinstance(make(), IntentLike)

    def test_a_real_generator_accepts_it_end_to_end(self):
        intent = make()
        generator = RCLowPassGenerator()

        assert generator.envelope(intent).accepted
        ir = generator.generate(intent)
        prediction = generator.predict(intent)

        assert {c.id for c in ir.components} == {"R1", "C1"}
        assert prediction.quantities["cutoff_hz"].contains(996.0)

    def test_generator_refuses_an_out_of_envelope_intent(self):
        intent = make(requirements={
            "function": "low_pass_filter", "targets": {"cutoff_hz": 2_000_000},
        })
        decision = RCLowPassGenerator().envelope(intent)
        assert decision.accepted is False
        assert "outside declared envelope" in decision.reason


class TestUnderdetermined:
    def test_complete_intent_is_answerable(self):
        assert make().is_answerable

    def test_missing_field_makes_it_unanswerable(self):
        # Stage 1 gate: underdetermined non-empty -> ask, never generate.
        intent = make(underdetermined=["constraints.supply_v"])
        assert not intent.is_answerable
        assert intent.open_questions() == ["constraints.supply_v"]

    def test_unnamed_gap_rejected(self):
        # "Something is missing" cannot be turned into a question.
        with pytest.raises(ValidationError):
            make(underdetermined=["  "])

    def test_questions_keep_their_declared_order(self):
        intent = make(underdetermined=["targets.cutoff_hz", "constraints.supply_v"])
        assert intent.open_questions() == ["targets.cutoff_hz", "constraints.supply_v"]


class TestSignOff:
    def test_signing_pins_the_requirements(self):
        intent = make().sign_off(by="user-1")
        assert intent.is_signed
        assert intent.signed_off.property_hash == intent.requirements_hash()
        assert intent.is_intact()

    def test_signature_records_who_and_when(self):
        signed = make().sign_off(by="user-1")
        assert signed.signed_off.by == "user-1"
        assert signed.signed_off.at.startswith("20")

    def test_anonymous_sign_off_rejected(self):
        with pytest.raises(ValidationError):
            SignOff(by="  ", property_hash="x")

    def test_cannot_sign_an_incomplete_specification(self):
        # A signature on a spec that is still missing pieces looks like
        # agreement, which is what sign-off exists to prevent.
        intent = make(underdetermined=["constraints.supply_v"])
        with pytest.raises(ValueError, match="ask first"):
            intent.sign_off(by="user-1")

    def test_cannot_construct_a_signed_and_underdetermined_intent(self):
        # Blocked at the schema too, not only at the helper.
        with pytest.raises(ValidationError):
            make(
                underdetermined=["constraints.supply_v"],
                signed_off=SignOff(by="u", property_hash="x"),
            )

    def test_unsigned_intent_is_vacuously_intact(self):
        assert make().is_intact()

    def test_editing_requirements_drops_the_signature(self):
        # Changed requirements are by definition not the ones agreed to.
        # Carrying a sign-off across an edit is the weakening Stage 4's freeze
        # exists to stop; defeater D-B.
        signed = make().sign_off(by="user-1")
        edited = signed.with_requirements(
            {"function": "low_pass_filter", "targets": {"cutoff_hz": 2000}}
        )
        assert signed.is_signed
        assert not edited.is_signed
        assert edited.is_intact()

    def test_tampering_with_a_signed_copy_is_detectable(self):
        signed = make().sign_off(by="user-1")
        forged = signed.model_copy(update={
            "requirements": {"function": "low_pass_filter", "targets": {"cutoff_hz": 9999}}
        })
        assert not forged.is_intact(), "a changed requirement kept a valid signature"


class TestRequirementsHash:
    def test_is_stable_across_key_order(self):
        # Two producers that asked for the same thing must hash the same, or
        # the §4.4 cache never hits and sign-off cannot survive a round trip.
        a = make(requirements={"function": "f", "targets": {"a": 1, "b": 2}})
        b = make(requirements={"function": "f", "targets": {"b": 2, "a": 1}})
        assert a.requirements_hash() == b.requirements_hash()

    def test_differs_when_a_requirement_differs(self):
        a = make()
        b = make(requirements={
            "function": "low_pass_filter", "targets": {"cutoff_hz": 2000},
        })
        assert a.requirements_hash() != b.requirements_hash()

    def test_does_not_depend_on_intent_id_or_provenance(self):
        a = make()
        b = make(provenance=Provenance(producer=Producer.LLM, model="m", prompt_hash="p"))
        assert a.intent_id != b.intent_id
        assert a.requirements_hash() == b.requirements_hash()
