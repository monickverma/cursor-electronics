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

---

## Upcoming

**Day 2 (next)** — Physical validation: build RC filter on breadboard, measure -3dB with oscilloscope, compare to ngspice. Flash DHT22 firmware to real Arduino Uno.

**Day 3 (after)** — Sign-off: external engineer reads explanation report cold. All 12 criteria formally checked. Tag commit as v0.1.0. Begin Phase 2 planning.
