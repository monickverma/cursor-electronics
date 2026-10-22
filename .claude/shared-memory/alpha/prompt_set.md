# Alpha — the overlooker's prompt set

> The master session owns this file. The builders never see it. The overlooker receives only the
> prompts it is given for a run, never this file.

---

## Set A — the five Phase 1 templates, complete and unambiguous

These should SUCCEED. They are the product's bread and butter. If any of these is refused, or produces a
design that does not match the request, that is a finding.

| # | Prompt |
|---|---|
| A1 | Design an RC low-pass filter on an Arduino Uno with a 5 V supply and a cutoff frequency of 1 kHz. |
| A2 | Design a voltage divider on an Arduino Uno with a 5 V supply: 10 kΩ top, 10 kΩ bottom, output read on an ADC pin. |
| A3 | Arduino Uno with a red LED on pin 8 driven through a 1 kΩ resistor at 10 mA, on a 5 V supply. |
| A4 | Arduino Uno reads a DHT22 sensor on a 2 metre cable and lights a status LED at 10 mA when the temperature exceeds 30 degrees. |
| A5 | Arduino Uno RS-485 Modbus RTU master using a MAX485E, 9600 baud, 10 metre bus, with fail-safe bias. |

## Set B — composition

| # | Prompt |
|---|---|
| B1 | Arduino Uno reads a DHT22 sensor with a 2 metre cable, sounds a buzzer above 30 degrees, and lights a status LED. |
| B2 | Arduino Uno reads a DHT22 over a 5 metre cable, drives a relay through a 2N2222A, and lights an LED on the same board. |

## Set C — realistic engineer requests (some SHOULD be refused)

These are where the product is judged on judgement, not just correctness. The right answer is sometimes a
clear refusal naming what is missing.

| # | Prompt | What it tests |
|---|---|---|
| C1 | Design an RC low-pass filter on an Arduino Uno. | Vague. Supply voltage and cutoff missing. The product should either ask, or state the defaults it used. |
| C2 | Design an RC low-pass filter on an Arduino Uno with a 1 kHz cutoff and a 5 V supply. | The minimum complete form. Contrast with C1 — a good product shows the same result here, which means C1's refusal was right. |
| C3 | Make a low-pass filter for me. 1k cutoff, 5V, Arduino Uno. | Terse, keyword style. Tests the parser, not the vocabulary. |
| C4 | Design an RC low-pass filter on an Arduino Uno with a 5 V supply and a cutoff frequency of 1 kHz, but the cutoff must also be 5 kHz. | Contradictory. The product should refuse, not pick one. |
| C5 | Design an RC low-pass filter on an Arduino Uno with a 5 V supply and a cutoff frequency of 1 kHz. Use a 2.2 µF capacitor. | A real engineering constraint. The product should honour it or explain why it cannot. |
| C6 | Design an RC low-pass filter on an Arduino Uno with a 5 V supply and a cutoff frequency of 1 kHz, using an XYZ123-45 chip. | The part does not exist. The product should refuse by name, not invent a part number. |
| C7 | Design an RC low-pass filter on an Arduino Uno with a 5 V supply and a cutoff frequency of 1 kHz. Cutoff frequency is 1 kHz. | Repeated requirement. Harmless, but tests for double-application of a value. |
| C8 | Design a buck converter on an Arduino Uno with a 12 V input and a 5 V output at 1 A. | Out of catalogue. A buck converter is explicitly Phase 2+ scope. The product should refuse and say so. |
| C9 | Design an RC low-pass filter on an ESP32-DevKitC with a 3.3 V supply and a cutoff frequency of 1 kHz. | A different board. Tests the multi-MCU path. |
| C10 | Design an RC low-pass filter on a WeAct Black Pill STM32F411 with a 3.3 V supply and a cutoff frequency of 1 kHz. | The third board. |

## Set D — the calibration boards (the seeded set)

The master session builds these from `tests/fixtures/alpha_known_bad/`. Each seeded board is presented to the
overlooker as a plain request, with the defect's location unknown to the overlooker. The master session
holds the answer key.

**The answer key is never shown to the overlooker.** The overlooker does not know which prompts are seeded
and does not get told where the fault is.

## Set E — the held-out set (never shown to builders)

A second prompt set, kept by the master session, used at the PR stage to measure whether the product's
overlooker pass rate generalises. Builders never see it. It is not run during A1 or A2.

---

## Grading

For each prompt, the overlooker scores all 14 rubric parameters and writes findings.

The A1 exit criterion, measured on Set D (the seeded set):

| Measure | Target |
|---|---|
| Recall on seeded defects | ≥ 90% |
| False passes on the critical classes (short, open, wrong pinout, reversed diode, creepage) | **0** |
| Recall per rubric parameter | recorded, not thresholded |
