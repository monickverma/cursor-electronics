# Knowledge — LAYER 5

> Domain facts, formulas, and lessons learned during this project.
> Append-only. Answers: "what has the project learned?"

---

## HVAC / Refrigeration

### Superheat
- **Definition:** Difference between actual vapor temperature and saturation temperature
- **Why it matters:** Must stay positive to prevent liquid refrigerant reaching the compressor
- **Target:** Typically 5–15 °C superheat at evaporator outlet
- **Formula:** Superheat = T_actual_vapor − T_saturation

### Subcooling
- **Definition:** Heat removed from liquid refrigerant below condensing temperature
- **Why it matters:** Ensures full liquid at expansion valve (prevents flash gas)
- **Target:** Typically 5–10 °C

### COP (Coefficient of Performance)
- **Formula:** COP = Q_evap / W_compressor
- **Typical values:** Air-to-air heat pumps: 3–5 in heating mode

### Refrigerant Circuit Topology
- Loop: Compressor → Condenser → Expansion Valve → Evaporator → Compressor
- SPICE modeling approach: thermal resistance ↔ electrical resistance, heat flow ↔ current, temperature ↔ voltage

---

## ngspice

### Key Commands
| Command | Purpose |
|---------|---------|
| `.tran [tstep] [tstop]` | Transient simulation |
| `.ac [type] [n] [fstart] [fstop]` | AC frequency sweep (types: dec, oct, lin) |
| `.dc [source] [start] [stop] [step]` | DC sweep |
| `.op` | Operating point (single DC solution) |

### Convergence Fixes (priority order)
1. Add `.options RELTOL=0.01 ITL1=500 ITL2=150` — relaxes tolerances
2. Add small resistors (1 mΩ) in series with voltage sources
3. Add `.ic` initial conditions near expected operating point
4. Use `UIC` flag on `.tran`
5. Reduce timestep by 10×

### Output Parsing
- Raw binary: use `--rawfile`, parse with custom binary reader or PySpice
- Text: use `--output`, grep for variable values

---

## Electronics Formulas

### RC Filter
- Cutoff frequency: `f_c = 1 / (2π × R × C)`
- At cutoff: gain = −3 dB (V_out = 0.707 × V_in)

### Buck Converter
- Duty cycle: `D = V_out / V_in`
- Inductor: `L = (V_in − V_out) × D / (f_sw × ΔI_L)`
- Output cap: `C = ΔI_L / (8 × f_sw × ΔV_out)`

---

## Lessons Learned

### [2026-06-02] Parser unit normalization
"1kHz", "1000Hz", "1 kHz" all parse to the same value — normalize unit prefixes
(k, M, G, m, u, n, p) early. Built into `parser.normalize_value()`.

### [2026-06-03] ngspice subprocess safety
Always set a timeout. ngspice can hang on bad netlists. Use
`subprocess.run(..., timeout=30)` and handle `TimeoutExpired`.

---

## TEMPLATE — adding a new lesson

```
### [YYYY-MM-DD] Short title
What was learned, why it matters.
Concrete fix or formula if applicable.
```
