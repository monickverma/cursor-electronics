"""
merge_runs.py — gather the per-board overlooker runs into one findings file.

WHY
---
The scorer reads one findings file and matches each finding back to a case by
the artifact it names. Each board's run is its own file, because each run is
one request, one board, one turn — and a run that dies half way must not take
the other runs' findings with it. But the A1 number is one number over all the
cases, so the runs have to be gathered before they can be scored.

THE ID PROBLEM
--------------
Two agents can both start their findings at `F-0001`. Left alone, the merged
file has two findings with the same id, and every id is a handle someone
will use to point at a finding. So the merge renumbers: a finding from
`board_03` called `F-0001` becomes `F-0300-01`. The board's own number is
kept, so the id still says which board it is about, and the id stays
readable.

Renumbering changes a LABEL, never a finding. The text, the artifact, the
severity, the rung and the evidence are copied through untouched — those are
the measurement. A test checks that: the number of findings in equals the
number out, and every row's content other than the id is byte-identical.

    python .claude/shared-memory/alpha/merge_runs.py
    python .claude/shared-memory/alpha/merge_runs.py --out runs/all.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNS = REPO / ".claude" / "shared-memory" / "alpha" / "runs"
DEFAULT_OUT = RUNS / "all.jsonl"


def _load(path: Path) -> list[dict]:
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated final line is what a killed agent leaves behind.
            # It is not a finding, so it is dropped — but the count of what
            # was dropped is reported, not swallowed.
            print(f"  ! {path.name}: one line did not parse and was dropped")
    return out


def _board_of(path: Path) -> str:
    """board_03 -> 03. The number the artifact names, not the case."""
    stem = path.stem
    tail = stem.split("_")[-1]
    return tail if tail.isdigit() else stem


def merge(out: Path) -> int:
    files = sorted(RUNS.glob("board_*.jsonl"))
    if not files:
        print(f"no per-board findings in {RUNS}")
        return 1

    merged: list[dict] = []
    for path in files:
        board = _board_of(path)
        rows = _load(path)
        for i, row in enumerate(rows, start=1):
            original = str(row.get("id", ""))
            row = dict(row)
            row["id"] = f"F-{board}-{i:02d}"
            row["_original_id"] = original
            merged.append(row)
        print(f"  {path.name:<20} {len(rows):>3} findings")

    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
        encoding="utf-8",
    )
    print(f"\nmerged {len(merged)} findings into {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    return merge(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
