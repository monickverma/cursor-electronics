# Group A — AI-native "design from intent" tools
Researcher A. Read 2026-11-13 (Flux, Celus, Circuit Mind, Diode, SnapMagic homepage) and 2026-11-14 (SnapMagic products page, the category search, ProtoFlow, Trace, short entries). A spend limit interrupted the web tools on 2026-11-13; the work resumed and finished on 2026-11-14.

## Products covered (one file each)
| Product | File | Depth | One line |
|---|---|---|---|
| Flux | `flux.md` | Deepest | Browser ECAD + cloud agent; since October 2026 adds EM/SI, PDN, thermal, compiled firmware, MCP, fab ordering. Most changed since the 2026-10-21 teardown |
| CELUS | `celus.md` | Deep | Requirements → Intent Document → CUBO blocks → reference schematic + BOM into Altium/KiCad/Xpedition/OrCAD X; agentic beta cites a datasheet per part; no simulation, no layout |
| Circuit Mind | `circuit-mind.md` | Full | Block diagram → schematic options, BOM, derating, power, FMEA; new AVE reviews any schematic against datasheets; enterprise, on-prem |
| Diode Computers | `diode-computers.md` | Full | Design-as-code (Zener, MIT) → KiCad, plus in-house fabrication and assembly in Brooklyn; enterprise design service from USD 10,000 |
| SnapMagic | `snapmagic.md` | Thin, on purpose | AI product (SnapMagic Engineer, ex-Copilot) is **still waitlist-only** three years after its 2023 announcement; shipped products are parts library, datasheet-to-footprint and pricing |

## Products found and added
| Product | Decision | Why |
|---|---|---|
| **ProtoFlow** | Full file `protoflow.md` | Desktop EDA with prompt → schematic → placement and routing → ngspice → Gerbers, free tier, Git diffs, CLI/MCP. Publishes the only routing benchmark numbers in this group (vendor-run: 99/99 small and 30/30 medium PCBWorld-Bench boards KiCad-clean; a 372-connection 2-layer board at 0 DRC errors in 43 min). Directly overlaps Circuit OS's English-in, simulated-design-out pitch at USD 0–20/month |
| **Trace** (buildwithtrace, WishEDA Inc.) | Full file `trace.md` | KiCad fork: natural language → hierarchical multi-sheet schematic → multi-layer placement and routing with length tuning → Gerber/ODB++/IPC-2581 → one-click PCBWay order; CI-ready ERC/DRC. No simulation or firmware |
| **siliXon** (UK) | Short entry | Claims text prompt → schematic, part selection, layout, BOM, Gerbers. USD 1.5M seed led by System.One with Antler (TechFundingNews 2026-05-21; AtlasPCB 2026-05-23; Dealroom 2026-06-03 — all **summary**/trade press). No official website found (silixon.ai and silixon.co do not resolve); status reported as early access. Matters as a stated competitor on the exact pitch; nothing verifiable to tabulate |
| **tscircuit** | Short entry | Open source (MIT) TypeScript "framework for AI-built electronics": any agent writes the board; sub-second autorouting on 4-layer boards (claim); WebAssembly ngspice via `tsci simulate`; exports fab files, KiCad, DSN, netlists ([tscircuit.com](https://tscircuit.com/), read 2026-11-14). Matters because it gives general-purpose coding agents the same prompt-to-board path for free |
| **atopile** | Short entry | Open-source hardware-as-code "built for agents"; released EEBench (circuit-design benchmark; Claude Opus 5 reportedly leads at 61.6%) — **summary** only; homepage fetch returned only a title. Matters as the benchmark others may cite |
| **EasyEDA Pro (JLCPCB) + external agent** | Short entry | No built-in AI, but an official open-source API skill lets Claude Code or Codex place symbols, wire, place footprints, route and run ERC/DRC inside EasyEDA Pro ([JLCPCB blog](https://jlcpcb.com/blog/ai-pcb-design-easyeda), 2026-09-18, updated 2026-11-10, read). The fab's free EDA tool is now agent-drivable, one click from ordering |
| **Cherry Blossom, PCBEditor, Skimatly** | Short entries | Browser prompt-to-schematic (and, for PCBEditor and Cherry Blossom, to PCB) tools in beta or with AI from about USD 20/month; known only from ProtoFlow's comparison page (competitor-authored, reviewed 2026-10-25/26) — **summary**. Small; listed so the matrix can track them |
| **AllSpice DRCY, CADY (SiliconExpert/Altair), Cadstrom** | Pointer only | AI schematic *review* tools (voltage mismatches, swapped signals). Not design-from-intent; they belong with the review/validation group if another researcher covers it. Cadstrom returned no results under that name on 2026-11-14 (the physics report read its site earlier) |
| **Frontier LLMs driving KiCad** (Claude, Fable via MCP/skills) | Context, no file | Hacker News stories in 2026 ("AI Can Now Design Circuit Boards—For Some Problems, Anyway"; "Fable 5 designs a working PCB from a one-sentence prompt") — **summary** (search titles only). The general model plus a KiCad MCP server is the free substitute every product here competes with |

## Dropped
- **MockFlow, Cloudairy**: draw circuit *pictures* from prompts (PNG/SVG); no netlist (summary, ProtoFlow comparison page). Not hardware design.
- **JITX, Quilter, DeepPCB, Cadence Allegro X AI, Siemens Fuse, Altium AI assistant**: layout engines or incumbent features; presumed in other groups. JITX is code-first and close in spirit; flag it to the merger if no other group has it.
- **SnapMagic as a design competitor**: kept as a file but should be marked "announced, not shipped" in the matrix.

## Facts from this group that most change the competitive picture
1. **Flux now sells layout physics.** Since October 2026 Flux runs cloud full-wave EM on the routed board (S-parameters, TDR, crosstalk, eye diagrams to 20 Gbps), PDN impedance and IR drop, and thermal estimates, "in every plan" ([review](https://www.flux.ai/p/blog/pcb-design-review-without-altium-license), [SI](https://www.flux.ai/p/blog/pcb-signal-integrity-simulation-every-board)). Solver, accuracy and limits are unpublished, but the market page's "physics layout validation: only you" is now wrong twice: Flux has it as a feature and Circuit OS has none at layout level.
2. **SPICE and compiled firmware are no longer differentiators.** Flux (ngspice, also on imported Altium/Cadence boards), ProtoFlow (ngspice), tscircuit (WASM ngspice) and Diode (blog claim) all simulate; Flux compiles and unit-tests firmware for STM32, nRF, ESP32, RP2040, RISC-V and AVR ([fw](https://www.flux.ai/p/blog/embedded-unit-testing-before-hardware)). What remains unmatched in this group: **proofs over tolerance boxes, per-claim evidence grading, deterministic generation from a requirement IR with refusal, and consequential explanation** — none found anywhere in the group. Flux's own Monte Carlo story is "install LTspice on a cloud computer".
3. **The requirement-as-artifact idea has arrived elsewhere.** CELUS's agentic beta (2026-10-29) writes an Intent Document, waits for plan approval, cites a datasheet for each part and checks the design against the Intent Document; Trace and Flux have plan-approve modes. Circuit OS's IntentIR is still more rigorous (patches cite the user's words; retries may not rewrite the requirement), but "we keep the requirement" alone no longer separates it.
4. **Datasheet-grounded verification is a funded product category.** Circuit Mind's AVE (2026-10-29, with a USD 25M financing; total USD 33.4M) reviews *any* schematic against datasheets and company rules and links each finding to datasheet evidence; customers include Emerson, Schneider, BAE Systems. That breaks the market page's "only you" on voltage/current rule checks and datasheet-grounded checking, and it reaches the industrial buyers Circuit OS's Phase 3 targets.
5. **Prices fell to consumer levels and everything ends in a fab order.** ProtoFlow is free to USD 19.99/month, Trace USD 29.99, Flux's Build about USD 80 (tracker) after cutting cost per design change by about 70%; Flux, Trace, Diode and EasyEDA's agent path all go straight to quoting or ordering boards. Circuit OS has no Gerber export yet (physics report; ROADMAP Phase 4).

## Where the owner's market page is wrong, group-wide
- "SPICE: only you" — wrong (Flux, ProtoFlow, tscircuit).
- "Complete firmware: only you / Flux pin maps only" — Flux compiles drivers and tests; still not complete protocol firmware, so "partial", not "no".
- "Physics layout validation: only you" — Flux has it; Circuit OS does not.
- "Voltage/current rule checks, datasheet grounding: only you" — Circuit Mind AVE, CELUS port rules, Flux datasheet checks.
- "Component selection with justification: only you" — CELUS cites a datasheet per part.
- "Gerber + fab export / BOM live pricing" — every product in this group except Circuit Mind and SnapMagic is ahead of Circuit OS on fab outputs; Flux reads six distributors live.
- Holds as "not found" elsewhere: confidence/evidence grading per decision, consequential explanation, proofs, stateful requirement-level patching with citations, industrial RS-485 rules.
