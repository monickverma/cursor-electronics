"""
merge_peer_events.py — fold the peer's events into the master's findings file.

WHAT THIS IS
------------
The peer program (S1-S8, on their own branches) reports in `events.jsonl`. Each
line is an EVENT, not a finding: "F-0002 fixed on branch X in commit Y". The
master program reports in `findings.jsonl`. Each line is a FINDING: the thing
is wrong, here is what was seen, here is what should have happened.

The peer asked for their events to be folded in. This script does that, and it
does it carefully, because folding events into findings naively would corrupt
the register in three ways.

WHAT IT DOES NOT DO
-------------------
1. It does not create a finding for a work item. The peer's `PHYS-STEP-0..5`
   and `PLAN-STAGE-3/4/6/7` are STAGES BUILT, not defects found. A finding
   says a thing is wrong. A milestone says a thing was made. Filing the
   milestones as findings would pad the register with the peer's work log and
   make the count of real defects a lie.

2. It does not duplicate a finding. The peer worked on the master's F-0001..
   F-0006 by name. Those rows already exist. The peer's diagnosis and fix are
   ATTACHED to the row that already exists, not written beside it. Two rows
   describing the same defect is how a register stops being countable.

3. It does not silently drop a line it cannot read. One line in the peer's
   file has a bad escape and does not parse. It is reported, not swallowed.

HOW A STATUS IS DERIVED
-----------------------
The peer's events for one finding are a sequence: new -> assigned -> diagnosed
-> fixed. The LAST event wins, because a finding that was diagnosed and then
fixed is fixed, whatever the middle of the sequence said. `wontfix` and
`blocked` are their own outcomes, not "open".

    python .claude/shared-memory/alpha/merge_peer_events.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ALPHA = REPO / ".claude" / "shared-memory" / "alpha"
EVENTS = ALPHA / "events.jsonl"
FINDINGS = ALPHA / "findings.jsonl"

#: Event -> the status it leaves the finding in.
STATUS_BY_EVENT = {
    "new": "open",
    "assigned": "in_progress",
    "diagnosed": "in_progress",
    "fixed": "fixed",
    "verified": "fixed",
    "wontfix": "wontfix",
    "blocked": "blocked",
    "note": "open",
}

#: Events that describe a DEFECT. Only an id that has one of these is a
#: finding. Everything else in the peer's log is a milestone or a session
#: event, and milestones are not findings.
DEFECT_EVENTS = ("new",)

#: Fields the peer's "new" event carries, mapped onto the master's schema.
FIELD_MAP = {
    "observed": "observed",
    "expected": "expected",
    "evidence": "evidence",
    "rung": "rung",
    "severity": "severity",
    "parameter": "parameter",
    "area": "area",
    "ref": "ref",
    "metric": "metric",
    "note": "peer_note",
}


def _load_events() -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(EVENTS.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # One of the peer's lines has a bad escape. It is reported, not
            # swallowed: a line that vanishes quietly is a finding that vanishes
            # quietly.
            print(f"  ! events.jsonl line {i} did not parse and was skipped")
    return rows


def main() -> int:
    events = _load_events()
    findings = [
        json.loads(l)
        for l in FINDINGS.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    by_id = {f["id"]: f for f in findings}

    # Group the peer's events by finding id, keeping the order.
    groups: dict[str, list[dict]] = {}
    for e in events:
        fid = e.get("finding")
        if fid:
            groups.setdefault(str(fid), []).append(e)

    added, enriched, milestones = [], [], []

    for fid, evs in groups.items():
        evs.sort(key=lambda e: str(e.get("ts", "")))
        new_events = [e for e in evs if e.get("event") in DEFECT_EVENTS]

        if not new_events:
            # No defect event. This id is a work item (a stage built) or a
            # reference to a finding the master already owns. If the master
            # owns it, the peer's later events still update the row; if not,
            # it is a milestone and is not filed.
            if fid not in by_id:
                last = evs[-1]
                milestones.append(
                    f"{fid} ({last.get('event')}): {str(last.get('note', ''))[:90]}"
                )
                continue
            new_events = []

        # The LAST event of any kind decides the status.
        last = evs[-1]
        status = STATUS_BY_EVENT.get(str(last.get("event")), "open")

        if fid in by_id:
            row = by_id[fid]
            # Replaced, not appended. The merge has to be safe to run twice:
            # a second run must not double the peer's event list on a row.
            peer: list[dict] = []
            for e in evs:
                line = {
                    "ts": e.get("ts"), "by": e.get("by"), "event": e.get("event"),
                    "area": e.get("area"), "note": e.get("note"),
                    "branch": e.get("branch"), "commit": e.get("commit"),
                }
                if e.get("file_line"):
                    line["file_line"] = e["file_line"]
                peer.append(line)
            row["peer_events"] = peer
            if status == "fixed":
                row["status"] = "fixed"
                row["fixed_by"] = row.get("fixed_by") or (
                    f"peer {last.get('by')} in {last.get('commit')} "
                    f"(branch {last.get('branch')})"
                )
                row["peer_status"] = "fixed"
            else:
                row["peer_status"] = status
            if last.get("commit"):
                row.setdefault("peer_commits", [])
                if last["commit"] not in row["peer_commits"]:
                    row["peer_commits"].append(last["commit"])
            enriched.append(fid)
            continue

        # A finding the master does not have. Build it in the master's shape.
        src = new_events[0] if new_events else evs[0]
        row = {
            "id": fid,
            "stage": "A1",
            "prompt": f"peer {src.get('by')} ({src.get('branch')})",
            "artifact": str(src.get("evidence", ""))[:200],
            "parameter": src.get("parameter"),
            "severity": src.get("severity", "major"),
            "observed": src.get("observed") or src.get("note", ""),
            "expected": src.get("expected", ""),
            "evidence": src.get("evidence", ""),
            "rung": src.get("rung", "evidence"),
            "status": status,
            "fixed_by": None,
            "verified_by": None,
            "source": "peer events.jsonl",
        }
        for k, v in src.items():
            if k in FIELD_MAP and FIELD_MAP[k] not in row:
                row[FIELD_MAP[k]] = v
        if status == "fixed":
            row["fixed_by"] = f"peer {last.get('by')} in {last.get('commit')}"
        row["peer_events"] = [
            {
                "ts": e.get("ts"), "by": e.get("by"), "event": e.get("event"),
                "area": e.get("area"), "note": e.get("note"),
                "branch": e.get("branch"), "commit": e.get("commit"),
            }
            for e in evs
        ]
        findings.append(row)
        by_id[fid] = row
        added.append(fid)

    FINDINGS.write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in findings) + "\n",
        encoding="utf-8",
    )

    print(f"peer events read    {len(events)}")
    print(f"findings added      {len(added)}  {added}")
    print(f"findings enriched   {len(enriched)}  {enriched}")
    print(f"milestones (not filed) {len(milestones)}")
    for m in milestones:
        print(f"    - {m}")
    print(f"total findings      {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
