# Knowledge — LAYER 5

> Domain facts, formulas, and hard-won lessons specific to Circuit OS.
> Append-only. Answers: "what do I need to know to work on this project?"

---

## The IR Schema Rules (critical — violating these breaks production)

### Field names are locked
```python
connection.component_id  ← CORRECT
connection.node_id       ← CORRECT
connection.component     ← WRONG (breaks SPICE generator, firmware generator, BOM)
connection.node          ← WRONG
```

### MCU in SPICE = 100Ω resistor
```spice
R_MCU_U1 VCC_5V GND 100   ← correct (50mA load at 5V)
VMCU_U1 VCC_5V GND DC 5   ← wrong (two voltage sources = singular matrix = crash)
```

### Floating nodes = singular matrix
Any node with fewer than 2 connections causes ngspice to fail with singular matrix.
The SPICE generator automatically adds `R_TIE_nodename node 0 1G` for any such node.

---

## ngspice on Windows (MSYS2 install)

### Location
```
C:\msys64\ucrt64\bin\ngspice_con.exe   ← the one that works
C:\msys64\ucrt64\bin\ngspice.exe       ← GUI version, don't use
```

### Capture output — stdout pipe does NOT work
ngspice_con.exe is a Windows console application. It writes directly to the Windows
console handle. `subprocess.run(capture_output=True)` returns empty strings.

**Fix:** Use `-o outfile` flag:
```python
subprocess.run([ngspice_con, "-b", "-o", out_path, cir_path], capture_output=True)
stdout = out_path.read_text()
```

### XSPICE model errors are harmless
ngspice prints these at startup — they don't affect basic SPICE:
```
Error: Library /ucrt64/lib/ngspice/analog.cm couldn't be loaded!
```
These are behavioral models (XSPICE). Circuit OS only uses R, C, L, V, I sources — unaffected.

---

## ngspice Output Format

### DC operating point (.op)
```
	Node                                  Voltage
	----                                  -------
	vout_5v                          5.057851e+00
	vin_12v                          1.200000e+01
	v_vin_12v#branch                 -9.91736e-04   ← branch current, skip (#)
```
All node names are lowercase in output. Grader lowercases expected names before lookup.

### AC sweep output
- ngspice emits ONE table per variable, even if `.print ac v(a) v(b)` lists both
- Each table paginates at ~55 rows (header repeats)
- Data format: `Index TAB frequency TAB real, TAB imag TAB`
- Trailing comma on real part — must strip before `float()` parse
- Magnitude = `sqrt(real^2 + imag^2)` — NOT just real part

Example at 1kHz RC filter:
```
40  1.000000e+03  2.502435e+00,  -2.50000e+00
```
sqrt(2.502^2 + 2.500^2) = 3.536V = -3dB ✓
Using only real part = 2.502V = 29% error ✗

---

## OpenRouter API

### URL construction with Anthropic SDK
The Anthropic SDK appends `/v1/messages` to `base_url`.
- `base_url = "https://openrouter.ai/api"` → SDK hits `https://openrouter.ai/api/v1/messages` ✓
- `base_url = "https://openrouter.ai/api/v1"` → SDK hits `.../api/v1/v1/messages` → 404 ✗

### DeepSeek does NOT work with Anthropic SDK + OpenRouter
- OpenRouter's Anthropic Messages API (`/api/v1/messages`) only routes Anthropic models
- DeepSeek models require OpenRouter's OpenAI-compatible endpoint (`/chat/completions`)
- Use `anthropic/claude-3-5-haiku-20241022` or `anthropic/claude-sonnet-4-5` with this SDK

### OpenRouter headers required
```python
kwargs["default_headers"] = {
    "HTTP-Referer": "http://localhost:3000",
    "X-Title": "Circuit OS",
}
```

---

## Arduino Uno Constraints

### Serial ports
- Has only ONE hardware UART: `Serial` (pins 0/1) — used for debug/Serial Monitor
- `Serial1`, `Serial2`, `Serial3` do NOT exist on Uno (Mega/Leonardo only)
- For RS-485 Modbus: use `SoftwareSerial` on pins 10 (RX) and 11 (TX)

### PWM-capable pins
Pins 3, 5, 6, 9, 10, 11 ONLY. The rule engine (`validation/rule_engine.py`)
enforces this. Any other pin → validation error.

### DHT22 requirements
- Pull-up resistor required: 10kΩ to VCC on DATA pin
- Without it: open-drain output never reaches logic HIGH → MCU reads timeout errors
- Cannot read faster than once every 2 seconds

---

## Celery on Windows

### Python 3.13 prefork failure
```
ValueError: not enough values to unpack (expected 3, got 0)
```
in `celery/app/trace.py:fast_trace_task`

**Fix:** `celery -A worker.app worker --pool=solo`
- `solo` runs tasks in main process, no subprocess spawn
- No concurrency in solo mode — fine for development

### Starting the worker
```bash
cd backend
PYTHONPATH=c:/Users/KIIT/cursor-electronics/backend \
  celery -A worker.app worker --loglevel=info --pool=solo
```

---

## Pydantic v2

### hasattr doesn't work for Optional fields
```python
# WRONG — hasattr returns True for declared Optional fields even if None
if hasattr(comp, 'sensor_type'):
    ...

# CORRECT
if comp.sensor_type is not None:
    ...
```

### from __future__ import annotations breaks FastAPI + slowapi
When a slowapi decorator wraps a FastAPI route function, FastAPI resolves types
against the wrapper's globals (not the route's). With lazy string annotations,
`GenerateRequest` and `Depends(get_db)` become unresolvable → FastAPI treats them
as query params → 422 on every POST request.

**Fix:** Remove `from __future__ import annotations` from route files.
Affected files: `api/routes/design.py`, `patch.py`, `simulate.py`.

---

## Electronics Formulas Used in Phase 1

### RC low-pass filter
- Cutoff frequency: `f_c = 1 / (2π × R × C)`
- At cutoff: gain = -3 dB (V_out = 0.707 × V_in = 3.536V for 5V AC input)
- Phase 1 reference: R=1590Ω, C=100nF → f_c = 1000 Hz

### Voltage divider
- V_out = V_in × R2 / (R1 + R2)
- Phase 1 reference: V_in=12V, R1=7kΩ, R2=5.1kΩ → V_out ≈ 5.07V

### LED current limiting
- I_LED = (V_supply - V_forward) / R_limit
- Typical: V_forward = 2.0V (red LED), I_LED = 20mA → R = (5-2)/0.02 = 150Ω
- Arduino Uno GPIO sink limit: 40mA per pin

---

## Test Suite Facts

```
257 passed, 24 skipped, 0 failing    (as of 2026-08-07, commit 1ae8f34)
```

That figure is a 2026-08-07 snapshot. **Current counts live in `state.json` (derived) — do not restate them here.**

- 18 skipped = live API tests (need real ANTHROPIC_API_KEY set) + were ngspice/arduino-cli
- ngspice tests now run (ngspice installed)
- arduino-cli tests now run (arduino-cli installed + libraries)
- Live API tests skip locally unless ANTHROPIC_API_KEY is set in env

Run: `cd cursor-electronics && PYTHONPATH=backend pytest tests/ -v`
