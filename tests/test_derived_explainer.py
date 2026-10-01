"""
Task 0.5 — the derived explainer, and the bar it has to clear.

`DerivedExplainer` produces an explanation with zero API calls, from the
requirements, `predict()`, and the justifications the generator authored as it
chose each part. These tests hold it to the same consequential-language bar
`tests/test_explainer.py` applies to the model, and pin the places where a
template can go confidently wrong.
"""

import pytest

from ai.derived_explainer import DerivedExplainer, explanation_markers
from core.ir_validator import IRValidationResult, validate_ir
from generators.protocol import ClaimScope, Interval, Prediction
from generators.rc_lowpass import RCLowPassGenerator
from test_rc_lowpass_generator import intent

GEN = RCLowPassGenerator()
MARKER_BAR = 3  # tests/test_explainer.py requires >= 3 distinct markers


@pytest.fixture
def rc_case():
    i = intent(cutoff=1000.0)
    ir = GEN.generate(i)
    return ir, GEN.predict(i), i.requirements


@pytest.fixture
def rc_text(rc_case):
    ir, prediction, requirements = rc_case
    return DerivedExplainer().explain(
        ir, validate_ir(ir), prediction=prediction, requirements=requirements
    )


class TestClearsTheSameBarAsTheModel:
    def test_uses_consequential_language(self, rc_text):
        hits = explanation_markers(rc_text)
        assert len(hits) >= MARKER_BAR, f"only matched {hits}"

    def test_markers_have_exactly_one_owner(self):
        # They were duplicated: an identical copy here and in
        # tests/test_explainer.py, one edit away from holding the two
        # explainers to different standards with nothing to notice it.
        from ai.explainer import CONSEQUENTIAL_MARKERS, consequential_markers

        assert explanation_markers.__module__ == "ai.derived_explainer"
        assert explanation_markers("if x would fail") == consequential_markers("if x would fail")
        assert explanation_markers("if x would fail") == ["if ", "would ", "fail"]
        assert len(CONSEQUENTIAL_MARKERS) == 9

    def test_names_every_component(self, rc_case, rc_text):
        ir, _, _ = rc_case
        for component in ir.components:
            assert component.id in rc_text

    def test_needs_no_api_call(self, rc_case, monkeypatch):
        # The whole point of §4.4. If this ever starts calling a model the
        # cost argument evaporates silently.
        import ai.client

        monkeypatch.setattr(
            ai.client, "make_client",
            lambda *a, **k: pytest.fail("derived explainer made an API call"),
        )
        ir, prediction, requirements = rc_case
        assert DerivedExplainer().explain(
            ir, prediction=prediction, requirements=requirements
        )


class TestContent:
    def test_states_what_was_asked_for(self, rc_text):
        assert "cutoff_hz" in rc_text and "1000" in rc_text

    def test_carries_the_generator_authored_reasons(self, rc_case, rc_text):
        # The section that would otherwise need a model: the generator already
        # knows why it chose each part, because it chose them by a rule.
        ir, _, _ = rc_case
        r1 = next(c for c in ir.components if c.id == "R1")
        assert r1.justification[:40] in rc_text

    def test_reports_the_band_not_just_the_nominal(self, rc_text):
        assert "across the full component tolerance" in rc_text
        assert "nominal" in rc_text

    def test_names_the_method_so_the_claim_can_be_graded(self, rc_text):
        assert "monotone corners" in rc_text

    def test_declares_the_model_and_its_limits(self, rc_text):
        # EVIDENCE_CLASSES §3.3 — an undeclared model is how a claim gets read
        # as stronger than it is.
        assert "mna_ideal" in rc_text
        assert "not hardware" in rc_text

    def test_prints_what_is_not_assessed(self, rc_text):
        # Omission is how a validation report lies without stating a falsehood.
        assert "not assessed" in rc_text.lower()

    def test_surfaces_validation_findings(self, rc_case):
        ir, prediction, requirements = rc_case
        result = IRValidationResult()
        result.add_error("components[1].supply_voltage_max",
                         "C1 rated 16V but supply is 24V")
        text = DerivedExplainer().explain(
            ir, result, prediction=prediction, requirements=requirements
        )
        assert "16V" in text and "Error" in text

    def test_surfaces_simulation_failure(self, rc_case):
        ir, prediction, requirements = rc_case
        text = DerivedExplainer().explain(
            ir, None, {"grade": "FAIL", "cutoff_hz": 1580.2},
            prediction=prediction, requirements=requirements,
        )
        assert "failed" in text.lower() and "1580" in text


class TestDoesNotSayConfidentlyWrongThings:
    def test_dominant_tolerance_names_an_input_not_the_result(self, rc_text):
        # Regression, found by reading the output rather than the score:
        # `predict()` returns the predicted outputs alongside the component
        # parameters, and the output band is necessarily the widest of all of
        # them. The first version therefore announced that **cutoff_hz**
        # dominated the spread and was "the part to change" — cutoff_hz is the
        # result, not a part.
        assert "capacitance_f** tolerance dominates" in rc_text
        assert "cutoff_hz** tolerance dominates" not in rc_text

    def test_dominant_tolerance_agrees_with_the_generator(self, rc_case, rc_text):
        # C1's own justification says it dominates because it is a 10% part.
        # Two parts of the system contradicting each other is worse than
        # neither saying anything.
        ir, _, _ = rc_case
        c1 = next(c for c in ir.components if c.id == "C1")
        assert "dominates" in c1.justification
        assert "capacitance_f" in rc_text

    def test_voltage_margin_wording_tracks_the_actual_margin(self, rc_case):
        ir, prediction, requirements = rc_case
        text = DerivedExplainer().explain(
            ir, prediction=prediction, requirements=requirements
        )
        # C1 is 16 V on a 5 V rail — margin, not a risk.
        assert "would only become a risk if you raised the supply above 16" in text

    def test_component_at_its_rating_is_called_a_failure(self, rc_case):
        ir, prediction, requirements = rc_case
        ir = ir.model_copy(deep=True)
        ir.constraints["supply_voltage"] = 16.0
        text = DerivedExplainer().explain(
            ir, prediction=prediction, requirements=requirements
        )
        assert "already at or past its rating" in text

    def test_low_confidence_choice_is_flagged(self, rc_case):
        ir, prediction, requirements = rc_case
        ir = ir.model_copy(deep=True)
        ir.components[0].confidence = 0.5
        text = DerivedExplainer().explain(
            ir, prediction=prediction, requirements=requirements
        )
        assert "50%" in text and "before ordering" in text


class TestDegradesHonestly:
    def test_works_without_a_prediction(self, rc_case):
        # The five Phase 1 example IRs have no generator behind them.
        ir, _, _ = rc_case
        text = DerivedExplainer().explain(ir)
        assert ir.components[0].id in text
        assert "What it will do" not in text  # claims nothing it cannot support

    def test_empty_what_breaks_section_is_omitted_not_left_hanging(self, rc_case):
        # A heading promising consequences with nothing under it reads as
        # "nothing breaks". A false reassurance is worse than an absent
        # section, especially in the layer the product is staked on.
        ir, _, _ = rc_case
        ir = ir.model_copy(deep=True)
        ir.constraints = {}
        for component in ir.components:
            component.supply_voltage_max = None

        text = DerivedExplainer().explain(ir)
        assert "## What breaks if you change it" not in text

    def test_what_breaks_appears_when_there_is_something_to_say(self, rc_text):
        assert "## What breaks if you change it" in rc_text

    def test_works_without_requirements(self, rc_case):
        ir, prediction, _ = rc_case
        text = DerivedExplainer().explain(ir, prediction=prediction)
        assert ir.intent in text

    def test_point_quantities_are_not_dressed_up_as_bands(self, rc_case):
        ir, _, requirements = rc_case
        prediction = Prediction(
            quantities={"v_out": Interval.at(3.3, "V")},
            scope=ClaimScope(model="mna_ideal"),
        )
        text = DerivedExplainer().explain(
            ir, prediction=prediction, requirements=requirements
        )
        assert "3.3 V" in text
        assert "across the full component tolerance" not in text
