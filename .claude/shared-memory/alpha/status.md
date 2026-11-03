# Alpha program — status

_Updated 2026-10-21. Master session._

| Field | Value |
|---|---|
| Stage | **A1 — Alpha 1, evaluator and calibration** |
| Branch | `alpha-program` (from `verifier-contact-fixes` @ `3d8da26`) |
| Blockers | none critical |

## Done
- Bootstrap read (vision, architecture, current_phase, progress, git log).
- Branch `alpha-program` created. Never commit to master.
- Runtime up: Docker Desktop, Postgres 16, Redis 7, uvicorn :8000, Celery worker (solo pool).
- **Product verified end-to-end** — `POST /auth/register` 201, `POST /design/generate` 201 for RC, LED
  and composition; composition returned 6 components, 5 nodes, 15 connections, a 6-row BOM, a schematic
  and a `pcb_netlist`. A PCB compile of the 8-part DHT22 board: 2.2 s, 12/12 routed, 0 DRC errors,
  `verified: true`, `proven: false`.
- Refusal path verified: an under-specified prompt returns 422 `underdetermined` naming the missing
  fields. Hard abstention works.
- `alpha/findings.jsonl` seeded with 5 open findings (F-0001..F-0005).
- `alpha/overlooker.md` written — the black-box prompt and the 14-parameter rubric.
- `alpha/ledger.jsonl` started.

## In progress
| Agent | Task | Owns |
|---|---|---|
| builder | F-0002 RS-485 A/B short | `pcb_engine/{router,kernel,compile_board,board_ir}.py`, `tests/test_pcb_rs485_short.py` |
| builder | F-0003 router metamorphic tests | `tests/test_pcb_router_metamorphic.py` |
| builder | F-0001 rate limit configurable | `core/config.py`, 4 route files, `.env.example`, `tests/test_rate_limit_config.py` |
| competitor | Quilter teardown | `reports/competitors/quilter.md` |
| workflow | A1 calibration set (8 defect classes, seed + adversarial verify) | `tests/fixtures/alpha_known_bad/` |

## Open findings: 5
F-0001 rate limit (major) · F-0002 RS-485 short (critical) · F-0003 router metamorphic tests (major) ·
F-0004 creepage rule vs reinforced insulation (critical) · F-0005 land patterns unverified (major)

## Next three actions
1. Finish the calibration set; run the overlooker on it; record recall per parameter.
2. Report A1 status and the A1 thresholds to the owner for confirmation.
3. Physics step 0 (rung vocabulary) — the change the physics report says answers most of the objection.

## Owner decisions needed
- **D1 — creepage (F-0004).** Decision 12 refuses below 2.5 mm and warns below 5.0 mm. 2.5 mm is
  *basic* insulation. Mains-to-SELV needs *reinforced* (~5 mm at 250 V). The plan's own note says the
  doubled figure is from memory and unconfirmed, and that only a qualified review settles safety.
  Amend decision 12, or accept 2.5 mm as a documented limitation?
- **D2 — A1 thresholds.** The handoff's proposed gates are proposals, to be confirmed by the owner:
  ≥90% recall on the seeded set, 0 false passes on the critical classes.
- **D3 — the LED's V_F minimum** and the other D7 figure confirmations are still open; they bear on
  parameter 3 (pinout and footprint) grading.

## Limits of this program
No tool proves a board works. Every result carries a rung: exact, sound, bounded, simulated, rule check,
evidence, unknown. "All physical errors detected" is not a reachable claim. The goal is that every physical
error class has a named check or a named physical test, and the gap list is explicit.
