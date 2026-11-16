# Embedder — feature inventory
Read 2026-11-13 (site, YC page) and 2026-11-14 (docs, pricing). Vendor: Embedder (YC S25, San Francisco, founded 2025, team of 6 per YC) · Latest release found: no dated release on pages read · Earlier teardown: none

## Added because

Embedder is the firmware-from-hardware product nearest to Circuit OS's firmware row. It reads datasheets **and the schematic**, writes drivers that match the board's pin muxing, pull-ups and bus addresses, then builds, flashes and tests on real hardware in a closed loop until the tests pass ([home], [yc], [docs]). Circuit OS generates firmware from templates and shows it only once it compiles. Embedder goes further, to flashing and observing, but its code is LLM-written.

## In one paragraph

Embedder is an "autonomous firmware engineer", delivered as a VS Code extension (and forks), a terminal UI and headless GitHub and Slack automation ([docs]). It takes datasheets, reference manuals, errata, register maps, schematics or netlists (Altium, KiCad, EDIF; Xpedition, PADS, Eagle and EasyEDA on Enterprise) and live lab data (serial, GDB, logic analyser, oscilloscope, power profiler). It drafts implementation plans that cite the manual, writes part-specific drivers and test cases, and runs build, flash, test and fix on real probes ([home], [pricing]). Structured data on its site claims 600+ platforms, 14 manufacturers and 5,800+ peripherals, with FreeRTOS, Zephyr and ThreadX ([home]). Its guarantee is **empirical**: the build succeeds and the hardware tests pass on the user's bench. It does not design circuits.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | NL prompt | Yes (firmware) | Agent chat with Plan, Act, Debug modes; no circuit design | read | [docs] |
| A2 | Structured spec input | Partial | Datasheets, register maps, schematics as inputs; no requirement schema | read | [home] |
| A3 | Design as code | No | Writes C/C++ firmware, not hardware descriptions | read | [home] |
| A4 | Imports existing designs | Yes | Schematics: Altium, KiCad, EDIF (Startup); Xpedition, PADS, Eagle, EasyEDA (Enterprise) | read | [pricing] |
| A5 | Requirement as own artifact | Partial | Implementation plans "drafted from your datasheet and schematic, with citations to the manual" | read | [home] |
| A6 | Clarifying questions / refusal | Partial | Asks before editing files or touching hardware | read | [docs] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic | No | Reads schematics | read | [home] |
| B2 | AI copilot in schematic | No | — | read (scope) | [home] |
| B3 | Part selection | No | — | read (scope) | [home] |
| B4 | Reusable modules | Partial | Hardware catalogue of boards and MCUs | read | [docs] |
| B5 | ERC | No | — | read (scope) | [home] |
| B6 | Hierarchy | No | — | read (scope) | [home] |
| B7 | Library | Partial | "600+ platforms, 14 manufacturers, 5,800+ peripherals" (site structured data, not page body) | read (structured data) | [home] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | No | — | read (scope) | [home] |
| C2 | Tolerance | No | — | read (scope) | [home] |
| C3 | Formal proof | Not found | — | not found | [home] |
| C4–C8 | SI, PI, thermal, EMC, creepage | No | Firmware product | read (scope) | [home] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1–D8 | Placement, routing, constraints, stackup, DRC, 3D, length tuning, HDI | No | Firmware product | read (scope) | [home] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Yes | Part-specific drivers, test cases, source patches when tests fail | read | [home] |
| E2 | Pin-mux / peripheral config | Yes | Drivers "match your board's pin muxing, pull-ups, and bus addresses" read from the schematic | read | [home] |
| E3 | Compiles / tests before showing | Yes (empirically) | Build → flash → serial output check; closed loop of build, flash, test, fix on real probes; each edit accepted or rejected by the user | read | [docs], [home] |
| E4 | Protocol stacks | Partial | Driver families: I2C, SPI, UART, CAN, CAN-FD, USB, Ethernet, BLE; RTOS: FreeRTOS, Zephyr, ThreadX (structured data); Modbus not found | read (structured data) | [home] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Partial | Plans cite the manual | read | [home] |
| F2 | Evidence grading | Partial | Pass/fail from hardware tests, merged across parallel agents | read | [home] |
| F3 | Automated design review | No | — | read (scope) | [home] |
| F4 | Datasheet-grounded (cited) | Partial | "Citations to the manual" in plans; docs do not describe citation format | read | [home], [docs] |
| F5 | Audit trail | Partial | Per-edit review (`/review-edits`); approval before programming | read | [docs] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Agent chat | read | [docs] |
| G2 | Version history | Partial | Works in the user's repo (inference); GitHub automation | inference from [docs] | [docs] |
| G3 | Comments / roles | Partial | Shared lab benches and HIL racks across teams ("Bridges") | read | [home] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1–H6 | BOM, pricing, alternates, fab outputs, DFM, ordering | No | Firmware product | read (scope) | [home] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | VS Code extension (≥1.106; Cursor, Windsurf), terminal UI | read | [docs] |
| I2 | API / headless | Yes | Headless automation for GitHub and Slack | read | [docs] |
| I3 | On-prem / certifications | Yes | Managed SaaS, VPC, on-prem, air-gapped; SOC 2 Type II and ISO 27001 claimed | read | [home], [pricing] |
| I4 | Pricing | Partial | Free (non-commercial, limited credits); Startup custom (≤5 seats, <25 staff and <$10M raised); Enterprise custom; student program 5 seats + $2,500 usage. Read 2026-11-14 | read | [pricing] |
| I5 | Who it is sold to | — | Embedded teams; startups and enterprises | read | [pricing] |
| I6 | Company facts | — | YC S25, founded 2025, 6 people, founders Ethan Gibbs (CEO), Bob Wei (CTO); funding not found; chip-vendor logos only | read | [yc] |
| I7 | Interop | Partial | Reads Altium/KiCad/EDIF and other schematics | read | [pricing] |
| I8 | Open source | No | — | inference (SaaS) | [pricing] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Partial | CAN / CAN-FD drivers; RS-485 / Modbus not found | read (structured data) | [home] |
| J2 | Power electronics | Not found | — | not found | [home] |
| J3 | RF / high-speed | Partial | BLE, Ethernet, USB drivers | read (structured data) | [home] |
| J4 | Safety / regulatory | Not found | — | not found | [home] |
| J5 | Stated limits | Partial | Free plan: select platforms and models, non-commercial | read | [pricing] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Embedder ahead on firmware:** any MCU in a large catalogue, RTOS support, drivers fitted to a real schematic, and tests run on real hardware. Circuit OS firmware covers three boards (Uno, ESP32-DevKitC, Black Pill) and template-generated behaviour, and its gate is compilation, not hardware execution (`.claude/CLAUDE.md`, `firmware/compile_gate.py`; no WiFi/BLE).
- **Circuit OS ahead:** its firmware is deterministic (Jinja2 templates; same input gives the same output) and derived from the same IR as the circuit, so pins come from the wiring by construction (`.claude/CLAUDE.md`, `firmware/arduino.py`). Embedder's is LLM-written and correct as far as the tests go. Circuit OS also designs and verifies the circuit.

## Not verified

- The supported build systems and the HIL rig list.
- How citations are presented.
- Funding.

[home]: https://embedder.com/
[docs]: https://docs.embedder.com/
[pricing]: https://embedder.com/pricing
[yc]: https://www.ycombinator.com/companies/embedder
