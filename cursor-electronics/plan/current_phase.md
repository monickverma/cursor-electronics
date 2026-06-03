# Current Phase: Phase 1 — Hardware Copilot

> Last updated: 2026-06-03

---

## Phase Goal

All 5 circuit templates end-to-end working: prompt → IR → simulation → schematic →
firmware → BOM → explanation. Zero crashes in 20 consecutive runs.

## Phase Success Test (definition of DONE)

All items on the Phase 1 launch checklist in `.claude/rules/testing.md` checked.
Key items:
- 20 different prompts tested end-to-end, zero crashes
- TPL_001 and TPL_002 firmware compiled and flashed to physical Arduino
- ngspice within 15% of bench measurement on RC filter
- JWT auth working, all design routes return 401 without token
- Rate limiting: 11th generation in one hour returns 429

---

## Next Tasks

### Task 1 — Simulation accuracy gate
**What:** Build the RC filter from TPL_004 on a breadboard. Measure -3dB cutoff with
oscilloscope. Compare to ngspice result. Gate: within 15%.
**File:** `backend/simulation/grader.py`
**Success:** Physical bench measurement vs ngspice within 15%. Record in `brain/decisions.md`.

### Task 2 — End-to-end integration test
**What:** 20 prompts covering all 5 templates. One test per template + edge cases.
**File:** `tests/test_integration.py`
**Success:** `pytest tests/test_integration.py -v` — all pass, zero crashes.

### Task 3 — Load test
**What:** 100 consecutive design requests. Target: zero HTTP 500s.
**Success:** `pytest tests/test_load.py` passes. Any 500 → investigate root cause first.

---

## Current Blockers

| Blocker | Since | Resolution Path |
|---------|-------|-----------------|
| Simulation accuracy gate not yet run (needs physical hardware) | 2026-06-03 | Task 1 above |

---

## Notes

- Always run `pytest tests/ -v` before considering a task done
- Always run `python tools/regen_state.py` at end of session
- Test status as of last run: **177 passing, 0 failing**
- All Phase 1 backend modules exist — focus is launch gate validation
