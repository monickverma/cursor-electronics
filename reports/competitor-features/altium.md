# Altium (Altium Designer, Altium 365, Develop / Agile) — feature inventory
Read 2026-11-13. Vendor: Altium LLC, a wholly owned subsidiary of Renesas Electronics · Latest release found: Altium Designer 26.11.1 (14 October 2026) · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\altium.md` (2026-10-21), plus the Altium section of `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report")

## In one paragraph

Altium is the incumbent professional PCB suite: Altium Designer (Windows desktop) plus Altium 365 (cloud workspace for versioning, reviews, BOM, requirements, manufacturing hand-off). Since 2025 it is sold as **Altium Develop** (one author seat plus a workspace; small teams) and **Altium Agile Teams / Agile Enterprise** (quote only; co-authoring, workflows, PLM, governance). It is bought by professional hardware teams. It automates the *mechanics* of design — rules-driven routing, a topological autorouter (Situs), guided routing (ActiveRoute), built-in SPICE (with Monte Carlo), a built-in reflection/crosstalk SI simulator and impedance solver, Output Jobs, live supply-chain data — but **the engineer still draws the schematic, picks the parts and places the board**. Its only shipped AI (since 2026) works on **requirements text**, not on the schematic or layout: an Engineering Assistant and an AI-assisted importer inside the Requirements Portal, with every change awaiting human approval. Official MCP servers for Altium Designer and Altium 365 are listed as "Coming Soon".

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No (for designs) / Partial (for requirements) | No prompt-to-schematic or prompt-to-board. The Requirements Portal's Engineering Assistant answers natural-language questions about requirements and proposes requirement edits | read | https://resources.altium.com/p/introducing-agentic-requirements-engineering (2026-10-14) |
| A2 | Structured form / spec / requirements input | Yes | Requirements Portal: structured requirements with ID, title, text, rationale, type; AI-assisted importer from PDF, spreadsheet, document or notes; linking to schematics, layouts and BOMs; verification tracking | read | https://resources.altium.com/p/introducing-agentic-requirements-engineering ; https://www.altium.com/agile/teams |
| A3 | Design as code | No | Scripting exists (DelphiScript; a C#/C++ "Altium Designer SDK" in closed beta) but designs are GUI documents, not code | read (SDK) / summary (DelphiScript) | https://developer.altium.com/ (read 2026-11-13); earlier teardown |
| A4 | Imports an existing design | Yes | Import Wizard: KiCad (legacy and current `.kicad_sch/.kicad_pcb/.kicad_sym/.kicad_mod`; no version number stated), OrCAD (variants supported since 26.9; "Advanced OrCAD Engine" open beta 26.8), Allegro ("Advanced Allegro Import Wizard" open beta 26.6), plus older importers (Eagle, PADS, etc.). Schematic and layout | read | https://www.altium.com/documentation/altium-designer/kicad-import (updated 2026-11-02); https://www.altium.com/documentation/altium-designer/new |
| A5 | Keeps the requirement as its own artifact | Yes | Requirements are first-class objects in Altium 365, traced to design data and across revisions. This is the closest any incumbent comes to Circuit OS's IntentIR, but the requirement does not *generate* or *check* the design | read | https://www.altium.com/agile/teams ; https://www.altium.com/documentation/altium-365/requirements-portal/agentic-engineering (updated 2026-10-26) |
| A6 | Clarifying questions / refuses out-of-scope | Not found | The assistant "proposes" changes for approval; no documented refusal behaviour | not found (searched requirements-portal docs and launch post) | as A1 |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | No | Not offered; the 2026 AI scope is requirements only | read (scope of the AI docs) | https://www.altium.com/documentation/altium-365/requirements-portal/agentic-engineering |
| B2 | AI edits / copilot inside a schematic | No (first party) / Partial (third party) | No first-party schematic copilot. Third-party MCP servers drive Altium Designer through its scripting layer (e.g. "Altium MCP Suite", MIT; `altium-designer-mcp`, GPL-3.0, library files only). Official "MCP Server for Altium Designer" is "Coming Soon" | read (official status) / summary (third-party) | https://developer.altium.com/ ; https://glama.ai/mcp/servers/integrations/altium-designer |
| B3 | Part selection with stated reasons | Partial | Live pricing, stock, lifecycle, risk and alternates shown at selection time (ActiveBOM, Octopart, optional SiliconExpert/Z2Data). No engineering justification is generated | read (Agile Teams page) / summary (ActiveBOM) | https://www.altium.com/agile/teams ; https://www.altium.com/altium-designer/features/bom-management |
| B4 | Reusable modules / reference designs | Yes | Design Reuse panel (enhanced, open beta 26.5), multi-channel design, Renesas reference designs published to the Altium Public Vault | read (26.5) / summary (Renesas) | https://www.altium.com/documentation/altium-designer/new ; https://www.renesas.com/en/blogs/renesas-365-powered-altium-first-implementation-renesas-digitalization-vision |
| B5 | ERC (voltage-aware?) | Yes, not voltage-aware | Pin-type connection matrix (Fatal / Error / Warning / No report). A PCB "Supply Nets" rule assigns a voltage to a net for SI and batch DRC, but no ERC compares voltages or currents against part ratings | read | https://www.altium.com/documentation/altium-designer/schematic/design-validation ; https://altium.com/documentation/altium-designer/pcb-signal-integrity-rule-supply-nets |
| B6 | Hierarchy / multi-sheet | Yes | Hierarchical and multi-channel design listed in Develop | read | https://www.altium.com/ru/develop/pricing (English page) |
| B7 | Library; symbols from datasheets | Partial | Cloud part libraries, Manufacturer Part Search, IPC-7351B footprint wizard (26.6). No datasheet-to-symbol AI found. Octopart claims daily updates for 95M+ parts (vendor claim) | read (wizard) / summary (95M) | https://www.altium.com/documentation/altium-designer/new ; https://resources.altium.com/p/part-selection-using-supply-chain-data-to-validate-choices |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes, included | Built-in Mixed Simulation, SPICE3f5-compatible, reads PSpice and LTspice models. Analyses: operating point, transient, Fourier, DC sweep, transfer function, pole-zero, AC, noise; plus temperature sweep, parameter sweep, Monte Carlo, sensitivity as multi-pass modes | read (physics report, checked) / summary (analysis list) | https://www.altium.com/documentation/altium-designer/circuit-simulation/configuring-running ; physics report §Altium |
| C2 | Tolerance / Monte Carlo / worst case | Yes (Monte Carlo, sensitivity) | Monte Carlo varies component values randomly across tolerances on top of a base analysis; subcircuit data is not varied. No worst-case (corner) analysis found | summary | https://www.altium.com/documentation/altium-designer/circuit-simulation/configuring-running |
| C3 | Formal proof / exhaustive verification | Not found | Searched docs and release notes; nothing beyond simulation and rule checks | not found | https://www.altium.com/documentation/altium-designer/new |
| C4 | Signal integrity | Yes (included) + paid add-on | Included: reflection and crosstalk simulator, 13 SI rules in batch DRC; Layer Stack Manager impedance via Simbeor 2D solver. Paid: **Signal Analyzer by Keysight** (impedance, reflections, losses), 14-day trial, "purchased as an add-on"; India store INR 112,565 term licence | read | https://www.altium.com/products/extensions/signal-analyzer ; https://stg.store.altium.com/ (staging store, read 2026-11-13) |
| C5 | Power integrity / IR drop | Paid add-on, DC only | **Power Analyzer by Keysight**: DC voltage drop, current density, via current; FAQ says not included in subscription. India store INR 112,565 / 1 year; bundle with Signal Analyzer INR 225,130 | read | physics report (Power Analyzer docs); https://stg.store.altium.com/ |
| C6 | Thermal | Not found | No native board thermal solver (physics report). Not found in 2026 release notes | not found | physics report; https://www.altium.com/documentation/altium-designer/new |
| C7 | EMC / EMI | Third party | EMIStream extensions (NEC) and Ansys SIwave via EDB export, licensed separately | read (physics report) | physics report §Altium |
| C8 | Creepage / clearance from voltage | Partial | Creepage Distance rule measures surface path between chosen nets; the user types the distance, voltage is not used, off by default. New "Z-Axis Clearance" rule (open beta 26.4). Not derived from working voltage or insulation class | read | https://www.altium.com/documentation/altium-designer/pcb-electrical-rule-creepage-distance (earlier teardown); https://www.altium.com/documentation/altium-designer/new |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Not found (first party) | No auto-placement or AI placement in docs or 2026 release notes. A fabricator news site claims an Altium 365 "placement assistant"; no primary source, contradicted by a Jan 2026 Quilter comparison | not found / summary (unverified claim) | https://www.altium.com/documentation/altium-designer/new ; https://atlaspcb.com/news/news-ai-pcb-design-tools-cadence-altium-ml-2026 |
| D2 | Automatic routing | Yes, rules-based | **Situs** topological autorouter routes the whole board with strategies for 2-layer and multi-layer boards; **ActiveRoute** guided routing (no vias, skips power nets and nets > 20 pins). No completion rate or time published | read | https://www.altium.com/documentation/altium-designer/pcb/routing/situs-topological-autorouter ; earlier teardown (ActiveRoute docs) |
| D3 | Constraint management | Yes | Constraint Manager with Simple/Advanced clearance modes (26.8); Design Rule Sets open beta (26.10) | read | https://www.altium.com/documentation/altium-designer/new |
| D4 | Stackup and controlled impedance | Yes | Layer Stack Manager with Simbeor field solver; via instancing (26.7); signal layers raised from 32 to 128 (open beta 26.8) | read | https://www.altium.com/documentation/altium-designer/new ; physics report |
| D5 | DRC | Yes | Online and batch DRC on user-typed geometric rules; no headless/CI DRC documented | read (physics report) | physics report |
| D6 | 3D and MCAD exchange | Yes | Native 3D; ECAD-MCAD CoDesign included in Develop; SOLIDWORKS 2024/2025 and Parasolid (26.3); Open CASCADE 7.9 (open beta 26.10) | read | https://www.altium.com/ru/develop/pricing ; https://www.altium.com/documentation/altium-designer/new |
| D7 | Length tuning / diff pairs | Yes | Interactive diff-pair routing; Interactive Length Tuning and Diff Pair Length Tuning (accordion, trombone, sawtooth patterns) against Length / Matched Length rules, including within-pair matching | summary (search over Altium docs, read 2026-11-14) | https://www.altium.com/documentation/altium-designer/pcb/high-speed-design/length-tuning |
| D8 | HDI / flex / rigid-flex | Yes | Rigid-Flex (Advanced) mode with substacks; microvia structures per IPC-2226 | read | https://www.altium.com/documentation/altium-designer/pcb/rigid-flex-design ; https://resources.altium.com/p/advanced-hdi-design-using-altium-designer |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | No firmware generation in Altium Designer or 365 docs. (Renesas 365 links Altium 365 with Renesas embedded tooling; no firmware generation stated) | not found | https://www.altium.com/documentation/altium-designer/new ; https://embeddedcomputing.com/application/industrial/industrial-iot/renesas-365-targets-design-challenges-with-cloud-based-collaboration-tools |
| E2 | Pin-mux / peripheral configuration | Not found | — | not found | as E1 |
| E3 | Compiles / tests firmware | Not found | — | not found | as E1 |
| E4 | Protocol stacks | Not found | — | not found | as E1 |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains why each choice was made | No (design) | Requirements carry a "rationale" field written by people or the importer; nothing explains schematic or part choices | read | https://resources.altium.com/p/introducing-agentic-requirements-engineering |
| F2 | Confidence / evidence grading | Not found | — | not found | requirements-portal docs |
| F3 | Automated design review | Partial | ERC (pin type), DRC (geometry), SI rules; "Background Agents" that scan *requirements* for risks, traceability issues and coverage gaps are "Coming soon" | read | https://resources.altium.com/p/introducing-agentic-requirements-engineering |
| F4 | Checks grounded in datasheets (cited pages) | Not found | — | not found | — |
| F5 | Audit trail of AI actions | Partial | Every AI change is previewed side by side and needs explicit approval; no AI-specific audit log described. Agile Teams has exportable event logs and a review audit trail | read | https://resources.altium.com/p/introducing-agentic-requirements-engineering ; https://www.altium.com/agile/teams |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No (design) / Partial (requirements) | Requirement edits by chat, approved by a person | read | as A1 |
| G2 | Version history, diff, branch, restore | Yes | Git-based version control in Altium 365; visual diff of schematic, PCB, BOM, Gerber/ODB++; Create Tag restored (26.4); partial LFS repos (26.5, with a data-loss warning) | read | https://www.altium.com/documentation/altium-designer/new ; physics report (design compare) |
| G3 | Comments / review workflow / roles | Yes | Develop: comments, tasks, unlimited free workspace users (no editing). Agile Teams: workflow templates, role-based access, SSO, co-authoring, Jira sync, guest access | read | https://www.altium.com/ru/develop/pricing ; https://www.altium.com/agile/teams |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | ActiveBOM in Designer; BOM Portal in 365 (Develop "Real-Time BOM Management", normalization and cleanup) | read | https://www.altium.com/ru/develop/pricing |
| H2 | Live price and stock | Yes | Octopart / IHS Markit data across 100+ suppliers (Digi-Key, Mouser, Arrow named); optional SiliconExpert (INR 179,300/yr for 1,000 queries) and Z2Data (from INR 359,500/yr) | summary (suppliers) / read (prices, staging store) | https://www.altium.com/altium-designer/features/bom-management ; https://stg.store.altium.com/ |
| H3 | Alternates / substitution | Partial | Alternates suggested from supply data; "evaluate alternatives". Not re-verified electrically | read | https://www.altium.com/agile/teams |
| H4 | Fabrication outputs | Yes | Gerber, Gerber X2, NC drill, ODB++ (with IP protection, 26.8), IPC-2581 via Output Jobs | read (ODB++ IP) / summary (rest, earlier teardown) | https://www.altium.com/documentation/altium-designer/new |
| H5 | DFM / DFA | Partial | Geometric manufacturing rules; Assembly Assistant (INR 71,900/yr on India store); cross-functional DFM *reviews* in Agile Teams | read | https://stg.store.altium.com/ ; https://www.altium.com/agile/teams |
| H6 | Order from a fab inside the tool | Partial | "Push to Manufacturing" / manufacturing portal for release packages; no integrated fab checkout found | read | https://www.altium.com/ru/develop/pricing ; https://www.altium.com/agile/teams |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Desktop + browser | Altium Designer on Windows; Altium 365 in browser for viewing, review, BOM, requirements | read | https://www.altium.com/agile/teams |
| I2 | API / CLI / headless | Partial | Altium 365 GraphQL API, Altium Designer SDK (C#/C++), Octopart API — all **Closed Beta**; MCP servers "Coming Soon". No headless DRC/SI | read | https://developer.altium.com/ |
| I3 | On-prem, certifications | Yes | SOC 2 Type 2; Altium 365 GovCloud (AWS GovCloud, US persons) for ITAR/EAR support; Agile Enterprise offers on-prem / single-tenant (vendor summary) | summary | https://www.altium.com/trust-faq ; https://resources.altium.com/p/how-is-your-design-data-protected-altium-365-govcloud |
| I4 | Pricing | See below | **Develop**: 1 author + workspace + unlimited workspace users; up to 4 more authors at **USD 995/year each** (read). Base price was not visible in the fetched page; third parties give **USD 1,990/year** (summary). India staging store: INR 379,200/year (or INR 32,000/month × 12) for the unnamed core product (read). **Agile Teams / Enterprise**: quote only (read). Add-ons: Signal Analyzer and Power Analyzer INR 112,565 each, both INR 225,130; BOM Portal USD 995/year per a 2026 Altium article (summary). Requirements AI: included in Develop and Agile Teams | read / summary as marked, all read 2026-11-13 | https://www.altium.com/ru/develop/pricing ; https://www.altium.com/develop/pricing ; https://stg.store.altium.com/ ; https://www.getapp.com.au/software/121767/altium-designer ; https://resources.altium.com/p/bom-portal-vs-bom-tool |
| I5 | Sold to | Professional PCB teams, from individuals (Develop) to regulated enterprises (Agile Enterprise) | read | https://www.altium.com/agile/teams |
| I6 | Company facts | Renesas completed the A$9.1bn / US$5.9bn acquisition (announced 2024-02-15); Altium is a wholly owned subsidiary; Don Cantow became General Manager 2026-01-01 with an "open platform" mandate; Renesas planned a US holding company for its Software & Digitalization business in early 2026. Renesas uses Altium company-wide; "Renesas 365, Powered by Altium" announced March 2025 for early 2026 — GA not confirmed | summary | https://www.eenewseurope.com/en/renesas-completes-5-9bn-altium-buy/ ; https://briefglance.com/articles/altium-taps-veteran-don-cantow-to-lead-open-platform-strategy ; https://pneda.com/technology/Renesas-and-Altium-jointly-launch-Renesas-365-Powered-by-Altium |
| I7 | KiCad / OrCAD interoperability | Import yes, export no | Imports KiCad, OrCAD, Allegro; no export to KiCad found | read | https://www.altium.com/documentation/altium-designer/kicad-import |
| I8 | Open source | No | Proprietary; a Master Services Agreement replaced the EULA in 26.3 | read | https://www.altium.com/documentation/altium-designer/new |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces (RS-485, 4–20 mA, 24 V) | Not found | General-purpose tool; no industrial rule library | not found | docs search |
| J2 | Power electronics | Partial | SPICE with LTspice/PSpice models; DC PI add-on; no power-stage design aid | inference (from C1, C5) | — |
| J3 | RF / high-speed | Yes | SI simulator, impedance solver, 128 signal layers (beta), Keysight SI add-on | read | as C4, D4 |
| J4 | Safety / regulatory standards | Partial | IPC-7351B footprints, IPC-2581 output, GovCloud for ITAR; no IEC 60664 / UL creepage derivation | read / inference | as above |
| J5 | Stated limits | Develop: up to 5 author seats per workspace (1 + 4); "unlimited signal layers" claimed (Altium comparison page) vs 128 (26.8 beta) | read | https://www.altium.com/documentation/altium-designer/installation-management/authoring-access-develop (updated 2026-10-08); https://www.altium.com/compare/autodesk/fusion/develop |

## What changed since the 2026-10-21 teardown

- **Official prices partly readable.** The Develop page now shows "add up to 4 more Altium Designer Authors for $995/year each"; the 2026-10-21 teardown had only third-party figures. The base Develop price was still not in the fetched text. The Keysight analyzers are now confirmed as add-ons in the store (INR 112,565 each), and the Signal Analyzer page no longer says "Open Beta" (the page does not state a beta status).
- **Agentic Requirements Engineering is shipped** (launch post 2026-10-14; docs updated 2026-10-26): Engineering Assistant, AI-assisted importer, AI Skills; Background Agents still "coming soon". Included in Develop and Agile Teams.
- **26.11 (2026-10-14)** adds nothing on AI, simulation or verification; 26.10 adds Design Rule Sets (open beta).
- **KiCad import** page (updated 2026-11-02) no longer states a version ceiling; the earlier "up to KiCad 8.x" and Altium's January 2026 migration table ("6.0x") are both unconfirmed for KiCad 9/10.
- **MCP**: still "Coming Soon" for both Altium Designer and Altium 365. Third-party MCP servers exist and work through the scripting layer.

## What the owner's market page gets wrong about this product

| Page claim | Evidence | Verdict |
|---|---|---|
| Altium is "manual only" | Situs autorouter routes a whole board; ActiveRoute routes selected nets; Output Jobs automate releases. Placement and part choice *are* manual; no AI layout | **Wrong as stated**; right for placement and schematic |
| "External SPICE only" | Built-in SPICE3f5-compatible Mixed Simulation with Monte Carlo and sensitivity, included in the product | **Wrong** (already corrected in the physics report; still wrong) |
| "Error codes only" (no plain-English validation) | ERC/DRC report rule-violation messages, not codes; but nothing explains consequences in English. The only natural-language AI is on requirements | **Mostly right in spirit**, wrong in wording |
| Physics layout validation = "paid add-on" | SI simulator and impedance solver ship in the product; Keysight SI and DC PI are paid add-ons | Partly wrong |
| V/I rule checks = "Yes" | ERC is pin-type only; only the paid DC Power Analyzer checks current density | **Wrong** |
| Natural-language input = No | No for designs; Yes for *requirements* since Oct 2026 | Needs a footnote |
| Version history / audit trail | Yes: Git-based history, visual diff, event-log export (Agile Teams) | Page should credit Altium |
| BOM with live pricing | Yes, and broader than Circuit OS (Octopart across 100+ suppliers vs one distributor) | Page should credit Altium |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

Circuit OS facts from `MENTAL_MODEL.md` (dated 2026-08-22, partly stale) and the current project map in `.claude/CLAUDE.md`.

**Altium ahead:** any board size and layer count (Circuit OS layout is experimental, 2-layer, at most 40 parts, behind a flag — MENTAL_MODEL §4 and physics report); signal integrity, impedance solving and paid PI; rigid-flex, HDI, 3D MCAD; mature version control, reviews, co-authoring, roles, SOC 2, GovCloud; supply chain across 100+ suppliers with lifecycle and risk data; complete fabrication outputs (Circuit OS has none yet — physics report corrections table); requirements management with traceability that is already sold to enterprises.

**Circuit OS ahead:** English (or a form) to a requirement IR to a generated circuit (Altium generates nothing); proofs of voltage/current properties over tolerance boxes (`backend/proof/`, `.claude/CLAUDE.md`) against pin-type-only ERC; graded claims with a declared scope and refusal of out-of-envelope requests; firmware generated from the wiring and shown only after it compiles (Uno, ESP32-DevKitC, Black Pill — `.claude/CLAUDE.md`); consequential plain-English explanation; a full HTTP API (Altium's APIs are closed beta); free part-figure provenance (`data/figures.py`). Only Circuit OS's requirement artifact *drives* the design; Altium's only traces to it.

## Not verified

- Altium Develop base list price on altium.com (page text omitted the figure; USD 1,990/year is third-party).
- Whether the INR 379,200 store product is Develop or a legacy Altium Designer subscription (unnamed on the staging store).
- Signal Analyzer beta status as of November 2026; USD prices of the Keysight add-ons (USD 2,000 each is a search summary of the staging store, not read).
- KiCad 9/10 import support in Altium's importer.
- Whether Agile Enterprise on-prem deployment exists today (vendor summary says "cloud, on-premise, or single-tenant").
- Whether "Renesas 365, Powered by Altium" reached general availability in 2026.
- Which LLM the Requirements Portal uses (not stated).
- D7 rests on a search summary of Altium's docs, not a page fetch.
- Altium headcount and claimed user count (not found in any source read).
