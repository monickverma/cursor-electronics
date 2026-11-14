# Zuken CR-8000 with AIPR — feature inventory
Read 2026-11-13. Vendor: Zuken · Latest release found: CR-8000 2026, announced 2026-10-20, "available now" · Earlier teardown: none

## In one paragraph

CR-8000 is Zuken's enterprise multi-board ECAD suite: System Planner for architecture, Design Gateway for schematic and Design Force for 3D layout, with SI/PI/EMI add-ons and the EMC Adviser EX rule checker. Its AI line is **AIPR / AI-PR** (Autonomous Intelligent Place and Route), announced September 2023 as a GPU-accelerated add-on "beginning $64K per year". It learns routing and placement patterns from Zuken's reference designs ("Basic Brain"), from the customer's own past designs ("Dynamic Brain", run on a locally hosted AI-PR server) and, later, continuously ("Autonomous Brain"). In practice it is AI-*assisted*. CR-8000 2026 added AI-PR smart design reuse, which searches earlier designs for placements that worked and applies them, plus a short-segment router, high-pin-count fanout to inner layers, a "Main Path View" ratsnest filter for placement analysis, and automatic schematic wiring. Zuken's own page still lists AI "Smart Placement" as under development. In May 2026 Zuken and Valeo announced an AI design platform for automotive aimed at Automotive SPICE 4.0 process compliance. No AI-PR completion rate, layer count or analysis-in-the-loop is published.

## Features

Main sources (read 2026-11-13): [CR-8000 2026 release, 2026-10-20](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) · [Zuken AI PCB design page](https://www.zuken.com/en/product/cr-8000/ai-pcb-design/) · [What's new in CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) · [DE247 on AIPR, 2023-09-27](https://www.digitalengineering247.com/article/zuken-launches-ai-powered-pcb-routing-tool-as-first-step-in-long-term-ai-strategy/news) · [MONOist on Zuken–Valeo, 2026-06-09](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html).

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | Not found | Valeo collaboration describes an AI agent and co-pilot assistant for checking, still in development | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| A2 | Structured spec input | Yes | System Planner architecture design; Valeo AI integrated into it (announced 2026-05-28) | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| A3 | Design as code | Not found | — | not found | — |
| A4 | Imports | Partial | Layer configuration exchange with Polar Instruments (summary); other importers not checked | summary | search snippet of Zuken release listing |
| A5 | Requirement as artifact | Partial | System Planner holds the architecture; ASPICE 4.0 HWE process targeted by the Valeo platform | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| A6 | Clarifying / refusal | Not found | — | not found | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic from intent | Partial | CR-8000 2025 generates RC filters, pull-ups and ESD protection blocks from signal and part attributes (per earlier report); 2026 adds automatic schematic wire routing from logical connections | summary (2025); read (2026) | `Generative EDA tool feature spec.md`, [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) |
| B2 | AI copilot in schematic | Not found | Valeo co-pilot is a stated aim | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| B3 | Part selection with reasons | Partial | Design Gateway checks component lifespan, power-IC voltage standards, power consumption | read | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| B4 | Reusable modules | Yes | AI-PR Smart Design Reuse; "Brain Files" store placement and routing strategies | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/), [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| B5 | ERC (voltage-aware?) | Partial | Power-IC voltage-standard checks in Design Gateway | read | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| B6 | Hierarchy / multi-board | Yes | Multi-board system design | summary | [Electronic Specifier](https://electronicspecifier.com/products/design-automation/cr-8000-zuken-pcb-design-suite-for-multi-board-system-design) |
| B7 | Library | Not found | — | not found | — |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | — | not found | — |
| C2 | Tolerance / MC | Not found | — | not found | — |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Yes, add-on | Design Force SI Advance; Touchstone from AMI simulations | read | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| C5 | Power integrity | Yes, add-on | Design Force PI/EMI Advance; rule-based decap placement from PI constraints | read | as C4 |
| C6 | Thermal | Partial | "Power consumption for thermal safety" check in Design Gateway; no thermal solver found | read | as C4 |
| C7 | EMC / EMI | Yes, add-on | PI/EMI Advance; EMC Adviser EX rule checker | read | as C4 |
| C8 | Creepage from voltage | Not found | — | not found | — |

No 2026 analysis feature was announced, and no AI-PR source says analysis runs inside the AI loop.

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | AI-PR reuse applies proven placements from past designs (2026); block-level placement suggestions (2025); "AI-based Smart Placement is under development" on Zuken's AI page | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/), [AI page](https://www.zuken.com/en/product/cr-8000/ai-pcb-design/) |
| D2 | Automatic routing | Partial | AI Smart Autorouter after outline, stackup and placement; short-segment router; high-pin-count fanout to inner layers (2026). Vendor speed claim: 30 min setup + 15 min routing by the old autorouter "might take AIPR 30 seconds" (2023). No completion rate or layer limit published | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/), [DE247](https://www.digitalengineering247.com/article/zuken-launches-ai-powered-pcb-routing-tool-as-first-step-in-long-term-ai-strategy/news) |
| D3 | Constraint management | Yes | Main Path View shows connection-distance constraints and power connections (2026) | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) |
| D4 | Stackup / impedance | Yes | Polar Instruments layer-stack exchange | summary | search snippet of Zuken release listing |
| D5 | DRC | Yes | Advanced DRC, ADM design for manufacture (menu labels) | read | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| D6 | 3D / MCAD | Yes | Design Force is a 3D layout tool; true 3D component shapes | summary | [Zuken 3D shapes](https://www.zuken.com/fr/resource/better-fit-with-true-3d-component-shapes/) |
| D7 | Length / diff pairs | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| D8 | HDI / flex | Not found | Not checked this pass | not found | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | Valeo platform mentions hardware and software verification support, no generation | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| E2 | Pin-mux | Not found | — | not found | — |
| E3 | Compiles firmware | Not found | — | not found | — |
| E4 | Protocol stacks | Not found | — | not found | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence per decision | Partial | Reuse search lets engineers "compare candidates" before applying one | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) |
| F3 | Automated design review | Yes | EMC Adviser EX, DRC, Design Gateway checks | read | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| F4 | Datasheet-grounded checks | Not found | — | not found | — |
| F5 | Audit trail of AI actions | Not found | — | not found | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | — | not found | — |
| G2 | Version history | Not found | Not checked this pass | not found | — |
| G3 | Comments / roles | Partial | Multi-user ECAD-MCAD collaboration (older release) | summary | [Zuken multi-user](https://www.zuken.com/fr/resource/zuken-raises-the-bar-for-ecad-mcad-and-multi-user-efficiencies-with-cr-8000/) |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| H2 | Live price | Not found | — | not found | — |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fabrication outputs | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| H5 | DFM | Yes | ADM (Advance Design for Manufacture) | read (menu label) | [CR-8000 2025](https://www.zuken.com/en/product/cr-8000/whats-new-in-cr-8000-release-2025/) |
| H6 | Order from fab | Not found | — | not found | — |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Desktop; AI-PR GPU-accelerated; Dynamic Brain on a locally hosted AI-PR server | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) |
| I2 | API / CLI | Not found | — | not found | — |
| I3 | Self-host | Yes | On-prem; AI-PR server keeps design data inside the customer network | read | [CR-8000 2026](https://www.zuken.com/en/resource/cr-8000-2026-pcb-design-automation/) |
| I4 | Pricing | Partial | AIPR add-on "beginning $64K per year" (2023); bundle as subscription or perpetual planned. CR-8000 price not published | read | [DE247](https://www.digitalengineering247.com/article/zuken-launches-ai-powered-pcb-routing-tool-as-first-step-in-long-term-ai-strategy/news) |
| I5 | Who it is sold to | Yes | Enterprise, automotive (Valeo) | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| I6 | Company facts | Partial | Japanese public EDA vendor (Zuken Inc.); Valeo collaboration via Zuken Valeo InnoLab | read | as I5 |
| I7 | Interop | Partial | Quilter and DeepPCB list Zuken among supported inputs | read | [DeepPCB](https://deeppcb.ai/), [Quilter docs index](https://docs.quilter.ai/llms.txt) |
| I8 | Open source | No | Proprietary | inference | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | Power-IC voltage checks, PI | read | as B5 |
| J3 | RF / high speed | Yes | SI Advance with AMI | read | as C4 |
| J4 | Standards | Partial | Automotive SPICE 4.0 (HWE) process compliance targeted by the Valeo platform (in development) | read | [MONOist](https://monoist.itmedia.co.jp/mn/spv/2606/09/news092.html) |
| J5 | Stated limits | Not found | AI page mentions limitations covered in a webinar, not listed | read | [AI page](https://www.zuken.com/en/product/cr-8000/ai-pcb-design/) |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Zuken ahead:** a production multi-board 3D layout suite with SI/PI/EMI add-ons; AI-assisted routing and reuse trained on the customer's own designs, kept on-prem.
- **Circuit OS ahead:** generation from intent with proofs and compiled firmware; a public API. Zuken's 2025 circuit-block generation (RC filters, pull-ups, ESD) is the nearest overlap and does not report any verification.

## Not verified

- Zuken's 2026 release on AI-PR placement: the release text says reuse, while the AI page says Smart Placement is in development. Which applies in 2026 is unclear.
- The AIPR price in 2026 (the $64K figure is from 2023).
- Whether the Valeo platform has shipped.
