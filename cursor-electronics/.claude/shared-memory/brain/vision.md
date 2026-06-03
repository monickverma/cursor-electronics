# Vision — LAYER 1

> What this project is, why it exists, and what success looks like.
> Source of truth: PRODUCT_MASTER.md at project root (read that for full detail).
> This file is the agent-readable summary. Manual, rarely changes.

---

## One Sentence

> An AI hardware compiler that turns a plain English hardware description into a complete,
> validated, simulation-tested, manufacture-ready electronics design — before a single
> physical component is touched.

## One Paragraph

You are building the GCC of physical hardware. Just as a compiler takes high-level code
and produces machine-executable binary, this system takes a high-level hardware intent
and produces a physically executable design. The engineer describes what they want.
The software decides how to build it, validates with physics simulation, catches every
mistake it can find, and hands back a folder of files ready to send to a manufacturer.
No other tool does all of this in a single workflow.

---

## The Product Is NOT

- A chatbot that talks about electronics
- A smarter Google for datasheets
- A drawing tool with AI autocomplete (that is Flux.ai)
- Standalone ngspice or KiCad with AI help

It is all of those things connected under a single intelligence layer that understands intent.

---

## The Critical Differentiator

**The explanation layer is the product.** (PRODUCT_MASTER.md Part 12)

Any engineer can run ngspice. Any engineer can open KiCad.
What no tool in existence does is look at a circuit design and say:

> "I chose this component for this reason. This is what will fail if you change it.
>  This is what you need to check before ordering. Here is what I am not certain about and why."

That reasoning — applied to every component, every connection, every decision — is what
earns engineer trust. It is what turns a junior engineer into a productive one.
It is what an enterprise buyer points to when justifying the seat license.

---

## Current Phase: Phase 1 — Hardware Copilot (10/12 criteria done)

**What Phase 1 delivers:**
- 5 circuit templates (DHT22, RS-485 Modbus, LED, RC filter, voltage divider)
- ngspice physics simulation (pass/fail grade, 15% tolerance)
- 5 hardware validation rules
- Arduino `.ino` firmware (Jinja2 templates, arduino-cli verified)
- KiCad `.kicad_sch` net-label schematic
- Static BOM with part numbers
- Consequential plain-English explanation
- Diff-and-patch conversational editing (never regenerates from scratch)
- JWT auth + rate limiting + PostgreSQL persistence

**Phase 1 Launch Criteria — 10 of 12 done as of 2026-06-02:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | JWT auth — all routes protected | ✅ |
| 2 | Full generation under 30s | ✅ ~15s |
| 3 | SPICE simulation runs and grades | ✅ |
| 4 | Simulation fails on wrong values | ✅ |
| 5 | Rule engine catches hardware violations | ✅ |
| 6 | Firmware compiles to real Arduino | ✅ arduino-cli |
| 7 | 5 sequential patches — no corruption | ✅ v1→v6 |
| 8 | 20 prompts — zero crashes | ✅ |
| 9 | 100 requests — zero HTTP 500s | ✅ |
| 10 | Rate limiting — 11th request → 429 | ✅ |
| 11 | RC filter bench test (oscilloscope) | ⏳ physical |
| 12 | External engineer reads explanation cold | ⏳ human |

**Phase 1 is done when:** 11 and 12 are checked → tag v0.1.0 → begin Phase 2.

---

## The 5-Phase Roadmap Summary

| Phase | Name | What it adds |
|-------|------|-------------|
| 1 | Hardware Copilot | 5 templates, simulation, firmware, BOM, auth |
| 2 | Validation Engine | Free-form generation, ESP32/STM32, live BOM, Qdrant RAG, waveforms |
| 3 | Industrial Layer | DCV boards, HVAC, RS-485 I/O, PCB auto-layout |
| 4 | Enterprise Platform | RTU/SCADA boards, Gerber export, SSO, ROI dashboard |
| 5 | Advanced Intelligence | Thermal sim, power electronics, MTBF, data pipeline |

Full detail in `plan/master_plan.md`. Full original in `PRODUCT_MASTER.md`.

---

## User Segments

- **Phase 1:** Arduino hobbyists, CS/EE students, indie makers
- **Phase 2:** Serious makers, IoT startup teams, freelance hardware engineers ($49/mo)
- **Phase 3:** HVAC controls companies, commercial kitchen, refrigeration OEMs ($99/seat/mo)
- **Phase 4:** OEMs, SCADA integrators, building automation vendors (enterprise contracts)

---

## The Five Competitors and Why We Win

From PRODUCT_MASTER.md Part 8:

| Competitor | What they do | Our edge |
|------------|-------------|----------|
| Flux.ai | NL → PCB, firmware assistance, 750K parts | We have integrated SPICE physics simulation (their roadmap, not built). We generate complete firmware, not assistance. |
| Celus.io | Requirements → schematic, compatibility check | We prove parts work with physics. We generate firmware. We own industrial vertical. |
| Quilter | Schematic → PCB layout (physics-driven) | Not a competitor — a partner. We generate the KiCad schematic. Quilter takes it for layout. |
| Altium 365 | Enterprise PCB design, manual only | No NL input, no simulation loop, no firmware, $500+/month |
| ChatGPT/Claude | General LLM | Hallucinates circuit values, no simulation, no files, no validation |
