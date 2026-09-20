"""
Stage 1 Task 1.4 — the LLM producer, and amendment X5.

X5 retires the retry loop for schema failures and keeps it for semantic
rejections. Both halves are tested here, and so is the guard that makes the
second half safe: **a retry may fix where a field landed, never what it says.**

That guard is not in the plan. It is here because the fix most available to a
model told "no generator accepted this" is to alter the requirement until it
fits — quietly turning "I need 2 MHz" into "1 kHz" and returning a design the
user never asked for. Materializing the requirement is the whole architecture
(`ARCHITECTURE_ASSURANCE_CASE.md` A1); a retry that rewrites it is worse than
no retry at all.
"""

import json

import pytest

from ai.intent_producer import (
    MAX_SEMANTIC_RETRIES,
    IntentProducer,
    IntentProductionError,
    _requested_values,
)
from core.intent_ir import IntentIR, Producer
from generators.protocol import EnvelopeDecision, GridSpec, PortContract
from generators.registry import GeneratorRegistry

PORTS = (PortContract(name="P", direction="input"),)


class _Block:
    def __init__(self, payload):
        self.type = "tool_use"
        self.input = payload


class _Response:
    def __init__(self, content):
        self.content = content


class _FakeMessages:
    """Returns a scripted sequence of tool inputs, one per call."""

    def __init__(self, payloads, recorder):
        self._payloads = list(payloads)
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.setdefault("calls", []).append(kwargs)
        payload = self._payloads.pop(0) if self._payloads else self._payloads
        if isinstance(payload, list):  # exhausted
            raise AssertionError("more model calls than the test scripted")
        if isinstance(payload, Exception):
            raise payload
        return _Response([_Block(payload)])


class _FakeClient:
    def __init__(self, payloads, recorder):
        self.messages = _FakeMessages(payloads, recorder)


class _Stub:
    version = "1.0.0"
    name = "stub"
    function = "low_pass_filter"

    def __init__(self, accept_when=None):
        self._accept_when = accept_when or (lambda i: True)

    def envelope(self, intent):
        if self._accept_when(intent):
            return EnvelopeDecision.accept(PORTS)
        return EnvelopeDecision.refuse("cutoff_hz outside declared envelope 10 Hz – 100 kHz")

    def generate(self, intent):
        raise NotImplementedError

    def predict(self, intent, box=None):
        raise NotImplementedError

    def grid(self):
        return GridSpec(axes={"cutoff_hz": [10.0, 100_000.0]}, units={"cutoff_hz": "Hz"})

    def dependency_closure(self, requirement_path):
        return frozenset()


def producer(payloads, generator=None, monkeypatch=None):
    recorder: dict = {}
    registry = GeneratorRegistry()
    registry.register(generator or _Stub())
    monkeypatch.setattr("ai.intent_producer.make_client", lambda: _FakeClient(payloads, recorder))
    return IntentProducer(registry), recorder


IN_ENVELOPE = {
    "function": "low_pass_filter",
    "targets": {"cutoff_hz": 1000},
    "constraints": {"supply_v": 5},
}


class TestHappyPath:
    def test_produces_an_intent_in_one_call(self, monkeypatch):
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        intent = p.produce("RC low-pass at 1 kHz")
        assert isinstance(intent, IntentIR)
        assert intent.requirements["targets"]["cutoff_hz"] == 1000
        assert len(rec["calls"]) == 1

    def test_records_llm_provenance_with_model_and_prompt_hash(self, monkeypatch):
        p, _ = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        intent = p.produce("RC low-pass at 1 kHz")
        assert intent.provenance.producer == Producer.LLM
        assert intent.provenance.model
        assert intent.provenance.prompt_hash

    def test_uses_forced_tool_choice(self, monkeypatch):
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        p.produce("x")
        assert rec["calls"][0]["tool_choice"]["type"] == "tool"

    def test_catalogue_is_given_to_the_model(self, monkeypatch):
        # The model should know what exists; inventing a match hides a gap.
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        p.produce("x")
        assert "low_pass_filter" in rec["calls"][0]["messages"][0]["content"]


class TestSchemaFailuresDoNotRetry:
    """X5, first half."""

    def test_malformed_requirement_raises_immediately(self, monkeypatch):
        p, rec = producer([{"targets": {"cutoff_hz": 1}}], monkeypatch=monkeypatch)  # no function
        with pytest.raises(IntentProductionError):
            p.produce("x")
        assert len(rec["calls"]) == 1, "a schema failure was retried"

    def test_error_carries_the_raw_tool_input(self, monkeypatch):
        # The argument for retiring schema retries is that the failure becomes
        # visible. An error without the evidence is strictly worse than the
        # loop it replaces.
        bad = {"function": "", "targets": {}}
        p, _ = producer([bad], monkeypatch=monkeypatch)
        with pytest.raises(IntentProductionError) as exc:
            p.produce("x")
        assert exc.value.raw == bad

    def test_non_object_tool_input_raises(self, monkeypatch):
        p, _ = producer(["not an object"], monkeypatch=monkeypatch)
        with pytest.raises(IntentProductionError, match="not an object"):
            p.produce("x")

    def test_missing_tool_use_block_raises(self, monkeypatch):
        class NoTool:
            messages = None

        recorder: dict = {}

        class Msgs:
            def create(self, **kw):
                recorder.setdefault("calls", []).append(kw)
                thinking = type("T", (), {"type": "thinking"})()
                return _Response([thinking])

        client = type("C", (), {"messages": Msgs()})()
        monkeypatch.setattr("ai.intent_producer.make_client", lambda: client)
        registry = GeneratorRegistry()
        registry.register(_Stub())
        with pytest.raises(IntentProductionError, match="no tool_use block"):
            IntentProducer(registry).produce("x")


class TestSemanticRetry:
    """X5, second half — and the guard the plan does not specify."""

    def test_envelope_refusal_triggers_one_retry(self, monkeypatch):
        out = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000}}
        fixed = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000, "tolerance_pct": 5}}
        gen = _Stub(accept_when=lambda i: "tolerance_pct" in i.requirements["targets"])
        p, rec = producer([out, fixed], generator=gen, monkeypatch=monkeypatch)

        intent = p.produce("x")
        assert len(rec["calls"]) == 2
        # The user's value survived the correction.
        assert intent.requirements["targets"]["cutoff_hz"] == 2_000_000

    def test_a_single_accepted_intent_never_retries(self, monkeypatch):
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        p.produce("x")
        assert len(rec["calls"]) == 1

    def test_retry_is_given_the_refusal_reasons(self, monkeypatch):
        out = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000}}
        gen = _Stub(accept_when=lambda i: False)
        p, rec = producer([out, out], generator=gen, monkeypatch=monkeypatch)
        p.produce("x")
        second = rec["calls"][1]["messages"][-1]["content"]
        assert "outside declared envelope" in second

    def test_retry_may_add_a_field_it_failed_to_record(self, monkeypatch):
        # The asymmetry: supplying a missing field is transcription catching
        # up with the request. Blocking additions too would make the retry
        # useless, since the commonest real correction is an omission.
        asked = {**IN_ENVELOPE, "targets": {"cutoff_hz": 1000}}
        completed = {**IN_ENVELOPE, "targets": {"cutoff_hz": 1000, "tolerance_pct": 5}}
        gen = _Stub(accept_when=lambda i: "tolerance_pct" in i.requirements["targets"])
        p, _ = producer([asked, completed], generator=gen, monkeypatch=monkeypatch)

        intent = p.produce("1 kHz low-pass within 5%")
        assert intent.requirements["targets"]["tolerance_pct"] == 5

    def test_retry_that_drops_a_recorded_value_is_refused(self, monkeypatch):
        asked = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000}}
        dropped = {**IN_ENVELOPE, "targets": {}}
        gen = _Stub(accept_when=lambda i: "cutoff_hz" not in i.requirements["targets"])
        p, _ = producer([asked, dropped], generator=gen, monkeypatch=monkeypatch)

        with pytest.raises(IntentProductionError, match="changed what was asked for"):
            p.produce("2 MHz low-pass")

    def test_retry_that_rewrites_the_request_is_refused(self, monkeypatch):
        # The guard. A model told "no generator accepted this" will happily
        # move 2 MHz to 1 kHz — and then the user gets a design they never
        # asked for, which defeats materializing the requirement at all.
        asked = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000}}
        rewritten = {**IN_ENVELOPE, "targets": {"cutoff_hz": 1000}}
        gen = _Stub(accept_when=lambda i: i.requirements["targets"]["cutoff_hz"] < 100_000)
        p, _ = producer([asked, rewritten], generator=gen, monkeypatch=monkeypatch)

        with pytest.raises(IntentProductionError, match="changed what was asked for"):
            p.produce("2 MHz low-pass")

    def test_out_of_catalogue_request_is_returned_not_negotiated(self, monkeypatch):
        # §4.2: users self-select against a visible catalogue. §4.6 defers the
        # labelled ring so uncovered requests are refused rather than guessed.
        asked = {**IN_ENVELOPE, "targets": {"cutoff_hz": 2_000_000}}
        gen = _Stub(accept_when=lambda i: False)
        p, rec = producer([asked, asked], generator=gen, monkeypatch=monkeypatch)

        intent = p.produce("2 MHz low-pass")
        assert intent.requirements["targets"]["cutoff_hz"] == 2_000_000
        assert len(rec["calls"]) == MAX_SEMANTIC_RETRIES + 1

    def test_underdetermined_intent_is_returned_without_a_retry(self, monkeypatch):
        # An unanswered question is for the user, not for another model call.
        payload = {**IN_ENVELOPE, "underdetermined": ["constraints.supply_v"]}
        p, rec = producer([payload], monkeypatch=monkeypatch)
        intent = p.produce("a low-pass filter")
        assert not intent.is_answerable
        assert len(rec["calls"]) == 1


class TestRequestedValues:
    def test_flattens_every_section(self):
        flat = _requested_values({
            "targets": {"cutoff_hz": 1000},
            "constraints": {"supply_v": 5},
            "preferences": {"package": "0402"},
        })
        assert flat == {
            "targets.cutoff_hz": 1000,
            "constraints.supply_v": 5,
            "preferences.package": "0402",
        }

    def test_preference_changes_count_as_changing_the_request(self):
        # A model that quietly swaps the package has changed what was asked
        # for, even if nothing downstream would refuse the result.
        before = _requested_values({"preferences": {"package": "0402"}})
        after = _requested_values({"preferences": {"package": "0603"}})
        assert before != after

    def test_moving_a_field_between_sections_is_a_change(self):
        # Deliberate: the sections mean different things, and a target that
        # became a preference is no longer checked by predict().
        assert _requested_values({"targets": {"supply_v": 5}}) != _requested_values(
            {"constraints": {"supply_v": 5}}
        )
