# Circuit OS — Claude Code Instructions

Circuit OS is an **AI hardware compiler**: plain English → physics-validated schematic + firmware + simulation + BOM.

## The One Rule Everything Depends On

> The LLM never writes SPICE, KiCad format, or firmware directly.
> It writes JSON against the IR schema. Deterministic compilers translate that JSON into all downstream formats.

If LLM output touches ngspice, KiCad, or `.ino` without passing through IR validation first — stop. That is wrong.

---

## Project Structure

```
cursor-electronics/
├── backend/
│   ├── main.py                     # FastAPI entry point, CORS, rate limiting
│   ├── worker.py                   # Celery app
│   ├── core/
│   │   ├── ir_schema.py            # THE canonical data model — never rename fields
│   │   ├── ir_validator.py         # Pre-simulation structural validation
│   │   ├── ir_examples.py          # 5 hardcoded IRs for tests
│   │   ├── intent_ir.py            # IntentIR — the requirement, materialized before the design
│   │   ├── intent_patch.py         # RFC 6902 patches over IntentIR.requirements (Stage 2)
│   │   ├── annotations.py          # Closed-list annotation layer; never a generation input
│   │   └── config.py               # pydantic-settings, fails fast on missing env vars
│   ├── data/
│   │   ├── component_constraints.py  # Python dict — zero LLM tokens
│   │   ├── mcu_targets.py            # Stage 5 — boards as data: Uno, ESP32-DevKitC, Black Pill
│   │   ├── parts.py                  # Stage 6 — passives as data: series, capacitors, one owner
│   │   ├── figures.py                # D7 — provenance per part figure; trusted only once verified
│   │   ├── figure_verifications.json # a person's checks, bound to each record's hash
│   │   ├── figure_evidence.json      # the agent's page-cited check of each record — evidence, not a verification
│   │   ├── bench/                    # D1 — bench records, judged by validation/bench.py
│   │   └── component_db.json         # 100-entry component database, prices dated
│   ├── ai/
│   │   ├── intent_parser.py        # Prompt → DesignSpec (tool_use)
│   │   ├── intent_producer.py      # Prompt → IntentIR (tool_use; X5 retry rules)
│   │   ├── form_producer.py        # Form → IntentIR — the reference producer, 0 API calls
│   │   ├── intent_patcher.py       # IntentIR + command → RFC 6902 ops, each citing the command
│   │   └── explainer.py            # IR → consequential plain English
│   ├── generators/
│   │   ├── protocol.py             # THE Generator contract — envelope/generate/predict
│   │   ├── registry.py             # Deterministic dispatch; collects every refusal
│   │   ├── realize.py              # IntentIR → stored CircuitIR; deterministic id, locality, predict delta
│   │   ├── rc_lowpass.py           # TPL_004 — first generator on the contract
│   │   ├── voltage_divider.py      # TPL_005 on the contract (Stage 3)
│   │   ├── led_indicator.py        # TPL_003 — Thevenin GPIO + fitted LED diode
│   │   ├── dht22_node.py           # TPL_001 — pull-up vs cable rise time
│   │   ├── rs485_node.py           # TPL_002 — fail-safe bias; wired as its firmware drives
│   │   ├── load_switch.py          # Composition M3 — NPN low-side switch; proves its own saturation
│   │   ├── compose.py              # Composition — blocks on one board; behaviour rules; board claims
│   │   ├── common.py               # E96, strict requirement reader, pins — one owner
│   │   ├── arduino_parts.py        # Shared MCU (per board) + bypass cap + rail model
│   │   ├── netlist/models.py       # Device models read by BOTH spice.py and predict()
│   │   ├── firmware/arduino.py     # IR → .ino (Jinja2), pins from the wiring, per board
│   │   ├── firmware/composite.py   # Composition M2 — one sketch for a board, from its behaviour rules
│   │   ├── firmware/project.py     # Stage 5 — PlatformIO project, pinned, keyed by SHA-256
│   │   ├── firmware/compile_gate.py # Stage 5 — build it; firmware shown only once it compiles
│   │   ├── netlist/spice.py        # IR → SPICE netlist
│   │   ├── schematic/kicad.py      # IR → .kicad_sch (net labels only)
│   │   ├── bom/compiler.py         # IR → BOM (static pricing; a part priced only as itself, dated)
│   │   └── bom/substitution.py     # Stage 6 — substitutes re-derived and re-proved through the gate
│   ├── simulation/
│   │   ├── runner.py               # ngspice async subprocess
│   │   ├── parser.py               # Columnar batch output parser
│   │   ├── grader.py               # Pass/fail grader (15% tolerance)
│   │   ├── waveforms.py            # AC / transient / DC shaped for the viewer
│   │   └── monitor.py              # Structured failure logger
│   ├── validation/
│   │   ├── rule_engine.py          # HardwareRuleEngine (RS-485, PWM, etc.)
│   │   ├── claims.py               # Claim objects + validation_coverage (X6, X8, Stage 4 proofs)
│   │   ├── defeaters.py            # The defeater register, D1–D9
│   │   ├── pin_rules.py            # Stage 5 — pin-mux, peripheral conflict, strapping pins
│   │   ├── figure_audit.py         # D7 — every figure a claim reads is declared, by experiment
│   │   ├── bench.py                # D1 — bench evidence: agrees, disagrees, stale
│   │   ├── build_check.py          # Did the person wire this design? faults, readings, plans, verdicts (2026-10-08)
│   │   ├── envelope_grid.py        # CI grid harness + M1 fault injection
│   │   └── grid_adapters.py        # Per-generator ngspice adapters and probes
│   ├── proof/                      # Stage 4 — properties proved from the design's netlist
│   │   ├── brackets.py             # π, ln, expm1 as exact rational enclosures (D8)
│   │   ├── netlist.py              # The SPICE text back into exact elements
│   │   ├── mna.py                  # sympy nodal analysis: DC, transfer, Thevenin
│   │   ├── dependence.py           # D2 — which MCU model elements a quantity depends on, exactly
│   │   ├── properties.py           # PropertySpec → Statement; English by template; hashes
│   │   └── prover.py               # z3 over tolerance boxes; frozen refine loop; mutation gate
│   ├── pricing/                    # Live Mouser quotes over the BOM, optional (MOUSER_API_KEY); cached in
│   │                               # PostgreSQL; exact part number only; never read by validation
│   ├── pcb_engine/                 # EXPERIMENTAL — A* router, DRC, footprints, SVG
│   │                               # placement tested; routing is not
│   │   ├── board_ir.py             # THE layout contract — the board's source of truth
│   │   └── scene3d.py              # Board IR → 3D scene (bodies per package, DRC, ratsnest)
│   ├── api/routes/                 # design.py, simulate.py, patch.py (+ sign-off), firmware.py, bom.py, auth.py
│   ├── db/                         # models.py, crud.py, schema.sql, migrations.py (startup DDL)
│   ├── tasks/                      # Celery: simulation_task.py, firmware_task.py (compile gate),
│   │                               # explain_task.py (the explanation, read back by GET /design/{id}/explanation)
│   └── middleware/rate_limit.py    # slowapi
├── frontend/
│   ├── app/page.tsx                # Two-panel layout
│   ├── components/                 # ChatPanel, SchematicViewer, FirmwareViewer, etc.
│   └── lib/api.ts                  # Typed API client
├── scripts/                        # capture_explanation.py, review_panel.py, verify_figures.py (D7),
│                                   # bench_template.py (D1), export_ui_fixtures.py,
│                                   # bench/rc_timer/ (D1: the Uno sketch that times an RC),
│                                   # real_data_check.py (generated vs real circuits, ngspice is the oracle),
│                                   # build_check_cli.py / _oracle.py / _accuracy.py (the build check at the bench,
│                                   # its arithmetic against ngspice, its accuracy), ngspice_batch.py
├── tests/                          # pytest, conftest.py, 12 test modules + fixtures/
└── docker-compose.yml
```

---

## Tech Stack

| Layer | Technology | Hard constraint |
|---|---|---|
| Backend | FastAPI + Python 3.11+ | `async def` for all routes |
| AI | Model from `AI_MODEL` in `.env` — do not hardcode | `tool_use` mode only — never raw text |
| Simulation | ngspice subprocess | BSD licensed — LTspice is NOT allowed (EULA) |
| Firmware | Jinja2 templates, compiled with PlatformIO in Celery | Never LLM-generated .ino directly; never shown before it compiles |
| Schematic | KiCad net labels | No wire routing in Phase 1 |
| Validation | Pydantic v2 strict | Fails at import if env vars missing |
| Queue | Celery + Redis | All ngspice runs — never inline HTTP. `predict()` is synchronous; see `rules/simulation.md` |
| Database | PostgreSQL + SQLAlchemy async | No in-memory storage ever |
| Frontend | Next.js 14 App Router | kicanvas with `ssr: false` |
| Rate limiting | slowapi | On all LLM + simulation endpoints |

---

## Phase 1 Scope (5 Templates Only)

| ID | Circuit | Firmware template |
|---|---|---|
| TPL_001 | Arduino + DHT22 temp/humidity alert | `sensor_read.ino.j2` |
| TPL_002 | Arduino + MAX485 RS-485 Modbus RTU master | `modbus_master.ino.j2` |
| TPL_003 | Arduino + LED with current-limiting resistor | `base.ino.j2` |
| TPL_004 | RC low-pass filter | No firmware |
| TPL_005 | Voltage divider | No firmware |

Free-form generation is Phase 2. Do not expand this list until all 5 are end-to-end tested.

## What Phase 1 Does NOT Have

Do not add these — they are Phase 2+ scope:

- Gerber export, DFM, fab APIs
- ~~PCB auto-layout~~ — **exists**: `backend/pcb_engine/` ships at `POST /pcb/compile`
  with a frontend tab. Pulled forward from Phase 3. Scope decision 2026-08-22 is
  **(b) experimental**, excluded from the v0.1.0 gate. When Phase 3 begins,
  integrate freerouting instead of extending the router. See `PHASE1_COMPLETE.md` §4.
  **Amended 2026-10-06 (owner):** the board is drawn in 3D from the Board IR
  (`pcb_engine/scene3d.py` → `frontend/components/Board3DView.tsx`, three.js via
  React Three Fiber, `ssr: false`), toward an editable 3D board. The Board IR stays
  the source of truth; edits will be patch operations re-checked by the DRC kernel.
  `brain/decisions.md` [2026-10-06].
- ~~Live distributor pricing~~ — **exists since 2026-09-25**: Mouser, optional (`MOUSER_API_KEY`),
  on `GET /design/{id}/bom` only; see `brain/decisions.md` [2026-09-25]. No Digikey/LCSC.
- Qdrant vector DB / RAG (use `component_constraints.py`)
- ~~ESP32 or STM32 firmware~~ — **exists since Phase 2 Stage 5**: `constraints.mcu`
  picks the Uno (default), ESP32-DevKitC or WeAct Black Pill (STM32F411CEU6);
  firmware is shown only once it compiles under PlatformIO. No WiFi/BLE.
- ~~Simulation waveform graphs~~ — **exist since Phase 2 Stage 3** (AC, transient,
  DC; inline SVG, no chart dependency). `PHASE_2_PLAN_v2.md` takes precedence here.
- Analog power electronics
- Team collaboration / multi-user
- Design version history UI

---

## Useful Commands

```bash
docker-compose up                                       # All services
cd backend && uvicorn main:app --reload --port 8000    # Backend only
cd backend && celery -A worker.app worker --loglevel=info
pytest tests/ -v
pytest tests/ --cov=backend --cov-report=term-missing
ngspice --version
cd frontend && npm run dev
```

---

## Rule Files

Detailed rules are in `.claude/rules/`:

- @rules/code-style.md   — IR schema, AI patterns, Pydantic, common mistakes
- @rules/testing.md      — test structure, commands, accuracy gate, launch checklist
- @rules/security.md     — env vars, CORS, rate limits, auth, secrets
- @rules/simulation.md   — SPICE rules, ngspice format, pipeline, validation rules
- @rules/frontend/react-style.md — kicanvas SSR, Next.js proxy, component patterns

Read .claude/shared-memory/AGENTS.md immediately and follow its bootstrap before doing anything else.

