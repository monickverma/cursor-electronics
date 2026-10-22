"""
log_overlooker_milestones.py — write the A1 overlooker runs into the ledger.

WHY A SCRIPT AND NOT A HAND EDIT
--------------------------------
The ledger is the cost record of the program. It is append-only, one JSON
object per line, and every row has to say the same things. A hand edit
drops a field on one row and the cost record stops being countable.

THE TOKEN FIGURES, AND WHY THEY ARE NOT ALL THE SAME
----------------------------------------------------
Three different things can be called "the tokens", and this program has all
three, so every row says which one it is:

  `tokens_in`           what the agent reported about itself. A self-report,
                        and an agent that ends on an error never reports one.
  `tokens_measured`    the transcript, counted after the fact: every message
                        the harness logged, with the input tokens of each
                        turn. The context is re-sent every turn, so this
                        number counts the same context many times over. It
                        is a measure of EFFORT, not of cost.
  `tokens_reported`    what the harness reported for the agent as a whole
                        (the same figure the task notification carries).

`token_source` says which one a row carries. A row with a number in
`tokens_in` and none in `tokens_measured` was self-reported. A row with
`tokens_measured` and no `tokens_in` was counted from the transcript,
because the agent never said. Both are true and they are not the same
number, and a ledger that pretends they are is not a cost record.

    python .claude/shared-memory/alpha/log_overlooker_milestones.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / ".claude" / "shared-memory" / "alpha" / "ledger.jsonl"

#: One row per overlooker run.
#:
#: board -> (tokens the agent reported, tool uses, wall-clock ms, findings
#: written, what it found). `None` means the number was never available —
#: a null is honest, a made-up number is not.
RUNS = {
    "board_01": (136702, 58, 5992276, 11,
                 "bridged_nets found: F-0001 names the shorted nets"),
    "board_02": (136646, 76, 6220758, 17,
                 "cut_track found: F-0202 names the severed RELAY_CTRL net, 0.5999 mm of no copper"),
    "board_03": (140948, 47, 4892250, 12,
                 "deleted_via found: F-0001 names the missing via"),
    "board_04": (499093, 69, 12203828, 10,
                 "reversed_diode found: F-0401 names the cathode on SW_LOAD instead of VCC_5V"),
    "board_05": (None, 198, None, 15,
                 "swapped_pins found: F-05-001 names the 2N2222A with its emitter and "
                 "collector transposed, and the coil current it computes is zero"),
    "board_06": (None, 109, None, 15,
                 "wrong_cap_value found: F-06-006 names 10 nF against the requested 100 nF"),
    "board_07": (None, 42, 1036140, 16,
                 "mains_gap found: F-07-001 measures 0.350 mm between MAINS_L and "
                 "DHT22_DATA on F.Cu and states the requirement it fails, measured "
                 "from the copper and not from the tool"),
}

#: The harness's own figure for an agent as a whole, where the task
#: notification carried one. A different unit again from the transcript
#: count: this is what the run consumed, not what the context re-sending
#: cost.
REPORTED = {
    "board_07": 161227,
}

#: What the transcript of the run was worth, where the transcript survived
#: to be counted. The context is re-sent every turn, so this is effort, not
#: cost. The board_01, board_03 and board_04 transcripts were cleaned up by
#: the harness before they could be counted, and their rows carry the
#: agent's own figure.
MEASURED = {
    "board_02": 4011347,
    "board_05": 5915369,
    "board_06": 4149685,
}

#: The milestone rows for the work that was not an overlooker run.
MILESTONES = [
    {
        "stage": "A1", "by": "master",
        "milestone": "the token figures, counted from the transcripts that survived",
        "agents": 0, "tool_calls": 0,
        "tokens_in": None, "tokens_out": None, "usd": 0.0,
        "result": ("Three of the seven overlooker transcripts were still on disk when the "
                   "cost was counted, and each was counted the same way: every message the "
                   "harness logged, with the input tokens of each turn. board_02 "
                   "4,011,347 over 96 tool uses; board_05 5,915,369 over 198; board_06 "
                   "4,149,685 over 119. The context is re-sent every turn, so these count "
                   "the same context many times over: they are a measure of EFFORT, not of "
                   "cost, and they are not comparable with the self-reported figures in "
                   "tokens_in (913,389 over the four runs that gave one). The board_01, "
                   "board_03 and board_04 transcripts were cleaned up by the harness before "
                   "they could be counted. The run rows written before this milestone "
                   "carry no token_source field: a row with a number in tokens_in is a "
                   "self-report, and a row with none is counted from the transcript or "
                   "reported by the harness, which is what token_source says."),
    },
    {
        "stage": "A1", "by": "master",
        "milestone": "the A1 gate: 7 of 7 seeded defects detected, 0 false passes",
        "agents": 0, "tool_calls": 0,
        "tokens_in": None, "tokens_out": None, "usd": 0.0,
        "result": ("All seven cases DETECTED, none flagged, none missed, and no board the "
                   "overlooker passed clean. Critical recall 6 of 6. The gate that was "
                   "BLOCKED at 6 of 7 is open. What it measures is the DETECTOR, not the "
                   "product: four of the seven defects are ones the product's own verifier "
                   "passes, and the mains case is one the product has no rule for at all. "
                   "The set is seven boards, so the 90% figure is 7 of 7 or nothing - a "
                   "single miss would have blocked the stage, and one nearly did."),
    },
    {
        "stage": "A1", "by": "master",
        "milestone": "the A1 scorer had two defects, and both of them moved the number",
        "agents": 0, "tool_calls": 0,
        "tokens_in": None, "tokens_out": None, "usd": 0.0,
        "result": ("(1) The key's phrases were matched against normalised text while the phrases "
                   "themselves were not, so a net name written 'relay_ctrl' could never match "
                   "'RELAY_CTRL' in a finding: a real detection scored as a miss. (2) The clean-bill "
                   "test was a substring search, and it fired on 'the flyback diode IS CORRECT under "
                   "a convention' and on 'the 2N2222A is BYPASSED', turning a board the overlooker had "
                   "refused to send to a fab into a FALSE PASS. Fixed, and the key was split: words "
                   "that name the FAULT detect, words that name the PART are a near miss, and a wrong "
                   "value is now caught by stating the specified value and a different one - a rule "
                   "from the defect, not from any one run's wording. 19 new tests on the scorer "
                   "(37 in all, 1 skipped until the set is complete)."),
    },
    {
        "stage": "A1", "by": "master",
        "milestone": "the seventh calibration case: mains_gap, a mains-to-SELV clearance fault",
        "agents": 1, "tool_calls": 81,
        "tokens_in": None, "tokens_out": None,
        "tokens_reported": 50938, "usd": 0.0,
        "duration_ms": 3533604,
        "result": ("The last case needed a mains-carrying board and the product has no mains "
                   "template, so the builder laid the mains domain by hand on top of the "
                   "product's own board. MAINS_L runs 0.35 mm from the DHT22_DATA net, where the "
                   "base board has 5.85 mm. The product's verifier returns ok=True on the "
                   "defective board and KiCad's own DRC is identical on both: a false pass, "
                   "declared as one. The 5.0 mm requirement is quoted from IEC 60664-1 Table F.4 "
                   "and is NOT qualified by anyone; the geometry is exact. That gap is owner "
                   "decision D1."),
    },
    {
        "stage": "A1", "by": "master",
        "milestone": "the A1 scorer grew a rule for a clearance fault, and the key with it",
        "agents": 0, "tool_calls": 0,
        "tokens_in": None, "tokens_out": None, "usd": 0.0,
        "result": ("A phrase list cannot catch 'mains-to-SELV creepage is 0.35 mm' in every "
                   "wording, the same way it could not catch a wrong capacitance. So the scorer "
                   "can now read a MEASURED GAP: a finding that measures a space and finds it "
                   "under 2 mm has named the fault. The number has to be a gap and not a feature "
                   "- a track width is not a clearance - and a number that belongs to a "
                   "configured rule ('the 0.2 mm clearance rules are set to zero') is not a "
                   "measurement of the board. A full stop between digits is a decimal point, not "
                   "a sentence end; the clause splitter was reading 0.35 mm as 0 and 35. "
                   "8 new tests on the scorer (45 in all, none skipped)."),
    },
]


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for board, (tokens, tools, ms, findings, note) in RUNS.items():
        measured = MEASURED.get(board)
        reported = REPORTED.get(board)
        if tokens is not None:
            source = "agent_self_report"
        elif measured is not None:
            source = "transcript_measurement"
        elif reported is not None:
            source = "harness_report"
        else:
            source = "unavailable"
        rows.append({
            "ts": now, "stage": "A1", "by": "master",
            "milestone": f"the A1 overlooker run: {board} ({findings} findings)",
            "agents": 1, "tool_calls": tools,
            "tokens_in": tokens, "tokens_out": None,
            "tokens_measured": measured,
            "tokens_reported": reported,
            "token_source": source,
            "usd": 0.0,
            "duration_ms": ms,
            "result": note,
        })
    rows.extend(MILESTONES)

    # The ledger is append-only, but running this twice must not double a
    # row. A milestone already in the file is skipped.
    already = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                already.add(str(json.loads(line).get("milestone")))
            except json.JSONDecodeError:
                continue
    fresh = [r for r in rows if r["milestone"] not in already]

    with LEDGER.open("a", encoding="utf-8") as fh:
        for row in fresh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"appended {len(fresh)} rows to {LEDGER} "
          f"({len(rows) - len(fresh)} were already there)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
