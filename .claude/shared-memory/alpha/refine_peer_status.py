"""
refine_peer_status.py — the two findings the peer's merge closed need a caveat.

WHY
---
`merge_peer_events.py` sets a finding to "fixed" when the peer's last event
says fixed or verified. For F-0003 and F-0004 that is right about the CODE and
wrong about everything else, and a register that says "fixed" with no caveat
is a register that hides the remaining work.

  F-0003 the router metamorphic tests. The peer's S4 wrote them and S7 merged
         them. The master's own row still said "not yet merged" because at the
         time the master wrote it, they were not. Now they are.

  F-0004 the creepage refusal. The peer's S5 implemented V.6: it refuses
         mains-to-SELV below the reinforced figure and never claims
         compliance. That is the code half, and the owner's decision D1
         (amend decision 12 in the implementation plan) is still open, and
         the IEC 60664-1 table the figures come from is marked UNVERIFIED in
         the peer's own words: it needs a qualified review. A creepage number
         nobody qualified is a creepage number that must not be trusted, and
         the register must say so rather than show a green tick.

So the caveat is written into the row. The status is right; the row now also
says what is still open.

    python .claude/shared-memory/alpha/refine_peer_status.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FINDINGS = REPO / ".claude" / "shared-memory" / "alpha" / "findings.jsonl"

REFINEMENTS: dict[str, dict] = {
    "F-0003": {
        "fixed_by": "S4 in 2f55cc2 + 52657b9 (branch claude/alpha-s4-build-router-e19024), merged by S7 in b4a010e",
        "verified_by": "S7 verified on the integration branch: tests/test_pcb_router_metamorphic.py (29 tests) pass in the full suite. The peer's mutation check is the point of the fix: a name-sorted net order fails the rename test and an unseeded RNG fails the determinism test, so the tests can actually fail. No router bug was found by them.",
    },
    "F-0004": {
        "verified_by": "CODE FIXED AND VERIFIED, BUT NOT CLOSED. S5 implemented verify.py V.6: it refuses a mains-to-SELV gap below the reinforced figure (5.0 mm at 250 V, PD2, group III, doubled basic per IEC 60664-1 Table F.4, with the next impulse step from F.2) and it never claims compliance. S7 verified it on the API: an RS485_A net declared at 230 V against SELV nets fails, needing 5.0 mm creepage and 3.0 mm clearance where the board has 0.35-0.67 mm. TWO THINGS REMAIN OPEN. (1) OWNER DECISION D1: implementation-plan decision 12 still reads 2.5 mm refuse / 5.0 mm warn; the plan has not been amended to the implemented rule, so the document and the code disagree. (2) THE TABLE IS UNVERIFIED: the peer's own note says the reinforced figure needs a qualified review. A creepage number nobody qualified must not be treated as a safe number, whatever the code says about it.",
        "still_open": [
            "owner decision D1: amend decision 12 in reports/PCB verification implementation plan.md to the implemented reinforced figure",
            "the IEC 60664-1 table the figures come from is marked unverified; it needs a qualified review before a board is built to it",
        ],
    },
}


def main() -> int:
    rows = [json.loads(l) for l in FINDINGS.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}
    changed = []
    for fid, fields in REFINEMENTS.items():
        row = by_id.get(fid)
        if row is None:
            print(f"  ! {fid} is not in the register")
            continue
        row.update(fields)
        changed.append(fid)
    FINDINGS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print("refined:", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
