# Architecture — Circuit OS

> How the system works, what modules exist, and how data flows.
> Manual, occasional updates as architecture evolves.

---

## The One Rule Everything Depends On

LLM output is always JSON. JSON is validated against the IR schema.
Deterministic compilers translate IR to SPICE / KiCad / .ino / BOM.
**Never LLM → ngspice / KiCad / .ino directly.**

---

## Module Map

```
User Prompt (natural language)
        │
        ▼
┌─────────────────────────┐
│   IntentParser          │  backend/ai/intent_parser.py
│   prompt → DesignSpec   │  Claude tool_use, never raw text
└──────────┬──────────────┘
           │ DesignSpec
           ▼
┌─────────────────────────┐
│   CircuitReasoner       │  backend/ai/circuit_reasoner.py
│   DesignSpec → CircuitIR│  3-attempt retry loop
│                         │  pydantic v2 strict validation
└──────────┬──────────────┘
           │ CircuitIR (validated JSON)
           │
     ┌─────┴──────────────────────────────────────────┐
     │                                                 │
     ▼                                                 ▼
┌─────────────────────┐              ┌──────────────────────────────┐
│  SpiceNetlistGen    │              │  ExplanationEngine           │
│  IR → .sp netlist   │              │  IR → plain English why/if   │
│  backend/generators │              │  backend/ai/explainer.py     │
│  /netlist/spice.py  │              └──────────────────────────────┘
└────────┬────────────┘
         │ netlist string
         ▼
┌─────────────────────┐
│  Celery Task        │  backend/tasks/simulation_task.py
│  submit → job_id    │  NEVER inline in HTTP handler
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  NgspiceRunner      │  backend/simulation/runner.py
│  ngspice -b         │  subprocess, 30s timeout
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  SpiceResultParser  │  backend/simulation/parser.py
│  columnar DC/AC     │  NOT v(x) = y regex
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  SimulationGrader   │  backend/simulation/grader.py
│  15% tolerance      │  grade() → GradeResult pass/fail
└─────────────────────┘

CircuitIR also compiles via:
  ArduinoFirmwareGen   →  backend/generators/firmware/arduino.py   (Jinja2)
  KiCadSchematicGen    →  backend/generators/schematic/kicad.py    (net labels only)
  BOMCompiler          →  backend/generators/bom/compiler.py       (static pricing)

Validation before simulation:
  ir_validator.py      →  structural (floating nodes, voltage ratings, I2C pull-ups)
  rule_engine.py       →  domain rules (RS-485, PWM pin validity)

Conversational editing:
  CircuitPatcher       →  backend/ai/patcher.py
  Returns ONLY changed fields — never full IR
```

---

## Data Formats

### CircuitIR — the canonical schema
Defined in `backend/core/ir_schema.py`. Never rename fields.

```
circuit_id, template_id, supply_voltage
components:   list[Component]    id, type, value, justification
nodes:        list[Node]         id, net_label
connections:  list[Connection]   component_id, node_id, pin
simulation_spec                  analysis_type, expected_outputs
validation_rules: list[str]      which rules to run
constraints:  dict               cutoff_hz, etc.
```

### Key invariants

| Invariant | Detail |
|-----------|--------|
| MCU SPICE model | `R_MCU VCC GND 100` — never voltage source (singular matrix) |
| ngspice output | columnar format — NOT `v(x) = y` |
| Floating nodes | auto-tied with 1GΩ resistors during SPICE generation |
| Patcher output | changed fields only — never full IR |
| kicanvas | `dynamic import`, `ssr: false` — browser-only APIs |

---

## Directory Ownership

| Path | Purpose |
|------|---------|
| `backend/core/` | IR schema, validator, examples, config |
| `backend/ai/` | LLM modules (tool_use only) |
| `backend/generators/` | Deterministic compilers — no LLM |
| `backend/simulation/` | ngspice runner, parser, grader, monitor |
| `backend/api/routes/` | FastAPI route handlers |
| `backend/db/` | PostgreSQL models, CRUD, schema.sql |
| `backend/tasks/` | Celery async simulation task |
| `backend/validation/` | Hardware rule engine |
| `backend/middleware/` | slowapi rate limiting |
| `frontend/app/` | Next.js 14 App Router pages |
| `frontend/components/` | React components |
| `tests/` | pytest — 177 passing, 24 skipped |
| `brain/` | Project knowledge — append-only |
| `plan/` | Roadmap and current phase tasks |
| `state.json` | DERIVED — run tools/regen_state.py |
| `progress.yaml` | DERIVED — run tools/regen_state.py |

---

## Tech Stack

| Layer | Technology | Hard constraint |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11 | `async def` for all routes |
| AI | Claude claude-sonnet-4-6 | `tool_use` mode only |
| Simulation | ngspice subprocess | BSD licensed — LTspice EULA forbidden |
| Firmware | Jinja2 templates | Never LLM-generated .ino |
| Queue | Celery + Redis | All simulation runs — never inline HTTP |
| Database | PostgreSQL + SQLAlchemy async | No in-memory storage |
| Frontend | Next.js 14 App Router | kicanvas ssr:false |
| Rate limiting | slowapi | LLM + simulation endpoints |
