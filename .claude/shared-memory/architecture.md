# Architecture — LAYER 2

> How the system works, what modules exist, and how data flows.
> Manual, occasional updates as architecture evolves.

---

## Module Map

```
User Input (natural language)
        │
        ▼
┌─────────────────┐
│   NL Parser     │  src/parser.py
│                 │  Converts natural language → ComponentSpec JSON
│                 │  Handles: R, C, L, V sources, I sources, subcircuits
└────────┬────────┘
         │ ComponentSpec
         ▼
┌─────────────────┐
│ Netlist Gen     │  src/netlist_gen.py
│                 │  ComponentSpec → SPICE netlist (.sp file)
│                 │  Writes to: sims/[name].sp
└────────┬────────┘
         │ .sp file path
         ▼
┌─────────────────┐
│   Simulator     │  src/simulator.py     ← IN PROGRESS
│   (ngspice)     │  Runs ngspice via subprocess → SimResult
│                 │  Convergence retry logic with relaxed options
└────────┬────────┘
         │ SimResult
         ▼
┌─────────────────┐
│   Verifier      │  src/verifier.py      ← NOT STARTED
│                 │  Checks SimResult against requirements
│                 │  HVAC-specific: superheat, COP, efficiency
└────────┬────────┘
    pass │ fail
         │────────────────→ [loop back to Parser with diagnosis]
         ▼
┌─────────────────┐
│  PCB Designer   │  src/pcb_designer.py  ← NOT STARTED
│                 │  Verified schematic → KiCad netlist + layout
└─────────────────┘
```

## Data Formats

### ComponentSpec (Parser output)
```json
{
  "type": "filter",
  "topology": "rc_lowpass",
  "components": [
    { "id": "R1", "type": "resistor", "value": "1k", "unit": "ohm" },
    { "id": "C1", "type": "capacitor", "value": "159n", "unit": "F" }
  ],
  "requirements": { "cutoff_freq_hz": 1000 }
}
```

### SimResult (Simulator output)
```json
{
  "status": "success",
  "analysis": "ac",
  "data_file": "sims/output/rc_filter.raw",
  "summary": { "cutoff_freq_hz": 998.3, "gain_at_cutoff_db": -3.02 },
  "convergence_attempts": 1
}
```

## Directory Ownership

| Directory | Owner | Description |
|-----------|-------|-------------|
| `src/` | Worker | Production code |
| `tests/` | Worker | Test suite (pytest), one test_xxx per function |
| `sims/` | Worker | SPICE netlists + simulation outputs |
| `plan/` | Planner | Strategic + tactical planning docs |
| `brain/` | Both | Shared knowledge (mostly append-only) |
| `state.json` | `regen_state.py` | DERIVED — never edit directly |
| `progress.yaml` | `progress_gen.py` | DERIVED — never edit directly |

## Tech Stack

- **Language:** Python 3.10+
- **Simulator:** ngspice (subprocess)
- **Testing:** pytest (one `test_function()` per `function()`)
- **Parsing:** regex + structured prompting
- **VCS:** git (ground-truth signal)
- **State derivation:** Python `ast` module for code introspection
