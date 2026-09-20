# Architecture — LAYER 2

> How the system is structured, what each module does, and how data flows.
> Manual, update when architecture changes.

---

## The Central Invariant

```
User Prompt
    │
    ▼  (IntentParser — tool_use)
DesignSpec (structured intent)
    │
    ▼  (IntentProducer — tool_use → IntentIR; registry dispatch → generator)
CircuitIR  ←── THE LOCKED CONTRACT — all modules read from here
    │
    ├──▶ SpiceNetlistGenerator  →  .cir netlist
    ├──▶ ArduinoFirmwareGenerator  →  .ino (Jinja2)
    ├──▶ KiCadSchematicGenerator  →  .kicad_sch
    ├──▶ BOMCompiler  →  BOM rows
    ├──▶ ExplanationEngine  →  plain English report
    └──▶ Celery task → NgspiceRunner → SpiceResultParser → SimulationGrader
```

**The LLM only ever writes CircuitIR JSON. It never writes SPICE, KiCad, or .ino.**

---

## Module Map

```
backend/
├── main.py                    FastAPI app — CORS, rate limiting, route registration
├── worker.py                  Celery app — broker=Redis, backend=Redis
│
├── core/
│   ├── ir_schema.py           CircuitIR Pydantic model — THE LOCKED SCHEMA
│   │                          Fields: circuit_id, components, nodes, connections,
│   │                          simulation_spec, validation_rules, patch_history
│   ├── ir_validator.py        Structural validation before any compiler runs
│   │                          Rules: no_floating_nodes, voltage_ratings_ok,
│   │                          i2c_pullups_present (if I2C nodes exist)
│   ├── ir_examples.py         5 hardcoded reference IRs (for tests)
│   └── config.py              pydantic-settings — fails at import if env vars missing
│                              .env resolved from project root via Path(__file__)
│
├── data/
│   ├── component_constraints.py   Python dict — zero LLM tokens
│   │                              DHT22, MAX485ECSA constraints injected into prompts
│   └── component_db.json          100-entry component database
│
├── ai/
│   ├── client.py              make_client() — supports Anthropic direct + OpenRouter
│   │                          ai_model() — reads AI_MODEL env var
│   ├── intent_parser.py       Prompt → DesignSpec via tool_use (forced, no raw text)
│   ├── intent_producer.py     Prompt → IntentIR (X5 retry rules; removed the
│   │                          LLM → CircuitIR path entirely, 2026-09-21)
│   ├── form_producer.py       Form → IntentIR — reference producer, 0 API calls
│   │                          Handles: APIError (no retry), JSONDecodeError, ValidationError
│   ├── patcher.py             IR + command → changes list ONLY (never full IR)
│   └── explainer.py           IR → consequential plain English report
│
├── generators/
│   ├── netlist/spice.py       CircuitIR → SPICE netlist
│   │                          MCU → 100Ω load, floating nodes → 1GΩ tie-down
│   ├── firmware/arduino.py    CircuitIR → .ino via Jinja2 templates
│   │   └── templates/         sensor_read.ino.j2, modbus_master.ino.j2,
│   │                          base.ino.j2, led_blink.ino.j2
│   ├── schematic/kicad.py     CircuitIR → .kicad_sch (net labels, no wire routing)
│   └── bom/compiler.py        CircuitIR → BOM rows (static pricing from constraints)
│
├── simulation/
│   ├── runner.py              NgspiceRunner — async subprocess
│   │                          On Windows: uses -o outfile (not stdout pipe capture)
│   │                          Falls back to C:\msys64\ucrt64\bin\ngspice_con.exe
│   ├── parser.py              SpiceResultParser — columnar DC + multi-table AC
│   │                          AC: parses complex format (real, imag), computes |Z|
│   ├── grader.py              SimulationGrader — 15% tolerance pass/fail
│   └── monitor.py             Per-circuit-type success rate logger → sim_monitor.jsonl
│
├── validation/
│   └── rule_engine.py         HardwareRuleEngine — RS-485 termination, PWM pins
│
├── tasks/
│   └── simulation_task.py     Celery task run_simulation — never inline in HTTP handler
│
├── api/routes/
│   ├── design.py              POST /design/generate (10/hour rate limit)
│   │                          POST /design/list
│   ├── patch.py               POST /design/{id}/patch (20/hour)
│   ├── simulate.py            GET /design/{id}/simulation/{job_id} (100/hour)
│   │                          POST /design/{id}/simulation/start
│   └── auth.py                POST /auth/register, /auth/login (OAuth2 form), /auth/me
│
├── db/
│   ├── schema.sql             6 tables: users, projects, circuit_designs,
│   │                          simulation_runs, validation_results, patch_history,
│   │                          generated_outputs
│   ├── models.py              SQLAlchemy async ORM models
│   └── crud.py                Async CRUD: save_design, get_design, update_design_ir,
│                              list_user_designs, record_patch, save_output
│
└── middleware/
    └── rate_limit.py          slowapi limiter — keyed by IP address

frontend/
├── app/page.tsx               Two-panel layout (chat | tabbed output)
├── components/
│   ├── ChatPanel.tsx          Auth form + chat. First message → generate, follow-up → patch
│   ├── SchematicViewer.tsx    kicanvas — dynamic import ssr:false (REQUIRED)
│   ├── SimulationResults.tsx  Polls every 3s, clears interval on unmount
│   ├── FirmwareViewer.tsx     Code display + .ino download
│   ├── BOMTable.tsx           Component list, CSV export
│   └── ValidationReport.tsx  Error/warning list
└── lib/api.ts                 Typed API client (login, register, generateDesign, patchDesign)
```

---

## PCB Layout Engine (`backend/pcb_engine/`) — added ~2026-07, documented 2026-08-07

Roughly 2,400 lines that were not described in this file until the 2026-08-07
re-sync. Pulled forward from Phase 3. Scope settled 2026-08-22 as **experimental,
labelled, behind a config flag** — see `brain/decisions.md`, "[2026-08-22] PCB
engine is in scope, experimental, and labelled".

Placement and `api/routes/pcb` are tested; routing is not. Per-module status is
derived — read `progress.yaml`, do not restate counts here.

This is a **custom engine, not KiCad freerouting**, which is what the master plan
originally specified. Anyone reading the roadmap alone will have the wrong model.

| Module | Lines | Responsibility |
|---|---|---|
| `board_ir.py` | 337 | Board-level IR: `Board`, `Pad`, `Component`, `Track`, `Via`, `Keepout`, `NetClass`, `DiffPair`. Separate from `CircuitIR` — this is geometry, that is topology. |
| `compile_board.py` | 274 | `from_netlist()` → Board IR; `place_constructive()` greedy placement by added wirelength; `compile_board()` main entry |
| `router.py` | 594 | `Grid` with obstacle mask + halo cells, `astar()` path search, `AStarRouter`, `generate_candidates()` for parallel candidate layouts |
| `kernel.py` | 320 | `drc()` → violations, `score()` → physics scorecard, `diff_pair_skew()`, segment-clearance primitives |
| `footprints.py` | 257 | `normalize_package()`, `guess()` footprint inference, `build()` pad geometry |
| `render_pretty.py` | 247 | `to_svg()` — board → SVG for the frontend PCB tab |

**Data flow:**

```
CircuitIR
   │
   ▼  generators/netlist/pcb.py  (PcbNetlistGenerator)
PCB netlist
   │
   ▼  pcb_engine/compile_board.py  (from_netlist → place_constructive)
Board IR  (placed, unrouted)
   │
   ▼  pcb_engine/router.py  (AStarRouter / generate_candidates)
Board IR  (routed candidates)
   │
   ▼  pcb_engine/kernel.py  (drc + score)
Candidates + physics scorecards
   │
   ▼  pcb_engine/render_pretty.py → SVG → frontend PCB tab
```

**Runs in-process inside the API** (`api/routes/pcb.py` → `POST /pcb/compile`),
not as a separate service and not via Celery. Commit `75b677d` moved it inward
deliberately. Note this cuts against the project's own rule that long-running
work goes through Celery — if layout times grow, that decision needs revisiting.

---

## Key Data Contracts

### CircuitIR (ir_schema.py) — the locked contract
```python
class CircuitIR(BaseModel):
    circuit_id: str          # UUID
    version: int             # increments on each patch
    intent: str              # human-readable design intent
    application_class: str   # hobby_arduino | iot_node | industrial_io | modbus_rtu
    target_mcu: Optional[str]
    components: List[Component]
    nodes: List[Node]
    connections: List[Connection]
    simulation_spec: Optional[SimulationSpec]
    validation_rules: List[str]
    patch_history: List[dict]

class Connection(BaseModel):
    component_id: str   # ← CORRECT — never 'component'
    pin: str
    node_id: str        # ← CORRECT — never 'node'
    direction: str
```

**Never rename `component_id` or `node_id` — breaks 5+ downstream files.**

### DesignSpec (intent_parser.py)
```python
class DesignSpec:
    intent: str
    application_class: str
    target_mcu: Optional[str]
    constraints: dict        # threshold_temp, baud_rate, cutoff_hz, etc.
    primary_sensor: Optional[str]
    use_rs485: bool
    has_relay: bool
```

---

## Infrastructure

| Service | Role | Port |
|---------|------|------|
| FastAPI (uvicorn) | HTTP API | 8000 |
| Next.js | Frontend | 3000 |
| PostgreSQL | Design persistence | 5432 |
| Redis | Celery broker + result backend | 6379 |
| Celery worker | Simulation jobs | — |
| ngspice | SPICE simulation | — (subprocess) |
| arduino-cli | Firmware compilation test | — (subprocess) |

### Running locally
```bash
docker-compose up -d db redis
cd backend && uvicorn main:app --port 8000
cd backend && celery -A worker.app worker --loglevel=info --pool=solo  # --pool=solo on Windows
cd frontend && npm run dev
```

### Known Windows quirks
- ngspice_con.exe writes to Windows console handle, not stdout pipe → use `-o outfile` flag
- Celery prefork pool fails on Python 3.13 Windows → use `--pool=solo`
- arduino-cli installed at `C:\Users\KIIT\bin\arduino-cli.exe` (not in PATH)
- ngspice at `C:\msys64\ucrt64\bin\ngspice_con.exe` (installed via MSYS2 pacman)
