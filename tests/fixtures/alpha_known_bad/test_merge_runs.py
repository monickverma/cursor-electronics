"""
test_merge_runs.py — does the merge change anything it should not?

WHY THIS FILE EXISTS
--------------------
The A1 recall number is computed from a merged findings file. The merge
renumbers the findings so two agents that both started at `F-0001` do not
collide, and it copies everything else through. "Everything else" is the
measurement: the text, the artifact, the severity, the rung, the evidence.
If the merge quietly dropped a finding, dropped a field, or changed a
finding's severity, the recall number would move and nothing would say why.

So the merge gets its own tests. They are tests of the MERGE, not of the
product.

    python -m pytest tests/fixtures/alpha_known_bad/test_merge_runs.py -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_MERGER = _HERE.parents[2] / ".claude" / "shared-memory" / "alpha" / "merge_runs.py"

_spec = importlib.util.spec_from_file_location("merge_runs", _MERGER)
assert _spec and _spec.loader, f"cannot load the merger at {_MERGER}"
_merger = importlib.util.module_from_spec(_spec)
sys.modules["merge_runs"] = _merger
_spec.loader.exec_module(_merger)


def _finding(**kw) -> dict:
    base = {
        "id": "F-0001", "stage": "A1", "prompt": "p", "artifact": "artifacts/board_01",
        "parameter": 4, "severity": "critical", "observed": "o", "expected": "e",
        "evidence": "v", "rung": "exact", "status": "open", "fixed_by": None,
        "verified_by": None,
    }
    base.update(kw)
    return base


def _write_runs(tmp_path: Path, monkeypatch) -> Path:
    """Three fake per-board runs, with colliding ids, in a fake runs dir."""
    runs = tmp_path / "runs"
    runs.mkdir()
    for board, count in (("01", 2), ("03", 3), ("06", 1)):
        rows = [_finding(artifact=f"artifacts/board_{board}") for _ in range(count)]
        (runs / f"board_{board}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8",
        )
    monkeypatch.setattr(_merger, "RUNS", runs)
    return runs


class TestTheMergeKeepsEveryFinding:
    def test_the_count_in_equals_the_count_out(self, tmp_path, monkeypatch):
        runs = _write_runs(tmp_path, monkeypatch)
        before = sum(
            len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
            for p in runs.glob("board_*.jsonl")
        )
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        after = len([l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()])
        assert after == before, f"{before} findings went in and {after} came out"

    def test_no_finding_is_lost_to_a_numbering_collision(self, tmp_path, monkeypatch):
        """Two agents both start at F-0001. The merged file must still hold
        both of them, under different ids."""
        _write_runs(tmp_path, monkeypatch)
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids)), f"the merged file has duplicate ids: {ids}"
        assert len(rows) == 6


class TestTheMergeChangesOnlyTheId:
    def test_every_other_field_is_copied_through(self, tmp_path, monkeypatch):
        runs = _write_runs(tmp_path, monkeypatch)
        original = json.loads(
            (runs / "board_03.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        # Every fake finding starts at the same id, so the original id alone
        # does not say which row is this one. The artifact does.
        moved = next(
            r for r in rows
            if r.get("_original_id") == original["id"]
            and r["artifact"] == original["artifact"]
        )
        for field, value in original.items():
            if field == "id":
                continue
            assert moved[field] == value, f"the merge changed {field!r}"

    def test_the_old_id_is_kept_beside_the_new_one(self, tmp_path, monkeypatch):
        """The rename must be traceable. A finding whose id changed has to say
        what it was, or the merge is not auditable."""
        _write_runs(tmp_path, monkeypatch)
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert all(r.get("_original_id") for r in rows)
        assert all(r["id"] != r["_original_id"] for r in rows)

    def test_the_new_id_carries_the_board_number(self, tmp_path, monkeypatch):
        """The id still says which board the finding is about."""
        _write_runs(tmp_path, monkeypatch)
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in rows:
            board = r["artifact"].split("_")[-1]
            assert board in r["id"], f"the id {r['id']!r} does not name board {board}"


class TestATruncatedLineIsNotAFinding:
    def test_a_killed_agents_last_line_is_dropped_and_reported(self, tmp_path, monkeypatch, capsys):
        """An agent killed mid-write leaves a half line. It is not a finding.
        It is dropped — and the drop is said out loud, not swallowed."""
        runs = tmp_path / "runs"
        runs.mkdir()
        good = json.dumps(_finding())
        (runs / "board_01.jsonl").write_text(
            good + "\n" + '{"id": "F-0002", "observ', encoding="utf-8",
        )
        monkeypatch.setattr(_merger, "RUNS", runs)
        out = tmp_path / "all.jsonl"
        _merger.merge(out)
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(rows) == 1
        assert "did not parse" in capsys.readouterr().out
