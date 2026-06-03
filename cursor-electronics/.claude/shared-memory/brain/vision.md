# Vision — Circuit OS

---

## What is this project?

**Circuit OS** is an AI hardware compiler — a platform that turns a plain English
hardware description into a complete, validated, simulation-tested, manufacture-ready
electronics design: schematic, firmware, bill of materials, and safety analysis —
before a single physical component is touched.

---

## Why I built this

I kept hitting the same wall. I'd have a hardware idea — a sensor node, a motor
controller, a comms board — and the gap between "I know what I want" and "I have a
verified design I can order" was enormous. Writing netlists by hand. Running ngspice
separately. Debugging convergence failures for hours. Cross-checking component
datasheets. Rewriting firmware every time a pin assignment changed. Each step was
manual, isolated, and error-prone.

Every AI tool I tried either talked *about* electronics or helped with one step —
a better autocomplete for schematic editors, a chatbot that could explain a circuit,
a script to format a BOM. None of them closed the whole gap. None of them took your
intent and gave you a physics-verified, firmware-ready design you could actually order.

I wanted the GCC of physical hardware. A compiler that takes high-level human intent
and produces physically executable output — circuit, firmware, BOM, validation — in
one workflow. So I built Circuit OS.

The industrial and HVAC controls market made this even more compelling. Engineers at
HVAC companies, refrigeration OEMs, and building automation vendors spend weeks on
designs that should take hours — DCV boards, RTU controllers, refrigeration control
circuits — all variations on known patterns, all requiring the same tedious manual
process. That entire vertical is uncontested by every AI tool that exists today.
No Flux.ai. No Celus. Nobody. That's where this goes.

---

## The end goal — concrete success scenario

A controls engineer types:
> "Design a DIN-rail RTU that reads 8 Modbus RTU devices on RS-485, samples every
> 30 seconds, buffers locally, and transmits to MQTT over LTE-M. Power from 24VDC."

Within 30 seconds, Circuit OS produces:
- A validated CircuitIR (JSON, schema-checked)
- SPICE netlist → ngspice simulation confirming voltages within 15% tolerance
- `.kicad_sch` schematic viewable in browser via kicanvas
- Working firmware: Modbus RTU master polling, JSON packaging, AT-command cellular, watchdog
- BOM with manufacturer part numbers, Digikey/LCSC SKUs, and unit pricing
- Plain English explanation: *"I chose the SIM7070G because it supports both LTE-M and
  NB-IoT on a single SKU. The 2A transmit spike requires 470μF decoupling at U3 pins 4–6.
  If you swap R4 from 10kΩ to 4.7kΩ, the RS-485 bias current exceeds the MAX485 drive
  limit — simulation confirms."*

The engineer reviews, patches conversationally ("use a cheaper sensor", "run on battery"),
and orders. One session. No separate tools. No manual netlist editing.

**Phase 1 (current):** Five Arduino templates. Proves the full pipeline works end-to-end
before expanding scope to free-form generation and industrial circuits.

---

## Users

| Phase | Target user |
|-------|-------------|
| Phase 1 | Arduino hobbyists, CS/EE students, indie makers |
| Phase 2 | IoT startup engineers, freelance hardware designers |
| Phase 3 | HVAC controls companies, commercial kitchen OEMs, refrigeration engineers |
| Phase 4 | SCADA integrators, building automation vendors, industrial OEMs |

---

## Hard success criteria — Phase 1 launch gate

- [ ] 20 different prompts end-to-end — zero crashes
- [ ] TPL_001 and TPL_002 firmware compiled and flashed to a physical Arduino Uno
- [ ] Simulation correctly fails on deliberately wrong values (C=1nF in RC filter → FAIL)
- [ ] Rule engine catches missing I2C pull-up on a test IR that deliberately omits it
- [ ] 5 sequential patches to same design — no data corruption, history preserved
- [ ] Designs survive server restart (PostgreSQL persistence confirmed)
- [ ] JWT auth enforced — all design routes return 401 without token
- [ ] Generation < 15s, patch < 20s (measured)
- [ ] Rate limiting: 11th generation in one hour → 429
- [ ] ngspice within 15% of physical bench measurement on RC filter (TPL_004)
- [ ] Explanation shown to one external engineer — they understand every decision without briefing

---

## What this is NOT (Phase 1)

- Not PCB auto-layout or Gerber export (Phase 3+)
- Not live Digikey/LCSC API pricing (Phase 2)
- Not ESP32 or STM32 firmware (Phase 2+)
- Not simulation waveform graphs (Phase 2)
- Not free-form generation beyond 5 templates (Phase 2)
- Not multi-user team collaboration (Phase 3+)
