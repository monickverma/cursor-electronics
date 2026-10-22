# The A1 calibration run — how to hand the seeded boards to an overlooker

> Written 2026-10-21 by the master session. This file is the RUNBOOK for the
> A1 calibration run. The overlooker's own instructions are
> `overlooker.md` and do not change per run. This file says what the master
> session hands over, and what it does with the answer.

---

## 0. What this run measures

**Did the overlooker find the defects we planted, and did it wrongly pass any
board that has a critical defect in it?**

That is the A1 exit criterion, and only that. The run does not measure
whether the product is correct — the seeded boards are wrong by construction.
It measures the *detector*.

Two numbers come out:

| Number | Meaning | A1 gate |
|---|---|---|
| Recall | of the seeded defects, how many did the overlooker name? | ≥ 90% |
| False passes | of the seeded defects, how many did the overlooker report as CLEAN? | **0** on the critical classes |

A false pass is worse than a miss. A miss is a hole in the detector. A false
pass is the detector saying "all well" over a board that is not.

---

## 1. What is staged, and where

`stage_artifacts.py` writes each seeded board as a real KiCad 10 project:

```
tests/fixtures/alpha_known_bad/artifacts/
├── board_01/
│   ├── board_01.kicad_pcb     the board, as KiCad 10.0.1 reads it
│   ├── board_01.kicad_pro     the project
│   ├── board_ir.json          the Board IR — the product's own source of truth
│   └── drc_summary.json       KiCad's own DRC, counted
├── board_02/ ...
├── presentation.json          which request goes with which board
└── MAPPING.json               board_01 = which case      ← DO NOT PASS THIS ON
```

Every folder is a DEFECTIVE board. The folder names say nothing about the
defect, so the overlooker cannot tell case A from case B.

**`MAPPING.json` and `presentation.json` are for the master session.**
`presentation.json` holds the request per board, so the master session knows
what to ask for each one. The overlooker gets a request and a folder. Nothing
else.

---

## 2. How to run it

The base URL, the register call, the auth header and the rubric are all in
`overlooker.md`. The calibration run adds three rules.

### 2.1 The request and the board go together

For each folder, send the request from `presentation.json` **and** hand over
the folder in the same turn. The request is what the engineer said; the
folder is what the product produced. The overlooker then does what an
engineer does: open the board, read it, decide.

Do NOT give the overlooker the whole set at once and let it choose. One
request, one board, one set of findings.

### 2.2 The artifacts are the product's output, and that is the point

The seeded board reaches the overlooker as a KiCad project. The question it
answers is about THE PRODUCT: would this tool have shipped a board with this
defect in it?

For the copper defects (cut track, deleted via, bridged nets) the answer is
in the board and in KiCad's DRC. For the netlist-level defects (swapped pins,
reversed diode) the board faithfully realises a wrong netlist — the board is
not wrong, the thing the board was built from is. The overlooker has to
compare the part's pinout against the datasheet and the circuit's intent to
find those. That is the hard half of the set, and it is the half that
matters: a tool that only catches broken copper has not caught the errors
that reach a fab.

### 2.3 What the overlooker does not get

- The answer key (`KEY.json`). Never.
- `MAPPING.json`. Never.
- The case's `manifest.json`. Never.
- Any file under `backend/`, `frontend/`, `tests/`, `reports/`, `brain/`, `plan/`.

The overlooker is a black-box engineer. Every finding it reports is worth
exactly as much as its independence. The master session checks its tool log
for a peek.

---

## 3. Where the answer goes

The overlooker writes findings to a JSONL file, one object per line, with
the schema in `overlooker.md` §6. Each finding names the artifact it is
about — the folder name, e.g. `artifacts/board_03`. The scorer matches on
that.

Then the master session scores it:

```bash
python .claude/shared-memory/alpha/score_overlooker.py \
    --findings <path to the findings file>
```

The scorer prints the per-case outcome, the recall, the critical recall and
the false passes, and exits non-zero if the gate fails.

### The four outcomes

| Outcome | What the overlooker did | Counts as |
|---|---|---|
| `detected` | named the fault, or the check that found it | recall |
| `flagged` | noticed something, did not name the fault | near miss — better than a false pass, worse than a detection |
| `missed` | said nothing about this board | a miss |
| `passed_clean` | said the board was fine | **a false pass** — blocks A1 on a critical class |

A report that says a CHECK IS MISSING is a `flagged`, never a `detected` and
never a `passed_clean`. "The product has no check for shorts" is a true and
useful finding about the product; it is not a finding that a short exists.

---

## 4. The calibration set as it stands (2026-10-22)

Seven cases. Six are critical. Three are caught by the product's own
verifier; four are declared gaps, where the product does not catch the
defect and says so.

| Case | Board | Class | Critical | Our verifier | KiCad DRC | The point |
|---|---|---|---|---|---|---|
| bridged_nets | board_01 | short | yes | III.2 fails | 26 violations (clean: 13) | the easy half |
| cut_track | board_02 | open | yes | III.1 fails | 5 unconnected (clean: 4) | the easy half |
| deleted_via | board_03 | open | yes | III.1 fails | 5 unconnected (clean: 4) | the easy half |
| reversed_diode | board_04 | reversed diode | yes | no check | nothing | the hard half — and the check that could have caught it RAN and passed |
| swapped_pins | board_05 | wrong pinout | yes | no check | nothing | the hard half — a transistor with E and C transposed |
| wrong_cap_value | board_06 | wrong value | no | no check | nothing | not critical — a capacitor ten times too small |
| mains_gap | board_07 | creepage | yes | no check | nothing | a mains net 0.35 mm from a SELV net |

The board number comes from `MAPPING.json` and never renumbers. The folder
name says nothing about the defect.

### The seventh case, `mains_gap` (built 2026-10-22)

The product has no mains template, so this board was laid by hand on top of
the product's own board: the mains domain added, and the same board with
MAINS_L moved from 5.85 mm to 0.35 mm away from the DHT22_DATA net.

It is a declared false pass: the product's own verifier returns `ok=True` on
the defective board, and KiCad's DRC is identical on both boards (9
violations, 4 unconnected GND pads). Nothing in the product looks at a
clearance. The 5.0 mm requirement is quoted from IEC 60664-1 Table F.4 and
is **not qualified by anyone** — see owner decision D1. The geometry itself
is exact.

### The two that matter most

`swapped_pins` and `reversed_diode` are the cases where the product emits
the board for fabrication with the defect in it. The verifier is not at
fault: it is handed the netlist the board was compiled from, so it can only
answer "is this board what I was told to build". On `reversed_diode` the
check that reaches a second source — IV.2, the KiCad symbol — actually runs,
resolves, agrees, and still passes, because a symbol says nothing about
which net belongs on which terminal.

A detection on either of those is the strongest result the set can give. It
means the overlooker read the board as an engineer would, went to the
datasheet, and caught something the product's own machinery cannot.

---

## 5. What the master session does with the result

1. Score it. `score_overlooker.py`.
2. Write the recall per parameter to the ledger, with tokens and dollars.
3. File a finding for every defect the overlooker missed, with the rung
   stated.
4. If the gate fails on a false pass, that is a **builder** task, not a
   threshold change. The threshold is the owner's, and it was confirmed
   before the run.
5. Report to the owner: recall, false passes, tokens, dollars, and what
   needs a decision.
