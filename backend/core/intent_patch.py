"""
Patching IntentIR. PHASE_2_PLAN_v2.md §4.1 and Stage 2; amendments X2 + X4.

    IntentIR v(n) ──patch (RFC 6902)──▶ IntentIR v(n+1)
                                              │
                                  envelope() → generate() → predict()

A patch edits what was **asked for**, never what was built. Patching the
CircuitIR directly produced a design no generator produced — no envelope, no
prediction, no proof obligation. Sending the edit through the same gate as a
fresh request means nothing extra has to validate it.

**The operation language is RFC 6902, restricted to `requirements`.** Paths
are JSON Pointers (RFC 6901) rooted at the requirements mapping —
`/targets/cutoff_hz`, `/constraints/pinned/R1` — so a patch cannot reach
`intent_id`, `provenance` or `signed_off` however it is written. `move` and
`copy` are not supported: neither corresponds to anything a user asks for, and
an unsupported operation is refused rather than approximated. One deliberate
departure: an `add` into a missing *container* (`CONTAINERS` — the three
sections and `constraints.pinned`) creates it, because an absent container is
an empty one to every reader of a requirement.

**A patch that changes nothing is not a version** (the Stage 2 idempotence
gate). An empty operation list, or one whose result equals the input, returns
the same IntentIR at the same revision.

**History reads as requirements.** `readable_changes()` renders a patch as
`targets.cutoff_hz: 1000 → 2000`, which is the Stage 2 "readable history"
property; Phase 1's history read `R1: 1590Ω → 795Ω`.

Nothing here talks to a model. `ai/intent_patcher.py` turns a sentence into
operations; this module is what applies them, for that path and for the
zero-call path where a client sends operations directly.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from core.intent_ir import IntentIR, Requirements

#: Top-level members of `requirements` a pointer may start at.
SECTIONS = ("function", "targets", "constraints", "preferences")

#: Objects whose absence means "empty". RFC 6902 §4.1 requires an `add`'s
#: parent to exist; for these, an absent parent *is* an existing empty one,
#: which is how `Requirements` reads a missing section and how a generator
#: reads a missing pin set. So `add /constraints/pinned/R1` works on an intent
#: that never mentioned pinning — the form the patcher is told to emit, which
#: failed on every first pin until the Stage 2 verification found it.
#: Emptying one removes it (`_prune`), so "no pins" has exactly one spelling
#: and adding an empty pin set is not a version.
CONTAINERS = frozenset({
    ("targets",), ("constraints",), ("preferences",),
    ("constraints", "pinned"),
})

_UNSET = object()


class PatchError(ValueError):
    """An operation that cannot be applied. Names the operation and why."""

    def __init__(self, message: str, op_index: Optional[int] = None) -> None:
        self.op_index = op_index
        prefix = f"operation {op_index}: " if op_index is not None else ""
        super().__init__(prefix + message)


class PatchOp(BaseModel):
    """One RFC 6902 operation. `value` is required for add, replace and test."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal["add", "remove", "replace", "test"]
    path: str
    value: Any = None

    @model_validator(mode="before")
    @classmethod
    def _value_present_when_required(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and data.get("op") in ("add", "replace", "test"):
            if "value" not in data:
                raise ValueError(f"'{data.get('op')}' requires a value (RFC 6902 §4)")
        return data

    def describe(self) -> str:
        if self.op == "remove":
            return f"remove {self.path}"
        return f"{self.op} {self.path} = {_fmt(self.value)}"


def parse_pointer(path: str) -> List[str]:
    """
    RFC 6901 pointer → reference tokens, restricted to `requirements`.

    The empty pointer (the whole document) is refused: replacing every
    requirement at once is a new request, not a patch, and should go through
    the producer that writes new requests.
    """
    if not isinstance(path, str) or not path.startswith("/"):
        raise PatchError(f"path {path!r} is not a JSON Pointer (must start with '/')")
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in path[1:].split("/")]
    if not tokens or tokens[0] not in SECTIONS:
        raise PatchError(
            f"path {path!r} is outside requirements — a patch may touch "
            f"{', '.join('/' + s for s in SECTIONS)} only"
        )
    if any(t == "" for t in tokens):
        raise PatchError(f"path {path!r} has an empty segment")
    if tokens[0] == "function" and len(tokens) > 1:
        raise PatchError(f"path {path!r} descends into function, which is a string")
    return tokens


def _resolve(doc: Dict[str, Any], tokens: Sequence[str], create_containers: bool) -> Tuple[Dict[str, Any], str]:
    """The mapping holding the final token, and that token."""
    parent: Any = doc
    for depth, token in enumerate(tokens[:-1]):
        if isinstance(parent, Mapping) and token in parent:
            parent = parent[token]
        elif create_containers and tuple(tokens[:depth + 1]) in CONTAINERS:
            # An absent container is an empty one (see CONTAINERS). Any other
            # missing parent is still an error, as RFC 6902 §4.1 requires.
            parent[token] = {}
            parent = parent[token]
        else:
            raise PatchError(f"/{'/'.join(tokens[:depth + 1])} does not exist")
        if not isinstance(parent, dict):
            raise PatchError(
                f"/{'/'.join(tokens[:depth + 1])} is not an object; only object "
                f"members are patchable in requirements"
            )
    return parent, tokens[-1]


def _apply_one(doc: Dict[str, Any], op: PatchOp) -> None:
    tokens = parse_pointer(op.path)
    parent, key = _resolve(doc, tokens, create_containers=op.op == "add")

    if op.op == "add":
        parent[key] = copy.deepcopy(op.value)
    elif op.op == "replace":
        if key not in parent:
            raise PatchError(f"replace target {op.path} does not exist (RFC 6902 §4.3); use add")
        parent[key] = copy.deepcopy(op.value)
    elif op.op == "remove":
        if tokens == ["function"]:
            raise PatchError("function cannot be removed — every requirement names what the circuit is for")
        if key not in parent:
            raise PatchError(f"remove target {op.path} does not exist (RFC 6902 §4.2)")
        del parent[key]
    elif op.op == "test":
        if parent.get(key, _UNSET) != op.value:
            raise PatchError(
                f"test failed: {op.path} is {_fmt(parent.get(key, _UNSET))}, "
                f"expected {_fmt(op.value)}"
            )


def _prune(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop nested containers left empty (`constraints.pinned: {}`), in place.

    Sections stay: `Requirements` fills them with {} anyway, and removing one
    a producer wrote would be churn with no meaning.
    """
    for path in sorted(CONTAINERS, key=len, reverse=True):
        if len(path) < 2:
            continue
        parent: Any = doc
        for token in path[:-1]:
            parent = parent.get(token) if isinstance(parent, Mapping) else None
        if isinstance(parent, dict) and parent.get(path[-1]) == {}:
            del parent[path[-1]]
    return doc


def _normalised(requirements: Mapping[str, Any]) -> Dict[str, Any]:
    """Requirements with defaults filled and empty containers dropped, for comparing two versions fairly."""
    return Requirements.model_validate(_prune(copy.deepcopy(dict(requirements)))).model_dump()


class PatchOutcome(BaseModel):
    """What a patch did to the requirement."""

    model_config = ConfigDict(frozen=True)

    intent: IntentIR
    changed: bool
    changed_paths: Tuple[str, ...]
    readable: Tuple[str, ...]


def apply_patch(intent: IntentIR, ops: Sequence[PatchOp]) -> PatchOutcome:
    """
    Apply `ops` atomically: every operation applies, or none does.

    Returns revision n+1 when the requirements changed, and the same intent
    otherwise. Raises `PatchError` naming the failing operation. The result is
    revalidated as an IntentIR, so a patch cannot produce a requirement that
    could not have been written directly.
    """
    doc = copy.deepcopy(dict(intent.requirements))
    for index, op in enumerate(ops):
        try:
            _apply_one(doc, op)
        except PatchError as exc:
            raise PatchError(str(exc), op_index=index) from None
    _prune(doc)

    try:
        unchanged = _normalised(doc) == _normalised(intent.requirements)
    except Exception as exc:  # noqa: BLE001 — surfaced as a patch error
        raise PatchError(f"the patched requirement is not valid: {exc}") from exc
    if unchanged:
        return PatchOutcome(intent=intent, changed=False, changed_paths=(), readable=())

    try:
        patched = intent.with_requirements(doc)
    except Exception as exc:  # noqa: BLE001
        raise PatchError(f"the patched requirement is not valid: {exc}") from exc

    before, after = flatten(intent.requirements), flatten(patched.requirements)
    paths = changed_paths(before, after)
    return PatchOutcome(
        intent=patched,
        changed=True,
        changed_paths=paths,
        readable=readable_changes(before, after, paths),
    )


# ── Reading a patch back ─────────────────────────────────────────────────────

def flatten(requirements: Mapping[str, Any]) -> Dict[str, Any]:
    """`section.key[.key…]` → leaf value. `function` stays `function`."""
    flat: Dict[str, Any] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping) and value:
            for key, child in value.items():
                walk(f"{prefix}.{key}", child)
        elif not (isinstance(value, Mapping) and (prefix in SECTIONS or tuple(prefix.split(".")) in CONTAINERS)):
            # An empty section or container carries no requirement; any other
            # empty nested object is a value the user set and is kept.
            flat[prefix] = value

    for key, value in requirements.items():
        walk(key, value)
    return flat


def changed_paths(before: Mapping[str, Any], after: Mapping[str, Any]) -> Tuple[str, ...]:
    """Dotted paths whose value differs, including added and removed ones."""
    keys = set(before) | set(after)
    return tuple(sorted(k for k in keys if before.get(k, _UNSET) != after.get(k, _UNSET)))


def readable_changes(
    before: Mapping[str, Any], after: Mapping[str, Any], paths: Sequence[str]
) -> Tuple[str, ...]:
    """`targets.cutoff_hz: 1000 → 2000`, one line per changed path."""
    return tuple(
        f"{path}: {_fmt(before.get(path, _UNSET))} → {_fmt(after.get(path, _UNSET))}"
        for path in paths
    )


def _fmt(value: Any) -> str:
    if value is _UNSET:
        return "(unset)"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)
