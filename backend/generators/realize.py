"""
Turning an accepted intent into a design, and comparing two designs.

PHASE_2_PLAN_v2.md §4.1, Stage 2. Three things live here because each one has
to happen in exactly one place:

1. **Stamping.** `realize()` is the only route from an IntentIR to a stored
   CircuitIR. It asks `envelope()`, calls `generate()`, and stamps the three
   fields a generator cannot know: `circuit_id`, derived from the intent's
   lineage; `version`, the intent's revision; and `generator`, `name@version`.
   Without the first, byte-identical determinism is unreachable, and the
   protocol forbids generators from working around it locally — so it is done
   here, once, for all of them. The derivation is recorded in
   `brain/decisions.md` [2026-09-21] X2 + X4, item 3.

2. **Locality.** A patch to one requirement may only change the components the
   generator declares as depending on it. `check_locality()` compares two
   realised designs against `dependency_closure()`.

3. **The `predict()` delta.** A patch is justified by what it does to the
   predicted behaviour, not by prose: *cutoff 1000.7 Hz → 2001.4 Hz* is the
   comparative justification the plan asks for.

Nothing here talks to a model. `tests/test_llm_cannot_write_circuit_ir.py`
scans this module like every other.
"""

from __future__ import annotations

import json
import uuid
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from core.intent_ir import IntentIR
from core.ir_schema import CircuitIR
from generators.protocol import Generator, Interval

#: Fixed forever. Changing it would change every design's `circuit_id` and
#: orphan every stored record keyed on one.
CIRCUIT_ID_NAMESPACE = uuid.UUID("5b3f9e2a-6c1d-4f0e-9a7b-2d8c4e6f1a30")


class RefusedIntent(Exception):
    """`realize()` was handed an intent the generator's envelope refuses."""

    def __init__(self, generator: str, reason: str) -> None:
        self.generator = generator
        self.reason = reason
        super().__init__(f"{generator} refused: {reason}")


def design_circuit_id(intent: IntentIR) -> str:
    """
    The `circuit_id` of every design realised from this intent's lineage.

    Derived from `intent_id` alone. Every revision of one intent shares it,
    because it is the key of the design record that the patch chain lives on;
    and two users asking for the same thing get different ids, because their
    intents do. The generator version is deliberately not an input: a design
    must not change identity when the generator that built it is upgraded.
    """
    return str(uuid.uuid5(CIRCUIT_ID_NAMESPACE, intent.intent_id))


def generator_tag(generator: Generator) -> str:
    return f"{generator.name}@{generator.version}"


def realize(generator: Generator, intent: IntentIR) -> CircuitIR:
    """
    The design for `intent`, byte-identical for the same intent and generator
    version. Raises `RefusedIntent` if the envelope does not accept it.

    Takes no annotations. v2 §4.1: annotations are merged after generation and
    are never an input to it — so this signature is the enforcement, and
    `tests/test_annotations.py` asserts it stays that way.
    """
    decision = generator.envelope(intent)
    if not decision.accepted:
        raise RefusedIntent(generator.name, decision.reason or "")
    circuit = generator.generate(intent).model_copy(update={
        "circuit_id": design_circuit_id(intent),
        "version": intent.revision,
        "generator": generator_tag(generator),
    })
    # Stage 3: every design carries its claims (v2 §6). Deterministic, so the
    # byte-identity gate covers them too.
    from validation.claims import assess

    coverage = assess(generator, intent, circuit)
    return circuit.model_copy(update={"validation_coverage": coverage.model_dump(mode="json")})


def canonical_json(circuit: CircuitIR) -> str:
    """The byte string the determinism gate compares."""
    return json.dumps(circuit.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


# ── Locality ─────────────────────────────────────────────────────────────────

def component_diff(before: CircuitIR, after: CircuitIR) -> FrozenSet[str]:
    """
    Component ids that were added, removed, or changed in any field.

    Scoped to components because that is what `dependency_closure()` declares.
    Circuit-level fields — the `intent` sentence, nodes' nominal voltages,
    `simulation_spec` — also follow the requirement, and the protocol does not
    ask a generator to declare them; they are outside what this checks.
    """
    old = {c.id: c.model_dump(mode="json") for c in before.components}
    new = {c.id: c.model_dump(mode="json") for c in after.components}
    changed = {cid for cid in old.keys() & new.keys() if old[cid] != new[cid]}
    return frozenset(changed | (old.keys() ^ new.keys()))


class LocalityReport(BaseModel):
    """Whether a patch touched only what its requirement paths declare."""

    model_config = ConfigDict(frozen=True)

    changed_paths: Tuple[str, ...]
    closure: Tuple[str, ...]
    diff: Tuple[str, ...]
    violations: Tuple[str, ...]
    #: False when the patch moved the design to a different generator, where
    #: one generator's closure says nothing about another's output.
    applicable: bool = True

    @property
    def ok(self) -> bool:
        return not self.violations


def check_locality(
    generator: Generator,
    changed_paths: Iterable[str],
    before: CircuitIR,
    after: CircuitIR,
) -> LocalityReport:
    """
    v2 §4.1 locality: the CircuitIR diff ⊆ the union of the closures of the
    changed requirement paths.

    A change of `function` has no closure worth the name — it asks for a
    different circuit — so it is checked against the whole of both designs,
    which passes by construction and is reported as such rather than dressed
    up as a narrow result.
    """
    paths = tuple(sorted(set(changed_paths)))
    diff = component_diff(before, after)

    if before.generator and after.generator and before.generator.split("@")[0] != after.generator.split("@")[0]:
        return LocalityReport(
            changed_paths=paths, closure=(), diff=tuple(sorted(diff)),
            violations=(), applicable=False,
        )

    closure: set = set()
    for path in paths:
        if path == "function":
            closure |= {c.id for c in before.components} | {c.id for c in after.components}
        else:
            closure |= set(generator.dependency_closure(path))

    return LocalityReport(
        changed_paths=paths,
        closure=tuple(sorted(closure)),
        diff=tuple(sorted(diff)),
        violations=tuple(sorted(diff - closure)),
    )


# ── The predict() delta ──────────────────────────────────────────────────────

class QuantityDelta(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    before: Optional[Interval]
    after: Optional[Interval]

    def describe(self) -> str:
        def fmt(i: Optional[Interval]) -> str:
            if i is None:
                return "—"
            if i.is_point:
                return f"{i.nominal:.4g} {i.units}"
            return f"{i.nominal:.4g} {i.units} [{i.lo:.4g}, {i.hi:.4g}]"
        return f"{self.name}: {fmt(self.before)} → {fmt(self.after)}"


def predict_delta(
    before_generator: Optional[Generator],
    before: Optional[IntentIR],
    after_generator: Generator,
    after: IntentIR,
) -> List[QuantityDelta]:
    """
    Every predicted quantity whose band moved, before → after.

    `before` may be unpredictable — built by a generator that is no longer
    installed, or now refused by an upgraded one. That side is then reported
    as absent rather than raising, because losing the justification must not
    lose the patch.
    """
    def quantities(generator: Optional[Generator], intent: Optional[IntentIR]) -> Dict[str, Interval]:
        if generator is None or intent is None:
            return {}
        try:
            return dict(generator.predict(intent).quantities)
        except Exception:  # noqa: BLE001 — an unpredictable side is reported empty
            return {}

    old = quantities(before_generator, before)
    new = quantities(after_generator, after)
    deltas = []
    for name in sorted(old.keys() | new.keys()):
        if old.get(name) != new.get(name):
            deltas.append(QuantityDelta(name=name, before=old.get(name), after=new.get(name)))
    return deltas
