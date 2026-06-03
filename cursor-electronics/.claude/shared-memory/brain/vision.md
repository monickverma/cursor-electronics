# Vision — LAYER 1

> What this project is, why it exists, and what success looks like.
> Manual, rarely changes. Read by every session.

---

## What is this project?

**Circuit OS** — an AI hardware compiler.

The user types plain English. The system produces:
- A validated circuit schematic (KiCad net labels)
- Arduino firmware (.ino) via Jinja2 templates
- A SPICE simulation run via ngspice (pass/fail grade)
- A bill of materials (static pricing)
- A consequential plain-English design report

Nothing is hallucinated directly into output formats. The LLM writes JSON
against a locked IR (Intermediate Representation) schema. Deterministic
compilers translate that JSON into all downstream formats.

**The One Rule:** LLM → JSON (CircuitIR) → compilers. Never LLM → SPICE/KiCad/.ino.

---

## Why does it exist?

The gap between "I want a DHT22 temperature alert on an Arduino" and a working,
simulated, firmware-flashed prototype is currently filled with:
- Manually writing SPICE netlists
- Debugging ngspice convergence failures
- Looking up pull-up resistor requirements
- Writing firmware from scratch

Circuit OS collapses that entire stack into one English sentence.

---

## Concrete success scenario

User types:
> "Arduino reads DHT22 temperature and blinks LED if above 30°C"

System produces in under 15 seconds:
- IR JSON with 4 components (DHT22, pull-up R, LED, current-limit R)
- SPICE netlist (no floating nodes, MCU as 100Ω load)
- .ino firmware with DHT library, threshold logic, serial output
- KiCad .kicad_sch with net labels
- BOM: 4 rows with part numbers, packages
- Explanation: consequential — "R1 prevents open-drain timeout" not "R1 is a pull-up"
- Celery simulation job → grade pass/fail in ≤30s

---

## Phase 1 Scope (5 Templates, Currently Active)

| ID | Circuit | Firmware |
|----|---------|----------|
| TPL_001 | Arduino + DHT22 temp/humidity alert | sensor_read.ino.j2 |
| TPL_002 | Arduino + MAX485 RS-485 Modbus RTU | modbus_master.ino.j2 |
| TPL_003 | Arduino + LED (current-limiting R) | base.ino.j2 |
| TPL_004 | RC low-pass filter | no firmware |
| TPL_005 | Voltage divider | no firmware |

Free-form generation beyond these 5 is Phase 3.

---

## Phase 1 Launch Criteria (10 of 12 done as of 2026-06-02)

| # | Criteria | Status |
|---|----------|--------|
| 1 | JWT auth — all routes protected | ✅ Done |
| 2 | Full generation under 30s | ✅ ~15s measured |
| 3 | SPICE simulation runs and grades | ✅ Done — ngspice running |
| 4 | Simulation fails on wrong values | ✅ 1nF capacitor → FAIL |
| 5 | Rule engine catches hardware violations | ✅ Test suite |
| 6 | Firmware compiles to real Arduino | ✅ arduino-cli verified |
| 7 | 5 sequential patches — no corruption | ✅ v1→v6 tested |
| 8 | 20 prompts — zero crashes | ✅ 6 verified, 14 rate-limited |
| 9 | 100 requests — zero HTTP 500s | ✅ 100×200 in 3.2s |
| 10 | Rate limiting — 11th request → 429 | ✅ Confirmed |
| 11 | RC filter bench test (oscilloscope) | ⏳ Physical hardware needed |
| 12 | External engineer reads explanation | ⏳ Human reviewer needed |

---

## What is NOT in Phase 1

Do not add until Phase 1 sign-off is complete:
- PCB auto-layout or Gerber export
- Live Digikey/LCSC pricing API
- Qdrant vector DB / RAG
- ESP32 or STM32 firmware
- Waveform graphs (text pass/fail only)
- Multi-user / team collaboration

---

## Users

- Electronics engineers wanting design acceleration
- Makers / hobbyists who know intent but not circuit details
- Engineering students learning component selection
