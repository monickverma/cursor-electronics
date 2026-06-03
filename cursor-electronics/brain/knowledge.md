# Knowledge — Circuit OS

> Domain facts, formulas, and lessons learned during this project.
> Append-only. Answers: "what has the project learned?"

---

## The IR Schema — Invariants Every Session Must Know

- Field names in `backend/core/ir_schema.py` are a contract. **Never rename them.**
  - `connection.component_id` ← correct
  - `connection.node_id` ← correct
  - `connection.component` ← WRONG (breaks all generators)
- `Component.sensor_type` is `Optional[str] = None`. Use `if component.sensor_type is not None:`
  not `hasattr()` — Pydantic v2 always returns True for declared optional fields.
- Patcher returns `{"changes": [...]}` only. Full IR from patcher = bug.

---

## ngspice — Critical Facts

### Output format is COLUMNAR, not `v(x) = y`

ngspice batch mode (`-b`) produces:
```
              Node                    Voltage
              ----                    -------
v(vcc_5v)               5.00000e+00
```

The regex `v\(x\)\s*=\s*(\d+)` does **NOT** match this output.

Parser uses:
- DC: `r'^\s*v\(([^)]+)\)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'`
- AC: column-index parsing on tabular output

### MCU SPICE model

```spice
* CORRECT — resistive load
R_MCU_U1 VCC_5V GND 100

* WRONG — voltage source loop, ngspice singular matrix
VMCU_U1 VCC_5V GND DC 5
```

### Floating node prevention

Any node with < 2 connections causes a singular matrix. The SPICE generator
auto-adds 1GΩ tie-down resistors:
```spice
R_TIE_dht22_data dht22_data 0 1G
```

### Convergence options on retry

If simulation fails convergence on first attempt:
```spice
.options RELTOL=0.01 ITL1=500 ITL2=150
```
Do NOT retry `anthropic.APIError` — raise immediately as 503.

---

## Hardware Rule Checks (Phase 1)

| Rule | What it catches |
|------|----------------|
| `no_floating_nodes` | Every node has ≥ 2 connections |
| `voltage_ratings_ok` | Component voltage_max ≥ circuit supply_voltage |
| `i2c_pullups_present` | SDA and SCL each have a resistor to VCC |
| `rs485_termination_present` | RS-485 A/B lines have 120Ω between them |
| `pwm_pin_valid` | PWM on Arduino Uno pins 3, 5, 6, 9, 10, 11 only |

`HardwareRuleEngine.run(ir)` only checks rules listed in `ir.validation_rules`.

---

## Electronics Formulas (Phase 1 Templates)

### RC Filter (TPL_004)
- Cutoff frequency: `f_c = 1 / (2π × R × C)`
- At cutoff: gain = −3 dB (V_out = 0.707 × V_in)
- Test values: R = 1590Ω, C = 100nF → f_c = 1000 Hz ±15%

### Voltage Divider (TPL_005)
- Output: `V_out = V_in × R2 / (R1 + R2)`
- Loading effect: output impedance = R1 ∥ R2

### LED Current Limiting (TPL_003)
- `R = (V_supply − V_forward) / I_led`
- ATmega328P GPIO source/sink limit: 40 mA per pin, 200 mA total
- Typical LED: V_forward ≈ 2.0 V (red/yellow), 3.0 V (blue/white), I_led = 10–20 mA

---

## Claude API — Circuit OS Patterns

### tool_use — the only permitted pattern

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[schema_tool],
    tool_choice={"type": "tool", "name": tool_name},
    messages=[{"role": "user", "content": prompt}]
)
result = response.content[0].input  # already a dict — NO json.loads()
```

### Retry loop failure modes

| Failure | Response |
|---------|----------|
| `anthropic.APIError` | Raise immediately → 503 (do NOT retry) |
| `json.JSONDecodeError` | Re-prompt with exact error position |
| `pydantic.ValidationError` | Re-prompt with specific field paths |
Maximum 3 attempts. All-fail → `CircuitGenerationError` → HTTP 422.

---

## kicanvas — Frontend Rule

```tsx
// CORRECT — browser-only APIs, must not run during SSR
const SchematicViewer = dynamic(
  () => import('@/components/SchematicViewer'),
  { ssr: false }
)
```

`document`, `customElements`, `URL.createObjectURL` do not exist in Node.js SSR.
Importing kicanvas at module level crashes the server render.

---

## Lessons Learned

### [2026-06-03] Windows terminal emoji encoding

`Path.write_text(content)` without `encoding="utf-8"` uses cp1252 on Windows.
Unicode characters (→, emoji) in YAML content crash the write.
Fix: always pass `encoding="utf-8"` to `Path.write_text()`.
Also: `sys.stdout.reconfigure(encoding="utf-8")` at top of any tool script that prints emoji.

### [2026-06-03] Git root at home directory

The git repo root is `C:\Users\KIIT`, not `cursor-electronics`. This means `.cargo/registry`
files trigger LF→CRLF warnings. Fix: add `.cargo/` to `C:\Users\KIIT\.gitignore`.

---

## TEMPLATE — adding a new lesson

```
### [YYYY-MM-DD] Short title
What was learned, why it matters.
Concrete fix or formula if applicable.
```
