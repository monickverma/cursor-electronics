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
Since Stage 5 the resistor is per part, from `supply_model_ohm` in
`component_constraints.py`, on the board's own rail: 100 Ω ATmega328P
(`VCC_5V`), 41 Ω ESP32-WROOM-32E and 132 Ω STM32F411CEU6 (`VCC_3V3`). Claims
name it `mcu_as_<R>R`. Still never a voltage source.

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

## ESP32-DevKitC and Black Pill (Stage 5)

The pin tables are in `data/mcu_targets.py`, and `validation/pin_rules.py`
checks them. Gotchas that cost a build or a board:

- **ESP32:**
  - GPIO6–11 are wired to the module's SPI flash; never use them.
  - GPIO34–39 are input-only, with no internal pull.
  - GPIO0, 2, 5, 12 and 15 are strapping pins: GPIO12 sets the flash voltage
    at reset, and GPIO0 low enters the bootloader.
  - UART0 (GPIO1/3) is the USB console, so RS-485 goes on UART2
    (`HardwareSerial rs485Serial(2)`, then `begin(baud, SERIAL_8N1, RX, TX)`).
  - There is no `LED_BUILTIN` on the DevKitC.
- **Black Pill STM32F411CEU6:**
  - PA11/PA12 are USB, and PA13/PA14 are SWD (the programming port).
  - PC13 is the on-board LED; PC14/PC15 are the 32 kHz crystal; PA0 is the
    KEY button. PB2 is BOOT1.
  - STM32duino's serial class is `Uart` (`Uart s(RX, TX)`); `HardwareSerial`
    is the abstract ArduinoCore-API base and does not compile.
  - The USB console needs
    `-D PIO_FRAMEWORK_ARDUINO_ENABLE_CDC -D USBCON` in platformio.ini.
- **3.3 V logic on both:** a 5 V pull-up on an ESP32 input damages the part.
  RS-485 uses the MAX3485, since the MAX485 needs 4.75–5.25 V.
- **PlatformIO** (6.2.0): platforms are pinned per project (atmelavr 5.3.0,
  espressif32 7.1.3, ststm32 20.0.0). A board's first build downloads its
  toolchain (hundreds of MB) into `~/.platformio`; after that, a build with a
  warm cache takes seconds.

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
