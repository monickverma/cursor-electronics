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
│   │   └── config.py               # pydantic-settings, fails fast on missing env vars
│   ├── data/
│   │   ├── component_constraints.py  # Python dict — zero LLM tokens
│   │   └── component_db.json         # 100-entry component database
│   ├── ai/
│   │   ├── intent_parser.py        # Prompt → DesignSpec (tool_use)
│   │   ├── circuit_reasoner.py     # DesignSpec → CircuitIR (retry loop, 3 attempts max)
│   │   ├── patcher.py              # IR + command → patch JSON ONLY, never full IR
│   │   └── explainer.py            # IR → consequential plain English
│   ├── generators/
│   │   ├── firmware/arduino.py     # IR → .ino (Jinja2)
│   │   ├── netlist/spice.py        # IR → SPICE netlist
│   │   ├── schematic/kicad.py      # IR → .kicad_sch (net labels only)
│   │   └── bom/compiler.py         # IR → BOM (static pricing)
│   ├── simulation/
│   │   ├── runner.py               # ngspice async subprocess
│   │   ├── parser.py               # Columnar batch output parser
│   │   ├── grader.py               # Pass/fail grader (15% tolerance)
│   │   └── monitor.py              # Structured failure logger
│   ├── validation/rule_engine.py   # HardwareRuleEngine (RS-485, PWM, etc.)
│   ├── pcb_engine/                 # EXPERIMENTAL — A* router, DRC, footprints, SVG
│   │                               # placement tested; routing is not
│   ├── api/routes/                 # design.py, simulate.py, patch.py, auth.py
│   ├── db/                         # models.py, crud.py, schema.sql
│   ├── tasks/simulation_task.py    # Celery task
│   └── middleware/rate_limit.py    # slowapi
├── frontend/
│   ├── app/page.tsx                # Two-panel layout
│   ├── components/                 # ChatPanel, SchematicViewer, FirmwareViewer, etc.
│   └── lib/api.ts                  # Typed API client
├── scripts/                        # capture_explanation.py, review_panel.py
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
| Firmware | Jinja2 templates | Never LLM-generated .ino directly |
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
  **(b) experimental**, excluded from the v0.1.0 gate. Do not extend it; when
  Phase 3 begins, integrate freerouting instead. See `PHASE1_COMPLETE.md` §4.
- Live Digikey/LCSC pricing API
- Qdrant vector DB / RAG (use `component_constraints.py`)
- ESP32 or STM32 firmware (Arduino Uno only)
- Simulation waveform graphs (text pass/fail only)
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

