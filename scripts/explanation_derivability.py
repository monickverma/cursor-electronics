"""
Task 0.5 — is the explanation derivable, or does it need a model call?

PHASE_2_PLAN_v2.md §4.4 calls this "the single highest-leverage experiment in
Phase 2": if the explanation is a template fill from `predict()` plus the
requirements, the dominant per-design cost disappears and the product works
offline.

This script answers it with evidence rather than opinion. For each case it
produces a derived explanation (zero API calls) and, when a key is available,
the live `ExplanationEngine` output, and scores both on the consequential
markers `tests/test_explainer.py` already enforces — the repo's existing
definition of "good enough", reused rather than reinvented.

    python scripts/explanation_derivability.py            # derived only
    python scripts/explanation_derivability.py --live     # also call the model
    python scripts/explanation_derivability.py --live --dump out/

What it cannot settle: whether an explanation is *good*. Marker counting
measures form. `tests/test_explainer.py` says so about itself, and criterion 12
— a human reading one cold — is still open. A high score here means "clears the
bar the test suite enforces", never "as good as the model".
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# This script prints em-dashes and Ω. On Windows the console encoding is
# cp1252, which mangles them. Same guard as regen_state.py and progress_gen.py,
# both of which learned it the hard way.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai.derived_explainer import DerivedExplainer, explanation_markers  # noqa: E402
from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005  # noqa: E402
from core.ir_schema import CircuitIR  # noqa: E402
from core.ir_validator import validate_ir  # noqa: E402
from generators.rc_lowpass import RCLowPassGenerator  # noqa: E402

MARKER_THRESHOLD = 3  # tests/test_explainer.py requires >= 3 distinct markers


class _Intent:
    def __init__(self, **requirements):
        self._requirements = requirements

    @property
    def requirements(self):
        return self._requirements


def _rc_intent(cutoff: float = 1000.0) -> _Intent:
    return _Intent(
        function="low_pass_filter",
        targets={"cutoff_hz": cutoff, "tolerance_pct": 5.0},
        constraints={"supply_v": 5.0, "source_impedance_ohm": 50.0},
        preferences={"package": "0402"},
    )


class Case:
    """One design to explain, with whatever derivation inputs exist for it."""

    def __init__(self, name: str, ir: CircuitIR, prediction=None, requirements=None,
                 from_generator: bool = False):
        self.name = name
        self.ir = ir
        self.prediction = prediction
        self.requirements = requirements
        self.from_generator = from_generator


def build_cases() -> List[Case]:
    """
    The RC case is the real test: a design produced by a Stage 0 generator, so
    both `predict()` and generator-authored justifications exist.

    The five shipped example IRs are included as a control with a caveat that
    has to survive into the writeup — their justifications were written by the
    LLM back in Phase 1, so a derived explanation over them is assembling model
    output, not deriving from requirements. They show what is recoverable from
    an IR alone, which is a weaker and different claim.
    """
    generator = RCLowPassGenerator()
    intent = _rc_intent()
    cases = [
        Case(
            "rc_lowpass (generated)",
            generator.generate(intent),
            prediction=generator.predict(intent),
            requirements=intent.requirements,
            from_generator=True,
        )
    ]
    for label, ir in [
        ("IR_001 dht22", IR_001), ("IR_002 led", IR_002), ("IR_003 rc_filter", IR_003),
        ("IR_004 divider", IR_004), ("IR_005 modbus", IR_005),
    ]:
        cases.append(Case(label, ir))
    return cases


def score(text: str, ir: CircuitIR) -> Dict[str, object]:
    markers = explanation_markers(text)
    covered = [c.id for c in ir.components if c.id in text]
    return {
        "chars": len(text),
        "markers": markers,
        "marker_count": len(markers),
        "passes_marker_bar": len(markers) >= MARKER_THRESHOLD,
        "component_coverage": f"{len(covered)}/{len(ir.components)}",
        "covers_all_components": len(covered) == len(ir.components),
    }


def _api_key_available() -> bool:
    """
    Read it through `settings`, not the raw environment: `core/config.py`
    resolves `.env` relative to its own location, so the key is present to the
    app even when it is absent from this process's environ.
    """
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return True
    try:
        from core.config import settings

        return bool((settings.anthropic_api_key or "").strip())
    except Exception:  # noqa: BLE001
        return False


class _RoomyClient:
    """
    The configured model reasons before it writes, and `ExplanationEngine`
    asks for `max_tokens=2048` — enough of which goes on thinking that the
    call returns truncated prose, or a response whose only block is thinking
    and no text at all. Both were observed on 2026-09-20.

    Raising the ceiling is a product decision with a cost attached, so this
    script does not make it. It widens the budget only for its own calls, so
    the comparison measures the model's explanation rather than the truncation
    — scoring a cut-off response against the derived one would flatter the
    derived one for the wrong reason.
    """

    def __init__(self, inner, max_tokens: int):
        self._inner = inner
        self._max_tokens = max_tokens

    def __getattr__(self, item):
        return getattr(self._inner, item)

    @property
    def messages(self):
        inner_messages = self._inner.messages
        max_tokens = self._max_tokens

        class _Messages:
            @staticmethod
            def create(**kwargs):
                kwargs["max_tokens"] = max(kwargs.get("max_tokens", 0), max_tokens)
                return inner_messages.create(**kwargs)

        return _Messages()


def live_explanation(case: Case, delay: float = 3.0, max_tokens: int = 16000) -> Optional[str]:
    """The model call. Returns None and says why if it cannot run."""
    from ai.explainer import ExplanationEngine

    try:
        time.sleep(delay)  # OpenRouter free tier is 10/hour by IP
        engine = ExplanationEngine()
        engine.client = _RoomyClient(engine.client, max_tokens)
        return engine.explain(case.ir, validate_ir(case.ir))
    except Exception as exc:  # noqa: BLE001 — a failed call is a result, not a crash
        print(f"    live call failed: {type(exc).__name__}: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also call the model")
    parser.add_argument("--dump", type=Path, help="write every explanation to this directory")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between model calls")
    args = parser.parse_args()

    if args.live and not _api_key_available():
        print("No API key — cannot run --live. Set ANTHROPIC_API_KEY in .env.")
        return 2
    if args.dump:
        args.dump.mkdir(parents=True, exist_ok=True)

    explainer = DerivedExplainer()
    rows = []

    for case in build_cases():
        derived = explainer.explain(
            case.ir,
            validate_ir(case.ir),
            prediction=case.prediction,
            requirements=case.requirements,
        )
        derived_score = score(derived, case.ir)
        live_score = None
        live = None

        if args.live:
            live = live_explanation(case, args.delay)
            if live:
                live_score = score(live, case.ir)

        if args.dump:
            (args.dump / f"{case.name.replace(' ', '_')}.derived.md").write_text(
                derived, encoding="utf-8"
            )
            if live:
                (args.dump / f"{case.name.replace(' ', '_')}.live.md").write_text(
                    live, encoding="utf-8"
                )

        rows.append((case, derived_score, live_score))

    _report(rows, args.live)
    return 0


def _report(rows, ran_live: bool) -> None:
    print()
    print("=" * 78)
    print("  EXPLANATION DERIVABILITY — Task 0.5")
    print("=" * 78)
    print(f"  Marker bar: >= {MARKER_THRESHOLD} distinct consequential markers")
    print("  (the same bar tests/test_explainer.py enforces on the model)")
    print()
    header = f"  {'case':24} {'derived':>26}"
    if ran_live:
        header += f" {'live model':>26}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for case, derived, live in rows:
        tag = "*" if case.from_generator else " "
        cell = (
            f"{derived['marker_count']} mk / {derived['component_coverage']} cmp / "
            f"{derived['chars']:>5}c {'PASS' if derived['passes_marker_bar'] else 'FAIL'}"
        )
        line = f"  {tag}{case.name:23} {cell:>26}"
        if ran_live:
            if live:
                lcell = (
                    f"{live['marker_count']} mk / {live['component_coverage']} cmp / "
                    f"{live['chars']:>5}c {'PASS' if live['passes_marker_bar'] else 'FAIL'}"
                )
            else:
                lcell = "unavailable"
            line += f" {lcell:>26}"
        print(line)

    derived_pass = sum(1 for _, d, _ in rows if d["passes_marker_bar"])
    derived_cov = sum(1 for _, d, _ in rows if d["covers_all_components"])
    print()
    print(f"  derived: {derived_pass}/{len(rows)} clear the marker bar, "
          f"{derived_cov}/{len(rows)} name every component, 0 API calls")
    if ran_live:
        live_pass = sum(1 for _, _, l in rows if l and l["passes_marker_bar"])
        live_n = sum(1 for _, _, l in rows if l)
        print(f"  live   : {live_pass}/{live_n} clear the marker bar, {live_n} API calls")
    print()
    print("  * = produced by a Stage 0 generator, so predict() and generator-authored")
    print("      justifications exist. The rest are Phase 1 example IRs whose")
    print("      justifications were originally model-written — a weaker claim.")
    print()
    print("  Marker counting measures form, not quality. Criterion 12 — a human")
    print("  reading one cold — remains the only test of whether these land.")
    print("=" * 78)


if __name__ == "__main__":
    raise SystemExit(main())
