# Testing — Circuit OS

## Test Structure

Every new piece of code needs a test before the PR is merged.

```
tests/
├── conftest.py                 # Fixtures: ir_dht22, ir_modbus, ir_led, ir_rc_filter, ir_voltage_divider
│                               # Also sets dummy env vars before any imports
├── test_ir_schema.py           # 20 cases: valid IRs, invalid IRs, edge cases
├── test_firmware_generator.py  # One test per template — output must be non-empty + valid .ino
├── test_rule_engine.py         # One PASS + one FAIL case per rule (10 tests minimum)
├── test_simulation.py          # RC filter: correct value → PASS, wrong value → FAIL
├── test_ai_layer.py            # Unit + live API tests (live auto-skipped if no key)
├── test_bom.py                 # BOM compiler: row count, required fields, pricing
└── test_auth.py                # Password hashing, JWT encode/decode, schema validation
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=term-missing

# Run only unit tests (no live API, no ngspice, no arduino-cli)
pytest tests/ -v

# Skip markers
pytest tests/ -m "not slow"
```

Current status: **171 passed, 24 skipped** (24 skipped = live API + ngspice + arduino-cli — auto-skipped when not available)

## conftest.py Bootstrap Pattern

`conftest.py` sets dummy env vars **before any imports** so `config.py`'s `settings = Settings()` does not fail at collection time:

```python
import os, sys
from pathlib import Path

# Must be first — before any backend imports
os.environ.setdefault("ANTHROPIC_API_KEY", "")     # empty → live tests auto-skipped
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
```

Empty `ANTHROPIC_API_KEY` → `bool("".strip()) = False` → `requires_api` mark skips all live tests.

## Live API Test Pattern

```python
API_KEY_PRESENT = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
requires_api = pytest.mark.skipif(not API_KEY_PRESENT, reason="ANTHROPIC_API_KEY not set")

@requires_api
class TestCircuitReasonerLive:
    ...
```

Live tests run in CI when `ANTHROPIC_API_KEY` is set as a GitHub Actions secret. They are skipped locally unless the developer sets the key.

## What Each Test Class Must Cover

| File | Minimum coverage |
|---|---|
| `test_ir_schema.py` | Valid IR, duplicate component IDs rejected, bad connection refs rejected, all 5 examples instantiate cleanly |
| `test_firmware_generator.py` | Each template produces non-empty output containing expected identifiers |
| `test_rule_engine.py` | Each rule: one IR that passes, one IR that deliberately fails |
| `test_simulation.py` | Correct RC filter → PASS; wrong capacitor value → FAIL; MCU modeled as resistor (not voltage source) |
| `test_ai_layer.py` | DesignSpec unit tests, format_pydantic_errors unit test, live: 5 prompts → valid CircuitIR |
| `test_bom.py` | Row count matches components, required fields present, pricing non-negative |
| `test_auth.py` | bcrypt hash/verify, JWT encode/decode, wrong secret fails, EmailStr validation |

## Simulation Accuracy Gate

Required before Phase 1 public launch. Cannot be automated — requires physical hardware:

1. Build the RC filter from IR_003 physically: R=1590Ω (RC0402FR-071K59L), C=100nF (CL05B104KO5NNNC)
2. Drive with function generator, measure -3dB cutoff frequency with oscilloscope
3. Compare to ngspice result for IR_003
4. **ngspice output must be within 15% of bench measurement**
5. If it fails: debug `backend/generators/netlist/spice.py` before launch

Expected: 1kHz ±150Hz. If ngspice reports anything outside 850Hz–1150Hz vs bench, investigate.

## Simulation Monitor — Launch Gate Check

`backend/simulation/monitor.py` tracks per-circuit-type success rates:

```python
from simulation.monitor import SimulationMonitor
gate = SimulationMonitor().check_launch_gate(min_rate=0.90, min_runs=5)
# gate["passed"] must be True before Phase 1 launch
```

Every circuit type (rc_filter, dht_sensor, modbus, led, voltage_divider) must show ≥90% success rate over at least 5 runs.

## Phase 1 Launch Checklist

Do not call Phase 1 done until every item is checked:

- [ ] 20 different prompts tested end-to-end, zero crashes
- [ ] Generated firmware for TPL_001 and TPL_002 compiled and flashed to physical Arduino
- [ ] Simulation correctly fails on deliberately wrong component values (C=1nF in RC filter)
- [ ] Rule engine catches missing I2C pull-up in test IR that deliberately omits it
- [ ] 5 sequential patches to the same design — no data corruption
- [ ] Designs survive server restart (PostgreSQL persistence confirmed)
- [ ] JWT auth working, all design routes return 401 without token
- [ ] New generation < 15s measured, patch < 20s measured
- [ ] Zero HTTP 500s in 100 consecutive requests (load test)
- [ ] Rate limiting: 11th generation in one hour returns 429
- [ ] Simulation accuracy gate passed (bench vs ngspice within 15%)
- [ ] Explanation report shown to one external engineer — they understand every component choice without being briefed
