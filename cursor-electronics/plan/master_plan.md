# Master Plan — Circuit OS Roadmap

> Phases 1–5. Rarely changes.
> For session-level tasks, see `plan/current_phase.md`.

---

## Phase Overview

| Phase | Name | Months | Status |
|-------|------|--------|--------|
| 1 | Hardware Copilot (5 templates, MVP) | 0–3 | 🔄 IN PROGRESS |
| 2 | Validation Engine (free-form, ESP32, live BOM) | 3–8 | ⬜ NOT STARTED |
| 3 | Industrial Layer (HVAC, RS-485, UL 508A, PCB layout) | 8–18 | ⬜ NOT STARTED |
| 4 | Enterprise Platform (SCADA RTU, Gerber, SSO) | 18–30 | ⬜ NOT STARTED |
| 5 | Advanced Hardware Intelligence (thermal, BMS, RF) | 30+ | ⬜ NOT STARTED |

---

## Phase Details

### Phase 1 — Hardware Copilot 🔄
**Target users:** Arduino hobbyists, CS/EE students, indie makers.
**Goal:** 5 circuit templates, end-to-end working, 0 crashes.

**Deliverables:**
- 5 templates: DHT22, MAX485, LED, RC filter, voltage divider
- ngspice SPICE simulation (Celery async)
- 5 hardware rule checks (floating nodes, I2C pull-ups, RS-485, PWM, voltage ratings)
- Arduino .ino firmware via Jinja2
- KiCad schematic export
- Diff-and-patch editing (patcher returns changed fields only)
- Static BOM (no live API)
- JWT auth, CORS, rate limiting
- PostgreSQL persistence

**Done when:** All Phase 1 launch checklist items checked in `rules/testing.md`.
**KPIs:** < 15s generation, ngspice within 15% of bench, 100 beta users.
**Revenue:** Free.

---

### Phase 2 — Validation Engine
**Target users:** Serious makers, IoT startup teams, freelance hardware engineers.

**Deliverables:**
- Free-form generation (beyond 5 templates, ~15 total)
- ESP32 and STM32 firmware support
- Live BOM pricing via Digikey/LCSC API (nightly cache sync — never call live)
- Design version history with timeline UI
- Qdrant RAG on 500 datasheet excerpts
- Simulation waveform viewer (Plotly.js)
- Component substitution engine

**KPIs:** 3 paying pilot teams. Average IoT node design under 45 minutes.
**Revenue:** Pro tier at $49/month.

---

### Phase 3 — Industrial Layer
**Target users:** HVAC controls companies, commercial kitchen equipment, refrigeration OEMs.

**Deliverables:**
- DCV board generation (CO2 sensor, 0–10V VFD output, RS-485 Modbus RTU, 24VAC power)
- Commercial kitchen hood controller generation
- Advanced refrigeration control (EEV stepper, superheat firmware)
- RS-485 industrial I/O with optoisolation
- UL 508A flagging and safety class enforcement
- PCB auto-layout via KiCad freerouting (2–4 layer boards)
- Private component libraries per organization
- Audit trail (ISO 13485/26262 ready)

**KPIs:** First enterprise contract. One customer prompt-to-ordered-PCB within one business day.
**Revenue:** Team tier at $99/seat/month.

---

### Phase 4 — Enterprise Platform
**Target users:** OEMs, SCADA integrators, building automation vendors.

**Deliverables:**
- Full SCADA RTU generation (Modbus RTU master + LTE-M cellular + 24VDC power)
- PLC-style control board generation
- Gerber export + JLCPCB/PCBWay API integration
- DFM report
- SSO/SAML enterprise identity
- ROI dashboard (time saved, mistakes caught per engineer)
- Fine-tuned domain model on accumulated design data

**KPIs:** $1M ARR. Average 40% prototype cycle reduction documented.
**Revenue:** Enterprise contracts, custom pricing.

---

### Phase 5 — Advanced Hardware Intelligence
**Target users:** Power electronics, RF, medical devices.

**Deliverables:**
- Thermal simulation (junction temperature analysis)
- Analog power electronics (switching supply, BMS)
- Multi-objective BOM optimization (cost vs. size vs. reliability Pareto)
- MTBF prediction
- Full data pipeline generation (board → firmware → cloud schema → dashboard spec)

---

## Guiding Principles

1. **LLM → JSON → compilers.** Never LLM → ngspice/KiCad/.ino directly.
2. One phase at a time. Don't start Phase 2 until Phase 1 launch gate passes.
3. Simulation is the physics truth. Not the LLM's opinion.
4. The explanation layer is the product. Engineers trust what they understand.
5. Breadth before depth = nothing works reliably. Finish 5 templates first.
