# Master Plan — Circuit OS

> Strategic roadmap. 5 phases. Rarely changes.
> For session-level tasks, see plan/current_phase.md.

---

## Phase Overview

| Phase | Name | Timeline | Status |
|-------|------|----------|--------|
| 1 | Hardware Copilot — 5 templates, MVP | Months 0–3 | 🔄 IN PROGRESS |
| 2 | Validation Engine — free-form, ESP32, live BOM | Months 3–8 | ⬜ NOT STARTED |
| 3 | Industrial Layer — HVAC, RS-485, UL 508A, PCB | Months 8–18 | ⬜ NOT STARTED |
| 4 | Enterprise Platform — SCADA RTU, Gerber, SSO | Months 18–30 | ⬜ NOT STARTED |
| 5 | Advanced Intelligence — thermal, BMS, RF | Months 30+ | ⬜ NOT STARTED |

---

## Phase 1 — Hardware Copilot 🔄

**Target users:** Arduino hobbyists, CS/EE students, indie makers.

**Deliverables:**
- 5 circuit templates (DHT22, MAX485, LED, RC filter, voltage divider)
- ngspice SPICE simulation via Celery
- 5 hardware rule checks
- Arduino .ino firmware via Jinja2 templates
- KiCad schematic export (net labels)
- Diff-and-patch editing (changed fields only)
- Static BOM — no live pricing API
- JWT auth, CORS, slowapi rate limiting
- PostgreSQL persistence

**Done when:** All Phase 1 launch checklist items in `.claude/rules/testing.md` checked.
**KPIs:** < 15s generation; ngspice within 15% of bench; 100 beta users.
**Revenue:** Free.

---

## Phase 2 — Validation Engine

**Target users:** Serious makers, IoT startup teams, freelance hardware engineers.

**Deliverables:**
- Free-form circuit generation (15 total templates)
- ESP32 and STM32 firmware support
- Live BOM via Digikey/LCSC API (nightly cache — never call live)
- Design version history with timeline UI
- Qdrant RAG on 500 datasheet excerpts
- Simulation waveform viewer (Plotly.js)
- Component substitution engine

**KPIs:** 3 paying pilot teams. Average IoT node design < 45 min. BOM accuracy within 5%.
**Revenue:** Pro tier — $49/month.

---

## Phase 3 — Industrial Layer

**Target users:** HVAC controls companies, commercial kitchen equipment, refrigeration OEMs.

**Deliverables:**
- DCV board (CO2 sensor → 0–10V VFD output, RS-485 Modbus RTU, 24VAC power)
- Commercial kitchen hood controller
- Advanced refrigeration control (EEV stepper, superheat firmware)
- UL 508A flagging and safety class enforcement
- PCB auto-layout via KiCad freerouting (2–4 layer)
- Private component libraries per organization
- Audit trail (ISO 13485/26262 ready)

**KPIs:** First enterprise contract. Prompt → ordered PCB within one business day.
**Revenue:** Team tier — $99/seat/month.

---

## Phase 4 — Enterprise Platform

**Target users:** OEMs, SCADA integrators, building automation vendors.

**Deliverables:**
- Full SCADA RTU board (Modbus RTU master + LTE-M cellular + 24VDC industrial power)
- PLC-style control board generation
- Gerber export + JLCPCB/PCBWay API integration
- DFM report
- SSO/SAML enterprise identity
- ROI dashboard (time saved, mistakes caught)
- Fine-tuned domain model on accumulated design data

**KPIs:** $1M ARR. 40% prototype cycle reduction documented.
**Revenue:** Enterprise contracts.

---

## Phase 5 — Advanced Hardware Intelligence

**Deliverables:**
- Thermal simulation (junction temperature)
- Analog power electronics (switching supply, BMS)
- Multi-objective BOM optimization (cost vs. size vs. reliability)
- MTBF prediction
- Full data pipeline generation (board → firmware → cloud schema → dashboard)

---

## Guiding Principles

1. LLM → JSON → compilers. Never LLM → ngspice/KiCad/.ino directly.
2. One phase at a time. Phase 2 only after Phase 1 launch gate.
3. Simulation is physics truth — not the LLM's opinion.
4. The explanation layer is the product. Trust requires evidence.
5. 5 templates that work 100% beat 20 that work 60%.
