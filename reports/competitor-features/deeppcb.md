# DeepPCB — feature inventory
Read 2026-11-13. Vendor: InstaDeep (a BioNTech company) · Latest release found: open-source KiCad 10 routing plugin, public on GitHub since May 2026; benchmark assets dated 2026-08 and 2026-09 on the homepage · Earlier teardown: none (a short entry in `C:\Users\KIIT\cursor-electronics\reports\Generative EDA tool feature spec.md`)

## In one paragraph

DeepPCB is a cloud reinforcement-learning **router** (and, as a separate job type, placer) for boards that already have a schematic, footprints and usually a placement. It is sold self-serve by the hour of routing time ($30 for one hour, down to about $26.67/hour in a 30-hour pack), to hobbyists and small teams, with an enterprise tier that adds a custom API, MCP, plugins and private-cloud or on-prem deployment. Its documented pattern is that the engineer routes the critical nets (DDR, RF, tight-impedance) and DeepPCB routes the rest to the user's clearances, net classes and layer assignments, returning a "DRC-clean board". An assistant called Cooper reviews the setup (stackup, net classes, diff pairs, planes, clearances) in plain language before a run. It does no physics: no impedance computation, no length matching across byte lanes, no SI/PI/thermal, and its pages say outputs "should be reviewed by a qualified professional".

## Features

Main sources: [homepage](https://deeppcb.ai/) · [pricing](https://deeppcb.ai/pricing/) · [Benchmark 2026, 2026-04-16](https://deeppcb.ai/pcb-autorouter-benchmark-2026/) · [KiCad autorouter alternative, 2026-06-12](https://deeppcb.ai/kicad-autorouter-alternative/) · [Placement post, 2026-06-24](https://deeppcb.ai/placement-is-the-decision-routing-cant-undo/). All read 2026-11-13.

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No | Input is a board file; component selection and BOM "stay upstream in the user's own tools" | read | [homepage](https://deeppcb.ai/) |
| A2 | Structured spec input | Partial | User sets net classes, clearances, layer roles (inner layers retyped as power/ground), wider power tracks before routing; Cooper checks the setup | read | [homepage](https://deeppcb.ai/) |
| A3 | Design as code | Not found | — | not found | [homepage](https://deeppcb.ai/), [help](https://deeppcb.ai/help/) (title only) |
| A4 | Imports an existing design | Yes | Altium .PcbDoc; KiCad (plugin, KiCad 10+); EasyEDA Pro/Std; Zuken; OrCAD, Allegro, Eagle via Specctra DSN. Layout files, not schematic | read | [homepage](https://deeppcb.ai/), [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/) |
| A5 | Requirement as its own artifact | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| A6 | Clarifying questions / refusal | Partial | Cooper flags setup issues and proposes fixes (e.g. defines a missing USB pair) before routing; boards beyond plan limits must contact support | read | [homepage](https://deeppcb.ai/), [pricing](https://deeppcb.ai/pricing/) |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic | No | Schematic stays in the user's tool | read | [homepage](https://deeppcb.ai/) |
| B2 | AI copilot in schematic | No | "Schematics-augmented placement" is in development; no schematic editing | read | [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/) |
| B3 | Part selection | No | Upstream in the user's tools | read | [homepage](https://deeppcb.ai/) |
| B4 | Reusable modules | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| B5 | ERC | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| B6 | Hierarchy | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| B7 | Library / footprint generation | Not found | Uses the board's footprints | inference (board-file input) | [homepage](https://deeppcb.ai/) |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| C2 | Tolerance / Monte Carlo | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| C3 | Formal proof | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| C4 | Signal integrity | No | Tight-impedance nets are listed among those engineers route by hand first; no impedance feature described. Benchmark "does not assess constraint satisfaction, apart from DRC rules" | read | [homepage](https://deeppcb.ai/), [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/) |
| C5 | Power integrity | Not found | Only wider power-track settings before routing | not found | [homepage](https://deeppcb.ai/) |
| C6 | Thermal | Not found | Placement post names noise coupling and decoupling as motivation, no thermal model | not found | [placement post](https://deeppcb.ai/placement-is-the-decision-routing-cant-undo/) |
| C7 | EMC / EMI | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| C8 | Creepage from voltage | Not found | — | not found | [homepage](https://deeppcb.ai/) |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | "Placement-only jobs" exist on the platform (named in the benchmark exclusions); the KiCad plugin routes only and keeps placement; the June 2026 post calls placement "the one still open" problem | read | [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/), [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/), [placement post](https://deeppcb.ai/placement-is-the-decision-routing-cant-undo/) |
| D2 | Automatic routing | Yes | RL router. Self-serve to 8 layers, 1,200 airwires, 1,000 components, 2,200 pins; enterprise beyond. Benchmark (vendor, 32,000+ completed jobs to April 2026): median completion 100%, mean 95.6%, 86% of boards ≥95%; 4-layer 201-500 airwires only 72% of boards reach ≥95%; median time 4.6 min, p90 153 min. Homepage examples: SAMD51 6-layer 99.5% in 1 h 51 m; USB-C PD 4-layer 100% in 40 m, critical nets pre-routed by hand. Independent 2023 EEVblog test: did not finish a board | read (vendor figures); summary (EEVblog) | [pricing](https://deeppcb.ai/pricing/), [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/), [homepage](https://deeppcb.ai/), [EEVblog forum](https://eevblog.com/forum/blog/eevblog-1535-deeppcb-ai-autorouting-tested!/msg4787999) |
| D3 | Constraint management | Partial | Honours the user's clearances, net classes, layer assignments; "advanced features and constraints" on enterprise | read | [homepage](https://deeppcb.ai/), [pricing](https://deeppcb.ai/pricing/) |
| D4 | Stackup and controlled impedance | No | Stackup reviewed by Cooper; no impedance computation; impedance nets left to the engineer | read | [homepage](https://deeppcb.ai/) |
| D5 | DRC | Yes | Returns a "DRC-clean board" against the user's rules | read | [homepage](https://deeppcb.ai/) |
| D6 | 3D / MCAD | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| D7 | Length tuning / diff pairs | Partial | Diff pairs can be marked and routed; DDR4/DDR5 byte-lane length matching "on the roadmap" | read | [homepage](https://deeppcb.ai/), [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/) |
| D8 | HDI / flex | Not found | BGA fanout "beyond what the engine has learned" listed as a limit | read (limit); not found (HDI/flex) | [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/) |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | Routing and placement product only | inference (product scope on homepage) | [homepage](https://deeppcb.ai/) |
| E2 | Pin-mux / peripheral configuration | No | Same | inference | as E1 |
| E3 | Compiles / tests firmware | No | Same | inference | as E1 |
| E4 | Protocol stacks | No | Same | inference | as E1 |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Partial | Cooper explains setup problems and fixes in plain language; routing choices are not explained | read | [homepage](https://deeppcb.ai/) |
| F2 | Confidence per decision | Not found | Completion rate per board only | not found | [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/) |
| F3 | Automated design review | Partial | Cooper's pre-route setup review (stackup, net classes, pairs, planes, clearances) plus DRC | read | [homepage](https://deeppcb.ai/) |
| F4 | Datasheet-grounded checks | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| F5 | Audit trail | Not found | Revisions are mentioned in the benchmark method ("latest revision") | not found | [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/) |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Partial | Cooper is conversational for setup, not for editing the layout | read | [homepage](https://deeppcb.ai/) |
| G2 | Version history | Partial | Jobs have revisions; stop and resume on paid plans | read | [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/), [pricing](https://deeppcb.ai/pricing/) |
| G3 | Comments / roles | Partial | "Team collaboration on one platform" on enterprise | read | [pricing](https://deeppcb.ai/pricing/) |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | No | Upstream in user's tools | read | [homepage](https://deeppcb.ai/) |
| H2 | Live price and stock | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| H3 | Alternates | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| H4 | Fabrication outputs | Not found | Results go back into the user's ECAD tool | not found | [homepage](https://deeppcb.ai/) |
| H5 | DFM / DFA | No | "Yield and manufacturability remain the responsibility of the user's team" | read | [homepage](https://deeppcb.ai/) |
| H6 | Order from fab | Not found | — | not found | [homepage](https://deeppcb.ai/) |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Standalone web app; KiCad plugin; native plugins on enterprise | read | [homepage](https://deeppcb.ai/) |
| I2 | API / CLI / headless | Partial | Enterprise "custom API" and MCP; no public API docs | read | [homepage](https://deeppcb.ai/) |
| I3 | Self-host; certifications | Partial | Public cloud, private cloud or on-prem (enterprise). No certification found | read; not found (certifications) | [homepage](https://deeppcb.ai/) |
| I4 | Pricing | Yes | USD: $30 for 1 hour; $280 for 10 hours; $800 for 30 hours; enterprise on request. Free trial: 30 min, 1 board, 4 layers, 150 airwires, 100 components. Pay-as-you-go: 8 layers, 1,200 airwires, 1,000 components, 2,200 pins. Read 2026-11-13; no effective date shown | read | [pricing](https://deeppcb.ai/pricing/) |
| I5 | Who it is sold to | Yes | Hobbyists (Hobbyist pack) to teams; enterprise | read | [pricing](https://deeppcb.ai/pricing/) |
| I6 | Company facts | Partial | InstaDeep, acquired by BioNTech in 2023; platform holds 100,000+ board designs (vendor) | summary (acquisition); read (board count) | [benchmark](https://deeppcb.ai/pcb-autorouter-benchmark-2026/) |
| I7 | Interop | Yes | Altium, KiCad, EasyEDA, Zuken native; others via Specctra DSN | read | [homepage](https://deeppcb.ai/) |
| I8 | Open source | Partial | KiCad plugin is open source on GitHub (`instadeepai/deeppcb-kicad-plugin`, May 2026; licence not stated on the page); the engine is closed | read | [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/) |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| J2 | Power electronics | Not found | Only wider power tracks and plane layers | not found | [homepage](https://deeppcb.ai/) |
| J3 | RF / high speed | No | RF, DDR and tight-impedance nets are routed by the engineer first | read | [homepage](https://deeppcb.ai/) |
| J4 | Standards support | Not found | — | not found | [homepage](https://deeppcb.ai/) |
| J5 | Stated limits | Yes | Sweet spot up to 4 layers and about 800 pins; public limit 1,200 airwires, 8 layers, 1,000 components, 2,200 pins | read | [KiCad page](https://deeppcb.ai/kicad-autorouter-alternative/), [pricing](https://deeppcb.ai/pricing/) |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

Circuit OS side: `MENTAL_MODEL.md` §4 and the code table in `reports/Physics layout validation - what the market does and what Circuit OS can build.md`.

- **DeepPCB ahead:** a learned router that finishes 4-8 layer boards of hundreds of airwires, with a published (vendor) completion distribution over 32,000 jobs. Circuit OS routes 2-layer boards of at most 40 parts, and its routing quality is untested. DeepPCB also has native import from five ECAD tools and an open-source KiCad plugin.
- **Circuit OS ahead:** everything upstream of the board: requirement, circuit, firmware, SPICE, proofs, BOM. Circuit OS also has an exact connectivity, short and pin-parity check (`pcb_engine/verify.py`); DeepPCB states only DRC-clean.
- **Neither:** layout physics (impedance, IR drop, thermal).

## Not verified

- Placement as a product: placement-only jobs exist on the platform, but no current placement product page was read. Earlier coverage gives placement limits of 1,000 components and 2,200 pins (summary, actuia.com).
- The licence of the KiCad plugin.
- What "AI Credit" means relative to hours.
- Any certification (SOC 2 or other).
