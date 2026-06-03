# Architecture — Circuit OS

---

## The One Rule Everything Depends On

**The LLM never writes SPICE, KiCad, or .ino directly.**
LLM → JSON (CircuitIR, schema-validated) → deterministic compilers → all downstream formats.
This eliminates hallucinated component values and unparseable syntax.

---

## System Flow

```
Browser / API Client
        │  POST /design/generate  {"prompt": "Arduino + DHT22 ..."}
        │  Authorization: Bearer <JWT>
        ▼
┌─────────────────────────────────────┐
│  FastAPI  (backend/main.py)         │
│  CORS → rate limit → JWT auth       │
│  async def generate_design(...)     │
└──────────┬──────────────────────────┘
           │
           ├─► IntentParser          backend/ai/intent_parser.py
           │   prompt → DesignSpec   Claude tool_use (never raw text)
           │
           ├─► CircuitReasoner       backend/ai/circuit_reasoner.py
           │   DesignSpec → CircuitIR  3-attempt retry, pydantic v2 strict
           │
           ├─► IRValidator           backend/core/ir_validator.py
           │   structural pre-checks before any compiler
           │
           ├─► HardwareRuleEngine    backend/validation/rule_engine.py
           │   domain checks: RS-485, PWM, I2C, voltage ratings
           │
           ├─► [all 4 compilers run in parallel on the validated IR]
           │   SpiceNetlistGen       backend/generators/netlist/spice.py
           │   ArduinoFirmwareGen    backend/generators/firmware/arduino.py  (Jinja2)
           │   KiCadSchematicGen     backend/generators/schematic/kicad.py   (net labels)
           │   BOMCompiler           backend/generators/bom/compiler.py      (static prices)
           │
           ├─► ExplanationEngine     backend/ai/explainer.py
           │   IR → consequential plain English (WHY, not what)
           │
           └─► Celery Task           backend/tasks/simulation_task.py
               submit → return job_id immediately (never block HTTP)

Simulation (background Celery worker):
   NgspiceRunner   backend/simulation/runner.py    subprocess, 30s timeout
        │ raw stdout
   SpiceResultParser  backend/simulation/parser.py  columnar format (not v(x)=y regex)
        │ SimulationData
   SimulationGrader   backend/simulation/grader.py  15% tolerance → GradeResult
        │
   SimulationMonitor  backend/simulation/monitor.py  structured JSONL log

Conversational editing:
   CircuitPatcher  backend/ai/patcher.py
   Returns ONLY changed fields — never a full IR regeneration

Persistence:
   PostgreSQL + SQLAlchemy async   backend/db/models.py + crud.py
   All designs saved immediately after generation — no in-memory store

Frontend polling (GET /design/{id}/simulation/{job_id}):
   SimulationResults.tsx  polls every 3s, clears interval on complete/failed
```

---

## API Contracts

### POST /design/generate
```json
Request:  { "prompt": "string" }
Response: {
  "circuit_id": "uuid",
  "ir": { ...CircuitIR... },
  "schematic": ".kicad_sch string",
  "firmware": ".ino string",
  "bom": [ {"component": "...", "mpn": "...", "price": 0.0} ],
  "explanation": "plain English string",
  "simulation_job_id": "uuid"
}
```

### GET /design/{id}/simulation/{job_id}
```json
{ "status": "queued|running|complete|failed", "result": { ...GradeResult... } }
```

### POST /design/{id}/patch
```json
Request:  { "command": "use a cheaper sensor" }
Response: { "patch": { "changes": [...] }, "new_ir": { ...CircuitIR... } }
```

### CircuitIR (canonical schema — backend/core/ir_schema.py)
```
circuit_id       str
template_id      str   (TPL_001 … TPL_005)
supply_voltage   float
components       list[Component]    id, type, value, justification
nodes            list[Node]         id, net_label
connections      list[Connection]   component_id, node_id, pin
simulation_spec  SimulationSpec     analysis_type, expected_outputs
validation_rules list[str]
constraints      dict               cutoff_hz, etc.
```

**Never rename IR fields** — every compiler reads them by name.

---

## Tech Stack

| Layer | Technology | Why chosen |
|-------|------------|------------|
| Backend | FastAPI + Python 3.11 | async throughout; best AI/ML ecosystem |
| AI | Claude claude-sonnet-4-6 via `tool_use` | Forces JSON output; eliminates free-text hallucination |
| Simulation | ngspice subprocess | BSD licensed — LTspice EULA forbids SaaS use |
| Firmware codegen | Jinja2 templates | Deterministic; LLM-generated .ino hallucinates pin numbers |
| Async jobs | Celery + Redis | 2–30s simulation can't block HTTP connection |
| Database | PostgreSQL + SQLAlchemy async | No in-memory store; survives restarts |
| Frontend | Next.js 14 App Router + TypeScript | |
| Schematic viewer | kicanvas (dynamic import, ssr:false) | Browser-native KiCad renderer |
| Styling | Tailwind CSS + EB Garamond / Figtree / JetBrains Mono | |
| Rate limiting | slowapi | On all LLM + simulation endpoints |
| Auth | JWT (bcrypt passwords, no passlib) | passlib 1.7.4 incompatible with bcrypt 4.x |

---

## Directory Ownership

| Path | Contents | Owner |
|------|----------|-------|
| `backend/main.py` | FastAPI app, CORS, rate limit middleware | backend |
| `backend/worker.py` | Celery app entry point | backend |
| `backend/core/ir_schema.py` | **Canonical IR schema** — never rename fields | everyone |
| `backend/core/ir_validator.py` | Pre-simulation structural checks | backend |
| `backend/core/ir_examples.py` | 5 hardcoded IRs used in tests | tests |
| `backend/ai/` | Intent parser, circuit reasoner, patcher, explainer | AI layer |
| `backend/generators/` | SPICE, firmware, KiCad, BOM compilers | compilers |
| `backend/simulation/` | ngspice runner, parser, grader, monitor | simulation |
| `backend/api/routes/` | design, patch, simulate, auth route handlers | API layer |
| `backend/db/` | SQLAlchemy models, CRUD, schema.sql | database |
| `backend/tasks/` | Celery simulation task | async |
| `backend/validation/` | Hardware rule engine | validation |
| `backend/data/` | component_constraints.py (Phase 1 static dict), component_db.json | data |
| `frontend/app/` | Next.js pages (page.tsx, layout.tsx, globals.css) | frontend |
| `frontend/app/api/` | Next.js proxy route handlers (forwards to FastAPI) | frontend |
| `frontend/components/` | ChatPanel, SchematicViewer, SimulationResults, BOMTable, etc. | frontend |
| `frontend/lib/api.ts` | Typed API client | frontend |
| `tests/` | pytest suite — 177 passing, 24 skipped | tests |
| `.claude/shared-memory/` | brain/, plan/, tools/ — Claude session context | tooling |

---

## Key Invariants (runtime rules that must never break)

| Invariant | Detail |
|-----------|--------|
| MCU SPICE model | `R_MCU VCC GND 100` — never a voltage source (singular matrix) |
| ngspice output | Columnar format. DC regex: `r'^\s*v\(([^)]+)\)\s+([+-]?\d+...)'` |
| Floating nodes | Auto-tied with 1GΩ resistors during SPICE generation |
| Patcher output | Changed fields only — never full IR (overwrites user edits) |
| kicanvas | `dynamic import`, `ssr: false` — browser-only APIs crash SSR |
| CORS order | CORSMiddleware added before any route registration |
| BOM Phase 1 | Static pricing only — no live Digikey/LCSC API calls |
