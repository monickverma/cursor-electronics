# Master Plan — Circuit OS

> Five phases from hobbyist MVP to enterprise platform.
> Update phase status when a phase completes. Don't add scope to a phase that's in progress.

---

## Phase Overview

| Phase | Name | Timeline | Revenue | Status |
|-------|------|----------|---------|--------|
| 1 | Hardware Copilot | Months 0–3 | Free | 🔄 IN PROGRESS |
| 2 | Validation Engine | Months 3–8 | $49/mo Pro | ⬜ NOT STARTED |
| 3 | Industrial Layer | Months 8–18 | $99/seat/mo Team | ⬜ NOT STARTED |
| 4 | Enterprise Platform | Months 18–30 | Custom Enterprise | ⬜ NOT STARTED |
| 5 | Advanced Intelligence | Months 30+ | Platform fees | ⬜ NOT STARTED |

---

## Phase 1 — Hardware Copilot 🔄

**Target users:** Arduino hobbyists, CS/EE students, indie makers.

**What it does:** Takes a plain English prompt → validates → simulates → produces
schematic, firmware, BOM, and explanation. Five circuit templates only. Free.

**Five templates:**
| ID | Circuit |
|----|---------|
| TPL_001 | Arduino + DHT22 temperature/humidity with alert LED |
| TPL_002 | Arduino + MAX485 RS-485 Modbus RTU master |
| TPL_003 | Arduino + LED with current-limiting resistor |
| TPL_004 | RC low-pass filter (calculated cutoff) |
| TPL_005 | Voltage divider (calculated output) |

**What is built:** FastAPI backend, Celery simulation queue, full IR pipeline,
all 4 compilers (SPICE, firmware, KiCad, BOM), 5 validation rules, JWT auth,
rate limiting, PostgreSQL persistence, Next.js frontend with kicanvas viewer.
177 tests passing.

**Done when:** All Phase 1 launch gate criteria in brain/vision.md are checked.

**KPIs:** Generation < 15s · ngspice ±15% of bench · 100 beta users · zero 500 errors in 100-request load test.

---

## Phase 2 — Validation Engine

**Target users:** Serious makers, IoT startup teams, freelance hardware engineers.

**Key additions:**
- Free-form circuit generation (beyond templates, targeting ~15 circuit types)
- ESP32 and STM32 firmware support
- Live BOM pricing via Digikey/LCSC API (nightly cache sync — never call live in-request)
- Design version history with timeline UI
- Qdrant RAG on 500 datasheet excerpts (replaces static component_constraints.py)
- Simulation waveform viewer (Plotly.js)
- Component substitution engine ("use a cheaper sensor")

**KPIs:** 3 paying pilot teams · avg IoT node design < 45 min · BOM accuracy ±5%.

---

## Phase 3 — Industrial Layer

**Target users:** HVAC controls companies, commercial kitchen OEMs, refrigeration engineers.

**Key additions:**
- DCV (Demand Controlled Ventilation) board template: CO2 sensor, 0–10V VFD output,
  RS-485 Modbus RTU, 24VAC-to-3.3V power supply, fail-safe logic
- Commercial kitchen hood controller template (duct temp, UV sensor, Ansul interlock,
  gas valve relay, VFD fan control)
- Advanced refrigeration control (NTC/PT100 inputs, EEV stepper via DRV8825,
  superheat calculation firmware, Modbus rack controller integration)
- UL 508A flagging and life-safety rule enforcement
- PCB auto-layout via KiCad freerouting (2–4 layer boards)
- Private component libraries per organization
- Audit trail suitable for ISO 13485 / IEC 26262

**KPIs:** First enterprise contract signed · prompt-to-ordered-PCB within one business day.

---

## Phase 4 — Enterprise Platform

**Target users:** SCADA integrators, building automation vendors, OEMs.

**Key additions:**
- Full SCADA RTU generation: Modbus RTU master + LTE-M cellular (SIM7070G) + 24VDC
  industrial power (TPS54360 buck), 4–20mA analog inputs, optoisolated digital I/O
- PLC-style control board generation (24VDC DI/DO, Modbus slave, watchdog)
- Gerber export + JLCPCB/PCBWay API integration
- DFM (Design for Manufacturability) report
- SSO / SAML enterprise identity
- ROI dashboard (time saved, mistakes caught — the renewal conversation)
- Fine-tuned domain model trained on accumulated design data

**KPIs:** $1M ARR · avg 40% prototype cycle reduction documented.

---

## Phase 5 — Advanced Hardware Intelligence

**Key additions:**
- Thermal simulation (junction temperature, thermal resistance modeling)
- Analog power electronics (full switching supply design, BMS circuits)
- Multi-objective BOM optimization (cost vs. size vs. reliability Pareto front)
- MTBF prediction
- Full data pipeline generation: board → firmware → cloud schema → dashboard config

---

## What Will Never Be in Scope

- Visual schematic editor (that's KiCad — use Quilter for layout)
- Real-time collaboration (Google Docs for schematics — out of scope)
- Replacing a full EDA tool — Circuit OS generates the starting point, engineers finish it

---

## Guiding Principles

1. **LLM → JSON → compilers.** Never LLM → ngspice/KiCad/.ino directly.
2. One phase at a time. Phase 2 starts only after Phase 1 launch gate is done.
3. Physics truth > LLM opinion. Simulation corrects the design, not the human.
4. The explanation layer is the product. Trust requires evidence, not just output.
5. Breadth before depth = nothing works reliably. Finish 5 templates before adding a 6th.
