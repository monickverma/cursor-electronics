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
already recorded. `_requested_values` is that check. The asymmetry is
deliberate: supplying a missing field is transcription catching up with the
request, while altering a recorded one is the model substituting its own.

The consequence is deliberate: a request genuinely outside the catalogue is
refused, not negotiated. §4.2 says users should self-select against a visible
catalogue, and §4.6 defers the labelled ring precisely so uncovered requests
get refused rather than guessed at.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ai.client import ai_model, make_client
from core.intent_ir import IntentIR, Producer, Provenance, Requirements
from generators.registry import GeneratorRegistry, default_registry
from observability.request_log import prompt_hash

MAX_SEMANTIC_RETRIES = 1

SYSTEM_PROMPT = """\
You transcribe a hardware request into a structured requirement. You are not \
designing anything and you must not choose components, topologies or part \
numbers — a deterministic generator does that afterwards from what you record.

Record only what the user actually asked for.

- `function` is what the circuit is for, from the catalogue given below. If \
the request does not match any catalogue entry, record the closest honest \
description anyway; refusing is the system's job, not yours, and inventing a \
match hides a gap in the catalogue.
- `targets` are the numbers the design will be checked against.
- `constraints` bound the design without being goals.
- `preferences` may be traded away.
- `underdetermined` lists fields the request does not pin down, as \
`section.field` paths. Leave a field out of the requirement AND name it here \
rather than guessing a value. A guessed value becomes a target the user never \
set.

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
    """

    def __init__(self, message: str, raw: Any = None, refusals: str = "") -> None:
        self.raw = raw
        self.refusals = refusals
        super().__init__(message)


def _requested_values(requirements: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Every value the user asked for, flattened to `section.field`.

    Used to prove a retry did not rewrite the request. Preferences are
    included: a model that quietly swaps the package has also changed what was
    asked for, even if nothing downstream would refuse it.
    """
    flat: Dict[str, Any] = {}
    for section in ("targets", "constraints", "preferences"):
        values = requirements.get(section) or {}
        if isinstance(values, Mapping):
            for key, value in values.items():
                flat[f"{section}.{key}"] = value
    return flat


class IntentProducer:
    """Prompt → IntentIR. One model call, or two when a retry is warranted."""

    def __init__(self, registry: Optional[GeneratorRegistry] = None) -> None:
        self.client = make_client()
        self._registry = registry if registry is not None else default_registry()

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
            requirements, underdetermined = self._split(raw)

            # Schema: validated once, never re-prompted. X5.
            try:
                Requirements.model_validate(requirements)
            except Exception as exc:  # noqa: BLE001
                raise IntentProductionError(
                    f"model returned a requirement that does not fit the schema: {exc}",
                    raw=raw,
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

    def _user_content(self, prompt: str) -> str:
        catalogue = ", ".join(self._registry.functions()) or "(nothing installed)"
        return (
            f"CATALOGUE (functions this system builds): {catalogue}\n\n"
            f"REQUEST:\n{prompt}"
        )

    def _call(self, messages: List[Dict[str, Any]]) -> Any:
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[_INTENT_TOOL],
            tool_choice={"type": "tool", "name": _INTENT_TOOL["name"]},
            messages=messages,
        )
        for block in response.content:
            tool_input = getattr(block, "input", None)
            if tool_input is not None:
                return tool_input
        raise IntentProductionError(
            "model returned no tool_use block",
            raw=[getattr(b, "type", type(b).__name__) for b in response.content],
        )

    def _split(self, raw: Any) -> Tuple[Dict[str, Any], List[str]]:
        if not isinstance(raw, Mapping):
            raise IntentProductionError(
                f"tool input was {type(raw).__name__}, not an object", raw=raw
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
