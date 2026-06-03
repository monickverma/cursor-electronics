# Current Phase: Phase 1 — Hardware Copilot

> Last updated: 2026-06-03

---

## Phase Goal

All 5 circuit templates working end-to-end. Zero crashes in 20 consecutive runs.
Full Phase 1 launch checklist in `.claude/rules/testing.md` checked.

## Phase Success Test

```
Input:   "Arduino + DHT22, alert LED when temp exceeds 40C"
Output:  CircuitIR → SPICE sim passes → .ino generated → .kicad_sch → BOM
Status:  progress.yaml shows all tracked functions verified_done
         All Phase 1 launch checklist items checked
```

---

## Next Tasks

### Task 1 — Simulation accuracy gate (needs physical hardware)
Build RC filter from TPL_004 (R=1590Ω, C=100nF). Measure −3dB cutoff with
oscilloscope. Compare to ngspice result. Gate: within 15%.
**File:** `backend/simulation/grader.py`
**Success:** Bench measurement vs ngspice within 15%. Record in `brain/decisions.md`.

### Task 2 — End-to-end integration tests
20 prompts covering all 5 templates. One test per template + edge cases.
**File:** `tests/test_integration.py`
**Success:** All pass, zero crashes.

### Task 3 — Load test (100 requests, zero 500s)
**File:** `tests/test_load.py`
**Success:** Zero HTTP 500s.

---

## Current Blockers

| Blocker | Since | Resolution Path |
|---------|-------|-----------------|
| Simulation accuracy gate not yet run — needs physical hardware | 2026-06-03 | Task 1 |

---

## Notes

- Run `pytest tests/ -v` before marking any task done
- Run `python tools/regen_state.py` at end of each session
- Test status: **177 passing, 0 failing** (24 skipped = live API + ngspice + arduino-cli)
