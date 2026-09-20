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

**2026-09-20** — `PRODUCT_MASTER.md` Part 10 amended: closed-form `predict()` becomes the per-request source of numerical truth from Phase 2 onwards, and ngspice becomes the CI regression check that guards it across a generator's declared envelope grid. The Celery rule is narrowed to ngspice specifically, so a synchronous `predict()` is legal. Amendment X1/X3 of `PHASE_2_PLAN_v2.md`; rationale in `decisions.md`. No code has changed — `predict()` does not exist yet.

**2026-09-20** — Phase 2 Stage 0 opened. Task 0.1 done: `backend/observability/request_log.py` and `backend/middleware/instrumentation.py` give one log row per request, flushed in a `finally` so exceptions and 4xx leave rows too. `tests/test_request_log.py` — 35 tests. The logger writes in its own transaction, because `get_db()` rolls back on exception and the rows most worth having come from requests that failed; a write that cannot reach Postgres lands in a JSONL sidecar rather than raising.

**2026-09-20** — **`progress.yaml` had been silently stale for four weeks.** `progress_gen.py` died on Windows cp1252 with `UnicodeEncodeError` before writing anything — the same bug commit `0a85755` fixed in `regen_state.py` on 2026-08-24 and did not apply here. `regen_state.py` discarded its exit code and filtered its output for keywords that a traceback does not contain, so the step printed nothing and read as success. Last good generation was 2026-08-23; every run since reported that day's state. Both fixed: the UTF-8 guard is now in both tools, and a non-zero exit prints `progress.yaml is STALE` with the tail of the traceback. Entry count 60 → 71 on the first working run.

**2026-09-20** — Stage 0 Task 0.2 done: `backend/generators/protocol.py` fixes the `Generator` contract before any generator exists to calcify it. `tests/test_generator_protocol.py` — 34 tests. Two invariants are enforced by validators rather than convention, both because they are stated G1 gates: a refusal cannot be built without a named reason, and an acceptance cannot be built without a `PortContract`. `Interval` makes `predict()` return bands rather than points, which is amendment X1 expressed as a type, and `ClaimScope.model` is required so the MCU-as-100Ω assumption (X6, D2) has a home from the first generator. `IntentLike` resolves v2's own ordering wrinkle — the protocol is scheduled in Stage 0 but IntentIR in Stage 1 — without pre-empting Task 1.1.

**2026-09-20** — Stage 0 Task 0.3 done: `backend/generators/rc_lowpass.py`, the first generator on the Task 0.2 contract. `tests/test_rc_lowpass_generator.py` — 55 tests. **Stage 0 gate met: `predict()` versus ngspice at all seven grid points from 100 Hz to 100 kHz, worst deviation 0.0000%** — ngspice's print precision, not disagreement. The gate pins the parameter box to the netlist's exact values so it compares point against point; checking the simulated point against the ±10% tolerance band would have passed on almost any prediction. Negative control included: a 20% capacitor shift must push the measurement outside the 2% gate, and does. `method="monotone_corners"` because f_c is monotone in R and C, so two corners give the exact worst case — G1 territory rather than G6.

**2026-09-20** — Adversarial audit of Stage 0 Tasks 0.1–0.3, going past the tests to things nothing covered. Verified for the first time: `main.py` wiring (`RequestLogMiddleware` is outermost, confirmed against the live middleware stack), that rate-limit 429s are logged (they are — proved with a real slowapi limiter rather than reasoned about), the SQLAlchemy model against `schema.sql` (16/16 columns, generated DDL identical), and a **real Postgres round trip** including JSONB, timezone retention, and a duplicate-primary-key error falling back to the sidecar instead of raising. Five defects found and fixed: `predict()` silently ignored a partial parameter box; `Interval` accepted infinities; `conformance_gaps` disagreed with `isinstance` on non-callable members; `.gitignore` had no rule for the log sidecars; and the test suite was writing `request_log_fallback.jsonl` into `backend/observability/` on every run. One suspected defect was **disproved** — a missing log row on a DB-using route looked like connection-pool contention but was an artifact of the audit harness running two event loops in one process; real uvicorn against real Postgres logged every request. Also found: `schema.sql` is mounted as a Postgres init script, so it never runs on an existing volume and `request_log` has to be applied by hand — noted in the file, since this repo has no migration tool.

**2026-09-20** — Stage 0 Task 0.4 done: `backend/validation/envelope_grid.py` and `tests/test_envelope_grid.py` (24 tests). This is **M1** and the refutation of defeater **D-G**. Both Stage 0 gates met — control arm 7/7 within 2% at worst 0.0000%, and seeded faults detected at every strength (P5 4.84%, P20 16.73%, X10 90.00%). **The number that decided the design: under the 5% fault every failing point reports `in-band True`** — the fault sits inside a tolerance band that is ±10% wide because the capacitor is a 10% part, so a harness gated on band containment would have passed the whole thing. The gate is therefore deviation from `Interval.nominal`, the claim at the generator's intended values. A blindness bug was caught in design rather than in code: an earlier draft pinned `predict()` to component values read back out of the generated design, which under a mutation arm reads the *mutated* values — claim and design would have agreed again and the harness would have been blind to the only fault it exists to catch. Unevaluable points (refusal, crash, non-finite measurement, no shared quantity) fail rather than skip, and `MatrixReport.passed` requires the control arm to pass as well as every fault to be caught, since either half alone is satisfiable by a broken harness.

**2026-09-20** — Stage 0 Task 0.5 done, and **Stage 0 is complete**. The explanation-derivability experiment returns a **qualified yes**: the structural explanation derives with zero API calls and clears the bar `tests/test_explainer.py` enforces on the model (6/6 designs, 6/6 component coverage), while the domain-knowledge layer — ADC source-impedance limits, dielectric choice, "use a ±2% C0G not a tighter resistor" — does not. Full answer with evidence in `decisions.md` [2026-09-20]. New: `backend/ai/derived_explainer.py`, `scripts/explanation_derivability.py`, `tests/test_derived_explainer.py`. Two caveats carried forward: only the generator-produced row is a real test, since the five example IRs carry Phase 1 LLM-written justifications; and marker counting measures form, not quality, so criterion 12 remains the only test of whether either version lands.

**2026-09-20** — Running that experiment found `ai/explainer.py` **crashing on every live call**: `response.content[0].text` assumed block zero is text, but the configured `AI_MODEL` reasons first, so block zero is a `ThinkingBlock`. Nobody had noticed because live tests skip without a key. Fixed with `_first_text()` and pinned by `TestReasoningModelResponses`. The three tool_use modules share the `content[0]` shape but were **verified against the live API and deliberately left alone** — forced `tool_choice` suppresses thinking blocks, so `content[0].input` is correct there. Also found and not changed: `max_tokens=2048` is too small for a reasoning model, which sometimes spends the whole budget thinking and returns no text block; raising it is a product decision with a cost attached. And an environment trap worth knowing — `ANTHROPIC_BASE_URL` exported in the shell takes precedence over `.env` under pydantic-settings, silently sending an OpenRouter key to Anthropic and producing a misleading "API key is invalid".

**2026-09-20** — Second adversarial audit, across Stage 0 Tasks 0.1–0.5. Every fix from the first audit re-verified and holding; `generate()` confirmed deterministic across separate interpreters under `PYTHONHASHSEED=random`; multi-axis grids confirmed correct. Six defects found and fixed. **The most serious was in `regen_state.py` itself: `run_tests()` used a 180 s timeout, the suite grew past it, pytest was killed, the summary regexes matched nothing, and zeros were written to `state.json` — 0 tests and every module untested, on a fully green suite.** Nothing checked the return code. Same class as the `progress_gen.py` breakage found earlier the same day, in the same file, one function along: a tool that cannot report its own failure. Timeout raised to 900 s and the writer now aborts rather than recording a run it did not measure, leaving the previous state intact. In the harness: `_format_value` emitted scientific notation for resistors at 1 MΩ and above, which `_parse_ohms` cannot read, so a large mutation would have injected an unparseable value and "detected" a broken netlist rather than the seeded fault — now `.10g` with a round-trip check that raises; and `MatrixReport.passed` was true for a matrix with no seeded faults at all, the third way to build a broken detector after "always passes" and "always fails". In the explainer: the consequential-marker list existed as two identical copies, one in `ai/derived_explainer.py` and one in `tests/test_explainer.py`, now owned solely by `ai/explainer.py`; and `_what_breaks` emitted a bare heading with nothing under it when an IR had no rail and no ratings, which reads as "nothing breaks".

**2026-09-21** — Stage 1 opened. Task 1.1 done: `backend/core/intent_ir.py` and `tests/test_intent_ir.py` (27 tests). `requirements` is validated through a typed `Requirements` model but stored as a mapping, so generators read it through the `IntentLike` protocol frozen in Task 0.2 without that protocol being reopened — `test_a_real_generator_accepts_it_end_to_end` drives `RCLowPassGenerator` through envelope → generate → predict on a real IntentIR, which is the evidence that the Stage 0 ordering call was right. Three invariants: the record is frozen after construction, an incomplete specification cannot be signed at the schema level, and a signature does not survive an edit to what it signed. The last is the cheap version of Stage 4's freeze and the mitigation for defeater D-B.

**2026-09-21** — Third instance of the same tooling root cause, and the first one that announced itself. `regen_state.py` invoked `progress_gen.py` with the default 120 s timeout while `progress_gen` runs the whole suite itself, which passed two minutes — so `progress.yaml` silently stopped updating again. The exit-code check added on 2026-09-20 caught it and printed "progress.yaml is STALE" with the TIMEOUT, instead of the step reading as success the way it did for four weeks in August. Timeout raised to 900 s. The lesson stands: the fix that matters was making the tool able to report its own failure, not any individual timeout value.

**2026-09-21** — **Stage 1 complete** (Tasks 1.1–1.7), and audited. `core/intent_ir.py`, `generators/registry.py`, `ai/form_producer.py`, `ai/intent_producer.py`, plus `tests/test_llm_cannot_write_circuit_ir.py`, `tests/test_abstention_corpus.py` and the log-row ratchet. Two decisions recorded in `decisions.md`: X5 accepted with a guard the plan does not specify — a semantic retry may **add** a value it failed to record but may never **change or drop** one, because a model told "no generator accepted this" will otherwise rewrite 2 MHz into 1 kHz and hand back a design the user never asked for — and the removal of `ai/circuit_reasoner.py`, which narrows generation to the catalogue until Stage 3 authors the remaining four generators. Abstention measured on a named 200-case corpus: false acceptance 0/200, false abstention 0/200.

**2026-09-21** — The Task 1.5 gate nearly shipped hollow. The first AST scanner looked only for `CircuitIR(...)` and **passed while the violating module was still in the tree**, because that module used `CircuitIR.model_validate(last_raw)`. Fixed to cover every Pydantic construction form, with a parametrised negative control per form. Widening it from `backend/` to `scripts/` then found a second real consequence: `scripts/amd_benchmark.py` still imported the deleted module and was broken. Rewritten onto the Stage 1 path, where it now separates transcription failures from catalogue refusals — scoring the two the same would make an open model look worse the narrower the catalogue got. Audit of all twelve tasks also found and fixed: `Refusal` was unhashable (`__eq__` without `__hash__`), a generator grid axis sharing a name with a universal form field produced the field twice so `build()` silently kept the wrong one, and `requirements` accepted non-JSON values that validated fine and then failed inside `requirements_hash()` and the request log.

---

## Upcoming

**Next** — Diagnose the flaky accuracy test. Suspected transient ngspice subprocess failure (~20 launches per run, 30s timeout, output read immediately after return). An infrastructure hiccup may be retried; an accuracy disagreement never may.

**Then** — PCB endpoint behind a config flag and the frontend tab labelled experimental, completing decision (b).

**Then** — `regen_state.py`, confirm `PHASE1_COMPLETE.md` matches, tag v0.1.0.

**Phase 2 entry** — Criterion 12: external engineer cold-reads a DHT22 explanation. `CRITERION_12_REVIEW.md` has the protocol.
