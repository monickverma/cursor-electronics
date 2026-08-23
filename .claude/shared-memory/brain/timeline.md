# Timeline — LAYER 6

> Append-only. One entry per significant event.
> Format: **YYYY-MM-DD** — [What changed] — [Why it matters]
> A new agent reading this knows the full history without conversation context.

---

## History

**2026-06-01** — Project started. Architecture designed: NL prompt → CircuitIR JSON → deterministic compilers (SPICE, firmware, KiCad, BOM). Core invariant established: LLM never writes output formats directly.

**2026-06-01** — Full backend scaffolded: FastAPI + Celery + PostgreSQL + Redis. All 7 modules built (ir_schema, ir_validator, ai layer ×4, generators ×4, simulation ×4, validation, db, api routes). Docker Compose for local dev.

**2026-06-01** — Frontend built: Next.js 14, two-panel layout (chat + tabbed output). All 6 components (ChatPanel, SchematicViewer, FirmwareViewer, SimulationResults, BOMTable, ValidationReport). kicanvas with ssr:false for schematic rendering.

**2026-06-01** — Test suite written: 7 test files, 171 tests, 24 skipped (live API + ngspice + arduino-cli not installed at time of writing).

**2026-06-02** — Auth verified end-to-end: register → login (OAuth2 form) → /auth/me returns user. JWT with bcrypt password hashing.

**2026-06-02** — Bug: `POST /design/generate` returned 422. Root cause: `from __future__ import annotations` in route files caused FastAPI to mis-classify `GenerateRequest` as a query parameter when slowapi decorator wraps the function. Fix: removed the import from design.py, patch.py, simulate.py.

**2026-06-02** — Bug: API error display showed `[object Object]`. Root cause: FastAPI 422 responses return `detail` as an array. `new Error(array)` stringified wrong. Fix: detect array + format as "field: message" in `frontend/lib/api.ts`.

**2026-06-02** — Bug: `anthropic==0.34.2` crashed on startup due to httpx 0.28.0 removing `proxies` parameter. Fix: upgraded to `anthropic==0.105.2`.

**2026-06-02** — OpenRouter support added: `backend/ai/client.py` as shared client factory. `ANTHROPIC_BASE_URL` and `AI_MODEL` env vars added to config.

**2026-06-02** — Bug: OpenRouter returned 404 for all AI calls. Root cause: Anthropic SDK appends `/v1/messages` to base_url. Setting `.../api/v1` produces `.../api/v1/v1/messages`. Fix: `ANTHROPIC_BASE_URL=https://openrouter.ai/api` (no /v1 suffix).

**2026-06-02** — End-to-end generation verified: DHT22 + LED circuit generated in ~15s with 4-component IR, valid firmware, schematic, BOM, explanation. First real AI call succeeded.

**2026-06-02** — Day 1 verification pass completed:
  - ngspice installed via MSYS2 pacman
  - arduino-cli downloaded + arduino:avr core + DHT + ModbusMaster libraries
  - Celery worker started (`--pool=solo` for Windows Python 3.13)

**2026-06-02** — Bug: ngspice output was empty string from subprocess. Root cause: ngspice_con.exe writes to Windows console handle, not stdout pipe. Fix: use `-o outfile` flag in `simulation/runner.py`.

**2026-06-02** — Bug: DC parser returned empty dict. Root cause: parser regex matched `v(nodename) value` but ngspice outputs bare `nodename  value` in the Node/Voltage table. Fix: added `_DC_COLUMNAR_PATTERN` + state machine in `simulation/parser.py`.

**2026-06-02** — Bug: AC parser returned empty list. Root cause: (1) ngspice emits one table per variable even with combined .print, (2) complex number format has trailing comma (`2.5e+00,`) that breaks float(), (3) magnitude was real part only, not sqrt(real^2+imag^2). Fix: full rewrite of `_parse_ac_table()`.

**2026-06-02** — All 42 simulation tests pass. Voltage divider DC test: vout_5v=5.058V ✓. RC filter AC test: magnitude at 1kHz=3.536V (-3dB) ✓. Wrong-capacitor test: 1nF → simulation FAIL ✓.

**2026-06-02** — Bug: Modbus firmware failed arduino-cli compilation with `'Serial1' was not declared`. Root cause: Arduino Uno has no Serial1 hardware UART. Fix: template rewrote to use SoftwareSerial on pins 10/11.

**2026-06-02** — Test suite now: 177 passed, 18 skipped (up from 171 passed, 24 skipped). 6 tests now run that were previously skipped (ngspice + arduino-cli now available).

**2026-06-02** — Phase 1 Day 1 criteria verified: 10 of 12 done. Remaining: RC filter bench test (physical oscilloscope) + external engineer review.

**2026-06-03** — shared-memory system fully operational: regen_state.py + progress_gen.py rewritten for real backend, /update-memory slash command created, all brain files aligned with PRODUCT_MASTER.md 5-phase roadmap. First successful /update-memory run: 177 tests passing, 27/32 entries verified_done, 10/12 Phase 1 criteria confirmed.

**2026-06-03** — /update-memory confirmed working from Claude Code slash command UI. Loop verified end-to-end: code → test → /update-memory → commit → any agent cold-starts from shared-memory with zero re-explanation.

**2026-07 (undated)** — PCB layout engine built and moved into the API process (`backend/pcb_engine/`, ~2,400 lines: A* router, DRC kernel, footprint inference, SVG render). PCB tab added to frontend. Deployed to Railway. Landing page + demo video added. None of this was recorded in memory at the time.

**2026-08-07** — Re-sync audit. Memory was 5 commits and ~2 months stale: claimed 177 tests, reality 257 passing / 0 failing / 24 skipped. Root cause found: `regen_state.py` and `progress_gen.py` track a hardcoded module list, so the PCB engine was invisible rather than untested.

**2026-08-07** — Registered `pcb_engine/*`, `generators/pcb_netlist`, `api/routes/pcb`, and `generators/kicad` (whose test file existed but was never mapped) in both trackers. Tracked entries 32 → 60. Verified 84.4% → 48.3% — the drop is better accounting, not a regression.

**2026-08-07** — Criterion 11 (RC filter bench test) changed from oscilloscope measurement at 15% tolerance to analytical cross-check at 2%. No lab access exists. Marked `met_by_substitute`, not `met`. See `brain/decisions.md`.

**2026-08-07** — Added `tests/test_patcher.py` (19 tests) and `tests/test_explainer.py` (42 tests, 3 live). Suite 257 → 318 passing, 0 failing. Verified 48.3% → 56.7%.

**2026-08-07** — Patcher invariant ("patch() never returns a full IR", `.claude/rules/code-style.md`) now has mechanical coverage; it was previously a rule with no test behind it. Criterion 7 (5 sequential patches) automated — it had only ever passed by hand on 2026-06-02 and could not be re-run.

**2026-08-07** — Found that `ai/patcher` and `ai/explainer` were reported `untested` partly through mis-registration: 8 unit + 6 live tests already existed in `test_ai_layer.py`, but the trackers mapped both modules to `test_file: None`. Real gap was narrower than reported — no deterministic coverage of `patch()`/`explain()` when ANTHROPIC_API_KEY is absent, which is the default.

**2026-08-22** — Added `tests/test_simulation_accuracy.py` (34 tests): netlist generator compared against closed-form equations across six R/C pairs, 100Hz–100kHz, 2% tolerance. Worst deviation 0.0003%. Closes criterion 11 as `met_by_substitute`.

**2026-08-22** — Found criterion 11 could never pass: index 10 was absent from `CRITERIA_TEST_MAP`, from `auto_pass`, and from the manual tuple in `regen_state.py`, so it fell through to a hardcoded `⏳`. The 2026-08-07 amendment reached three prose files and not the one that writes `state.json`. `auto_pass` is now derived from `CRITERIA_TEST_MAP`; substitute criteria render `✅*` via `SUBSTITUTE_CRITERIA`.

**2026-08-22** — `read_blockers()` was reporting resolved blockers as live; struck-through rows are now skipped. `MODULES['test']` and `PLANNED['test_file']` accept lists, aggregated worst-case, so a module covered by two test files credits both.

**2026-08-22** — Wrote `tests/test_pcb_placement.py` (52 tests) as a placement characterization harness. Its first run found `footprints.py` had no SMD packages at all: every 0402 passive failed the footprint lookup and was dropped by `from_netlist()`. IR_003 and IR_004 compiled to empty boards, and the frontend PCB tab had been rendering them for ~2 months.

**2026-08-22** — Added SMD footprints (0402–1210, SOT-23, SOIC-8/14/16) at IPC-7351B nominal. All five templates now place 100% of components. SMD pads are `rect`, not `th` — `th` means all-layer reachable to the router and skips the DRC layer check. SOIC-8 pin assignment remains arbitrary and warns; per-part pinmaps are the fix.

**2026-08-22** — PCB scope decided: **(b) in scope, experimental, excluded from the v0.1.0 gate**. Endpoint flag and UI label are still outstanding — under (b) the label is the decision.

**2026-08-22** — Criterion 12 moved off the v0.1.0 gate to a Phase 2 entry condition. It was the only criterion depending on a third party's calendar and had been open since 2026-06-02. `PHASE1_COMPLETE.md` written, signing off at 11/12 with the unmet criterion stated on its first page.

**2026-08-22** — `PRODUCT_MASTER.md` at repo root confirmed canonical; the pre-build v1.0 archived to `docs/PRODUCT_MASTER_v1.md`. The two disagreed on Phase 3 (KiCad Workflow Layer vs Industrial Layer) and Pro pricing ($29 vs $49). Phase 2 is the Validation Engine.

**2026-08-22** — `PCB_STRATEGY.md` and `PRODUCT_MASTER.md` were found to agree on routing, not conflict: both say consume freerouting rather than build a router. The custom A* engine was a deviation from both. The constraint layer belongs in Phase 3, where PCB work already lives.

**2026-08-22** — Added a one-owner-per-fact table to `AGENTS.md` after finding the Phase 1 criteria list restated in seven files and `MENTAL_MODEL.md` carrying 318 tests / 10 of 12 two weeks after both changed. Derived numbers removed from prose in favour of pointers to `state.json`.

**2026-08-23** — **Open:** one test in `test_simulation_accuracy.py` is flaky. Regen at `2edfbc8` reported 410 passing / 0 failing; regen at `f5fbd3d` reported 409 / 1 failing with no code change between them. Criterion 11 shows `❌` and `generators/spice`, `simulation/runner`, `simulation/parser` show `broken`. Do not tag v0.1.0 until it is reproducible.

---

## Upcoming

**Next** — Diagnose the flaky accuracy test. Suspected transient ngspice subprocess failure (~20 launches per run, 30s timeout, output read immediately after return). An infrastructure hiccup may be retried; an accuracy disagreement never may.

**Then** — PCB endpoint behind a config flag and the frontend tab labelled experimental, completing decision (b).

**Then** — `regen_state.py`, confirm `PHASE1_COMPLETE.md` matches, tag v0.1.0.

**Phase 2 entry** — Criterion 12: external engineer cold-reads a DHT22 explanation. `CRITERION_12_REVIEW.md` has the protocol.
