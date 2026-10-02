"""
The Phase 2 exit gate (`PHASE2_GATES` in .claude/shared-memory/tools/regen_state.py,
brain/decisions.md [2026-10-02] "Phase 2 closes"). The phase status is derived from
these gates, so the derivation itself is tested: a skipped test is not evidence, a
failing one blocks, and a deferred gate never counts as met.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("regen_state", ROOT / ".claude" / "shared-memory" / "tools" / "regen_state.py")
regen_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen_state)


def _all_passing_output() -> str:
    """-v output in which every evidence file and every required test passed."""
    lines = []
    for gate in regen_state.PHASE2_GATES:
        for test_file, required in gate.get("evidence", []):
            lines.append(f"{test_file}::{required or 'test_x'}::case PASSED")
    return "\n".join(lines)


def test_every_gate_is_met_or_deferred_when_all_evidence_passes():
    rows, status = regen_state.check_phase2_gates(_all_passing_output())
    assert status == "complete"
    assert {r["status"] for r in rows} == {"met", "deferred"}


def test_every_deferred_gate_names_its_trigger():
    for gate in regen_state.PHASE2_GATES:
        if "deferred" in gate:
            assert "trigger" in gate["deferred"], gate["gate"]


def test_a_skipped_required_test_is_not_evidence():
    # The PlatformIO compile gate: its file is present and nothing failed, but the
    # compiles were skipped — the gate is not met, so the phase is not complete.
    raw = _all_passing_output().replace("TestEveryVariantCompiles::case PASSED", "TestEveryVariantCompiles::case SKIPPED")
    rows, status = regen_state.check_phase2_gates(raw)
    gate = next(r for r in rows if "PlatformIO" in r["gate"])
    assert gate["status"] == "not_met" and status == "in_progress"


def test_a_failing_evidence_file_blocks_the_phase():
    raw = _all_passing_output() + "\ntests/test_substitution.py::test_y FAILED"
    rows, status = regen_state.check_phase2_gates(raw)
    assert status == "in_progress"
    assert any(r["status"] == "not_met" and "substitution" in r["gate"] for r in rows)


def test_a_missing_evidence_file_blocks_the_phase():
    raw = "\n".join(line for line in _all_passing_output().splitlines() if "test_proof.py" not in line)
    _, status = regen_state.check_phase2_gates(raw)
    assert status == "in_progress"


@pytest.mark.parametrize("stage", range(7))
def test_every_stage_of_the_plan_has_gates(stage):
    assert any(g["stage"] == stage for g in regen_state.PHASE2_GATES)
