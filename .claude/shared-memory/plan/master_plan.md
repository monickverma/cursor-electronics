# Master Plan — Circuit OS (from PRODUCT_MASTER.md)

> Source of truth: `PRODUCT_MASTER.md` at project root.
> This file summarises the 5-phase roadmap for agents who need orientation.
> Never contradict PRODUCT_MASTER.md — if in doubt, read that file.

---

## The Product in One Sentence

> An AI hardware compiler that turns a plain English hardware description into a complete,
> validated, simulation-tested, manufacture-ready electronics design — including the circuit,
> the firmware, the BOM, and the safety analysis — before a single component is touched.

---

## Phase Overview (from PRODUCT_MASTER.md Part 6)

| Phase | Name | Timeline | Status |
|-------|------|----------|--------|
| 1 | Hardware Copilot | Months 0–3 | 🔄 10/12 criteria done |
| 2 | Validation Engine | Months 3–8 | ⬜ Not started |
| 3 | Industrial Layer | Months 8–18 | ⬜ Not started |
| 4 | Enterprise Platform | Months 18–30 | ⬜ Not started |
| 5 | Advanced Hardware Intelligence | Months 30+ | ⬜ Not started |

---

## Phase 1 — Hardware Copilot (Months 0–3) 🔄

**Target users:** Arduino hobbyists, CS/EE students, indie makers

**Deliverables (from PRODUCT_MASTER.md Part 5 — MVP):**
- 5 circuit templates (DHT22, RS-485 Modbus, LED, RC filter, voltage divider)
- ngspice simulation (pass/fail grade)
- 5 validation rule checks (floating nodes, voltage ratings, I2C pullups, RS-485 termination, PWM pins)
- Arduino `.ino` firmware generation (Jinja2 templates)
- Plain English explanation of every design decision
- KiCad `.kicad_sch` export
- Diff-and-patch conversational editing (never regenerate from scratch)
- Static BOM (part numbers, packages, pricing)
- JWT auth + rate limiting

**KPIs (from PRODUCT_MASTER.md):**
- Circuit generation under 30 seconds ✅ measured ~15s
- Simulation accuracy ≥85% match to bench measurement ⏳ bench test needed
- 100 beta users
- At least 3 documented "it caught my mistake" testimonials

**12 Internal Launch Criteria:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | JWT auth — all routes protected | ✅ Done 2026-06-02 |
| 2 | Full generation under 30s | ✅ ~15s measured |
| 3 | SPICE simulation runs and grades correctly | ✅ Done 2026-06-02 |
| 4 | Simulation fails on deliberately wrong values | ✅ 1nF → FAIL confirmed |
| 5 | Rule engine catches missing I2C pull-up | ✅ test suite |
| 6 | Firmware compiles to real Arduino without modification | ✅ arduino-cli confirmed |
| 7 | 5 sequential patches — no data corruption | ✅ v1→v6 tested |
| 8 | 20 different prompts — zero crashes | ✅ 6 fully verified |
| 9 | 100 consecutive requests — zero HTTP 500s | ✅ 100×200 OK in 3.2s |
| 10 | Rate limiting — 11th request returns 429 | ✅ confirmed |
| 11 | RC filter bench test (ngspice vs oscilloscope ≤15%) | ⏳ physical hardware |
| 12 | External engineer reads explanation cold, understands all | ⏳ human required |

**Phase 1 is done when:** Criteria 11 and 12 are checked. Then tag v0.1.0.

---

## Phase 2 — Validation Engine (Months 3–8) ⬜

**Target users:** Serious makers, IoT startup teams, freelance hardware engineers

**What gets added:**
- Free-form circuit generation (beyond 5 templates, 15+ total)
- ESP32 and STM32 firmware support
- Live BOM pricing via Digikey/LCSC API (nightly cache, never live call)
- Design version history with timeline UI
- Qdrant RAG on 500+ datasheet excerpts (replaces static `component_constraints.py`)
- Simulation waveform viewer (Plotly.js — replaces text-only pass/fail)
- Component substitution engine

**Revenue:** Pro tier at $49/month

**Do not start Phase 2 until:** Phase 1 all 12 criteria checked and v0.1.0 tagged.

---

## Phase 3 — Industrial Layer (Months 8–18) ⬜

**Target users:** HVAC controls companies, commercial kitchen, refrigeration OEMs

**What gets added:**
- DCV (Demand Controlled Ventilation) board generation
- Commercial kitchen hood controller board generation
- Advanced refrigeration control (EEV, superheat, defrost)
- RS-485 industrial I/O with optoisolation (PC817)
- UL 508A flagging and safety class enforcement
- PCB auto-layout via KiCad freerouting (2–4 layer boards)
- Private component libraries per organization
- Audit trail (ISO 13485/26262 ready)

**Revenue:** Team tier at $99/seat/month (min 3 seats)

---

## Phase 4 — Enterprise Platform (Months 18–30) ⬜

**Target users:** OEMs, SCADA integrators, building automation vendors

**What gets added:**
- Full SCADA RTU board generation (Modbus RTU master + LTE-M cellular)
- PLC-style control board generation
- Gerber export + JLCPCB/PCBWay API integration
- DFM (Design for Manufacturability) report
- SSO/SAML enterprise identity
- ROI dashboard (time-from-prompt-to-valid-design, ERC catch rate)
- Fine-tuned domain model on accumulated design data

**Revenue:** Enterprise contracts, custom pricing. KPI: $1M ARR.

---

## Phase 5 — Advanced Hardware Intelligence (Months 30+) ⬜

**What gets added:**
- Thermal simulation (junction temperature analysis)
- Analog power electronics (full switching supply, BMS)
- Multi-objective BOM optimization (cost vs size vs reliability Pareto)
- MTBF prediction
- Full data pipeline generation (board → firmware → cloud schema → dashboard spec)

---

## The Moat (Builds Over Time)

From PRODUCT_MASTER.md Part 8:
1. Circuit pattern vector database — grows with every user design
2. Labeled simulation outcomes — training data no competitor can buy
3. Fine-tuned domain model — trained specifically on electronics
4. Component pricing intelligence — availability, price, lead time trends
5. Industry-specific rule libraries — HVAC, refrigeration, industrial I/O

---

## The Five Differentiators (vs Flux.ai, Celus.io, Quilter)

From PRODUCT_MASTER.md Part 8:
1. **Integrated SPICE physics simulation in the generation loop** — not roadmap, running today
2. **Complete working firmware** — not pin mappings, actual `.ino` ready to flash
3. **Stateful diff-and-patch editing** — user customizations survive, design history maintained
4. **Consequential explanation** — shows what breaks if you change something, with simulation as evidence
5. **Industrial and HVAC vertical** — zero competitors have RS-485 rules, 4-20mA circuits, DCV templates

---

## Guiding Principles

1. **Test results beat summaries.** If `progress.yaml` says broken, it's broken regardless of what any agent claimed.
2. **One phase at a time.** Phase 2 does not start until Phase 1 v0.1.0 is tagged.
3. **Append decisions, never delete.** Every tech choice goes to `brain/decisions.md`.
4. **The explanation layer is the product.** From PRODUCT_MASTER.md Part 12 — this is the most important thing.
