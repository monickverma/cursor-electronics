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

---

## Upcoming

**Next** — Criterion 11 via `tests/test_simulation_accuracy.py`: closed-form comparison across 5+ R/C pairs spanning 100Hz–100kHz, 2% tolerance.

**Then** — Criterion 12: external engineer cold-reads a DHT22 explanation. Do this after the explainer tests exist.

**Then** — Scope decision on the PCB engine (in-scope tested / experimental behind a flag / deferred to Phase 3), then `PHASE1_COMPLETE.md` and tag v0.1.0.
