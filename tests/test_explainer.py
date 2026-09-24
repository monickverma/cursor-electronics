"""
Explanation engine tests.

PRODUCT_MASTER.md Part 12: the explanation layer is the product. Phase 1
criterion 12 is an external engineer cold-reading this module's output. Until
now its only coverage was three live tests in `test_ai_layer.py`, which skip
whenever ANTHROPIC_API_KEY is absent — the default locally and in CI without
secrets. So in practice it shipped with no enforced coverage at all.

This file adds deterministic coverage that always runs:

- `_build_prompt()` includes every component, node, connection, validation
  finding and simulation number. Anything dropped here is invisible to the
  model, so the explanation cannot mention it no matter how good the prompt is.
- The system prompt keeps enforcing consequential over descriptive language.
  That distinction is the stated product differentiator; if someone softens the
  prompt, a test should object.
- `explain()` wiring, via a mocked client.

Plus live tests (auto-skipped without a key) that assert the *output* is
consequential — the property criterion 12 actually measures.

WHAT THESE TESTS CANNOT DO: judge whether an explanation is genuinely good.
Keyword checks catch a prompt regression, not a quality regression. Criterion 12
still requires a human reader. See plan/current_phase.md Task 3.
"""

from __future__ import annotations

import os

import pytest

from ai.explainer import (
    CONSEQUENTIAL_MARKER_BAR,
    CONSEQUENTIAL_MARKERS,
    SYSTEM_PROMPT,
    ExplanationEngine,
    _first_text,
)
from core.ir_validator import IRValidationResult, validate_ir

API_KEY_PRESENT = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
requires_api = pytest.mark.skipif(
    not API_KEY_PRESENT,
    reason="ANTHROPIC_API_KEY not set — live explanation tests skipped",
)


# ── Mock plumbing ─────────────────────────────────────────────────────────────

class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, text: str, recorder: dict):
        self._text = text
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str, recorder: dict):
        self.messages = _FakeMessages(text, recorder)


@pytest.fixture
def explainer_factory(monkeypatch):
    """Returns (build_explainer, recorder) with the model call stubbed out."""
    recorder: dict = {}

    def build(reply_text: str = "stub explanation") -> ExplanationEngine:
        monkeypatch.setattr(
            "ai.explainer.make_client",
            lambda: _FakeClient(reply_text, recorder),
        )
        return ExplanationEngine()

    return build, recorder


# ── Prompt assembly: nothing may be silently dropped ──────────────────────────

class TestPromptCompleteness:
    """If the IR does not reach the prompt, the explanation cannot mention it.

    These are the cheapest possible guards on criterion 12 — a component missing
    here guarantees a reviewer finds a gap later.
    """

    def test_every_component_id_and_part_number_present(self, all_example_irs):
        prompt = ExplanationEngine._build_prompt(None, all_example_irs, None, None)
        for comp in all_example_irs.components:
            assert comp.id in prompt
            assert comp.part_number in prompt

    def test_component_justifications_included(self, all_example_irs):
        """Justification is the raw material for the explanation."""
        prompt = ExplanationEngine._build_prompt(None, all_example_irs, None, None)
        for comp in all_example_irs.components:
            assert comp.justification[:30] in prompt

    def test_confidence_is_surfaced(self, ir_dht22):
        """Low-confidence decisions must be flaggable as warnings, per the
        merged MVP spec. That is impossible if confidence never reaches the model."""
        prompt = ExplanationEngine._build_prompt(None, ir_dht22, None, None)
        for comp in ir_dht22.components:
            assert f"{comp.confidence:.0%}" in prompt

    def test_every_node_present(self, all_example_irs):
        prompt = ExplanationEngine._build_prompt(None, all_example_irs, None, None)
        for node in all_example_irs.nodes:
            assert node.id in prompt

    def test_every_connection_present(self, all_example_irs):
        prompt = ExplanationEngine._build_prompt(None, all_example_irs, None, None)
        for conn in all_example_irs.connections:
            assert f"{conn.component_id}.{conn.pin}" in prompt
            assert conn.node_id in prompt

    def test_intent_and_target_mcu_present(self, ir_dht22):
        prompt = ExplanationEngine._build_prompt(None, ir_dht22, None, None)
        assert ir_dht22.intent in prompt
        assert (ir_dht22.target_mcu or "unspecified") in prompt

    def test_missing_mcu_renders_as_unspecified(self, ir_rc_filter):
        """Passive circuits have no MCU — must not render as 'None'."""
        prompt = ExplanationEngine._build_prompt(None, ir_rc_filter, None, None)
        if ir_rc_filter.target_mcu is None:
            assert "unspecified" in prompt
            assert "TARGET MCU: None" not in prompt


# ── Validation and simulation findings must reach the prompt ──────────────────

class TestFailuresAreNotSwallowed:
    def test_validation_errors_appear(self, ir_dht22):
        result = IRValidationResult()
        result.add_error("components[1].supply_voltage_max", "DHT22 rated 5.5V, supply is 12V")

        prompt = ExplanationEngine._build_prompt(None, ir_dht22, result, None)
        assert "FAIL" in prompt
        assert "supply_voltage_max" in prompt
        assert "5.5V" in prompt

    def test_validation_warnings_appear(self, ir_dht22):
        result = IRValidationResult()
        result.add_warning("components[2].confidence", "Low confidence on R1 selection")

        prompt = ExplanationEngine._build_prompt(None, ir_dht22, result, None)
        assert "WARN" in prompt
        assert "Low confidence" in prompt

    def test_passing_validation_is_reported_as_pass(self, ir_dht22):
        prompt = ExplanationEngine._build_prompt(None, ir_dht22, validate_ir(ir_dht22), None)
        assert "VALIDATION RESULT" in prompt

    def test_simulation_numbers_reach_the_prompt(self, ir_rc_filter):
        """'Simulation confirms' is the evidence behind every claim. The actual
        numbers must be present, not just a pass/fail verdict."""
        sim = {"grade": "FAIL", "cutoff_hz": 1580.2, "expected_hz": 1000.0}

        prompt = ExplanationEngine._build_prompt(None, ir_rc_filter, None, sim)
        assert "SIMULATION RESULTS" in prompt
        assert "1580.2" in prompt
        assert "FAIL" in prompt

    def test_absent_optional_sections_are_omitted_cleanly(self, ir_dht22):
        prompt = ExplanationEngine._build_prompt(None, ir_dht22, None, None)
        assert "VALIDATION RESULT" not in prompt
        assert "SIMULATION RESULTS" not in prompt
        assert "None" not in prompt.replace("TARGET MCU: unspecified", "")


# ── The system prompt is a product asset ──────────────────────────────────────

class TestSystemPromptEnforcesConsequentialLanguage:
    """PRODUCT_MASTER.md Part 12 and the Kimi review both single this out as the
    differentiator. Weakening the prompt should break a test, not slip through."""

    def test_prompt_demands_what_breaks_reasoning(self):
        assert "what would break" in SYSTEM_PROMPT.lower()

    def test_prompt_contains_both_a_wrong_and_right_example(self):
        assert "WRONG:" in SYSTEM_PROMPT and "RIGHT:" in SYSTEM_PROMPT

    def test_prompt_requires_reader_needs_no_briefing(self):
        """This is criterion 12 restated inside the prompt itself."""
        lowered = SYSTEM_PROMPT.lower()
        assert "has not seen this design" in lowered or "not seen this design" in lowered

    def test_prompt_asks_for_risks_and_verification(self):
        assert "risk" in SYSTEM_PROMPT.lower()

    def test_prompt_references_simulation_numbers(self):
        assert "simulation" in SYSTEM_PROMPT.lower()


# ── explain() wiring ──────────────────────────────────────────────────────────

class TestExplainWiring:
    def test_returns_text_not_a_response_object(self, ir_dht22, explainer_factory):
        build, _ = explainer_factory
        text = build("R1 pulls DATA high; without it the MCU reads timeouts.").explain(ir_dht22)
        assert isinstance(text, str)
        assert "timeouts" in text

    def test_system_prompt_is_sent(self, ir_dht22, explainer_factory):
        build, recorder = explainer_factory
        build().explain(ir_dht22)
        assert recorder["system"] == SYSTEM_PROMPT

    def test_no_tool_choice_is_forced(self, ir_dht22, explainer_factory):
        """The explainer is the one AI module that legitimately returns prose.

        Its output is read by a human, never compiled — so unlike the parser,
        reasoner and patcher it is exempt from the tool_use rule. Documented
        here so nobody 'fixes' it into tool_use later.
        """
        build, recorder = explainer_factory
        build().explain(ir_dht22)
        assert "tools" not in recorder
        assert "tool_choice" not in recorder

    def test_token_budget_allows_a_full_report(self, ir_dht22, explainer_factory):
        """Five structured sections do not fit in a small budget; a truncated
        explanation fails criterion 12 by omission."""
        build, recorder = explainer_factory
        build().explain(ir_dht22)
        assert recorder["max_tokens"] >= 2000

    def test_all_five_templates_produce_a_prompt(self, all_example_irs, explainer_factory):
        build, recorder = explainer_factory
        build().explain(all_example_irs)
        assert len(recorder["messages"][0]["content"]) > 100


class TestReasoningModelResponses:
    """
    Regression for a live crash found on 2026-09-20 while running the Task 0.5
    derivability experiment: the configured `AI_MODEL` reasons before it
    writes, so `response.content[0]` is a thinking block and the old
    `content[0].text` raised `AttributeError: 'ThinkingBlock' object has no
    attribute 'text'`. Every explanation call was failing.

    The tool_use modules are deliberately not changed — forced `tool_choice`
    suppresses thinking blocks, and `content[0].input` was verified correct
    against the live API before this fix was narrowed to the explainer.
    """

    class _Thinking:
        type = "thinking"
        thinking = "let me work through the divider ratio…"

    class _Text:
        type = "text"

        def __init__(self, text):
            self.text = text

    class _Response:
        def __init__(self, content):
            self.content = content

    def test_text_after_a_thinking_block_is_found(self):
        response = self._Response([self._Thinking(), self._Text("the explanation")])
        assert _first_text(response) == "the explanation"

    def test_plain_text_response_still_works(self):
        assert _first_text(self._Response([self._Text("plain")])) == "plain"

    def test_first_of_several_text_blocks_wins(self):
        response = self._Response([self._Text("first"), self._Text("second")])
        assert _first_text(response) == "first"

    def test_thinking_only_response_raises_a_legible_error(self):
        # Seen for real: the model spent the whole max_tokens budget thinking
        # and emitted no prose. An AttributeError here would send the reader
        # hunting in the wrong place.
        with pytest.raises(ValueError, match="no text block"):
            _first_text(self._Response([self._Thinking()]))

    def test_error_names_the_block_types_it_did_get(self):
        with pytest.raises(ValueError, match="thinking"):
            _first_text(self._Response([self._Thinking()]))


# ── Live tests — the property criterion 12 actually measures ──────────────────

@requires_api
class TestExplanationIsConsequentialLive:
    # The list lives in ai/explainer.py. It used to be duplicated here and in
    # ai/derived_explainer.py — identical on the day it was written, and one
    # edit away from holding two explainers to different standards.

    def test_output_uses_consequential_language(self, ir_dht22):
        text = ExplanationEngine().explain(ir_dht22).lower()
        hits = [m for m in CONSEQUENTIAL_MARKERS if m in text]
        assert len(hits) >= CONSEQUENTIAL_MARKER_BAR, (
            f"Explanation reads as descriptive, not consequential. "
            f"Only matched {hits}. See PRODUCT_MASTER.md Part 12."
        )

    def test_simulation_failure_is_reflected_in_output(self, ir_rc_filter):
        sim = {"grade": "FAIL", "cutoff_hz": 1580.2, "expected_hz": 1000.0}
        text = ExplanationEngine().explain(ir_rc_filter, None, sim)
        assert "1580" in text or "fail" in text.lower()

    def test_validation_error_is_reflected_in_output(self, ir_dht22):
        result = IRValidationResult()
        result.add_error("components[1].supply_voltage_max",
                         "DHT22 rated 5.5V but supply is 12V")
        text = ExplanationEngine().explain(ir_dht22, result).lower()
        assert "5.5" in text or "voltage" in text
