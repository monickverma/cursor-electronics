# Simulation — Circuit OS

## Rule: Simulation Is Always Async via Celery

Never run ngspice inline in an HTTP handler. Simulation takes 2–30 seconds.

```python
# CORRECT — submit job, return immediately, client polls
task = run_simulation.apply_async(args=[circuit_id, netlist, job_id], task_id=job_id)
return {"job_id": job_id, "status": "queued"}

# WRONG — blocks HTTP connection for up to 30s
result = await sim_runner.run(netlist)
return {"result": result}
```

`await` in FastAPI releases the event loop but does **not** release the HTTP connection. The client browser, load balancer, or mobile SDK will time out. Celery is the correct pattern.

---

## Rule: MCU SPICE Model Is a Resistor, Not a Voltage Source

```spice
* CORRECT — model as resistive load (100Ω = 50mA at 5V)
R_MCU_U1 VCC_5V GND 100

* WRONG — creates voltage source loop, ngspice refuses to simulate
VMCU_U1 VCC_5V GND DC 5
```

Two voltage sources on the same node = singular matrix = ngspice error. If the power supply is `V1 VCC_5V 0 DC 5` and the MCU is also `VMCU VCC_5V GND DC 5`, ngspice will fail with "voltage source loop" and produce no output.

The MCU draws current, it does not supply voltage. 100Ω gives 50mA at 5V — close to ATmega328P typical quiescent draw.

---

## Rule: ngspice Batch Output Is Columnar, Not `v(x) = y`

ngspice batch mode (`-b`) produces columnar output, not `v(x) = y` format:

```
              Node                    Voltage
              ----                    -------
v(vcc_5v)               5.00000e+00
v(gnd)                  0.00000e+00
v(dht22_data)           5.00000e+00
```

The regex `v\(x\)\s*=\s*(\d+)` does NOT match this. The parser uses:
- DC pattern: `r'^\s*v\(([^)]+)\)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'`
- Column-index parsing for AC sweep tabular output

The AC sweep format uses `.print` directives and produces a table with `frequency` as the first column.

---

## Simulation Pipeline

```
CircuitIR
    │
    ▼
SpiceNetlistGenerator.generate(ir)     → SPICE netlist string
    │  MCU → R_MCU_U1 VCC GND 100
    │  Floating nodes → R_TIE_node node 0 1G
    ▼
run_simulation.apply_async(circuit_id, netlist, job_id)   → Celery task ID
    │
    ▼  (background Celery worker)
NgspiceRunner._run_sync(netlist)
    │  writes to tempfile, subprocess.run(["ngspice", "-b", path])
    │  30s timeout, cleanup in finally
    ▼
SpiceResultParser.parse(stdout, stderr)
    │  columnar DC parser + AC table parser
    ▼
SimulationGrader.grade(ir, parsed_data)
    │  15% tolerance for all checks
    │  AC sweep: finds closest point to constraints["cutoff_hz"]
    ▼
SimulationMonitor.record(...)          → sim_monitor.jsonl
    ▼
Results in GET /design/{id}/simulation/{job_id}
```

---

## Floating Node Handling in SPICE

Any node with fewer than 2 connections causes a singular matrix in ngspice. The SPICE generator automatically adds 1GΩ tie-down resistors to prevent this:

```spice
* Auto-generated for floating node DHT22_DATA
R_TIE_dht22_data dht22_data 0 1G
```

This is added during `SpiceNetlistGenerator.generate()` by counting element appearances per node. Any node appearing fewer than 2 times in element lines gets the tie-down.

---

## 5 Validation Rules (Phase 1)

`ir_validator.py` — structural validation, runs synchronously before any compiler:

| Rule | What it catches | Source |
|---|---|---|
| `no_floating_nodes` | Every node has ≥2 connections | ir_validator.py |
| `voltage_ratings_ok` | Component supply_voltage_max ≥ circuit supply_voltage | ir_validator.py |
| `i2c_pullups_present` | SDA and SCL nodes each have a resistor to VCC | ir_validator.py |
| `rs485_termination_present` | RS-485 A/B lines have 120Ω resistor between them | rule_engine.py |
| `pwm_pin_valid` | PWM signals on Arduino Uno PWM-capable pins only (3,5,6,9,10,11) | rule_engine.py |

`HardwareRuleEngine.run(ir)` only checks rules listed in `ir.validation_rules`. A circuit without RS-485 nodes does not run the RS-485 rule.

---

## Simulation Grader Tolerance

```python
_TOLERANCE = 0.15  # 15% — must match CLAUDE.md accuracy gate
```

Pass condition: `abs(actual - expected) / abs(expected) <= 0.15`

For DC: checks each node in `ir.simulation_spec.expected_outputs` against parsed DC voltages.

For AC: finds the frequency point in parsed AC data closest to `ir.constraints["cutoff_hz"]`, compares the output voltage at that frequency against the expected value.

The 15% tolerance matches the Phase 1 launch gate: ngspice output must be within 15% of a physical bench measurement on the RC filter.

---

## Why ngspice Instead of LTspice

LTspice EULA explicitly prohibits commercial redistribution and server-side automation. You cannot legally call LTspice in a SaaS product. ngspice is BSD-licensed — free for commercial use, scriptable via subprocess, and already integrated into KiCad. Not negotiable.
