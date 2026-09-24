# Bench check for defeater D1

D1: *predict() and the proofs are validated against mathematics and ngspice,
not hardware.* Every behavioural claim cites it, and no amount of software can
close it — ngspice agreeing with the prover is one model checked against
another. This sheet is the smallest bench session that puts hardware evidence
behind three of the library's designs. It needs a multimeter, a bench supply,
a signal generator and an oscilloscope, and about an hour.

The designs are what the generators produce today (rc_lowpass 0.2.3,
voltage_divider 0.1.0, led_indicator 0.1.1). The bands are the Stage 4
proven properties — the sentences a user signs.

## Parts

The generators place 0402 parts. A bench build may use through-hole parts of
the **same value and tolerance**: the claims are about values, not packages.
Measure every part with the meter before building and write the value down —
the check below uses it.

| Design | Part | Value | Tolerance | Catalogue part |
|---|---|---|---|---|
| RC low-pass, 1 kHz | R1 | 3.40 kΩ | 1% | RC0402FR-073K4L |
| | C1 | 47 nF | 10% | CL05B473KO5NNNC |
| Divider, 3.3 V from 5 V | R1 | 3.40 kΩ | 1% | RC0402FR-073K4L |
| | R2 | 6.65 kΩ | 1% | RC0402FR-076K65L |
| LED, 10 mA | R1 | 280 Ω | 1% | RC0402FR-07280RL |
| | LED1 | red | V_f 1.7–2.4 V @ 20 mA | 67-21URC/S530-A3/TR8 |
| | U1 | Arduino Uno pin, driven high | | ATmega328P |

## Procedure

**RC low-pass.** Drive IN with a 1 V sine from a low-impedance source (the
proof assumes an ideal source; a generator's 50 Ω output moves f_c by 1.4%).
Sweep and find the frequency where OUT is 0.707 of IN.
Proven band: **896 Hz – 1.12 kHz**.

**Divider.** 5.00 V on VIN (measure it), meter on VOUT, nothing else
connected (the meter's 10 MΩ against the divider's 2.25 kΩ output is a 0.02% load).
Proven band: **3.28 V – 3.34 V** at exactly 5 V — scale by the measured VIN.

**LED.** Sketch: `pinMode(13, OUTPUT); digitalWrite(13, HIGH);`, R1 and the
LED from D13 to GND, meter in series (use the 200 mA range; its shunt adds a
few ohms — note it).
Proven band: **8.19 mA – 11.4 mA** on a 5 V board.

## Pass rule

A measurement **agrees** when it lies inside the proven band. Record also the
ngspice value at your **measured** part values — the design's netlist is
saved with it (`{circuit_id}_v{n}.cir`); edit the values and run it, or ask
Claude to. The project's accuracy gate is bench against ngspice within 15%,
and the Stage 0 grid gate already holds ngspice to 2% of predict().

## Results

| Design | Measured parts | Measured value | Proven band | Inside? | ngspice at measured parts | Δ |
|---|---|---|---|---|---|---|
| RC low-pass | R1 = … C1 = … | f_c = … | 896 Hz – 1.12 kHz | | | |
| Divider | VIN = … R1 = … R2 = … | VOUT = … | 3.28 – 3.34 V (at 5.00 V) | | | |
| LED | pin V = … R1 = … | I = … | 8.19 – 11.4 mA | | | |

## What it closes, and what it does not

Three agreeing rows are hardware evidence for those three claims, at those
points — record them in `brain/decisions.md` and cite them from the claims.
They do not eliminate D1 for the library: the register says D1 is eliminated
by "a bench measurement agreeing within tolerance", per claim. The DHT22 rise
time and RS-485 bias need a scope on a cable and a second node; they are the
next session, not this one.
