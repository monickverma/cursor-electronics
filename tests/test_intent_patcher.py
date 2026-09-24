"""
Stage 2 — the LLM patcher for IntentIR. `ai/intent_patcher.py`.

Replaces the coverage `tests/test_patcher.py` gave the CircuitIR patcher. The
invariant that file pinned — *the patcher never returns a full IR* — becomes
stronger here: this patcher returns operations on a requirement and cannot
name the design type at all (`test_llm_cannot_write_circuit_ir.py` asserts it).

The guard under test (decisions.md, X2 + X4, item 7, tightened by the Stage 2
verification entry): **every operation cites the command in whole words, no
two operations share words, and every value written appears in its
citation.** A patch is a rewrite by definition, so X5's "add, never rewrite"
cannot govern it; what it must stop is a model that, asked for one change,
makes two.
"""

import json

import pytest

from ai.intent_patcher import (
    MAX_OUTPUT_TOKENS,
    IntentPatcher,
    IntentPatchError,
    PatchFailure,
    cites_command,
    quantities,
)
from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp


class _Block:
    def __init__(self, payload):
        self.type = "tool_use"
        self.input = payload


class _Thinking:
    type = "thinking"


class _Response:
    def __init__(self, content, stop_reason="tool_use"):
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, response, recorder):
        self._response = response
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.setdefault("calls", []).append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, response, recorder):
        self.messages = _FakeMessages(response, recorder)


@pytest.fixture
def patcher(monkeypatch):
    recorder = {}

    def build(payload=None, response=None):
        resp = response or _Response([_Block(payload)])
        monkeypatch.setattr("ai.intent_patcher.make_client", lambda: _FakeClient(resp, recorder))
        return IntentPatcher(catalogue=("low_pass_filter",))

    return build, recorder


def intent():
    return IntentIR(
        requirements={
            "function": "low_pass_filter",
            "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
            "constraints": {"supply_v": 5},
        },
        provenance=Provenance(producer=Producer.FORM),
    )


PARTS = [{"id": "R1", "type": "resistor", "value": "1580"}, {"id": "C1", "type": "capacitor", "value": "100nF"}]
COMMAND = "Make the cutoff 2 kHz"


class TestHappyPath:
    def test_returns_operations_not_a_design(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [
            {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
        ]}).propose(intent(), COMMAND, PARTS)
        assert proposal.ops == (PatchOp(op="replace", path="/targets/cutoff_hz", value=2000),)
        assert proposal.citations == ("cutoff 2 kHz",)
        for forbidden in ("components", "nodes", "connections", "circuit_id"):
            assert not hasattr(proposal, forbidden)

    def test_a_pin_names_the_part_it_was_told_about(self, patcher):
        build, recorder = patcher
        proposal = build({"operations": [
            {"op": "add", "path": "/constraints/pinned/R1", "value": "4.7k",
             "because": "use the 4.7k"},
        ]}).propose(intent(), "Use the 4.7k resistor I have", PARTS)
        assert proposal.ops[0].path == "/constraints/pinned/R1"
        content = recorder["calls"][0]["messages"][0]["content"]
        assert "R1: resistor" in content and "C1: capacitor" in content

    def test_no_operations_with_a_note_is_a_valid_answer(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [], "note_to_user": "That needs a band-pass filter."}) \
            .propose(intent(), "make it a band-pass", PARTS)
        assert proposal.ops == () and "band-pass" in proposal.note_to_user


class TestRequestShape:
    def test_forced_tool_choice_one_call(self, patcher):
        build, recorder = patcher
        build({"operations": []}).propose(intent(), COMMAND, PARTS)
        assert len(recorder["calls"]) == 1
        call = recorder["calls"][0]
        assert call["tool_choice"] == {"type": "tool", "name": "propose_requirement_patch"}

    def test_the_model_sees_the_requirement_not_a_circuit(self, patcher):
        build, recorder = patcher
        build({"operations": []}).propose(intent(), COMMAND, PARTS)
        content = recorder["calls"][0]["messages"][0]["content"]
        assert "CURRENT REQUIREMENT" in content
        assert json.dumps(intent().requirements, sort_keys=True, indent=2) in content
        assert "CHANGE REQUEST: Make the cutoff 2 kHz" in content

    def test_a_thinking_block_first_does_not_hide_the_tool_call(self, patcher):
        build, _ = patcher
        response = _Response([_Thinking(), _Block({"operations": []})])
        assert build(response=response).propose(intent(), COMMAND, PARTS).ops == ()


class TestTheCitationGuard:
    def test_an_operation_the_user_did_not_ask_for_refuses_the_whole_patch(self, patcher):
        # The failure this guard exists for: asked for one change, made two.
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
                {"op": "replace", "path": "/constraints/supply_v", "value": 3.3,
                 "because": "a 3.3 V rail is more common"},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.UNCITED_OPERATION.value
        assert "supply_v" in str(exc.value)
        assert exc.value.raw["operations"][1]["value"] == 3.3   # evidence travels with it

    @pytest.mark.parametrize("because", [None, "", "   ", 42])
    def test_a_missing_citation_is_refused(self, patcher, because):
        build, _ = patcher
        with pytest.raises(IntentPatchError, match="not in the command"):
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": because},
            ]}).propose(intent(), COMMAND, PARTS)

    def test_citations_match_modulo_case_and_spacing_only(self):
        assert cites_command("CUTOFF   2 kHz", COMMAND)
        assert not cites_command("cutoff 20 kHz", COMMAND)
        assert not cites_command("cutoff to 2 kHz", COMMAND)

    @pytest.mark.parametrize("fragment", ["e", "cut", "off 2", "kH"])
    def test_a_citation_must_be_whole_words(self, fragment):
        # `"e"` was accepted as a citation of "Make the cutoff 2 kHz" until the
        # Stage 2 verification, which put an uncited supply change through it.
        assert not cites_command(fragment, COMMAND)


class TestTheBypassesTheVerificationFound:
    """
    Both got `supply_v: 5 → 12` through the first version of the guard on the
    command "make the cutoff 2 kHz", which never mentions a supply.
    """

    def test_quoting_the_whole_command_for_a_second_change(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": COMMAND},
                {"op": "replace", "path": "/constraints/supply_v", "value": 12, "because": COMMAND},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.UNGROUNDED_VALUE.value
        assert "supply_v" in str(exc.value)

    def test_quoting_a_single_letter(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
                {"op": "replace", "path": "/constraints/supply_v", "value": 12, "because": "e"},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.UNCITED_OPERATION.value

    def test_quoting_an_unrelated_whole_word(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
                {"op": "replace", "path": "/constraints/supply_v", "value": 12, "because": "the"},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.UNGROUNDED_VALUE.value

    def test_one_phrase_cannot_justify_two_changes(self, patcher):
        # "4.7k" grounds a 4700 Hz cutoff as well as the pin — so this one is
        # stopped by the spans, not the values.
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "add", "path": "/constraints/pinned/R1", "value": "4.7k", "because": "4.7k"},
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 4700, "because": "4.7k"},
            ]}).propose(intent(), "Use the 4.7k resistor I have", PARTS)
        assert exc.value.kind == PatchFailure.SHARED_CITATION.value

    def test_two_changes_with_words_of_their_own_are_fine(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [
            {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
            {"op": "replace", "path": "/constraints/supply_v", "value": 12, "because": "supply 12 V"},
        ]}).propose(intent(), "Make the cutoff 2 kHz and the supply 12 V", PARTS)
        assert [o.value for o in proposal.ops] == [2000, 12]


class TestValuesAreGroundedInTheCitation:
    def test_a_mis_transcribed_value_is_refused(self, patcher):
        # Listed as uncaught by the first version of the guard; now caught.
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 20000, "because": "2 kHz"},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.UNGROUNDED_VALUE.value
        assert "20000" in str(exc.value)

    def test_a_relative_request_asks_for_the_value(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000,
                 "because": "double the cutoff"},
            ]}).propose(intent(), "double the cutoff", PARTS)
        assert exc.value.kind == PatchFailure.UNGROUNDED_VALUE.value
        assert "state the new value" in str(exc.value)

    @pytest.mark.parametrize("command, because, value", [
        ("use the 4k7 I have", "4k7", "4.7k"),              # R-notation grounds the pin
        ("pin C1 to 0.1 uF", "C1 to 0.1 uF", {"C1": "100nF"}),
        ("tolerance 1%", "tolerance 1%", 1),
        ("run it from 3.3V", "3.3V", 3.3),
        ("make it 0603 parts", "0603", "0603"),
    ])
    def test_values_compare_as_quantities_across_notations(self, patcher, command, because, value):
        build, _ = patcher
        path = "/constraints/pinned" if isinstance(value, dict) else "/constraints/x"
        proposal = build({"operations": [
            {"op": "add", "path": path, "value": value, "because": because},
        ]}).propose(intent(), command, PARTS)
        assert proposal.ops[0].value == value

    def test_case_decides_milli_versus_mega(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError):
            build({"operations": [
                {"op": "replace", "path": "/targets/cutoff_hz", "value": 2e6, "because": "2 mHz"},
            ]}).propose(intent(), "cutoff 2 mHz", PARTS)

    def test_a_removal_needs_a_citation_but_no_value(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [
            {"op": "remove", "path": "/constraints/supply_v", "because": "drop the supply limit"},
        ]}).propose(intent(), "drop the supply limit", PARTS)
        assert proposal.ops[0].op == "remove"

    @pytest.mark.parametrize("text, expected", [
        ("2 kHz", [2000.0]), ("2kHz", [2000.0]), ("4k7", [4700.0]), ("4.7 kΩ", [4700.0]),
        ("100nF", [1e-7]), ("0.1 µF", [1e-7]), ("12 V", [12.0]), ("5%", [5.0]),
        ("2,000 Hz", [2000.0]), ("1e3", [1000.0]), ("2 MHz", [2e6]), ("-5 V", [-5.0]),
        ("5 more", [5.0]), ("R1", []), ("3rd", []), ("4.7K5", []), ("10 kilohms", [1e4]),
    ])
    def test_the_quantity_reader(self, text, expected):
        got = quantities(text)
        assert len(got) == len(expected)
        assert all(abs(g - e) <= 1e-12 * max(1.0, abs(e)) for g, e in zip(got, expected))


class TestWhatTheGuardStillDoesNotCatch:
    """
    Pinned so nobody reads the guard as covering these. The route returns the
    requirement diff with every patch; that is the mitigation for both.
    """

    def test_values_swapped_between_two_operations(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [
            {"op": "replace", "path": "/targets/cutoff_hz", "value": 12, "because": "supply 12 V"},
            {"op": "replace", "path": "/constraints/supply_v", "value": 2000, "because": "cutoff 2 kHz"},
        ]}).propose(intent(), "Make the cutoff 2 kHz and the supply 12 V", PARTS)
        assert [o.value for o in proposal.ops] == [12, 2000]

    def test_a_removal_citing_an_unrelated_whole_word(self, patcher):
        build, _ = patcher
        proposal = build({"operations": [
            {"op": "replace", "path": "/targets/cutoff_hz", "value": 2000, "because": "cutoff 2 kHz"},
            {"op": "remove", "path": "/constraints/supply_v", "because": "the"},
        ]}).propose(intent(), COMMAND, PARTS)
        assert proposal.ops[1].op == "remove"


class TestFailuresAreLoudAndNamed:
    def test_a_malformed_operation_is_a_schema_failure_with_the_raw(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"operations": [
                {"op": "move", "path": "/targets/cutoff_hz", "because": "cutoff"},
            ]}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.SCHEMA.value
        assert exc.value.raw is not None

    def test_no_operations_list_is_malformed(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build({"ops": []}).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.MALFORMED_TOOL_INPUT.value

    def test_truncation_is_not_reported_as_schema(self, patcher):
        build, _ = patcher
        response = _Response([_Block({"operations": [{"op": "rep"}]})], stop_reason="max_tokens")
        with pytest.raises(IntentPatchError) as exc:
            build(response=response).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.TRUNCATED.value
        assert str(MAX_OUTPUT_TOKENS) in str(exc.value)

    def test_no_tool_use_block(self, patcher):
        build, _ = patcher
        with pytest.raises(IntentPatchError) as exc:
            build(response=_Response([_Thinking()])).propose(intent(), COMMAND, PARTS)
        assert exc.value.kind == PatchFailure.NO_TOOL_USE.value

    def test_log_entry_carries_kind_and_capped_raw(self):
        err = IntentPatchError("bad", raw={"x": "y" * 10_000}, kind=PatchFailure.SCHEMA)
        entry = err.as_log_entry()
        assert entry.startswith("intent_patch_failed[schema]: bad | raw=")
        assert "truncated" in entry and len(entry) < 4_200
