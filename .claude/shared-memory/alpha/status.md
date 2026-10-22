# Alpha program — status

_Updated 2026-10-21 21:00 UTC. Master session._

| Field | Value |
|---|---|
| Stage | **A1 — Alpha 1, evaluator and calibration** |
| Branch | `alpha-program` (from `verifier-contact-fixes` @ `3d8da26`) |
| Commits this session | `e4e23bd` (F-0009 timestamps), `33b8eba` (calibration set, staging, first run) |
| Blockers | **A1 gate is blocked** by 2 declared critical known gaps (F-0004, F-0008) |
| Model | `minimax-m3.1-flash:cloud` via Ollama — free until **2026-10-22 23:59 UTC** (~27 h left) |

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
- **A1 calibration set: 6 of 7 cases built.** `bridged_nets`, `cut_track`, `deleted_via`,
  `reversed_diode`, `swapped_pins`, `wrong_cap_value` — each with the script that seeded it, a manifest,
  the base and defective boards, and the netlists. `KEY.json` is the answer key.
- **The scorer can fail.** `tests/fixtures/alpha_known_bad/test_score_overlooker.py` (18 tests) proves
  the four outcomes are reachable — DETECTED, FLAGGED, MISSED, PASSED_CLEAN. PASSED_CLEAN (the false
  pass) was unreachable before 2026-10-21, which meant the A1 gate "0 false passes on the critical
  classes" was a gate that could not fail.
- **The staging hides the answer.** `stage_artifacts.py` writes each seeded board as a real KiCad 10
  project; `stage_boards.py` writes the raw Board IR. Both use opaque file names. The case id AND the
  defect class live in `MAPPING.json`, which the overlooker never sees.
- **KiCad 10.0.1 is proven to be an independent judge.** On the seeded boards: cut_track 4→5
  unconnected, deleted_via 4→5 unconnected, bridged_nets 13→26 violations (10 `shorting_items`),
  while reversed_diode 10→10, swapped_pins 13→13, wrong_cap_value 13→13. KiCad sees the copper
  defects and is blind to the netlist-level ones — exactly as the architecture predicts.
- **The overlooker found the reversed diode.** board_04 → `runs/board_04.jsonl`, 10 findings. F-0401
  names the cathode on SW_LOAD instead of VCC_5V, read off the board against KiCad's `D_SOD-123` and
  the 1N4148W datasheet. Evidence in `runs/evidence_board_04/`. This is the strongest result the set
  can produce, and it confirms the key's reasoning: a netlist-level defect must be found by reading
  the board as an engineer would.
- **Quilter pilot teardown written** (`reports/competitors/quilter.md` — PRC tolerances ±10 %, Simbeor
  impedance, ALPHA router strategy, 2–10+ layers). Six teardowns copied into the tree.
- Test suite: 2819 passed, 33 skipped. 13 failures, all in the peer's in-flight work (5 router
  metamorphic, 2 scene3d) or the timestamp test now fixed. The 4 order-dependent `TestRailShort`
  failures are **gone**.

## In progress
| Agent | Task | Owns | State |
|---|---|---|---|
| overlooker | board_01 (bridged_nets) | `runs/board_01.jsonl` | running, gerbers written |
| overlooker | board_03 (deleted_via) | `runs/board_03.jsonl` | running, DRC written |
| overlooker | board_06 (wrong_cap_value) | `runs/board_06.jsonl` | running |
| peer (3 Claude Desktop sessions) | Uno R3 shield architecture, router metamorphic | `pcb_engine/shields.py`, `router.py`, `scene3d.py` | uncommitted in the working tree — **not touched by the master session** |

Still to run: board_02 (cut_track), board_05 (swapped_pins). Still to build: `mains_gap` (creepage).
Several agents died on HTTP 429 "too many concurrent requests" from the model endpoint. **Run three at
a time, not six.**

## Open findings: 8 total — 4 open, 4 fixed
| ID | Severity | State | What |
|---|---|---|---|
| F-0001 | major | fixed | rate limit not configurable |
| F-0002 | critical | fixed | RS-485 A/B short |
| F-0003 | major | in progress | router metamorphic tests (peer) |
| F-0004 | critical | **open** | creepage rule vs reinforced insulation |
| F-0005 | major | open | every land pattern carries `verified: false` |
| F-0006 | major | fixed | explanation queued once, not once per poll |
| F-0008 | critical | **open** | no check compares a part's pin-to-net map against the DESIGN INTENT |
| F-0009 | critical | fixed | naive timestamps (fixed this session) |

**F-0008 is the architectural one.** `compile_board` calls `verify_board(board, netlist)` with the same
netlist it just compiled from. The verifier can answer "is this board what I was told to build" and
never "is what we were told to build right". On the reversed-diode board the check that could reach
the second source **actually ran and still passed**: IV.2 compared D1's pinout against the KiCad symbol
for 1N4148W-7-F, agreed, and reported "3 part(s) agree with an independent transcription". The diode is
fitted backwards and the board is emitted for fabrication.

## The A1 gate, measured two ways
**Our own verifier** (`verify_calibration.py`, mechanical — loads both boards, diffs them, runs the
verifier on both, prints what it saw):
```
cases 6 | seeded 6 | detected 3 | known gap 3 | false pass 0
critical 5 cases, 0 false passes, 2 known gaps
GATE: BLOCKED — a DECLARED known gap on a critical class.
```
Detected: `cut_track` (III.1), `deleted_via` (III.1), `bridged_nets` (III.2).
Declared gaps: `reversed_diode` (F-0008), `swapped_pins` (F-0008 / F-S0-0001), `wrong_cap_value`
(no check reads a passive's value).

**The black-box overlooker** (`score_overlooker.py` against `KEY.json`): 1 of 6 run, 1 detected.
**Not yet a number.** Three are running.

## Next three actions
1. Finish the overlooker run — boards 02 and 05, then build and run `mains_gap` — and score the set
   with `score_overlooker.py` for the A1 recall and false-pass number.
2. Close F-0008: a check that compares each part's pin-to-net map against the DESIGN INTENT, not
   against the netlist the board was compiled from. This is what turns three known gaps into either
   detections or honest remaining gaps.
3. Report A1 status and the A1 thresholds to the owner for confirmation (D2 below).

## Blockers
- The A1 gate needs **0 false passes on the critical classes and ≥90 % recall**. Two critical classes
  are declared gaps. A1 cannot exit on a gap; it can exit on a fix.
- `mains_gap` (the creepage case, F-0004) is unbuilt, so the critical class list is 5 of 5 only if
  the creepage case counts. It does not yet.

## Owner decisions needed
- **D1 — creepage (F-0004).** Decision 12 refuses below 2.5 mm and warns below 5.0 mm. 2.5 mm is
  *basic* insulation. Mains-to-SELV needs *reinforced* (~5 mm at 250 V). The plan's own note says the
  doubled figure is from memory and unconfirmed, and that only a qualified review settles safety.
  Amend decision 12, or accept 2.5 mm as a documented limitation?
- **D2 — A1 thresholds.** The handoff's proposed gates are proposals, to be confirmed by the owner:
  ≥90 % recall on the seeded set, 0 false passes on the critical classes. A1's exit criterion also
  requires a token and cost log per milestone (in `alpha/ledger.jsonl`) and the Quilter pilot teardown
  (written).
- **D3 — the LED's V_F minimum** and the other D7 figure confirmations are still open; they bear on
  parameter 3 (pinout and footprint) grading.

## Limits of this program
No tool proves a board works. Every result carries a rung: exact, sound, bounded, simulated, rule check,
evidence, unknown. "All physical errors detected" is not a reachable claim. The goal is that every physical
error class has a named check or a named physical test, and the gap list is explicit.

## Where the next session starts
1. `python .claude/shared-memory/alpha/verify_calibration.py` — the mechanical harness, ~2 s.
2. `python .claude/shared-memory/alpha/score_overlooker.py --findings <merged findings>` — the A1 number.
3. `alpha/ledger.jsonl` — every milestone, with tokens and USD.
4. `alpha/findings.jsonl` — the open findings, assigned.
5. `alpha/overlooker_run.md` — the runbook for one board, one turn, one request.
6. `reports/competitors/quilter.md` — the A1 pilot teardown.
