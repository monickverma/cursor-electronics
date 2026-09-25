# Bench check for defeater D1

D1: *predict() and the proofs are validated against mathematics and ngspice,
not hardware.* Every behavioural claim cites it, and no software can close it —
ngspice agreeing with the prover is one model checked against another. This
sheet is how a measurement on real parts closes it, one design at a time, with
equipment a student is likely to have: **a multimeter and an Arduino Uno**.
`brain/decisions.md` [2026-09-24] D1, D2, D7 is why it works this way.

## How a measurement counts

1. Pick a design and print its record template:

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
| RS-485 node | `rs485.failsafe_bias` | R1 (terminator), R2, R3, the rail, then V(A) − V(B) | Idle bus, driver off (DE/RE low). **Many MAX485 modules carry their own 120 Ω terminator and 10–20 kΩ bias resistors** — remove them, or the circuit measured is not the design. Meter across A–B. In volts. |
| RC low-pass | `rc.cutoff` | R1, C1 if the meter has a capacitance range, then f_c | See below: the Uno times the charge curve. In hertz. |

### The RC filter without a signal generator

A single-pole RC's cutoff is `f_c = 1 / (2π·R·C)`, and its step response is
`v(t) = V·(1 − e^(−t/RC))`. Time the charge from 0 to two thresholds and the
constant `RC` falls out of the difference, independent of any fixed delay in
the comparator:

```
t2 − t1 = RC · ln((1 − k1) / (1 − k2))
```

With an Uno: drive IN from a digital pin, put OUT on the analog comparator's
AIN0 (D6), and put two reference dividers on ADC0 and ADC1, selected in turn
as the comparator's negative input (ACME). Discharge (pin LOW for ≥ 10·RC),
set the pin HIGH and start Timer1 together, and capture the comparator edge
(input capture, 62.5 ns per tick at 16 MHz). Average ≥ 100 runs per threshold.
Measure both dividers' ratios `k1`, `k2` with the meter. The pin's own output
resistance (≈ 25 Ω) adds to R1: pick a design where R1 is kilohms and it is
under 1%, or add it to the accuracy you record. This works well up to about
10 kHz; above that the timing error grows and a signal generator and
oscilloscope are the better instruments.

*The sketch for this is not written or run yet — it is the first thing to
build at the bench, and until it has been run this row is the least tested
method on the sheet.*

## What it closes, and what it does not

An agreeing record closes D1 on the claims it measured, for that design, and
nothing else. The register keeps D1 open for the library. The DHT22 rise time
needs a timed edge on a real cable (the Uno method above, on the DATA line),
and the RS-485 bias on a real bus needs a second node; both are later sessions.
