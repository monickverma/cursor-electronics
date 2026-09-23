"""
The LLM producer for IntentIR. PHASE_2_PLAN_v2.md §4.2 and §5 Stage 1.

> **The LLM** is a convenience layer over the same schema, for free text.

Convenience layer is the whole job description. The form producer in
`ai/form_producer.py` is the reference, this is a transcription service on top
of it, and nothing downstream can tell which one wrote an intent except by
reading `provenance`.

**Amendment X5, as implemented here.** The plan retires the retry loop for
schema failures and keeps it for semantic rejections. Both halves are here,
and the second one needed a guard the plan does not mention:

*Schema failures do not retry.* Forced `tool_choice` returns a parsed dict
conforming to the tool schema, so re-prompting for a schema failure re-prompts
for something that should not happen. But "should not happen" is an empirical
claim about frontier models — §4.3 concedes it is only structural under
constrained decoding, which is unbuilt — so a schema failure raises
`IntentProductionError` carrying the raw tool input. Loud, once, with the
evidence attached, rather than silently absorbed by a retry that hides how
often it fires.

*Semantic rejections retry once, and may not rewrite what was asked for.* This
is the guard. A refusal from `envelope()` is a reason the model can act on,
but the fix most available to a model is to **alter the requirement until it
fits** — quietly turning "I need 2 MHz" into "1 kHz" and handing back a design
the user never asked for. That would defeat the entire point of materializing
the requirement.

So a retry may **add** a value it failed to record the first time, which is
the correction the retry exists for, but may not **change or drop** one it
already recorded. `_requested_values` is that check, and it covers
`requirements.function` as well as the three value sections — a guard that
watched only the sections could be walked straight through by rewriting
`band_pass_filter` to `low_pass_filter` with every target untouched.

*A truncated tool call is not a schema failure.* `_call` checks `stop_reason`
before anything else, because a call cut off at the token ceiling produces a
partial dict that fails validation for missing fields and looks exactly like
the model getting the schema wrong. Reporting it as schema would corrupt the
one measurement Departure 1 exists to take. `Failure` names each cause so the
evidence can be counted by kind.

**The field catalogue, and questions decided by code** (Stage 3 + 4
verification, live). The model used to be told the catalogue's function
names only, so it invented field names — `targets.output_v` for the divider's
`targets.vout_v` — and listed as "underdetermined" fields no generator reads
(`targets.order`, `stopband_attenuation_db`). With the Stage 1 rule
"underdetermined → ask, never generate", every plain request came back as a
page of questions. The prompt now carries each function's fields — path,
units, required or optional — from the form catalogue, which is the envelope
catalogue; and `underdetermined` keeps only what the model flags that is a
REQUIRED field of the chosen function and really unset — invented, optional
and already-recorded fields are dropped. A required field the model neither
records nor flags goes to the envelope and X5's retry, as before. An
uncatalogued function has nothing to ask — the registry refuses it.

The consequence is deliberate: a request genuinely outside the catalogue is
refused, not negotiated. §4.2 says users should self-select against a visible
catalogue, and §4.6 defers the labelled ring precisely so uncovered requests
get refused rather than guessed at.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ai.client import ai_model, make_client
from core.intent_ir import IntentIR, Producer, Provenance, Requirements
from generators.registry import GeneratorRegistry, default_registry
from observability.request_log import prompt_hash

MAX_SEMANTIC_RETRIES = 1

#: Output ceiling for one transcription. Named rather than inlined because the
#: truncation guard below reports it: a reader who hits that error needs to
#: know which number to raise. An IntentIR is small, so this is generous for a
#: non-reasoning model — a model that emits long thinking blocks before its
#: tool call may need more, and will now say so instead of failing as schema.
MAX_OUTPUT_TOKENS = 2048


class Failure(str, Enum):
    """
    Why a transcription could not be used.

    X5's argument for retiring schema retries is that the failure becomes
    *visible* instead of absorbed. Visible is not the same as classifiable: an
    error that lumps a truncated tool call together with a genuine schema
    violation reports that "schema failure is structurally impossible" broke
    when in fact the token ceiling was too low. The evidence has to name which
    thing happened or it cannot answer the question it was collected for.
    """

    SCHEMA = "schema"
    TRUNCATED = "truncated"
    NO_TOOL_USE = "no_tool_use"
    MALFORMED_TOOL_INPUT = "malformed_tool_input"
    RETRY_REWROTE_REQUEST = "retry_rewrote_request"

SYSTEM_PROMPT = """\
You transcribe a hardware request into a structured requirement. You are not \
designing anything and you must not choose components, topologies or part \
numbers — a deterministic generator does that afterwards from what you record.

Record only what the user actually asked for.

- `function` is what the circuit is for, from the catalogue given below. If \
the request does not match any catalogue entry, record the closest honest \
description anyway; refusing is the system's job, not yours, and inventing a \
match hides a gap in the catalogue.
- For a catalogue function, record each value under the exact field path the \
catalogue lists for it, in the listed units — 2 kHz is 2000 for a field in \
Hz. Do not rename a listed field. A value the user gave that fits none of the \
listed fields may be recorded under a short snake_case name in its section.
- `targets` are the numbers the design will be checked against.
- `constraints` bound the design without being goals.
- `preferences` may be traded away.
- `underdetermined` lists REQUIRED catalogue fields of the chosen function \
that the request does not state, as `section.field` paths. Leave such a field \
out of the requirement AND name it here rather than guessing a value — a \
guessed value becomes a target the user never set. Optional fields the \
request does not mention are simply left out; they are not questions.

Never convert a value the user gave into a different one. If they said 2 MHz, \
record 2000000, even if it looks out of range.\
"""

_INTENT_TOOL: Dict[str, Any] = {
    "name": "record_requirement",
    "description": "Record the user's hardware requirement as structured data.",
    "input_schema": {
        "type": "object",
        "required": ["function"],
        "properties": {
            "function": {
                "type": "string",
                "description": "What the circuit is for, e.g. low_pass_filter",
            },
            "targets": {
                "type": "object",
                "description": "Numbers the design is checked against, e.g. cutoff_hz",
            },
            "constraints": {
                "type": "object",
                "description": "Bounds that are not goals, e.g. supply_v",
            },
            "preferences": {
                "type": "object",
                "description": "Tradeable choices, e.g. package",
            },
            "underdetermined": {
                "type": "array",
                "items": {"type": "string"},
                "description": "section.field paths the request does not pin down",
            },
        },
    },
}


class IntentProductionError(Exception):
    """
    Raised when a prompt could not be turned into a usable IntentIR.

    Carries `raw` — whatever the model actually returned — because the whole
    argument for retiring schema retries is that the failure should be visible
    rather than absorbed. An error without the evidence would make X5 strictly
    worse than the loop it replaces.

    `kind` says which failure it was, so the evidence can be counted by cause
    rather than by volume. See `Failure`.
    """

    def __init__(
        self,
        message: str,
        raw: Any = None,
        refusals: str = "",
        kind: "Failure | str" = Failure.SCHEMA,
    ) -> None:
        self.raw = raw
        self.refusals = refusals
        # Normalised to the plain string: `str, Enum` members format as
        # "Failure.SCHEMA" under f-strings, which is not what should reach a
        # log line or an HTTP body.
        self.kind = kind.value if isinstance(kind, Enum) else str(kind)
        super().__init__(message)

    def as_log_entry(self, max_raw_chars: int = 4000) -> str:
        """
        One line for `request_log.error`, carrying the evidence with it.

        Departure 1 of X5 attaches the raw tool input to this exception so a
        broken assumption announces itself. An exception is not a record: it
        lives until the handler returns. This is what makes it durable, and
        `request_log.error` is the column it fits in — `request_log` has no
        JSONB slot for it and this repo has no migration tool, so adding one
        would silently push *every* row to the sidecar on any existing volume
        until someone applied the DDL by hand.

        The raw is capped: a runaway tool input should not bloat every row of
        the table that has to stay queryable to be worth writing.
        """
        try:
            raw = json.dumps(self.raw, default=str, sort_keys=True)
        except (TypeError, ValueError):  # pragma: no cover - default=str is broad
            raw = repr(self.raw)
        if len(raw) > max_raw_chars:
            raw = f"{raw[:max_raw_chars]}…[truncated, {len(raw)} chars total]"
        return f"intent_production_failed[{self.kind}]: {self} | raw={raw}"


def _requested_values(requirements: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Every value the user asked for, flattened to `section.field`.

    Used to prove a retry did not rewrite the request. Preferences are
    included: a model that quietly swaps the package has also changed what was
    asked for, even if nothing downstream would refuse it.

    **`function` is in here, and leaving it out was a hole in the guard.** It
    is the one *required* field and it does not live inside a section, so the
    original flatten never saw it. A retry told "no generator accepted this"
    could rewrite `band_pass_filter` to `low_pass_filter` while leaving every
    target byte-identical — passing an add-only check that never looked at the
    field, and handing the user the wrong circuit at exactly the cutoff they
    asked for. That is the negotiation this guard exists to forbid, routed
    through the one field it did not cover.
    """
    flat: Dict[str, Any] = {}

    # Compared stripped, because `Requirements` strips on validation: a retry
    # returning the same name with different surrounding whitespace has
    # changed formatting, not the request, and must not trip the guard.
    function = requirements.get("function")
    flat["function"] = function.strip() if isinstance(function, str) else function

    for section in ("targets", "constraints", "preferences"):
        values = requirements.get(section) or {}
        if isinstance(values, Mapping):
            for key, value in values.items():
                flat[f"{section}.{key}"] = value
    return flat


class IntentProducer:
    """Prompt → IntentIR. One model call, or two when a retry is warranted."""

    def __init__(self, registry: Optional[GeneratorRegistry] = None) -> None:
        from ai.form_producer import FormProducer

        self.client = make_client()
        self._registry = registry if registry is not None else default_registry()
        self._forms = FormProducer(self._registry)

    def produce(self, prompt: str) -> IntentIR:
        """
        Transcribe `prompt`. Raises `IntentProductionError` if it cannot.

        A returned IntentIR may still be underdetermined or outside every
        envelope — both are legitimate outcomes that the caller surfaces.
        Only a failure to produce a well-formed requirement raises.
        """
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": self._user_content(prompt)}
        ]
        raw: Any = None
        first_requested: Optional[Dict[str, Any]] = None

        for attempt in range(MAX_SEMANTIC_RETRIES + 1):
            raw = self._call(messages)
            requirements, claimed = self._split(raw)
            underdetermined = self._questions(requirements, claimed)

            # Schema: validated once, never re-prompted. X5.
            try:
                Requirements.model_validate(requirements)
            except Exception as exc:  # noqa: BLE001
                raise IntentProductionError(
                    f"model returned a requirement that does not fit the schema: {exc}",
                    raw=raw,
                    kind=Failure.SCHEMA,
                ) from exc

            intent = IntentIR(
                requirements=requirements,
                underdetermined=underdetermined,
                provenance=Provenance(
                    producer=Producer.LLM,
                    model=ai_model(),
                    prompt_hash=prompt_hash(prompt),
                ),
            )

            if first_requested is None:
                first_requested = _requested_values(requirements)
            else:
                # A retry may *add* — supplying a field it failed to record the
                # first time is the correction this retry exists for. It may
                # not change or drop anything it already recorded: that is the
                # move that turns "I need 2 MHz" into "1 kHz" and hands back a
                # design the user never asked for.
                current = _requested_values(requirements)
                altered = {
                    key: (was, current.get(key, "<dropped>"))
                    for key, was in first_requested.items()
                    if current.get(key, "<dropped>") != was
                }
                if altered:
                    raise IntentProductionError(
                        "the retry changed what was asked for rather than how it "
                        f"was recorded; refusing the rewrite. altered={altered}",
                        raw=raw,
                        kind=Failure.RETRY_REWROTE_REQUEST,
                    )

            # Underdetermined is a question for the user, not a retry.
            if not intent.is_answerable:
                return intent

            result = self._registry.dispatch(intent)
            if result.accepted or attempt == MAX_SEMANTIC_RETRIES:
                return intent

            # Semantic rejection with a reason the model can act on. X5.
            messages = self._append_refusal(messages, raw, result.refusal_summary())

        return intent  # pragma: no cover - loop always returns

    # ── Plumbing ──────────────────────────────────────────────────────────

    def _questions(self, requirements: Mapping[str, Any], claimed: List[str]) -> List[str]:
        """
        What to ask the user: fields the model says the request does not state
        (its judgment — only it has read the prose), restricted by code to the
        chosen function's REQUIRED catalogue fields the requirement leaves
        unset. Invented, optional and already-recorded fields are dropped. A
        required field that is missing but *not* claimed is the model failing
        to record what the user said: it goes to the envelope, which refuses
        it by name, and X5's one retry adds it.
        """
        try:
            spec = self._forms.spec_for(str(requirements.get("function")))
        except ValueError:
            return []          # uncatalogued: the registry refuses it with reasons
        wanted = set(claimed)
        out = []
        for field in spec.required_fields():
            path = f"{field.section}.{field.name}"
            section = requirements.get(field.section)
            unset = not isinstance(section, Mapping) or section.get(field.name) is None
            if unset and path in wanted:
                out.append(path)
        return out

    def catalogue_text(self) -> str:
        """Each function the system builds, and the fields it reads."""
        lines = []
        for spec in self._forms.catalogue():
            fields = "; ".join(
                f"{f.section}.{f.name}" + (f" [{f.units}]" if f.units else "")
                + (" required" if f.required else " optional")
                for f in spec.fields
            )
            lines.append(f"- {spec.function}: {fields}")
        return "\n".join(lines) or "(nothing installed)"

    def _user_content(self, prompt: str) -> str:
        return (
            f"CATALOGUE (functions this system builds, and the fields each reads):\n"
            f"{self.catalogue_text()}\n\n"
            f"REQUEST:\n{prompt}"
        )

    def _call(self, messages: List[Dict[str, Any]]) -> Any:
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[_INTENT_TOOL],
            tool_choice={"type": "tool", "name": _INTENT_TOOL["name"]},
            messages=messages,
        )

        partial = self._tool_input(response)

        # A tool call cut off at the token ceiling yields a *partial* dict,
        # which then fails `Requirements` for missing fields — a symptom
        # identical to the model getting the schema wrong. Filing it as a
        # schema failure would make X5's own evidence lie about the one
        # assumption it was collected to test. The module this replaced
        # carried this guard; the rewrite lost it, so it is back.
        #
        # Both clients agree on the marker: `openai_compat` maps OpenAI's
        # `finish_reason: length` onto `max_tokens`.
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise IntentProductionError(
                f"the model hit the {MAX_OUTPUT_TOKENS}-token ceiling and its "
                f"tool call was truncated, so the requirement is incomplete. "
                f"This is a budget problem, not a schema problem — raise "
                f"MAX_OUTPUT_TOKENS in ai/intent_producer.py, or use a model "
                f"that writes less before calling the tool "
                f"(current: {ai_model()!r}).",
                raw=partial,
                kind=Failure.TRUNCATED,
            )

        if partial is not None:
            return partial

        raise IntentProductionError(
            "model returned no tool_use block",
            raw=[getattr(b, "type", type(b).__name__) for b in response.content],
            kind=Failure.NO_TOOL_USE,
        )

    @staticmethod
    def _tool_input(response: Any) -> Any:
        """The first block carrying tool input, or None. Reasoning models put
        a thinking block at index 0, so position is not a safe assumption."""
        for block in response.content:
            tool_input = getattr(block, "input", None)
            if tool_input is not None:
                return tool_input
        return None

    def _split(self, raw: Any) -> Tuple[Dict[str, Any], List[str]]:
        if not isinstance(raw, Mapping):
            raise IntentProductionError(
                f"tool input was {type(raw).__name__}, not an object",
                raw=raw,
                kind=Failure.MALFORMED_TOOL_INPUT,
            )
        payload = dict(raw)
        underdetermined = [str(x) for x in (payload.pop("underdetermined", None) or [])]
        requirements = {
            "function": payload.get("function", ""),
            "targets": payload.get("targets") or {},
            "constraints": payload.get("constraints") or {},
            "preferences": payload.get("preferences") or {},
        }
        return requirements, underdetermined

    def _append_refusal(
        self, messages: List[Dict[str, Any]], raw: Any, refusals: str
    ) -> List[Dict[str, Any]]:
        return messages + [
            {"role": "assistant", "content": json.dumps(raw, default=str)},
            {
                "role": "user",
                "content": (
                    f"No generator accepted that requirement:\n{refusals}\n\n"
                    f"If you mis-recorded the request — wrong field, wrong "
                    f"section, a value that was stated but omitted — correct it. "
                    f"Do NOT change any value the user actually asked for to "
                    f"make it fit; if the request genuinely falls outside the "
                    f"catalogue, return it unchanged and the system will refuse "
                    f"it, which is the correct outcome."
                ),
            },
        ]
