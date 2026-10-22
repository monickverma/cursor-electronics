# Alpha program — status

_Updated 2026-10-22 09:00 UTC. Master session._

| Field | Value |
|---|---|
| Stage | **A1 — Alpha 1, evaluator and calibration** |
| Branch | `alpha-program` (from `verifier-contact-fixes` @ `3d8da26`) |
| Commits this session | `e4e23bd` (F-0009 timestamps), `33b8eba` (calibration set, staging, first run), `7003f64` (the seventh case, the gap rule, six runs) |
| Blockers | **the A1 gate is OPEN** — measured 7/7 with 0 false passes. What is still open is the product: F-0004 and F-0008 |
| Model | `minimax-m3.1-flash:cloud` via Ollama — free until **2026-10-22 23:59 UTC** (~15 h left) |
| Cost | **$0.00.** Every agent in this program ran on the free local model. No Anthropic API call was made by any agent in this program. |

## The A1 gate, measured

The A1 gate is on the **overlooker** — a black-box engineer given one request and
one board folder, and nothing else. It measures the detector, not the product.

```
cases              7
detected           7
flagged (near miss)0
missed             0
recall             100%   (A1 target: >= 90%)
critical recall    100%   over 6 cases
false passes       0      (A1 target: 0 on critical classes)

GATE: every critical defect was detected.
```

| Case | Board | Class | Critical | Outcome | The finding that named it |
|---|---|---|---|---|---|
| bridged_nets | board_01 | short | yes | DETECTED | F-01-01: names the shorted nets |
| cut_track | board_02 | open | yes | DETECTED | F-02-02: names the severed RELAY_CTRL net, 0.5999 mm of no copper |
| deleted_via | board_03 | open | yes | DETECTED | F-03-01: names the missing via |
| reversed_diode | board_04 | reversed diode | yes | DETECTED | F-04-01: names the cathode on SW_LOAD instead of VCC_5V |
| swapped_pins | board_05 | wrong pinout | yes | DETECTED | F-05-01: names the 2N2222A with E and C transposed |
| wrong_cap_value | board_06 | wrong value | no | DETECTED | F-06-006: states 10 nF against the requested 100 nF |
| mains_gap | board_07 | creepage | yes | DETECTED | F-07-001: measures 0.350 mm between MAINS_L and DHT22_DATA and states the requirement it fails |

**No board was passed clean.** The false pass — the outcome that blocks the stage —
did not happen on any of the seven.

The set is seven boards, so 90 % is 7 of 7 or nothing. One miss would have blocked
the stage, and one nearly did: at six of seven the gate read BLOCKED, and the last
case was the only one that could close it.

### The same set, against our own verifier

`verify_calibration.py` measures the product, not the detector:

```
cases      7 | seeded 7 | detected 3 | known gap 4 | false pass 0
critical   6 cases, 0 false passes, 3 known gaps
GATE: BLOCKED — a DECLARED known gap on a critical class.
```

Detected: `bridged_nets` (III.2), `cut_track` (III.1), `deleted_via` (III.1).
Declared gaps: `mains_gap` (F-0004), `reversed_diode` (F-0008), `swapped_pins`
(F-0008 / F-S0-0001), `wrong_cap_value` (no check reads a passive's value).

**Both numbers are true and they are about different things.** A black-box engineer
finds the defect; the product does not. That is the gap the program exists to close,
and A1 has now shown it can be closed by something outside the product.

## What the seventh case showed

`mains_gap` is the case that had to be built by hand: the product has no mains
template, so the fixture laid the mains domain on top of the product's own board.
MAINS_L runs **0.35 mm** from the DHT22_DATA net, where the base board has
**5.85 mm**.

Every check the product runs returns the same answer on the defective board as on
the base board: the verifier returns `ok=True` on both, the kernel's DRC reports
zero violations on both, and KiCad 10.0's own DRC reports the same 11 warnings and
the same 4 unconnected GND pads on both. The exported `.kicad_pro` has every
manufacturing minimum set to **0.0**, so the board's own DRC in the fab data
enforces nothing at all.

The overlooker measured the gap from the copper — 0.350 mm, centre-to-centre
0.900 mm less the two half-widths — and stated the requirement it fails beside it.
It also ran KiCad's DRC with the mains net class set to 3.2 mm and got 14 mains
clearance violations, which is the same fact seen from the other side.

**This is now a measured false pass in the product, not a suspicion.**

## Cost and tokens

Every agent ran on the free local model. **$0.00** in API spend.

| Measure | Figure | What it is |
|---|---|---|
| overlooker runs | 7 | one per seeded board |
| findings written | 96 | 11, 17, 12, 10, 15, 15, 16 |
| tool calls | 599 | as reported by each agent |
| agent self-reported tokens | 913,389 | over the four runs that gave a figure |
| transcript-counted tokens | 14,076,401 | board_02, board_05, board_06 — effort, not cost; the context is re-sent every turn |
| harness-reported tokens | 161,227 | board_07, the run that closed the gate |
| wall clock | 505.8 min | across the seven runs |

The three token measures are three different units and the ledger says which one
each row carries (`token_source`). A self-report and a transcript count are not the
same number, and the ledger does not pretend they are.

## Done
- Bootstrap read. Branch `alpha-program` created. Never commit to master.
- Runtime up: Docker Desktop, Postgres 16, Redis 7, uvicorn :8000, Celery worker.
- **Product verified end-to-end** — `POST /auth/register` 201, `POST /design/generate` 201 for RC, LED
  and composition; composition returned 6 components, 5 nodes, 15 connections, a 6-row BOM, a schematic
  and a `pcb_netlist`. A PCB compile of the 8-part DHT22 board: 2.2 s, 12/12 routed, 0 DRC errors,
  `verified: true`, `proven: false`.
- Refusal path verified: an under-specified prompt returns 422 `underdetermined` naming the missing
  fields. Hard abstention works.
- **F-0009 (critical, fixed).** Every timestamp the ORM wrote used `datetime.utcnow()` — the UTC wall
  clock with no tzinfo. asyncpg reads a naive datetime as LOCAL time, so on this host (UTC+5:30) a row
  written at 15:21 landed at 09:51 UTC. The explanation route compares a design's age against a 300 s
  staleness window, so a design two seconds old looked five and a half hours old, the route decided the
  attempt was lost, and it fired its one allowed retry on the very first poll — while the worker was
  running and answering. Measured against the live database: naive 15:21:10 stored as 09:51:10+00, age
  5:30:00.000333. Fixed at the source (`_utcnow()` in `db/models.py`, 14 column defaults; 10 explicit
  writes in `db/crud.py`). `tests/test_utc_timestamps.py` (10 tests) pins it and was **verified to fail
  with the bug put back**.
- **A1 calibration set: 7 of 7 cases built.** Each with the script that seeded it, a manifest, the base
  and defective boards, and the netlists. `KEY.json` is the answer key and was written for the seventh
  case **before** the run, so the instrument was not tuned to the answer.
- **The scorer can fail.** `tests/fixtures/alpha_known_bad/test_score_overlooker.py` (46 tests) proves
  the four outcomes are reachable — DETECTED, FLAGGED, MISSED, PASSED_CLEAN. PASSED_CLEAN (the false
  pass) was unreachable before 2026-10-21, which meant the A1 gate "0 false passes on the critical
  classes" was a gate that could not fail.
- **The staging hides the answer.** `stage_artifacts.py` writes each seeded board as a real KiCad 10
  project; `stage_boards.py` writes the raw Board IR. Both use opaque file names. The case id AND the
  defect class live in `MAPPING.json`, which the overlooker never sees. The board number never renumbers.
- **KiCad 10.0.1 is proven to be an independent judge.** On the seeded boards: cut_track 4→5
  unconnected, deleted_via 4→5 unconnected, bridged_nets 13→26 violations (10 `shorting_items`),
  while reversed_diode 10→10, swapped_pins 13→13, wrong_cap_value 13→13. KiCad sees the copper
  defects and is blind to the netlist-level ones — exactly as the architecture predicts.
- **The overlooker found the reversed diode.** board_04 → `runs/board_04.jsonl`, 10 findings. F-0401
  names the cathode on SW_LOAD instead of VCC_5V, read off the board against KiCad's `D_SOD-123` and
  the 1N4148W datasheet. Evidence in `runs/evidence_board_04/`.
- **The set is complete and the gate is open.** 7/7, 0 false passes.
- **Quilter pilot teardown written** (`reports/competitors/quilter.md` — PRC tolerances ±10 %, Simbeor
  impedance, ALPHA router strategy, 2–10+ layers). Six teardowns copied into the tree.
- Test suite: 2819 passed, 33 skipped. 13 failures, all in the peer's in-flight work (5 router
  metamorphic, 2 scene3d) or the timestamp test now fixed. The 4 order-dependent `TestRailShort`
  failures are **gone**.

## In progress
| Agent | Task | Owns | State |
|---|---|---|---|
| peer (3 Claude Desktop sessions) | Uno R3 shield architecture, router metamorphic | `pcb_engine/shields.py`, `router.py`, `scene3d.py` | uncommitted in the working tree — **not touched by the master session** |

The seven overlooker runs are finished. The peer's in-flight work stays in the
working tree; the master session's commits carry only its own rows, and
`alpha/stage_master_rows.py` is how the two programs share one JSONL file without
one committing the other's.

## Open findings: 12 total — 4 open, 8 fixed
| ID | Severity | State | What |
|---|---|---|---|
| F-0001 | major | fixed | rate limit not configurable |
| F-0002 | critical | fixed | RS-485 A/B short |
| F-0003 | major | in progress | router metamorphic tests (peer) |
| F-0004 | critical | **open** | creepage rule vs reinforced insulation — now with a root cause: F-0024 |
| F-0005 | major | open | every land pattern carries `verified: false` — now with two named instances: F-0025, F-0026 |
| F-0006 | major | fixed | explanation queued once, not once per poll |
| F-0008 | critical | **open** | no check compares a part's pin-to-net map against the DESIGN INTENT |
| F-0009 | critical | fixed | naive timestamps (fixed this session) |
| F-0024 | critical | **open** | the clearance model is binary: two net classes, and nothing knows what mains is |
| F-0025 | critical | **open** | the relay's land pattern states no geometry, and the board places it 15.00 mm apart anyway |
| F-0026 | major | **open** | the DHT22's courtyard is 16.9 mm too small for the body |
| F-0027 | major | **open** | the mains conductor is 0.8 mm and the current it must carry is never stated |

**F-0008 is the architectural one.** `compile_board` calls `verify_board(board, netlist)`
with the same netlist it just compiled from. The verifier can answer "is this board
what I was told to build" and never "is what we were told to build right". On the
reversed-diode board the check that could reach the second source **actually ran and
still passed**: IV.2 compared D1's pinout against the KiCad symbol for 1N4148W-7-F,
agreed, and reported "3 part(s) agree with an independent transcription". The diode is
fitted backwards and the board is emitted for fabrication.

**F-0024 is the root of F-0004.** The product's clearance model is binary — a
"default" class at 0.25 mm and a "power" class at 0.30 mm — and nothing reads a net's
name or domain. A mains net declared as a power net gets 0.30 mm. Raising the
2.5 mm creepage threshold to 5 mm would not help, because no rule knows which nets
are mains. The fix is a class for a hazardous net, not a bigger number.

## Next three actions
1. **F-0008** — a check that compares each part's pin-to-net map against the DESIGN
   INTENT, not against the netlist the board was compiled from. This is what turns
   three of the four known gaps into either detections or honest remaining gaps.
2. **F-0024** — a net class for a hazardous net, and a rule that puts a net there.
   This is what turns the fourth known gap into a detection.
3. **Report A1 status and the A1 thresholds to the owner** (D2 below). The gate is
   measured; the thresholds are the owner's to confirm, and the exit criterion asks
   for it in writing.

## Blockers
- Nothing blocks the A1 gate. The gate is open on the evidence.
- What the gate does **not** say is that the product is safe. Four of the seven
  seeded defects are ones the product passes today, and the program has no software
  that can prove otherwise.

## Owner decisions needed
- **D1 — creepage (F-0004).** Decision 12 refuses below 2.5 mm and warns below 5.0 mm. 2.5 mm is
  *basic* insulation. Mains-to-SELV needs *reinforced* (~5 mm at 250 V). The plan's own note says the
  doubled figure is from memory and unconfirmed, and that only a qualified review settles safety.
  Amend decision 12, or accept 2.5 mm as a documented limitation? The mains case was built on the
  5.0 mm figure **as a quoted reference, not a qualified one**, and its manifest says so. The geometry
  is exact either way; only the threshold is in question.
- **D2 — A1 thresholds.** The handoff's proposed gates are proposals, to be confirmed by the owner:
  ≥90 % recall on the seeded set, 0 false passes on the critical classes. **Measured: 100 % recall
  (7/7) and 0 false passes.** A1's exit criterion also requires a token and cost log per milestone
  (in `alpha/ledger.jsonl`) and the Quilter pilot teardown (written). The owner is asked to confirm the
  thresholds, and to say whether A1 may exit on the overlooker's number alone, or must also wait for
  F-0008 and F-0024.
- **D3 — the LED's V_F minimum** and the other D7 figure confirmations are still open; they bear on
  parameter 3 (pinout and footprint) grading. They now have company: the relay's land pattern states
  no geometry either (F-0025), and the DHT22's courtyard is 16.9 mm short (F-0026).

## Limits of this program
No tool proves a board works. Every result carries a rung: exact, sound, bounded, simulated, rule check,
evidence, unknown. "All physical errors detected" is not a reachable claim. The goal is that every physical
error class has a named check or a named physical test, and the gap list is explicit. The 100 % recall
above is a recall on seven seeded boards — a sample, not a proof, and a detector that has read the
answer key is not a detector.

## Where the next session starts
1. `python .claude/shared-memory/alpha/score_overlooker.py --findings .claude/shared-memory/alpha/runs/all.jsonl` — the A1 number.
2. `python .claude/shared-memory/alpha/verify_calibration.py` — the product's own number, ~2 s.
3. `alpha/ledger.jsonl` — every milestone, with tokens and USD.
4. `alpha/findings.jsonl` — the open findings, assigned.
5. `alpha/overlooker_run.md` — the runbook for one board, one turn, one request.
6. `reports/competitors/quilter.md` — the A1 pilot teardown.
