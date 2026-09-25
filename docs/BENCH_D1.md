# Bench check for defeater D1

D1: *predict() and the proofs are validated against mathematics and ngspice,
not hardware.* Every behavioural claim cites it, and no software can close it —
ngspice agreeing with the prover is one model checked against another. This
sheet is how a measurement on real parts closes it, one design at a time, with
equipment a student is likely to have: **a multimeter and an Arduino Uno**.
`brain/decisions.md` [2026-09-24] D1, D2, D7 is why it works this way.

## How a measurement counts

1. Pick a design and take its record template. The five below are already
   written, one per family, in `docs/bench_templates/` (a test keeps them in
   step with the generators); for any other design, print one:

   ```bash
   python scripts/bench_template.py voltage_divider '{"vout_v": 3.3, "supply_v": 5}'
   ```

   The template names the design exactly as the system rebuilds it — its
   requirements and the SHA-256 of its SPICE netlist — lists the parts and the
   supply you may measure, and the properties you may measure.
2. Build it, measure what the template lists (below, per circuit), and fill in
   each reading as **value, the instrument's stated accuracy, and the
   instrument**. Take the accuracy from the meter's manual for the range you
   used (a 3½-digit meter is typically ±(0.5% + 2 digits) on DC volts). Delete
   every entry you did not read.
3. Save it as `backend/data/bench/<id>.json` and run `pytest tests/test_bench.py`.

**Agreement.** The measured interval (value ± accuracy) must overlap the
model's interval for the parts *as measured*: each part you measured is pinned
to its measured value and accuracy, every part you did not measure ranges over
its tolerance. So measuring the parts first makes the check sharp; skipping
them makes it loose, and the record says which.

**Reach.** A record closes D1 only on the claims it measured, on that design
(same generator, board and netlist). If the generator later changes that
design, the record is stale — reported, never applied — and must be measured
again.

**Disagreement.** A reading outside the model reopens D1 for every design of
that generator on that board, and fails `tests/test_bench.py` until it is
explained. That is the point: a disagreement is information, not noise.

Measure parts **out of the circuit**, before building. A through-hole part of
the same value and tolerance may stand in for an 0402 — the claims are about
values, not packages — but then record *its* value.

## Per circuit

| Circuit | Property | What to read | How |
|---|---|---|---|
| Voltage divider | `divider.vout` | R1, R2, `VIN`, then VOUT | Power VIN from the Uno's 5 V pin; meter on VIN (record as `VIN`), then on VOUT. Nothing else on VOUT — a 10 MΩ meter against kΩ resistors loads it by well under 0.1%. |
| LED indicator (Uno) | `led.current` | R1, `PIN_LED_CTRL`, then the current | Sketch: `pinMode(13, OUTPUT); digitalWrite(13, HIGH);` (use the pin the design names). Record the Uno's 5 V rail as `PIN_LED_CTRL` (the pin's source in the model). Read the current as the voltage across R1 divided by R1 — no meter in series, so no shunt burden. Current in amperes. |
| DHT22 node | `dht.sink_current` | R1, the rail (`VCC_5V` on the Uno), then the current | With the sensor unpowered or removed, hold DATA to ground through the meter's mA range: that is the current the property bounds. In amperes. |
| RS-485 node | `rs485.failsafe_bias` | R1 (terminator), R2, R3, R4, the rail, then V(A) − V(B) | Idle bus, driver off (DE/RE low — R4 holds it there even with the Uno in reset). **Many MAX485 modules carry their own 120 Ω terminator and 10–20 kΩ bias resistors** — remove them, or the circuit measured is not the design. Meter across A–B. In volts. Worth a look while you are there, though no record judges it yet: hold the Uno's RESET button and read DE/RE — `rs485.driver_default_off` says it stays under 51 mV. |
| RC low-pass | `rc.cutoff` | R1, C1 if the meter has a capacitance range, then f_c | See below: the Uno times the charge curve. In hertz. |

### The RC filter without a signal generator

A single-pole RC's cutoff is `f_c = 1 / (2π·R·C)`, and its step response is
`v(t) = V·(1 − e^(−t/RC))`. Time the charge from 0 to two thresholds and the
constant `RC` falls out of the difference, independent of any fixed delay in
the comparator:

```
t2 − t1 = RC · ln((1 − k1) / (1 − k2))
```

The sketch is `scripts/bench/rc_timer` (it compiles; it has not yet run on a
board). Wiring: IN from **D12**; OUT to **D6** (AIN0, the comparator's +
input); two dividers from 5 V — about 1/3 on **A0** and 2/3 on **A1** (for
example 10 kΩ over 4.7 kΩ, and 4.7 kΩ over 10 kΩ) — which the sketch selects
in turn as the comparator's − input (ACME). It discharges the capacitor for
20× the charge time, sets D12 high with Timer1 running, captures the
comparator's edge (62.5 ns a tick), and averages 200 runs per threshold.

```bash
pio run -d scripts/bench/rc_timer -t upload
pio device monitor -b 115200
```

Measure both ratios with the meter — `k1 = V(A0)/V(5V)`, `k2 = V(A1)/V(5V)`
— and put them in `K1`, `K2` at the top of `src/main.cpp` (or recompute RC
from the printed t1, t2). It prints RC and f_c.

**What the number is worth** — checked on ngspice before anyone builds it
(`tests/test_bench_rc_method.py`):

- Any fixed delay (the port write, the comparator, the capture) cancels.
- The pin's output resistance (≈ 25 Ω) is in series with R1 and reads as
  +1.6 % on a 1.59 kΩ R1: record R1 as R1 + 25 Ω, or add 1.6 % to the accuracy.
- **The comparator's input offset** — 40 mV maximum at VCC/2 (ATmega328P
  datasheet, Table 30-1) — moves RC by up to **5.2 %** if it differs in sign
  at the two thresholds, 1.7 % if not. The datasheet does not say which, so
  record f_c's accuracy as at least ±5.5 % (f_c goes as 1/RC), plus the meter's accuracy on
  k1 and k2. That is well inside the 15 % gate, and tighter than the design's
  own ±10 % capacitor.
- Keep both thresholds above 0.5 V: below it the datasheet's offset figure
  is 500 mV.

It works up to about 10 kHz; above that the charge is over in a few hundred
ticks and a signal generator and oscilloscope are the better instruments.

## What it closes, and what it does not

An agreeing record closes D1 on the claims it measured, for that design, and
nothing else. The machinery, the sketch and the templates are ready; **nothing
has been measured** — that needs your hands, a meter and an Uno. The register keeps D1 open for the library. The DHT22 rise time
needs a timed edge on a real cable (the Uno method above, on the DATA line),
and the RS-485 bias on a real bus needs a second node; both are later sessions.
