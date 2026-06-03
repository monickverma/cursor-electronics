# Architecture — Circuit OS

> How the system works, what modules exist, how data flows.

---

## The One Rule Everything Depends On

LLM → JSON (CircuitIR) → deterministic compilers → SPICE / KiCad / .ino / BOM.
Never LLM → ngspice/KiCad/.ino directly.

## Module Map

```
User Prompt (natural language)
        │
        ▼
┌──────────────────────┐
│  IntentParser        │  backend/ai/intent_parser.py
│  prompt → DesignSpec │  tool_use forces structured output
└──────────┬───────────┘
           │ DesignSpec
           ▼
┌──────────────────────┐
│  CircuitReasoner     │  backend/ai/circuit_reasoner.py
│  DesignSpec →        │  3-attempt retry loop
│  CircuitIR           │  JSON validated against ir_schema.py
└──────────┬───────────┘
           │ CircuitIR (validated)
           ├──────────────────────────────────────────┐
           │                                          │
           ▼                                          ▼
┌────────────────────┐  ┌────────────────────────────────────┐
│ SpiceNetlistGen    │  │  ExplanationEngine                 │
│ IR → .sp           │  │  IR → plain English why/what-if    │
│ backend/generators │  │  backend/ai/explainer.py           │
│ /netlist/spice.py  │  └────────────────────────────────────┘
└────────┬───────────┘
         │ netlist string
         ▼
┌────────────────────┐
│  Celery Task       │  backend/tasks/simulation_task.py
│  (never inline)    │  submit → return job_id → client polls
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  NgspiceRunner     │  backend/simulation/runner.py
│  ngspice -b        │  subprocess, 30s timeout
└────────┬───────────┘
         │ raw output
         ▼
┌────────────────────┐
│  SpiceResultParser │  backend/simulation/parser.py
│  columnar DC/AC    │  NOT "v(x) = y" regex
└────────┬───────────┘
         │ SimulationData
         ▼
┌────────────────────┐
│  SimulationGrader  │  backend/simulation/grader.py
│  15% tolerance     │  grade() → GradeResult pass/fail
└────────────────────┘

CircuitIR also compiles via:
  ArduinoFirmwareGen  → backend/generators/firmware/arduino.py  (Jinja2 templates)
  KiCadSchematicGen   → backend/generators/schematic/kicad.py   (net labels only)
  BOMCompiler         → backend/generators/bom/compiler.py      (static pricing Phase 1)

Validation before simulation:
  ir_validator.py     → structural checks (floating nodes, voltage ratings, I2C pull-ups)
  rule_engine.py      → domain rules (RS-485, PWM pin validity)

Conversational editing:
  CircuitPatcher      → backend/ai/patcher.py
  patch() returns ONLY changed fields, never full IR
```

## Data Formats

### CircuitIR (the canonical schema)
Defined in `backend/core/ir_schema.py`. Never rename fields — all compilers read them.

```python
CircuitIR:
  circuit_id, template_id, supply_voltage
  components: list[Component]   # id, type, value, justification, ...
  nodes: list[Node]             # id, net_label
  connections: list[Connection] # component_id, node_id, pin
  simulation_spec               # analysis_type, expected_outputs
  validation_rules: list[str]   # which rules to run
  constraints: dict             # cutoff_hz, etc.
```

### Key invariants

| Rule | Detail |
|------|--------|
| MCU SPICE model | 100Ω resistor, NOT voltage source (singular matrix) |
| ngspice output | columnar, NOT `v(x) = y` format |
| Floating nodes | auto-tied to GND via 1GΩ during SPICE generation |
| Patcher output | patch dict only, never full IR |
| kicanvas | `dynamic import, ssr: false` — browser-only APIs |

## Directory Ownership

| Path | Purpose |
|------|---------|
| `backend/core/` | IR schema, validator, examples, config |
| `backend/ai/` | LLM modules (tool_use only) |
| `backend/generators/` | Deterministic compilers (no LLM) |
| `backend/simulation/` | ngspice runner, parser, grader |
| `backend/api/routes/` | FastAPI route handlers |
| `backend/db/` | PostgreSQL models, CRUD, schema |
| `backend/tasks/` | Celery async tasks |
| `backend/validation/` | Rule engine |
| `frontend/` | Next.js 14 App Router |
| `tests/` | pytest (171 passing, 24 skipped) |
| `plan/` | Phase docs |
| `brain/` | Project knowledge (append-only) |
| `state.json` | DERIVED — run tools/regen_state.py |
| `progress.yaml` | DERIVED — run tools/regen_state.py |

## Tech Stack

| Layer | Technology | Constraint |
|-------|------------|------------|
| Backend | FastAPI + Python 3.11 | async def all routes |
| AI | Claude claude-sonnet-4-6 | tool_use only, never raw text |
| Simulation | ngspice subprocess | BSD — LTspice EULA forbids SaaS |
| Firmware | Jinja2 templates | Never LLM-generated .ino |
| Queue | Celery + Redis | All simulation — never inline HTTP |
| Database | PostgreSQL + SQLAlchemy async | No in-memory storage |
| Frontend | Next.js 14 App Router | kicanvas ssr:false |
| Rate limiting | slowapi | LLM + simulation endpoints |
