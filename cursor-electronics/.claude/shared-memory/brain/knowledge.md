# Knowledge — Circuit OS

> Domain facts, formulas, and lessons learned during this project.
> Append-only. Answers: "what has the project learned?"

---

## IR Schema — Invariants Every Session Must Know

- Field names in `backend/core/ir_schema.py` are a contract. **Never rename them.**
  - `connection.component_id` ← correct
  - `connection.node_id`      ← correct
  - `connection.component`    ← WRONG — breaks all generators
- `Optional` fields in Pydantic v2: use `if x is not None:` not `hasattr()`.
- Patcher returns `{"changes": [...]}` only. Full IR from patcher = bug.

## ngspice — Output Is Columnar, Not `v(x) = y`

ngspice batch (`-b`) output:
```
              Node                    Voltage
              ----                    -------
v(vcc_5v)               5.00000e+00
```
Correct DC regex: `r'^\s*v\(([^)]+)\)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'`
AC output: column-index parsing on tabular data — not regex on labels.

## ngspice — MCU SPICE Model

```spice
* CORRECT
R_MCU_U1 VCC_5V GND 100

* WRONG — singular matrix, ngspice refuses to simulate
VMCU_U1 VCC_5V GND DC 5
```

## ngspice — Floating Node Prevention

Nodes with < 2 connections → singular matrix.
Generator auto-inserts: `R_TIE_nodename nodename 0 1G`

## Phase 1 Hardware Rule Checks

| Rule | Catches |
|------|---------|
| `no_floating_nodes` | Every node ≥ 2 connections |
| `voltage_ratings_ok` | Component voltage_max ≥ supply_voltage |
| `i2c_pullups_present` | SDA and SCL each have resistor to VCC |
| `rs485_termination_present` | RS-485 A/B have 120Ω between them |
| `pwm_pin_valid` | PWM on Arduino Uno pins 3,5,6,9,10,11 only |

## Electronics Formulas

**RC filter cutoff:** `f_c = 1 / (2π × R × C)` — at cutoff gain = −3 dB
**Voltage divider:** `V_out = V_in × R2 / (R1 + R2)`
**LED resistor:** `R = (V_supply − V_fwd) / I_led` — ATmega GPIO limit: 40 mA per pin

## Claude API Pattern

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[schema_tool],
    tool_choice={"type": "tool", "name": tool_name},
    messages=[{"role": "user", "content": prompt}]
)
result = response.content[0].input  # already a dict — NO json.loads()
```
Never use `response.content[0].text` — that is raw text, not structured output.

## Lessons Learned

### [2026-06-03] Windows terminal UTF-8

`Path.write_text(content)` without `encoding="utf-8"` uses cp1252 on Windows.
Unicode chars (→, emoji) crash the write. Always pass `encoding="utf-8"`.
Add `sys.stdout.reconfigure(encoding="utf-8")` to any script that prints emoji.

### [2026-06-03] Git root at home directory

The git repo root is `C:\Users\KIIT`, not `cursor-electronics`.
`.cargo/registry` files trigger LF→CRLF warnings. Fix: `.cargo/` in `C:\Users\KIIT\.gitignore`.
