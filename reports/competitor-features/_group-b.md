# Group B: AI and automated PCB layout, and layout physics
Researcher B. Reads dated 2026-11-13 (web) and checked for completeness 2026-11-14. Schema, labels and file format as in the shared brief.

## Products covered (full files)

| Product | File | Rows | read | summary | not found | inference | checked (carried from the 2026-10-16 report) |
|---|---|---|---|---|---|---|---|
| Quilter | `quilter.md` | 60 | 44 | 2 | 12 | 2 | 0 |
| DeepPCB (InstaDeep) | `deeppcb.md` | 60 | 31 | 1 | 23 | 5 | 0 |
| Cadence Allegro X AI / OrCAD X / AuraStack | `cadence-allegro-orcad-x.md` | 60 | 4 | 30 | 22 | 1 | 3 |
| Siemens Xpedition / PADS / HyperLynx / Valor / Fuse | `siemens-xpedition-pads.md` | 60 | 36 | 9 | 11 | 1 | 3 |
| Zuken CR-8000 with AIPR | `zuken-cr-8000.md` | 60 | 29 | 9 | 21 | 1 | 0 |
| Freerouting (open baseline) | `freerouting.md` | 43 lines covering all 60 (schematic, firmware, supply-chain and domain rows grouped as out of scope) | 29 | 0 | 5 | 9 | 0 |

Cadence is mostly summary because cadence.com and community.cadence.com returned HTTP 403 to the fetch tool. Its licensing facts come from search snippets of Cadence FAQs and reseller pages.

## Products found and added (short entries)

| Product | What it is | Why it matters, or not | Decision |
|---|---|---|---|
| **General-purpose LLM agents doing layout** (OpenAI "GPT-6 Astra" demo, Sept 2026; Claude Code in EasyEDA Pro) | Frontier models driving KiCad or EasyEDA Pro through computer use or the tool's API | **Matters most of the additions.** NextPCB found that Astra's KiCad layout demo routed through **Freerouting** (DSN → Freerouting → SES); routing through the GUI alone made three trace segments in an hour ([NextPCB](https://www.nextpcb.com/blog/gpt-6-astra-kicad-pcb-routing-test), read). JLCPCB had Astra design a 2-layer, 40-part TPA3116D2 amplifier in EasyEDA Pro 3.2.149 with Freerouting 2.0.1 and KiCad 10.0.4, ending at 0 DRC violations, not fabricated ([JLCPCB, 2026-09-15](https://jlcpcb.com/blog/gpt-6-astra-pcb-design-in-easyeda-pro), read). This is the same architecture Circuit OS plans (a model orchestrating deterministic tools), now available to anyone with a frontier model. The difference has to be the verification, not the orchestration | Short entry here; the owner may want a full file |
| **Freerouting as an agent service** | v2.3-2.5 (2026) added MCP, A2A, `POST /v1/autoroute`, JSON DRC | It is now the default router for LLM agents. Circuit OS plans the same integration | Covered in `freerouting.md` |
| **PCBWorld / PCBWorld-Bench** (LG AI Research, arXiv 2607.05915) | Open KiCad environment and routing benchmark: 679 real boards, 8 engine-checked metrics | It is a public yardstick that Circuit OS's router could be scored on; DeepPCB already cites it | Short entry in `freerouting.md` |
| **ProtoFlow** | Free desktop app: plain English → editable schematic with LCSC/DigiKey/Mouser parts → own autorouter or KiCad export; says it does no SI ([protoflow.ai](https://www.protoflow.ai/compare/ai-pcb-routing-companies), read) | English in, board out: nearer to Circuit OS's front end than any layout tool in this group. Only its own comparison page was read | Hand to the group covering prompt-to-schematic tools (A or C) for a full file |
| **EasyEDA Pro (JLCPCB)** | Classical autorouter (vendor: 1,000 components in 20 min, ≥90% completion, ≤10 DRC errors) plus a public API that agents drive ([EasyEDA docs](https://prodocs.easyeda.com/en/pcb/route-auto-routing/), summary) | A fab house's free tool that agents already use for layout. No native AI layout announced | Short entry only |
| **Altium ML router / ActiveRoute** | AtlasPCB calls Altium's router "machine-learning"; Quilter's blog calls ActiveRoute guided interactive routing | Altium belongs to another group. A July 2026 review found no shipped AI features in Altium (`Generative EDA tool feature spec.md`), which conflicts with AtlasPCB | Dropped here; flagged to Altium's owner |
| **Flux AI Auto-Layout, JITX router, tscircuit autorouter** | AI or solver layout inside prompt- or code-first tools | Covered by other groups | Dropped here |
| **Cadstrom, CircuitMind, Celus** | Design review, or schematic and BOM generation | Not layout. Celus also powers Siemens' schematic front end (see the Siemens file) | Dropped here |
| **AtlasPCB "landscape" articles** | A PCB maker's blog with tool roundups | Unreliable: claims (Quilter "10-30 minutes", Siemens "EMC prediction", 55% completion) are unsourced and some contradict primary pages | Not used as a source except where labelled |

No funded AI-layout startup newer than Quilter or DeepPCB was found in 2026 searches, nor any 2026 seed round in this niche (searched 2026-11-13; absence only).

## Facts from this group that most change the competitive picture

1. **"Physics layout validation" splits three ways, and the AI tool doing the most layout does the least physics.** Quilter computes impedance geometry (Simbeor 2D quasi-static, <6 GHz), sets IPC-2221 widths, runs 8 geometric PRCs and a **beta** DC IR drop. Its docs still make "signal simulation and validation" the user's job. Real physics simulation (AC PDN impedance, SI, thermal FEA/CFD, full-wave) is sold by Siemens (HyperLynx) and Cadence (Sigrity X, Celsius, Clarity), mostly as **separate licences**. In OrCAD X only impedance and coupling are included; IR drop needs Sigrity X Aurora. On Xpedition Standard, HyperLynx SI comes as paid tokens. The owner's "best-in-class physics" cell for Quilter is wrong. No product, AI or incumbent, closes the loop from simulation back to the layout in shipped form: Cadence AuraStack and Siemens Fuse both *announce* it for 2026 without a ship date.
2. **Creepage is now an incumbent check, and still absent from every AI layout tool.** Xpedition 2604 (April 2026) checks creepage in the layout editor, and HyperLynx has a Creepage Wizard. Quilter states it cannot handle creepage, dielectric breakdown or arcing, and caps itself at 48 V. DeepPCB and Zuken AIPR do not mention it. Creepage derived from voltage and insulation class remains an open lane for Circuit OS's mains relay board. Whether Siemens derives the distance or takes it from the user was not established.
3. **The Quilter target has not moved since 30 September, but its enterprise posture has.** No changelog entry after 2026-09-30 was found. In 2026 it gained SOC 2 Type II (March), a self-hosted Helm deployment with air-gap support, GovCloud, native Xpedition and Cadence schematic input, any differential impedance, BGA fanout, and Eric Bogatin as Technical Fellow (September), which signals SI/PI work ahead. It still has no API, no schematic, through-vias only, and no published price.
4. **Freerouting became an agent-ready service in 2026, and frontier LLMs already use it.** v2.5.0 (5 October 2026) has a REST and MCP single-call autoroute, a JSON DRC and native executables. The publicised GPT-6 Astra layout demo routed through it. "AI does PCB layout" now often means "an LLM calls Freerouting". Circuit OS's planned Freerouting integration gives it the same routing as everyone, so its differentiation has to be intent-derived constraints and verification.
5. **Voltage-aware schematic checking is not unique, and Siemens has had it for years.** Xpedition Schematic Analysis has 150+ voltage-aware rules on MPN-derived models, and Zuken Design Gateway checks power-IC voltage standards. What none of them claims is proof over tolerance ranges, a graded per-claim report, or refusal: those remain Circuit OS's distinct rows.

## What could not be verified in this group

- cadence.com pages (403): Allegro X AI licensing, any 2026 OrCAD X / Allegro X release notes, AuraStack shipping status.
- Quilter: the DC IR solver, Gerber output, free-tier limits, Zuken/EasyEDA support (pages unreadable), and whether the FAQ still says "detailed physics simulations".
- DeepPCB: placement product details, plugin licence, certifications.
- Siemens: full Xpedition 2610 notes; whether Fuse PCB features have shipped; how creepage distance is set.
- Zuken: whether AI placement shipped in 2026 (release text and AI page disagree); 2026 AIPR price.
- Freerouting: layer ceiling, diff-pair support, the corpus behind the 75.0% figure.
