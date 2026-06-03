# Vision — Circuit OS

> What this project is, why it exists, and what success looks like.

---

## One-Sentence Definition

> A software platform that turns a plain English hardware description into a
> complete, validated, simulation-tested, manufacture-ready electronics design —
> schematic, firmware, BOM, and safety analysis — before a single component is touched.

## Why It Exists

The gap between "I want to build X" and a verified board ready to order is currently
filled with manual work: selecting components, writing netlists, running simulators
separately, debugging convergence, cross-checking values. Circuit OS closes that gap
with a single workflow: English → IR → physics-validated outputs.

## End Goal — Concrete Success Scenario

User types:
> "Arduino + DHT22 temperature sensor, alert LED when temp exceeds 40°C"

System produces in under 30 seconds:
- CircuitIR (validated JSON)
- SPICE netlist → ngspice simulation (confirms voltages within 15% tolerance)
- .kicad_sch schematic (viewable in browser via kicanvas)
- .ino firmware (working Arduino code, ready to flash)
- BOM with part numbers and static pricing
- Plain English explanation: "I chose DHT22 because... If you change R3 from 10kΩ
  to 4.7kΩ, LED current hits 42mA, exceeding ATmega GPIO sink limit."

## The Fundamental Rule

**LLM never writes SPICE, KiCad, or .ino directly.**
LLM outputs JSON → IR schema → deterministic compilers → all downstream formats.
This single rule eliminates hallucinated circuit values.

## Hard Success Criteria (Phase 1 Launch Gate)

- [ ] 20 different prompts tested end-to-end, zero crashes
- [ ] Generated firmware for TPL_001 and TPL_002 compiled and flashed to Arduino
- [ ] Simulation correctly fails on deliberately wrong component values
- [ ] Rule engine catches missing I2C pull-up
- [ ] 5 sequential patches — no data corruption
- [ ] Designs survive server restart (PostgreSQL confirmed)
- [ ] JWT auth working, all design routes 401 without token
- [ ] Generation < 15s, patch < 20s
- [ ] Rate limiting: 11th generation in one hour → 429
- [ ] ngspice within 15% of bench measurement on RC filter

## Phase 1 Supported Circuits (5 Templates)

| ID | Circuit |
|----|---------|
| TPL_001 | Arduino + DHT22 temperature/humidity alert |
| TPL_002 | Arduino + MAX485 RS-485 Modbus RTU master |
| TPL_003 | Arduino + LED with current-limiting resistor |
| TPL_004 | RC low-pass filter |
| TPL_005 | Voltage divider |

## What This Is NOT (Phase 1)

- Not PCB auto-layout (Phase 3)
- Not live Digikey/LCSC pricing API (Phase 2)
- Not ESP32 or STM32 firmware (Phase 2+)
- Not simulation waveform graphs (Phase 2)
- Not free-form generation beyond 5 templates (Phase 2)
