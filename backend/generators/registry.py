"""
The generator registry and dispatch. PHASE_2_PLAN_v2.md §5 Stage 1.

Dispatch is deterministic and keyed on the declared envelope, not on a model's
judgement. The formal-verification report is explicit about why:

> The LLM also adds little to solver choice at Tier 0 to 2. A deterministic
> dispatcher keyed on circuit class is more reliable and easier to defend, and
> LLM selection is worth its cost only at Tier 3 and above.

The same argument applies one level up, to choosing a generator: every
generator already states what it will take, so asking a model to guess is
strictly worse than asking them.

**Every refusal is collected, not just the first.** §4.5 makes the
out-of-envelope log the generator backlog, ranked by frequency — and *"nothing
accepted this"* is a far weaker backlog entry than the set of reasons each
generator gave. A request refused because the cutoff was out of range tells
you to widen an envelope; one refused because no generator builds band-pass
filters tells you to author a generator. Collapsing those into a single "no"
loses the distinction the backlog exists to make.

**Overlapping envelopes are surfaced, never silently resolved.** Two generators
accepting the same intent is a catalogue design question, and a dispatcher
that quietly picks one hides it until the two disagree about a design.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from generators.protocol import (
    EnvelopeDecision,
    Generator,
    IntentLike,
    conformance_gaps,
)


class Refusal:
    """One generator's reason for declining, kept with its author."""

    __slots__ = ("generator", "reason")

    def __init__(self, generator: str, reason: str) -> None:
        self.generator = generator
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Refusal({self.generator!r}, {self.reason!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Refusal)
            and (self.generator, self.reason) == (other.generator, other.reason)
        )

    def __hash__(self) -> int:
        # Defining __eq__ sets __hash__ to None, which made these unusable in
        # a set or as a dict key. Deduplicating refusals by reason is the
        # obvious thing to do when ranking the backlog, so the type has to
        # survive being put in a set.
        return hash((self.generator, self.reason))


class DispatchResult:
    """
    What the registry decided, and everything it learned deciding it.

    A refused result carries every reason, because that set is the backlog
    entry. An accepted result still carries the refusals from the generators
    that declined, so a request answered by a narrow generator does not hide
    the fact that a broader one turned it down.
    """

    __slots__ = ("generator", "decision", "refusals", "also_accepted")

    def __init__(
        self,
        generator: Optional[Generator],
        decision: Optional[EnvelopeDecision],
        refusals: Sequence[Refusal],
        also_accepted: Sequence[str] = (),
    ) -> None:
        self.generator = generator
        self.decision = decision
        self.refusals = tuple(refusals)
        self.also_accepted = tuple(also_accepted)

    @property
    def accepted(self) -> bool:
        return self.generator is not None

    @property
    def is_ambiguous(self) -> bool:
        """
        More than one generator would have taken this intent.

        Not an error — the first registered still wins, deterministically —
        but a catalogue smell worth logging, because the day the two disagree
        about a design is not the day you want to discover the overlap.
        """
        return bool(self.also_accepted)

    def refusal_summary(self) -> str:
        """One line per reason, for the request log and for the user."""
        if self.accepted:
            return ""
        if not self.refusals:
            return "no generators are registered"
        return "; ".join(f"{r.generator}: {r.reason}" for r in self.refusals)


class GeneratorRegistry:
    """
    The catalogue. Registration order is dispatch order.

    Order is explicit rather than sorted by name or by import: it is decided in
    one place, which makes it reviewable, and a name-sorted order would be just
    as arbitrary while reading as though it meant something.
    """

    def __init__(self) -> None:
        self._generators: List[Generator] = []

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, generator: Generator) -> None:
        """
        Add a generator, refusing anything that does not satisfy the contract.

        The gaps are named rather than reported as a bare "not a Generator" —
        an author who mistyped a method should be told which one.
        """
        gaps = conformance_gaps(generator)
        if gaps:
            raise TypeError(
                f"{type(generator).__name__} does not satisfy the Generator "
                f"contract; missing or non-callable: {', '.join(gaps)}"
            )
        name = generator.name
        if any(g.name == name for g in self._generators):
            raise ValueError(
                f"a generator named {name!r} is already registered — names are "
                f"how a design records which generator built it, so they have "
                f"to be unique"
            )
        self._generators.append(generator)

    def __len__(self) -> int:
        return len(self._generators)

    @property
    def generators(self) -> Tuple[Generator, ...]:
        return tuple(self._generators)

    def by_name(self, name: str) -> Optional[Generator]:
        return next((g for g in self._generators if g.name == name), None)

    def functions(self) -> Tuple[str, ...]:
        """
        The distinct `requirements.function` values this system covers.

        This is the catalogue the form producer renders, and the honest answer
        to "what can it do" — derived from the generators rather than written
        down beside them, so it cannot drift from what is actually installed.
        """
        seen: List[str] = []
        for generator in self._generators:
            if generator.function not in seen:
                seen.append(generator.function)
        return tuple(seen)

    def for_function(self, function: str) -> Tuple[Generator, ...]:
        return tuple(g for g in self._generators if g.function == function)

    # ── Dispatch ──────────────────────────────────────────────────────────

    def dispatch(self, intent: IntentLike) -> DispatchResult:
        """
        The first registered generator whose `envelope()` accepts, with every
        refusal collected either way.

        `envelope()` is contracted never to raise; a generator that does anyway
        is recorded as a refusal naming the exception rather than being allowed
        to take the whole dispatch down. One misbehaving generator should not
        make the catalogue unusable.
        """
        refusals: List[Refusal] = []
        accepted: List[Tuple[Generator, EnvelopeDecision]] = []

        for generator in self._generators:
            try:
                decision = generator.envelope(intent)
            except Exception as exc:  # noqa: BLE001 — a crash is a refusal here
                refusals.append(Refusal(
                    generator.name,
                    f"envelope() raised {type(exc).__name__}: {exc} "
                    f"(envelope() is contracted never to raise)",
                ))
                continue
            if decision.accepted:
                accepted.append((generator, decision))
            else:
                refusals.append(Refusal(generator.name, decision.reason or ""))

        if not accepted:
            return DispatchResult(None, None, refusals)

        winner, decision = accepted[0]
        return DispatchResult(
            generator=winner,
            decision=decision,
            refusals=refusals,
            also_accepted=[g.name for g, _ in accepted[1:]],
        )


def default_registry() -> GeneratorRegistry:
    """
    The installed catalogue.

    Imported here rather than at module scope so the registry module itself
    stays importable without pulling in every generator — which matters for
    the conformance tests, and will matter more as the library grows.
    """
    from generators.dht22_node import DHT22NodeGenerator
    from generators.led_indicator import LedIndicatorGenerator
    from generators.rc_lowpass import RCLowPassGenerator
    from generators.rs485_node import RS485NodeGenerator
    from generators.voltage_divider import VoltageDividerGenerator

    registry = GeneratorRegistry()
    registry.register(RCLowPassGenerator())
    # Stage 3: the four Phase 1 templates, back in coverage on the contract.
    registry.register(VoltageDividerGenerator())
    registry.register(LedIndicatorGenerator())
    registry.register(DHT22NodeGenerator())
    registry.register(RS485NodeGenerator())
    return registry
