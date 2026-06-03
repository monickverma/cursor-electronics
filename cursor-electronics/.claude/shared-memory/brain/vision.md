# Vision — Circuit OS

> What this project is, why it exists, and what success looks like.
> Manual, rarely changes. Read by every session.

---

## What is this project?

**Circuit OS** — an AI hardware compiler that turns a plain English hardware
description into a complete, validated, simulation-tested, manufacture-ready
electronics design: schematic, firmware, BOM, and safety analysis — before a
single physical component is touched.

## Why does it exist?

The gap between "I want to build X" and a verified, orderable board is filled
with manual work: selecting components, writing netlists, running simulators,
debugging convergence, cross-checking values. Every other AI tool either talks
*about* electronics or assists one step of the process. Circuit OS closes the
entire gap in one workflow.

**The GCC of physical hardware.** Just as a compiler takes high-level source code
and produces executable binary, Circuit OS takes a high-level hardware intent and
produces a physically executable design.

## End goal — concrete success scenario

User types:
> "Arduino + DHT22 temperature sensor, alert LED when temp exceeds 40°C"

System produces in under 30 seconds:
- Validated CircuitIR (JSON schema)
- SPICE netlist → ngspice simulation confirming voltages within 15% tolerance
- `.kicad_sch` schematic viewable in browser via kicanvas
- `.ino` firmware ready to flash
- BOM with part numbers and static pricing
- Plain English explanation: *"I chose DHT22 because… If you change R3 from 10kΩ
  to 4.7kΩ, LED current hits 42mA, exceeding the ATmega328P GPIO sink limit.
  Simulation confirms."*

## The Fundamental Rule

**The LLM never writes SPICE, KiCad, or .ino directly.**
LLM → JSON (validated IR schema) → deterministic compilers → all downstream formats.
This eliminates hallucinated circuit values.

## Hard success criteria — Phase 1 launch gate

- [ ] 20 different prompts tested end-to-end, zero crashes
- [ ] Firmware for TPL_001 and TPL_002 compiled and flashed to physical Arduino
- [ ] Simulation correctly fails on deliberately wrong component values
- [ ] Rule engine catches missing I2C pull-up on a test IR that omits it
- [ ] 5 sequential patches to same design — no data corruption
- [ ] Designs survive server restart (PostgreSQL persistence confirmed)
- [ ] JWT auth working — all design routes 401 without token
- [ ] Generation < 15s, patch < 20s (measured)
- [ ] Rate limiting: 11th generation in one hour → 429
- [ ] ngspice within 15% of bench measurement on RC filter

## Phase 1 — five supported circuit templates

| ID | Circuit |
|----|---------|
| TPL_001 | Arduino + DHT22 temperature/humidity alert |
| TPL_002 | Arduino + MAX485 RS-485 Modbus RTU master |
| TPL_003 | Arduino + LED with current-limiting resistor |
| TPL_004 | RC low-pass filter (calculated cutoff) |
| TPL_005 | Voltage divider (calculated output) |

## Users

- Arduino hobbyists, CS/EE students, indie makers (Phase 1)
- IoT startup teams, freelance hardware engineers (Phase 2)
- HVAC controls companies, refrigeration OEMs (Phase 3)
- SCADA integrators, building automation vendors (Phase 4)

## What this is NOT (Phase 1)

- Not PCB auto-layout (Phase 3)
- Not live Digikey/LCSC pricing API (Phase 2)
- Not ESP32 or STM32 firmware (Phase 2+)
- Not simulation waveform graphs (Phase 2)
- Not free-form generation beyond 5 templates (Phase 2)
