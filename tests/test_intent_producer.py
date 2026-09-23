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
    MAX_OUTPUT_TOKENS,
    MAX_SEMANTIC_RETRIES,
    Failure,
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
    def __init__(self, content, stop_reason="tool_use"):
        self.content = content
        self.stop_reason = stop_reason


class _Truncated:
    """Scripts a tool call cut off at the token ceiling.

    The partial dict it carries is what the API actually hands back in that
    case: a well-formed object that is simply missing the fields the model had
    not written yet. That is exactly why it is indistinguishable from a schema
    failure unless `stop_reason` is checked.
    """

    def __init__(self, partial):
        self.partial = partial


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
        if isinstance(payload, _Truncated):
            return _Response([_Block(payload.partial)], stop_reason="max_tokens")
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
        payload = {"function": "low_pass_filter", "targets": {"cutoff_hz": 1000},
                   "underdetermined": ["constraints.supply_v"]}
        p, rec = producer([payload], monkeypatch=monkeypatch)
        intent = p.produce("a low-pass filter")
        assert not intent.is_answerable
        assert intent.open_questions() == ["constraints.supply_v"]
        assert len(rec["calls"]) == 1


class TestQuestionsAreDecidedByCode:
    """
    Found live (Stage 3 + 4 verification): the model, told only function
    names, invented field names and listed fields no generator reads as
    underdetermined — so every plain request came back as questions.
    """

    def test_fields_the_model_invents_are_not_questions(self, monkeypatch):
        payload = {**IN_ENVELOPE, "underdetermined": ["targets.order", "targets.stopband_attenuation_db",
                                                      "constraints.max_series_resistance_ohms"]}
        p, _ = producer([payload], monkeypatch=monkeypatch)
        intent = p.produce("RC low-pass at 1 kHz on 5 V")
        assert intent.is_answerable and intent.open_questions() == []

    def test_a_required_field_the_model_flags_is_asked_and_the_rest_dropped(self, monkeypatch):
        payload = {"function": "low_pass_filter", "targets": {"cutoff_hz": 1000},
                   "underdetermined": ["targets.order", "constraints.supply_v", "targets.tolerance_pct"]}
        p, rec = producer([payload], monkeypatch=monkeypatch)
        # supply_v: required and unset. order: invented. tolerance_pct: optional.
        assert p.produce("RC low-pass at 1 kHz").open_questions() == ["constraints.supply_v"]
        assert len(rec["calls"]) == 1

    def test_an_uncatalogued_function_asks_nothing(self, monkeypatch):
        payload = {"function": "buck_converter", "targets": {"vout_v": 3.3},
                   "underdetermined": ["targets.efficiency_pct"]}
        p, _ = producer([payload, payload], monkeypatch=monkeypatch)
        intent = p.produce("12 V to 3.3 V buck")
        assert intent.open_questions() == []

    def test_the_prompt_carries_every_field_path(self, monkeypatch):
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        p.produce("RC low-pass at 1 kHz on 5 V")
        sent = str(rec["calls"][0])
        for path in ("targets.cutoff_hz", "constraints.supply_v", "targets.tolerance_pct"):
            assert path in sent


class TestRequestedValues:
    def test_flattens_every_section_and_the_function(self):
        flat = _requested_values({
            "function": "low_pass_filter",
            "targets": {"cutoff_hz": 1000},
            "constraints": {"supply_v": 5},
            "preferences": {"package": "0402"},
        })
        assert flat == {
            "function": "low_pass_filter",
            "targets.cutoff_hz": 1000,
            "constraints.supply_v": 5,
            "preferences.package": "0402",
        }

    def test_function_is_compared_at_all(self):
        # The hole this closes: `function` is the one required field and the
        # only one not inside a section, so a flatten over sections alone
        # never saw it.
        assert _requested_values({"function": "band_pass_filter"}) != _requested_values(
            {"function": "low_pass_filter"}
        )

    def test_function_whitespace_is_not_a_changed_request(self):
        # `Requirements` strips on validation, so the same name with different
        # surrounding whitespace is a formatting difference. Tripping the
        # guard on it would refuse a retry that changed nothing.
        assert _requested_values({"function": " low_pass_filter "}) == _requested_values(
            {"function": "low_pass_filter"}
        )

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


class TestARetryCannotRewriteTheFunction:
    """
    The hole the council found, closed.

    `function` is the only *required* field and the only one outside the three
    value sections, so the original flatten never compared it. Told "no
    generator accepted this", a model could rewrite `band_pass_filter` to
    `low_pass_filter`, leave every target byte-identical, pass the add-only
    check, and hand back the wrong circuit at exactly the cutoff asked for —
    the precise negotiation the guard exists to forbid, routed through the one
    field it did not watch.
    """

    #: A generator refuses a function it does not build. The default `_Stub`
    #: accepts anything, which is what let this case hide.
    @staticmethod
    def _function_aware():
        return _Stub(
            accept_when=lambda i: i.requirements.get("function") == "low_pass_filter"
        )

    def test_rewriting_the_function_to_fit_the_catalogue_is_refused(self, monkeypatch):
        asked = {"function": "band_pass_filter", "targets": {"cutoff_hz": 1000}}
        # Same numbers, different circuit. Every target is untouched.
        rewritten = {"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}}
        p, rec = producer(
            [asked, rewritten], generator=self._function_aware(), monkeypatch=monkeypatch
        )

        with pytest.raises(IntentProductionError, match="changed what was asked for"):
            p.produce("band-pass at 1 kHz")

    def test_the_refusal_names_the_function_as_what_changed(self, monkeypatch):
        asked = {"function": "band_pass_filter", "targets": {"cutoff_hz": 1000}}
        rewritten = {"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}}
        p, rec = producer(
            [asked, rewritten], generator=self._function_aware(), monkeypatch=monkeypatch
        )

        with pytest.raises(IntentProductionError) as caught:
            p.produce("band-pass at 1 kHz")
        # A backlog entry that says only "something changed" cannot be acted on.
        assert "function" in str(caught.value)
        assert caught.value.kind == Failure.RETRY_REWROTE_REQUEST.value

    def test_a_retry_that_keeps_the_function_can_still_correct_a_field(self, monkeypatch):
        # The guard must not have become "never retry": the add case is the
        # reason the retry exists at all.
        asked = {"function": "low_pass_filter", "targets": {}}
        corrected = {"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}}
        gen = _Stub(accept_when=lambda i: "cutoff_hz" in i.requirements.get("targets", {}))
        p, rec = producer([asked, corrected], generator=gen, monkeypatch=monkeypatch)

        intent = p.produce("a low-pass filter at 1 kHz")
        assert intent.requirements["targets"]["cutoff_hz"] == 1000
        assert len(rec["calls"]) == 2


class TestTruncationIsNotASchemaFailure:
    """
    The guard the rewrite lost.

    A tool call cut off at the token ceiling returns a *partial* dict, which
    fails `Requirements` for missing fields — a symptom identical to the model
    getting the schema wrong. X5's whole argument for retiring schema retries
    is that the failure becomes visible; filing a budget problem under that
    heading makes the evidence lie about the assumption it was collected to
    test.
    """

    #: Identical in both tests below. Only `stop_reason` differs, which is the
    #: entire point: nothing about the payload distinguishes the two cases.
    PARTIAL = {"targets": {"cutoff_hz": 1000}}

    def test_a_truncated_tool_call_reports_the_token_ceiling(self, monkeypatch):
        p, rec = producer([_Truncated(self.PARTIAL)], monkeypatch=monkeypatch)

        with pytest.raises(IntentProductionError) as caught:
            p.produce("a low-pass filter")

        assert caught.value.kind == Failure.TRUNCATED.value
        assert str(MAX_OUTPUT_TOKENS) in str(caught.value)
        assert "budget problem, not a schema problem" in str(caught.value)

    def test_the_same_payload_untruncated_is_a_schema_failure(self, monkeypatch):
        # The discriminating case. Same bytes, different cause, different kind.
        p, rec = producer([self.PARTIAL], monkeypatch=monkeypatch)

        with pytest.raises(IntentProductionError) as caught:
            p.produce("a low-pass filter")

        assert caught.value.kind == Failure.SCHEMA.value

    def test_a_truncated_call_is_not_retried(self, monkeypatch):
        # Retrying a truncation makes it strictly worse: the failed attempt is
        # appended to the conversation, so attempt two has less room than one.
        p, rec = producer([_Truncated(self.PARTIAL)], monkeypatch=monkeypatch)
        with pytest.raises(IntentProductionError):
            p.produce("a low-pass filter")
        assert len(rec["calls"]) == 1

    def test_the_partial_output_is_kept_as_evidence(self, monkeypatch):
        p, rec = producer([_Truncated(self.PARTIAL)], monkeypatch=monkeypatch)
        with pytest.raises(IntentProductionError) as caught:
            p.produce("a low-pass filter")
        assert caught.value.raw == self.PARTIAL

    def test_the_request_asks_for_the_declared_ceiling(self, monkeypatch):
        p, rec = producer([IN_ENVELOPE], monkeypatch=monkeypatch)
        p.produce("RC low-pass at 1 kHz")
        assert rec["calls"][0]["max_tokens"] == MAX_OUTPUT_TOKENS


class TestTheEvidenceSurvivesTheHandler:
    """
    Departure 1 attaches the raw tool input to the exception. An exception
    announces a broken assumption only to whoever is holding it; `as_log_entry`
    is what turns it into a row that can still be counted next month.
    """

    def test_carries_kind_message_and_raw(self):
        exc = IntentProductionError(
            "does not fit", raw={"targets": {"cutoff_hz": 1000}}, kind=Failure.SCHEMA
        )
        entry = exc.as_log_entry()
        assert entry.startswith("intent_production_failed[schema]:")
        assert "does not fit" in entry
        assert '"cutoff_hz": 1000' in entry

    def test_kind_is_the_plain_value_not_the_enum_repr(self):
        # `str, Enum` members format as "Failure.SCHEMA" under an f-string,
        # which is not what should reach a log line or an HTTP body.
        exc = IntentProductionError("x", kind=Failure.TRUNCATED)
        assert exc.kind == "truncated"
        assert "Failure." not in exc.as_log_entry()

    def test_a_runaway_raw_is_capped(self):
        exc = IntentProductionError("x", raw={"junk": "y" * 50_000})
        entry = exc.as_log_entry()
        assert len(entry) < 5_000
        assert "truncated" in entry and "chars total" in entry

    def test_unserialisable_raw_still_produces_an_entry(self):
        # The evidence path must never be the thing that raises: a logging
        # failure on an error path would hide the error it was recording.
        exc = IntentProductionError("x", raw={"blocks": {object()}})
        assert "intent_production_failed" in exc.as_log_entry()


class TestTheRouteRecordsTheEvidence:
    """
    The last link in Departure 1.

    Attaching the raw tool input to the exception only helps if something
    durably writes it down: an exception announces a broken assumption to
    whoever is holding it and nobody else. This asserts the design route puts
    it in the row, because that is the difference between "schema failure is
    structurally impossible" being *measured* and being merely *claimed*.
    """

    def _client(self, exc, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routes import design as design_route
        from api.routes.auth import get_current_user
        from db.models import get_db
        from middleware.instrumentation import RequestLogMiddleware
        from middleware.rate_limit import limiter

        rows = []

        class CapturingLogger:
            async def record(self, row):
                rows.append(row)
                return True

        app = FastAPI()
        app.state.limiter = limiter
        app.add_middleware(RequestLogMiddleware, logger=CapturingLogger())
        app.include_router(design_route.router, prefix="/design")

        async def _no_db():
            yield None

        app.dependency_overrides[get_db] = _no_db
        app.dependency_overrides[get_current_user] = lambda: type(
            "U", (), {"id": "00000000-0000-0000-0000-000000000001"}
        )()

        class Failing:
            def __init__(self, registry=None):
                pass

            def produce(self, prompt):
                raise exc

        # monkeypatch, not assignment: a bare rebind here would leak the
        # failing producer into every later test that imports this module.
        monkeypatch.setattr(design_route, "IntentProducer", Failing)
        return TestClient(app, raise_server_exceptions=False), rows

    def test_raw_tool_input_reaches_the_log_row(self, monkeypatch):
        raw = {"targets": {"cutoff_hz": 1000}}  # no `function` — truncated mid-write
        exc = IntentProductionError(
            "truncated", raw=raw, kind=Failure.TRUNCATED
        )
        client, rows = self._client(exc, monkeypatch)

        resp = client.post("/design/generate", json={"prompt": "a low-pass filter"})

        assert resp.status_code == 422
        assert resp.json()["detail"]["kind"] == "truncated"
        assert rows, "the request produced no log row at all"
        assert "cutoff_hz" in (rows[0].error or ""), (
            "the raw tool input did not survive the handler — Departure 1 "
            "attaches evidence that nothing then records"
        )
        assert "[truncated]" in (rows[0].error or "")

    def test_a_schema_failure_is_recorded_under_its_own_kind(self, monkeypatch):
        # The two must be distinguishable in the table, not just in the code.
        exc = IntentProductionError("bad", raw={"x": 1}, kind=Failure.SCHEMA)
        client, rows = self._client(exc, monkeypatch)
        client.post("/design/generate", json={"prompt": "x"})
        assert "[schema]" in (rows[0].error or "")
