# Master Plan — Circuit OS Strategic Roadmap

> This is the steering document. Phases 0 → 10. Rarely changes.
> For session-level tasks, see `plan/current_phase.md`.

---

## Phase Overview

| Phase | Name | Status |
|-------|------|--------|
| 0 | Architecture + Scaffold | ✅ DONE |
| 1 | Phase 1 Sign-off (5 Templates, 12 Criteria) | 🔄 10/12 DONE |
| 2 | Phase 1 → 2 Bridge: Physical + External Validation | ⏳ Day 2–3 |
| 3 | Free-form Circuit Generation (beyond 5 templates) | ⬜ NOT STARTED |
| 4 | Live BOM Pricing (Digikey / LCSC API) | ⬜ NOT STARTED |
| 5 | Component Datasheet RAG (Qdrant) | ⬜ NOT STARTED |
| 6 | Simulation Waveform Graphs | ⬜ NOT STARTED |
| 7 | ESP32 / STM32 Firmware Support | ⬜ NOT STARTED |
| 8 | PCB Auto-layout + Gerber Export | ⬜ NOT STARTED |
| 9 | Multi-user + Design Sharing | ⬜ NOT STARTED |
| 10 | Production Deployment | ⬜ NOT STARTED |

---

## Phase 0 — Architecture + Scaffold ✅ DONE

**Goal:** Skeleton, tools, database schema, CI, all decisions locked.

**Done when:** `pytest tests/ -v` runs with 0 failures (even if all skipped).
`docker-compose up -d db redis` starts cleanly.

**Outcome:** Full backend + frontend written. 171 tests pass. Everything runs.

---

## Phase 1 — 5 Templates, 12 Criteria 🔄 IN PROGRESS (10/12)

**Goal:** Prove the system works reliably on 5 circuit types end-to-end.

**Done when:** All 12 launch criteria checked (see brain/vision.md).

**Current state (2026-06-02):**
- ✅ 10 of 12 criteria verified in software
- ⏳ Criteria 11: RC filter bench measurement (oscilloscope needed)
- ⏳ Criteria 12: External engineer review (human needed)

---

## Phase 2 — Physical + External Validation ⏳

**Goal:** Prove the hardware output is real.

**Tasks:**
1. Build RC filter (R=1590Ω, C=100nF) on breadboard
2. Drive with function generator, measure -3dB point with oscilloscope
3. Compare to ngspice result — must be within 15%
4. Flash DHT22 firmware to real Arduino Uno, verify sensor reads
5. Print explanation report for one external engineer
6. Tag v0.1.0 and commit `PHASE1_COMPLETE.md`

**Deliverables:**
- `sims/rc_filter_bench_vs_ngspice.md` with actual measurements
- Photo of Arduino with DHT22 working
- Engineer's verbal/written feedback on explanation quality

---

## Phase 3 — Free-form Circuit Generation

**Goal:** Accept any circuit description, not just the 5 Phase 1 templates.

**Key change:** `circuit_reasoner.py` currently uses `format_for_prompt(["DHT22"])` —
looks up only known components. Phase 3 extends this with Qdrant RAG for arbitrary
component datasheets.

**Not starting until:** Phase 2 complete. Running on an unverified Phase 1 = building Phase 2 on sand.

---

## Phase 4 — Live BOM Pricing

**Goal:** Replace static pricing dict with real-time Digikey / LCSC prices.

**Current state:** `generators/bom/compiler.py` uses `component_constraints.py` (static dict).
**Phase 4 adds:** Digikey API calls with caching, LCSC fallback.
**Do not add early** — creates authenticated, rate-limited, cacheable dependency.

---

## Phase 5 — Component Datasheet RAG

**Goal:** Inject datasheet excerpts for arbitrary components via Qdrant vector search.

**Current state:** `component_constraints.py` covers ~20 components.
**Phase 5 adds:** Qdrant with full datasheet excerpts, semantic lookup by component name.

---

## Phase 6 — Simulation Waveform Graphs

**Goal:** Replace text pass/fail with visual waveform output.

**Current state:** `SimulationResults.tsx` shows `{passed, failures, notes}` text.
**Phase 6 adds:** ngspice raw output parsed into Plotly/Chart.js compatible format.

---

## Phase 7 — ESP32 / STM32 Firmware Support

**Goal:** Extend firmware generation beyond Arduino Uno.

**Current state:** `ArduinoFirmwareGenerator` is Uno-specific (SoftwareSerial, 40mA GPIO, etc.)
**Phase 7 adds:** New template set + constraint lookup for ESP32 (3.3V GPIO, WiFi).

---

## Phase 8 — PCB Auto-layout + Gerber Export

**Goal:** KiCad net labels → KiCad PCB file with basic auto-placement.

**Current state:** `kicad.py` outputs net-label-only `.kicad_sch`.
**Phase 8 adds:** Pin coordinate lookup from KiCad symbol library + wire routing.

---

## Phase 9 — Multi-user + Design Sharing

**Goal:** Teams can share designs, comment, fork.

**Current state:** Single-user JWT auth, all designs private.
**Phase 9 adds:** Design sharing links, project teams, role-based access.

---

## Phase 10 — Production Deployment

**Goal:** Docker → cloud, monitored, scalable.

**Current state:** docker-compose for local dev.
**Phase 10 adds:** Kubernetes/ECS manifests, Sentry error tracking, Prometheus metrics.

---

## Guiding Principles

1. **Ground truth beats summaries.** If the test fails, the feature is not done.
2. **One phase at a time.** Phase N+1 must not start until Phase N success test passes.
3. **Append decisions.** Every tech choice goes to `brain/decisions.md`. Future sessions need the why.
4. **Workers read `current_phase.md`** before writing a single line of code.
5. **Never expand Phase 1 scope.** Every "just one more thing" before sign-off is debt.
