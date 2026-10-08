# Step 1 — Bench afternoon (D1)

The full method is in [`docs/BENCH_D1.md`](../docs/BENCH_D1.md), and the blank records are in
[`docs/bench_templates/`](../docs/bench_templates/). Both were checked on 2026-10-02: the records' netlist hashes
still match the designs the generators build today.

## Kit

- Arduino Uno R3 and a USB cable
- A multimeter (write down its stated DC accuracy), with a capacitance range if you have one
- A breadboard and jumpers
- 1% resistors: 3.4 kΩ, 6.65 kΩ, 280 Ω and 10 kΩ, or whatever the records name (measure each one anyway)
- 100 nF capacitors
- A red LED (the catalogue part is Würth 150080RS75000; any red LED works if you write down which one)
- A DHT22

## First, check the board is the design (about 10 minutes a design)

A resistor in the wrong breadboard row would be charged to the model: D1 would reopen for a design that was never
built. So before each design's measurements, build it, then — power off — read the few resistances on its sheet in
[`docs/BUILD_CHECK_SHEETS.md`](../docs/BUILD_CHECK_SHEETS.md) (three for the divider, DHT22 and RC, five for the LED
and RS-485; the sheet says between which nets and what to expect), and type them in:

```bash
python scripts/build_check_cli.py diagnose voltage_divider '{"r:vin,vout": 3412, "r:vout,0": 6603, "r:vin,0": 10010}'
```

`as_designed` means the board is the design (a capacitor's value excepted — the sheet says so; use the `rc_timer`
sketch). Anything else names the fault, or the part that reads off — fix the board first. Only if every resistance
agrees and the powered voltages still do not, is it a model question. The method, and how accurate it was in
simulation, is in [`docs/REAL_DATA_CHECK.md`](../docs/REAL_DATA_CHECK.md) §8.

## Order (about 3 hours)

| # | Design | Measure | Record file |
|---|---|---|---|
| 1 | Voltage divider (3.3 V from 5 V) | R1, R2, `VIN`, then VOUT | `voltage_divider.json` |
| 2 | LED, 10 mA | R1, the 5 V rail as `PIN_LED_CTRL`, V across R1 (current = V/R1), **and V across the LED → `notes`** | `led_indicator.json` |
| 3 | RC low-pass, 1 kHz | R1, C1, then f_c timed by the Uno ([`scripts/bench/rc_timer`](../scripts/bench/rc_timer)) | `rc_lowpass.json` |
| 4 | DHT22 node | R1, the rail, the DATA sink current with the sensor removed | `dht22_node.json` |
| 5 | Flash the firmware (below) | Does it run? | note in the decision log |

For each one, copy the template to `backend/data/bench/<id>.json` and fill in **only what you actually read**:
delete the fields you didn't measure, and fill in `measured_by`. Then run:

```bash
pytest tests/test_bench.py -v
```

If a record disagrees with the model, it fails loudly. That's a result, not a mistake: commit it as it is and we
investigate.

**The LED forward voltage.** The catalogue assumes V_F ≥ 1.6 V, and no document gives that minimum. Your reading
across LED1 at about 10 mA is the first real number for it. If it reads below 1.6 V, the LED assumption is wrong
and the LED proofs are proving the wrong box.

## Firmware on a real board

The projects were exported with `python scripts/bench_firmware.py fieldwork/firmware`, and on 2026-10-02 they built
under PlatformIO (LED: 2.0 KB flash; DHT22: 5.3 KB).

```bash
cd fieldwork/firmware/led_indicator && pio run -t upload
```

Expected: the LED on D13 blinks at 1 s on / 1 s off. Measure the LED current with BENCH_D1's steady-HIGH sketch,
not with this firmware, because the blink makes the meter reading meaningless.

```bash
cd fieldwork/firmware/dht22_node && pio run -t upload && pio device monitor
```

Expected at 115200 baud: a `Temperature: … C   Humidity: … %` line every 2 s, with DATA on D2. Breathe on the
sensor and humidity should rise. Pull DATA out and you should get `[ERROR] Sensor read failed…`.

Write down what you see, including failures. "Firmware has run on a real board" is a claim this repo has never
been able to make.

## What it closes

An agreeing record closes D1 **for the claims it measured, on that design**, and nothing else. The library-wide D1
stays open until the DHT22 rise time on a real cable and the RS-485 bias on a real bus are measured too.
