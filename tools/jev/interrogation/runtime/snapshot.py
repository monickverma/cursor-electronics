"""Import the exact Circuit OS snapshot code (origin/phase2-stage0 @ e803a99) without network.

The snapshot's ai/client.py imports `anthropic`, which is not installed here and is not needed
for the pure functions used by this study, so `ai.client` is stubbed before import. Nothing in
this module calls a model. Set P2_SNAPSHOT to point at another checkout of the backend's parent.
"""
import os
import sys
import types

P2 = os.environ.get(
    "P2_SNAPSHOT",
    "/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2",
)
for k, v in {
    "ANTHROPIC_API_KEY": "",
    "DATABASE_URL": "postgresql+asyncpg://t:t@localhost/t",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
}.items():
    os.environ.setdefault(k, v)
sys.path.insert(0, os.path.join(P2, "backend"))

import ai  # noqa: E402  (the package itself has no side effects)

_stub = types.ModuleType("ai.client")
_stub.ai_model = lambda: "stub-no-model"
_stub.make_client = lambda: None
sys.modules["ai.client"] = _stub

from ai.intent_patcher import (  # noqa: E402
    _assign, _spaced, citation_spans, grounded, quantities,
)
from core.intent_ir import IntentIR, Producer, Provenance, Requirements  # noqa: E402
from core.intent_patch import PatchOp, apply_patch, PatchError  # noqa: E402

__all__ = ["P2", "_assign", "_spaced", "citation_spans", "grounded", "quantities", "IntentIR",
           "Producer", "Provenance", "Requirements", "PatchOp", "apply_patch", "PatchError",
           "catalogue", "guard_check"]


def catalogue():
    """The live catalogue: function -> list of (section.field, units, required, choices)."""
    from ai.form_producer import FormProducer
    from generators.registry import default_registry
    out = {}
    for spec in FormProducer(default_registry()).catalogue():
        out[spec.function] = [(f"{f.section}.{f.name}", f.units, f.required, f.choices) for f in spec.fields]
    return out


def guard_check(command, ops):
    """Re-run IntentPatcher.propose()'s deterministic citation guard on already-proposed ops.

    Mirrors backend/ai/intent_patcher.py:302-352 line for line, minus the model call.
    Returns (passes, failure_kind, detail).
    """
    candidates = []
    spaced = _spaced(command)
    for index, item in enumerate(ops):
        because = item.get("because")
        spans = citation_spans(because, command)
        if not spans:
            return False, "uncited_operation", f"op {index} cites {because!r}"
        try:
            op = PatchOp.model_validate({k: v for k, v in item.items() if k != "because"})
        except Exception as exc:  # noqa: BLE001
            return False, "schema", f"op {index}: {exc}"
        if op.op != "remove":
            spans = [s for s in spans if grounded(op.value, spaced[s[0]:s[1]])]
            if not spans:
                return False, "ungrounded_value", f"op {index} value {op.value!r} not in {because!r}"
        candidates.append(spans)
    if _assign(candidates) is None:
        return False, "shared_citation", "two ops rest on the same words"
    return True, None, ""
