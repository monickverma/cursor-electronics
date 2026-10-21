"""
probe_cases.py — report, for each seeded case, what changed and which checks moved.

A diagnostic, not a gate. It exists so the manifest's `expected_check_ids`
is written from what the verifier actually does, rather than from a guess.

    python .claude/shared-memory/alpha/probe_cases.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
FIXTURES = REPO / "tests" / "fixtures" / "alpha_known_bad"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "pcb_engine"))

from pcb_engine.board_ir import Board  # noqa: E402
from pcb_engine.verify import verify_board  # noqa: E402


def _statuses(report) -> dict[str, str]:
    return {f.check: f.status for f in report.findings}


def main() -> int:
    if not FIXTURES.exists():
        print(f"no calibration set at {FIXTURES}")
        return 1

    for case in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        base_p = case / "board_base.json"
        defect_p = case / "board_defective.json"
        if not (base_p.exists() and defect_p.exists()):
            print(f"\n=== {case.name}: INCOMPLETE (missing boards) ===")
            continue

        netlist = None
        nl_p = case / "netlist.json"
        if nl_p.exists():
            netlist = json.loads(nl_p.read_text(encoding="utf-8"))

        try:
            base = Board.from_json(base_p.read_text(encoding="utf-8"))
            defective = Board.from_json(defect_p.read_text(encoding="utf-8"))
            base_rep = verify_board(base, netlist)
            defect_rep = verify_board(defective, netlist)
        except Exception as exc:  # noqa: BLE001
            print(f"\n=== {case.name}: RAISED {type(exc).__name__}: {exc} ===")
            continue

        bs, ds = _statuses(base_rep), _statuses(defect_rep)
        flipped = sorted(c for c, s in ds.items() if s == "fail" and bs.get(c) != "fail")
        changed = sorted(c for c in set(bs) | set(ds) if bs.get(c) != ds.get(c))
        both = sorted(c for c, s in ds.items() if s == "fail" and bs.get(c) == "fail")

        print(f"\n=== {case.name} ===")
        print(f"  base ok={base_rep.ok} proven={base_rep.proven}  "
              f"defect ok={defect_rep.ok} proven={defect_rep.proven}")
        print(f"  FLIPPED to fail: {flipped or 'NONE'}")
        print(f"  changed (any status): {changed or 'none'}")
        print(f"  fail on BOTH (base not clean): {both or 'none'}")
        print(f"  gate: {defect_rep.to_dict().get('gate')}")
        for f in defect_rep.findings:
            if f.status == "fail":
                print(f"    FAIL {f.check}: {f.claim} | {f.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
