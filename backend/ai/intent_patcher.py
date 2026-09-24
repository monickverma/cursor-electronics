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

**The guard: every operation cites the command, and the citation carries its
value.** X5's rule for the producer — a retry may add, never rewrite — cannot
govern a patch, because a patch is a rewrite by definition. The failure it has
to stop is a model that, asked to change the cutoff, also "helpfully" changes
the supply. So each operation carries `because`, the user's words that asked
for it, and three things are checked mechanically:

1. **Verbatim and whole-word.** The citation is a span of the command, modulo
   case and spacing, starting and ending on word boundaries — `"e"` is not a
   citation of anything.
2. **One span, one operation.** Citations are assigned non-overlapping spans
   of the command. A model cannot justify a second change by quoting the
   words that justified the first.
3. **The value is in the span.** An operation that writes a value must cite
   words containing it. Numbers compare as quantities, so "2 kHz" grounds
   2000 and not 20000; strings compare as text. A relative request — "double
   the cutoff" — grounds nothing, and is refused until the user states the
   value.

The first version checked only (1), without word alignment, and the Stage 2
verification got an uncited supply change through it both by quoting the whole
command and by quoting `"e"`. Rule 3 also closes most of what that version
listed as uncaught: a value mis-transcribed from words that were cited.

What it still does **not** catch, stated so nobody believes otherwise: values
swapped between two operations whose spans each contain the other's number
("cutoff 2 kHz and supply 12 V" recorded as cutoff 12, supply 2000), and a
removal citing an unrelated whole word — a removal writes no value to ground.
The route returns the requirement diff with every patch so the user can see
it. A check that the path's name appears in the command was considered and
rejected as a heuristic dressed as a guard; so is binding spans to paths.

**No retries of any kind.** Schema failures raise with the raw tool input
(X5); a patch the envelope refuses is reported and the user rephrases. A
semantic retry is where a model would negotiate the requirement until it fits.
"""

from __future__ import annotations

import json
import math
import re
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
    UNGROUNDED_VALUE = "ungrounded_value"
    SHARED_CITATION = "shared_citation"


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
verbatim, and those words must contain the value you write — for 2000, cite \
"cutoff 2 kHz", not "cutoff". Each operation cites its own words; two \
operations may not quote the same words. An operation you cannot justify with \
the user's own words must not be returned.
- Never convert a value the user gave into a different one. 2 kHz is 2000.
- If the user asks for a relative change without stating the new value \
("double the cutoff", "a bit higher"), return no operations and ask for the \
value in note_to_user.
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
                        "because": {"type": "string", "description": "Verbatim words from the change request, containing the value written"},
                    },
                },
            },
            "note_to_user": {"type": "string"},
        },
    },
}


def _spaced(text: str) -> str:
    """Whitespace collapsed, case kept — case carries meaning in "2 MHz" vs "2 mHz"."""
    return re.sub(r"\s+", " ", text).strip()


Span = Tuple[int, int]


def citation_spans(citation: Any, command: str) -> List[Span]:
    """
    Every place `citation` occurs in `command`, modulo case and spacing, on
    word boundaries. Positions are in `_spaced(command)`. Overlapping
    occurrences are all returned; choosing among them is `_assign`'s job.
    """
    if not isinstance(citation, str) or not citation.strip():
        return []
    quoted = _spaced(citation)
    pattern = re.escape(quoted)
    if quoted[0].isalnum():
        pattern = r"(?<!\w)" + pattern
    if quoted[-1].isalnum():
        pattern += r"(?!\w)"
    return [
        (m.start(1), m.end(1))
        for m in re.finditer(f"(?=({pattern}))", _spaced(command), re.IGNORECASE)
    ]


def cites_command(citation: Any, command: str) -> bool:
    """True if `citation` is a whole-word verbatim span of `command`, modulo case and spacing."""
    return bool(citation_spans(citation, command))


# ── Grounding a value in the words that asked for it ─────────────────────────

_PREFIXES = {
    "pico": 1e-12, "nano": 1e-9, "micro": 1e-6, "milli": 1e-3,
    "kilo": 1e3, "mega": 1e6, "giga": 1e9, "meg": 1e6, "Meg": 1e6, "MEG": 1e6,
    "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
    "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
}

#: A number, an optional SI prefix (case-sensitive: m is milli, M is mega),
#: optional R-notation digits ("4k7"), an optional unit, and then no letter or
#: digit — so "5 more" is 5, "3rd" is nothing, and "R1" is nothing.
_QUANTITY = re.compile(
    r"(?<![\w.])"
    r"(?P<sign>[-−+])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|\.\d+)"
    r"(?:\s*(?P<prefix>" + "|".join(sorted(map(re.escape, _PREFIXES), key=len, reverse=True)) + r")"
    r"(?P<rdigits>\d+)?)?"
    r"(?:\s*(?i:hz|volts?|v|amps?|a|farads?|f|ohms?|Ω|%|percent))?"
    r"(?![A-Za-z0-9])"
)


def quantities(text: str) -> List[float]:
    """Every quantity written in `text`, in SI base units: "2 kHz" → 2000.0, "4k7" → 4700.0."""
    # "kilohm" and "megohm" share the o between prefix and unit.
    text = re.sub(r"(?i)(?<![a-z])(?:(kil)|(meg))ohm", lambda m: "kilo ohm" if m.group(1) else "mega ohm", text)
    found = []
    for m in _QUANTITY.finditer(text):
        num, prefix, rdigits = m.group("num").replace(",", ""), m.group("prefix"), m.group("rdigits")
        if rdigits:
            if "." in num or "e" in num.lower():
                continue          # "4.7K5" is not a value; refuse rather than guess
            num = f"{num}.{rdigits}"
        value = float(num) * (_PREFIXES[prefix] if prefix else 1.0)
        found.append(-value if m.group("sign") in ("-", "−") else value)
    return found


def _as_quantity(text: str) -> Optional[float]:
    """The one quantity a string *is* ("4.7k", "100nF"), or None if it is not one."""
    m = _QUANTITY.fullmatch(text.strip())
    if m is None:
        return None
    values = quantities(text.strip())
    return values[0] if len(values) == 1 else None


def _squash(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def grounded(value: Any, text: str) -> bool:
    """True if `text` — the cited words — contains `value`."""
    if isinstance(value, bool) or value is None:
        return False                     # neither is something a user writes as a value
    if isinstance(value, (int, float)):
        return any(math.isclose(q, value, rel_tol=1e-9, abs_tol=1e-15) for q in quantities(text))
    if isinstance(value, str):
        as_number = _as_quantity(value)
        if as_number is not None:
            return grounded(as_number, text)
        return bool(_squash(value)) and _squash(value) in _squash(text)
    if isinstance(value, Mapping):
        return all(grounded(v, text) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(grounded(v, text) for v in value)
    return False


def _assign(candidates: Sequence[Sequence[Span]]) -> Optional[List[Span]]:
    """One span per operation, no two overlapping, or None. Patches are small; backtrack."""
    chosen: List[Span] = []

    def place(i: int) -> bool:
        if i == len(candidates):
            return True
        for span in candidates[i]:
            if all(span[1] <= s or span[0] >= e for s, e in chosen):
                chosen.append(span)
                if place(i + 1):
                    return True
                chosen.pop()
        return False

    return list(chosen) if place(0) else None


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
        candidates: List[List[Span]] = []
        spaced = _spaced(command)
        for index, item in enumerate(raw["operations"]):
            if not isinstance(item, Mapping):
                raise IntentPatchError(
                    f"operation {index} is {type(item).__name__}, not an object",
                    raw=raw, kind=PatchFailure.SCHEMA,
                )
            because = item.get("because")
            spans = citation_spans(because, command)
            if not spans:
                raise IntentPatchError(
                    f"operation {index} ({item.get('op')} {item.get('path')}) cites "
                    f"{because!r}, which is not in the command as whole words — an "
                    f"operation the user did not ask for is refused with the whole patch",
                    raw=raw, kind=PatchFailure.UNCITED_OPERATION,
                )
            try:
                op = PatchOp.model_validate({k: v for k, v in item.items() if k != "because"})
            except Exception as exc:  # noqa: BLE001
                raise IntentPatchError(
                    f"operation {index} is not a valid RFC 6902 operation: {exc}",
                    raw=raw, kind=PatchFailure.SCHEMA,
                ) from exc
            if op.op != "remove":
                # Grounded against the command's own text at the span, not the
                # model's copy of it: case decides milli versus mega.
                spans = [s for s in spans if grounded(op.value, spaced[s[0]:s[1]])]
                if not spans:
                    raise IntentPatchError(
                        f"operation {index} ({op.describe()}) cites {because!r}, which "
                        f"does not contain {json.dumps(op.value, default=str)} — every value "
                        f"written must appear in the words that asked for it. If the "
                        f"request was relative, state the new value (e.g. 'cutoff 2 kHz')",
                        raw=raw, kind=PatchFailure.UNGROUNDED_VALUE,
                    )
            ops.append(op)
            citations.append(because)
            candidates.append(spans)

        if _assign(candidates) is None:
            raise IntentPatchError(
                "two operations rest on the same words of the command — each change "
                "must be asked for by words of its own, so a quote cannot justify a "
                "second edit the user did not make",
                raw=raw, kind=PatchFailure.SHARED_CITATION,
            )

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
