"""
The LLM patcher for IntentIR. PHASE_2_PLAN_v2.md §4.1, Stage 2; X2 + X4.

Replaces `ai/patcher.py`, which let a model write CircuitIR component fields
directly — an LLM → CircuitIR path that the Task 1.5 scanner missed because it
went through `model_copy(update=...)`. This module writes **operations on a
requirement** and nothing else. It does not import `CircuitIR`; it is told the
design's part ids as plain data so that "use the 4.7 k I have" can name R1.

Like `ai/intent_producer.py`, it is a convenience layer: the patch route also
accepts RFC 6902 operations directly, with zero model calls, which is what
keeps patching LLM-optional (§4.2).

**The guard: every operation cites the command.** X5's rule for the producer —
a retry may add, never rewrite — cannot govern a patch, because a patch is a
rewrite by definition. The failure it has to stop is a model that, asked to
change the cutoff, also "helpfully" changes the supply. So each operation
carries `because`: the exact words of the user's command that asked for it,
checked mechanically as a substring. An operation that cannot point at the
text that motivated it is refused with the rest of the patch.

What it does **not** catch, stated so nobody believes otherwise: a value
mis-transcribed from words that were cited — "2 kHz" recorded as 20000. The
route returns the requirement diff with every patch so the user can see it;
the exposure is the one `brain/decisions.md` [2026-09-21] names for the
producer. A check that the path's name appears in the command was considered
and rejected as a heuristic dressed as a guard.

**No retries of any kind.** Schema failures raise with the raw tool input
(X5); a patch the envelope refuses is reported and the user rephrases. A
semantic retry is where a model would negotiate the requirement until it fits.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Dict, List, Mapping, Sequence

from ai.client import ai_model, make_client
from core.intent_ir import IntentIR
from core.intent_patch import PatchOp

#: A patch is a handful of operations; this is generous for a non-reasoning model.
MAX_OUTPUT_TOKENS = 2048


class PatchFailure(str, Enum):
    SCHEMA = "schema"
    TRUNCATED = "truncated"
    NO_TOOL_USE = "no_tool_use"
    MALFORMED_TOOL_INPUT = "malformed_tool_input"
    UNCITED_OPERATION = "uncited_operation"


class IntentPatchError(Exception):
    """A command that could not be turned into usable operations. Carries the evidence."""

    def __init__(self, message: str, raw: Any = None, kind: "PatchFailure | str" = PatchFailure.SCHEMA) -> None:
        self.raw = raw
        self.kind = kind.value if isinstance(kind, Enum) else str(kind)
        super().__init__(message)

    def as_log_entry(self, max_raw_chars: int = 4000) -> str:
        """One line for `request_log.error`, raw capped — same shape as the producer's."""
        try:
            raw = json.dumps(self.raw, default=str, sort_keys=True)
        except (TypeError, ValueError):  # pragma: no cover - default=str is broad
            raw = repr(self.raw)
        if len(raw) > max_raw_chars:
            raw = f"{raw[:max_raw_chars]}…[truncated, {len(raw)} chars total]"
        return f"intent_patch_failed[{self.kind}]: {self} | raw={raw}"


class ProposedPatch:
    """Operations, each with the words of the command that asked for it."""

    __slots__ = ("ops", "citations", "note_to_user")

    def __init__(self, ops: Sequence[PatchOp], citations: Sequence[str], note_to_user: str) -> None:
        self.ops = tuple(ops)
        self.citations = tuple(citations)
        self.note_to_user = note_to_user


SYSTEM_PROMPT = """\
You edit a hardware *requirement*, never a design. A deterministic generator \
rebuilds the circuit from the requirement afterwards; you must not choose \
components, values or part numbers yourself.

You receive the current requirement as JSON, the catalogue of circuit \
functions the system builds, the ids of the parts in the current design, and \
the user's change request. Return RFC 6902 operations whose paths are JSON \
Pointers into the requirement: /function, /targets/<name>, \
/constraints/<name>, /preferences/<name>.

Rules:
- Change only what the user asked for. Every operation must include \
`because`: the exact words from the change request that ask for it, copied \
verbatim. An operation you cannot justify with the user's own words must not \
be returned.
- Never convert a value the user gave into a different one. 2 kHz is 2000.
- When the user wants to use a specific part they already have, pin it: \
add /constraints/pinned/<part id> with the value they gave, e.g. "4.7k".
- If the request cannot be expressed as a change to the requirement, return \
no operations and explain in note_to_user.\
"""

_PATCH_TOOL: Dict[str, Any] = {
    "name": "propose_requirement_patch",
    "description": "Return RFC 6902 operations on the requirement, each citing the user's words.",
    "input_schema": {
        "type": "object",
        "required": ["operations"],
        "properties": {
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["op", "path", "because"],
                    "properties": {
                        "op": {"type": "string", "enum": ["add", "remove", "replace"]},
                        "path": {"type": "string", "description": "JSON Pointer, e.g. /targets/cutoff_hz"},
                        "value": {"description": "New value; omitted for remove"},
                        "because": {"type": "string", "description": "Verbatim words from the change request"},
                    },
                },
            },
            "note_to_user": {"type": "string"},
        },
    },
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def cites_command(citation: Any, command: str) -> bool:
    """True if `citation` is a non-empty verbatim span of `command`, modulo case and spacing."""
    if not isinstance(citation, str) or not citation.strip():
        return False
    return _normalise(citation) in _normalise(command)


class IntentPatcher:
    """Command → operations. Exactly one model call."""

    def __init__(self, catalogue: Sequence[str] = ()) -> None:
        self.client = make_client()
        self._catalogue = tuple(catalogue)

    def propose(
        self,
        intent: IntentIR,
        command: str,
        parts: Sequence[Mapping[str, Any]] = (),
    ) -> ProposedPatch:
        raw = self._call(self._user_content(intent, command, parts))
        if not isinstance(raw, Mapping) or not isinstance(raw.get("operations"), list):
            raise IntentPatchError(
                "tool input did not carry an operations list",
                raw=raw, kind=PatchFailure.MALFORMED_TOOL_INPUT,
            )

        ops: List[PatchOp] = []
        citations: List[str] = []
        for index, item in enumerate(raw["operations"]):
            if not isinstance(item, Mapping):
                raise IntentPatchError(
                    f"operation {index} is {type(item).__name__}, not an object",
                    raw=raw, kind=PatchFailure.SCHEMA,
                )
            because = item.get("because")
            if not cites_command(because, command):
                raise IntentPatchError(
                    f"operation {index} ({item.get('op')} {item.get('path')}) cites "
                    f"{because!r}, which is not in the command — an operation the "
                    f"user did not ask for is refused with the whole patch",
                    raw=raw, kind=PatchFailure.UNCITED_OPERATION,
                )
            try:
                ops.append(PatchOp.model_validate(
                    {k: v for k, v in item.items() if k != "because"}
                ))
            except Exception as exc:  # noqa: BLE001
                raise IntentPatchError(
                    f"operation {index} is not a valid RFC 6902 operation: {exc}",
                    raw=raw, kind=PatchFailure.SCHEMA,
                ) from exc
            citations.append(because)

        return ProposedPatch(ops, citations, str(raw.get("note_to_user") or ""))

    # ── Plumbing ──────────────────────────────────────────────────────────

    def _user_content(
        self, intent: IntentIR, command: str, parts: Sequence[Mapping[str, Any]]
    ) -> str:
        part_lines = "\n".join(
            f"  {p.get('id')}: {p.get('type')}" + (f", value {p['value']}" if p.get("value") else "")
            for p in parts
        ) or "  (none)"
        return (
            f"CATALOGUE (functions this system builds): {', '.join(self._catalogue) or '(none)'}\n\n"
            f"CURRENT REQUIREMENT:\n{json.dumps(intent.requirements, sort_keys=True, indent=2)}\n\n"
            f"PARTS IN THE CURRENT DESIGN:\n{part_lines}\n\n"
            f"CHANGE REQUEST: {command}"
        )

    def _call(self, content: str) -> Any:
        response = self.client.messages.create(
            model=ai_model(),
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[_PATCH_TOOL],
            tool_choice={"type": "tool", "name": _PATCH_TOOL["name"]},
            messages=[{"role": "user", "content": content}],
        )
        partial = next(
            (b.input for b in response.content if getattr(b, "input", None) is not None),
            None,
        )
        # A truncated tool call looks exactly like a schema failure. Named
        # separately for the same reason the producer does it.
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise IntentPatchError(
                f"the model hit the {MAX_OUTPUT_TOKENS}-token ceiling and its tool call "
                f"was truncated — a budget problem, not a schema one "
                f"(model: {ai_model()!r})",
                raw=partial, kind=PatchFailure.TRUNCATED,
            )
        if partial is None:
            raise IntentPatchError(
                "model returned no tool_use block",
                raw=[getattr(b, "type", type(b).__name__) for b in response.content],
                kind=PatchFailure.NO_TOOL_USE,
            )
        return partial
