"""
Stage 1 Task 1.6 — the labelled corpus, and the false-acceptance rate.

> **Gate:** On a labelled 200-case corpus: false-acceptance **rate**, reported
> with the corpus named. empirical, G5.

v2 §1.2 calls the original phrasing — "false acceptance at zero" — unmeasurable
as written: *"zero on **what sample**?"* So the corpus is named, generated
deterministically, and its construction is visible here rather than being a
file of opaque fixtures.

**The two errors are not symmetric, and the plan separates them for a reason.**

- A **false acceptance** is `envelope()` taking an intent it should not. The
  system then emits a design carrying a claim it cannot support, and nothing
  downstream will catch it, because everything downstream trusts the envelope.
  This is the one that must be zero.
- A **false abstention** is refusing something it could have built. That costs
  coverage and shows up in the refusal log as a generator to widen. It is a
  product problem, not a correctness one.

Reporting them as a single "accuracy" number would let one hide the other,
which is why §1.1 keeps them as separate metrics.

**What this corpus can and cannot establish.** The labels are derived from the
generator's *declared* envelope — the same declaration `envelope()` reads — so
this measures whether the implementation honours its own declaration. It does
not measure whether the declaration is *right*; a generator that declares it
can do something it cannot would pass this and fail the CI envelope grid,
which is what Task 0.4 exists for. Two different questions, deliberately
checked by two different harnesses.
"""

import math

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from generators.rc_lowpass import (
    MAX_CUTOFF_HZ,
    MIN_CUTOFF_HZ,
    RCLowPassGenerator,
    select_components,
)
from generators.registry import default_registry

CORPUS_NAME = "rc_lowpass_envelope_v1"


def _intent(function="low_pass_filter", cutoff=None, supply_v=5.0, tolerance_pct=5.0):
    targets = {"tolerance_pct": tolerance_pct}
    if cutoff is not None:
        targets["cutoff_hz"] = cutoff
    return IntentIR(
        requirements={
            "function": function,
            "targets": targets,
            "constraints": {"supply_v": supply_v, "source_impedance_ohm": 50.0},
        },
        provenance=Provenance(producer=Producer.FORM),
    )


def _should_be_buildable(cutoff, supply_v, tolerance_pct) -> bool:
    """
    The ground truth, derived from the declared envelope rather than from
    `envelope()` itself — otherwise the corpus would be checking the
    implementation against a copy of itself.
    """
    if not (MIN_CUTOFF_HZ <= cutoff <= MAX_CUTOFF_HZ):
        return False
    if supply_v <= 0 or not math.isfinite(supply_v):
        return False
    selection = select_components(cutoff, supply_v)
    if selection is None:
        return False
    achieved_err_pct = abs(selection.achieved_hz - cutoff) / cutoff * 100.0
    return achieved_err_pct <= tolerance_pct


def build_corpus():
    """
    200 labelled cases, deterministic.

    Spread across the boundaries that matter rather than uniformly: most of
    the interesting behaviour is within a factor of two of an envelope edge,
    and a corpus of comfortable mid-range cases would report a flattering
    number while testing nothing.
    """
    cases = []

    # 120 in-range cutoffs, log-spaced across three decades.
    for i in range(120):
        cutoff = MIN_CUTOFF_HZ * (10 ** (4.0 * i / 119))
        cases.append(("cutoff_sweep", _intent(cutoff=cutoff), cutoff, 5.0, 5.0))

    # 40 straddling the declared edges, including the edges themselves.
    for cutoff in (
        MIN_CUTOFF_HZ * 0.5, MIN_CUTOFF_HZ * 0.9, MIN_CUTOFF_HZ, MIN_CUTOFF_HZ * 1.1,
        MAX_CUTOFF_HZ * 0.9, MAX_CUTOFF_HZ, MAX_CUTOFF_HZ * 1.1, MAX_CUTOFF_HZ * 2,
        0.001, 1e9,
    ):
        for supply_v in (3.3, 5.0, 12.0, 15.0):
            cases.append(("edge", _intent(cutoff=cutoff, supply_v=supply_v),
                          cutoff, supply_v, 5.0))

    # 20 with supplies that no capacitor in the catalogue survives, or that
    # are not usable rails at all.
    for supply_v in (0.0, -5.0, 6.5, 17.0, 60.0, 100.0, 250.0, float("inf"),
                     float("nan"), 1e6):
        for cutoff in (100.0, 10_000.0):
            cases.append(("supply", _intent(cutoff=cutoff, supply_v=supply_v),
                          cutoff, supply_v, 5.0))

    # 10 asking for a tolerance the E96 catalogue cannot deliver.
    for tolerance_pct in (0.001, 0.01, 0.05, 0.1, 0.2):
        for cutoff in (1000.0, 7777.0):
            cases.append(("tolerance", _intent(cutoff=cutoff, tolerance_pct=tolerance_pct),
                          cutoff, 5.0, tolerance_pct))

    # 10 the generator does not build at all.
    for function in ("band_pass_filter", "high_pass_filter", "buck_converter",
                     "voltage_divider", "led_driver"):
        for cutoff in (1000.0, 50_000.0):
            cases.append((
                "wrong_function",
                _intent(function=function, cutoff=cutoff),
                cutoff, 5.0, 5.0,
            ))

    return cases


CORPUS = build_corpus()


def _label(kind, cutoff, supply_v, tolerance_pct) -> bool:
    if kind == "wrong_function":
        return False
    return _should_be_buildable(cutoff, supply_v, tolerance_pct)


class TestCorpusItself:
    def test_corpus_is_the_declared_size(self):
        assert len(CORPUS) == 200, f"{CORPUS_NAME} is {len(CORPUS)} cases, not 200"

    def test_corpus_contains_both_labels(self):
        # A corpus that is all one label cannot measure the error it is named
        # for, however large it is.
        labels = [_label(k, c, s, t) for k, _, c, s, t in CORPUS]
        assert any(labels) and not all(labels)

    def test_corpus_is_deterministic(self):
        again = build_corpus()
        assert [k for k, *_ in again] == [k for k, *_ in CORPUS]


class TestAbstentionRates:
    """The gate. Reported as rates, on a named corpus, and kept separate."""

    def _measure(self):
        generator = RCLowPassGenerator()
        false_accepts, false_abstains = [], []
        for kind, intent, cutoff, supply_v, tolerance_pct in CORPUS:
            expected = _label(kind, cutoff, supply_v, tolerance_pct)
            accepted = generator.envelope(intent).accepted
            if accepted and not expected:
                false_accepts.append((kind, cutoff, supply_v, tolerance_pct))
            elif expected and not accepted:
                false_abstains.append((kind, cutoff, supply_v, tolerance_pct))
        return false_accepts, false_abstains

    def test_false_acceptance_rate_is_zero(self):
        # The asymmetric one. A false acceptance emits a design carrying a
        # claim nothing downstream will question, because everything
        # downstream trusts the envelope.
        false_accepts, _ = self._measure()
        rate = len(false_accepts) / len(CORPUS)
        assert rate == 0.0, (
            f"false-acceptance rate {rate:.2%} on {CORPUS_NAME} "
            f"({len(false_accepts)}/{len(CORPUS)}); first few: {false_accepts[:5]}"
        )

    def test_false_abstention_rate_is_reported_and_bounded(self):
        # Costs coverage, not correctness. Bounded rather than zero because
        # abstaining when unsure is the designed behaviour.
        _, false_abstains = self._measure()
        rate = len(false_abstains) / len(CORPUS)
        assert rate <= 0.05, (
            f"false-abstention rate {rate:.2%} on {CORPUS_NAME} "
            f"({len(false_abstains)}/{len(CORPUS)}); first few: {false_abstains[:5]}"
        )

    def test_envelope_never_raises_across_the_whole_corpus(self):
        # envelope() is contracted never to raise. 200 cases including
        # negative, zero, infinite and NaN supplies is where that gets tested.
        generator = RCLowPassGenerator()
        for kind, intent, *_ in CORPUS:
            generator.envelope(intent)  # must not raise

    def test_every_refusal_names_a_reason(self):
        # §4.5: the refusal log is the generator backlog. An unexplained
        # refusal is an entry nobody can act on.
        generator = RCLowPassGenerator()
        for kind, intent, *_ in CORPUS:
            decision = generator.envelope(intent)
            if not decision.accepted:
                assert decision.reason and decision.reason.strip()

    def test_registry_dispatch_agrees_with_the_generator(self):
        # The registry must not accept what the generator refuses, or the
        # abstention measured here would not be the one users experience.
        registry = default_registry()
        generator = RCLowPassGenerator()
        for kind, intent, *_ in CORPUS:
            assert registry.dispatch(intent).accepted == generator.envelope(intent).accepted
