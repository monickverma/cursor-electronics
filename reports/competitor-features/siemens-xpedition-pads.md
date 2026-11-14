# Siemens EDA: Xpedition, PADS Professional, HyperLynx, Valor and Fuse — feature inventory
Read 2026-11-13. Vendor: Siemens Digital Industries Software (Siemens EDA) · Latest releases found: Xpedition 2604 and HyperLynx 2604 (2026-04-27); HyperLynx 2610 and Valor NPI 2610 (2026-10-26); Fuse EDA AI Agent (launched 2026-03-16, PCB scope widened 2026-07-26) · Earlier teardown: none (Siemens sections in `reports/Physics layout validation - what the market does and what Circuit OS can build.md`)

## In one paragraph

Siemens sells the most complete PCB *checking* stack of any vendor, and it sells it in pieces. Xpedition (enterprise) and PADS Professional (mid-market) handle schematic and layout. Xpedition Schematic Analysis checks schematics with 150+ voltage-aware rules. HyperLynx covers SI, PI (DC drop, AC PDN impedance, decap optimisation, and since 2604 a beta time-domain droop wizard), a 90+ rule electrical DRC and a creepage wizard. Valor NPI runs 1,000+ DFM checks and, since 2610, nine free IPC standards-compliance profiles. Siemens' AI is mostly assistive. It adds documentation copilots in every product (2026), a CELUS-powered front end that turns functional block diagrams into a reference schematic and BOM (PADS Pro Essentials 2025, Xpedition Standard May 2026), and routing automation (sketch routing, which Siemens itself does not label as AI). It also adds the **Fuse EDA AI Agent**, which "aids layout, signal integrity and other analyses" and is said to "continuously validate decisions against deterministic, physics-based EDA engines". Its PCB capabilities are promised "in forthcoming releases". No Siemens product found does autonomous placement and routing of a whole board, and none goes from English to a verified design.

## Features

Main sources (read 2026-11-13): [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) · [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/) · [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) · [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) · [Fuse launch, 2026-03-16](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) · [Siemens-NVIDIA, 2026-07-26](https://news.siemens.com/en-us/siemens-nvidia-dac-2026/) · [Xpedition Standard AI blog, 2026-05-18](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/) · [PADS Pro Essentials / Xpedition Standard launch, 2025-05-21](https://mail.iconnect007.com/article/145432/siemens-democratizes-aidriven-pcb-design-for-small-and-medium-electronics-teams/145429/milaero).

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Partial | Not a prompt: the CELUS-powered front end starts from functional block diagrams and "high-level requirements" and generates a reference schematic and BOM (Xpedition Standard, 2026-05-18; PADS Pro Essentials, 2025-05-21). Natural language is used for documentation questions (support copilot) | read | [Xpedition Standard blog](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/), [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| A2 | Structured spec input | Yes | Requirements tabs in Xpedition design capture (reorganised in 2604); multi-user constraint editor | read; summary | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/), [Siemens constraints blog](https://blogs.sw.siemens.com/electronic-systems-design/2017/02/23/collaborative-management-of-design-constraints/) |
| A3 | Design as code | Partial | HyperLynx DRC is scriptable in Python, with action scripts since 2604; Valor NPI is Python-scriptable | read; checked (physics report) | [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/) |
| A4 | Imports existing designs | Yes | Rival-format importers are table stakes; Quilter and DeepPCB read Xpedition / PADS data | summary | `Generative EDA tool feature spec.md` |
| A5 | Requirement as its own artifact | Yes | Requirements management in design capture, with a hierarchical tree view (2604) | read | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| A6 | Clarifying questions / refusal | Partial | Fuse claims "built-in validation and guardrails" and "human checkpoints"; nothing shipped for PCB found | read | [Fuse launch](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | Partial | CELUS front end: block diagram to reference schematic and BOM ("AI-powered assistance and smart algorithms") | read | [Xpedition Standard blog](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/) |
| B2 | AI copilot in schematic | Partial | Product Support Copilot answers documentation questions in natural language; it does not edit the design | read | [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/), [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| B3 | Part selection with reasons | Partial | CELUS front end picks "suitable solutions"; reasons not described | read | as B1 |
| B4 | Reusable modules | Yes | Hierarchical design and reusable blocks; physical reuse and copy-circuit improvements (2604) | read | [Xpedition Standard blog](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/), [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| B5 | ERC (voltage-aware?) | Yes, add-on | **Xpedition Schematic Analysis** (ex-Valydate): "over 150 voltage-aware rules", models built from BOM MPNs, voltage-level mismatches, capacitor derating, missing pull-ups, multi-board. Multi-board interface signal matcher (2604) | checked (physics report); read | [EEJournal 2018](https://www.eejournal.com/article/validate-twice-build-once/), [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| B6 | Hierarchy / multi-sheet | Yes | Table stakes; multi-board systems | summary | `Generative EDA tool feature spec.md` |
| B7 | Library; models from symbols | Partial | Active-model wizard builds part models from Designer symbols for all part types (2604); Valor Parts Library; no datasheet-to-footprint AI found | read | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/), [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes, add-on | HyperLynx AMS (analog/mixed-signal) is named among HyperLynx products; semi-automated SPICE extraction (2610) | read | [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) |
| C2 | Tolerance / Monte Carlo | Not found | Not checked this pass for HyperLynx AMS | not found | — |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Yes, add-on | HyperLynx SI: DDRx (parallel batch, CUDIMM), SerDes / IBIS-AMI to 100G PAM-n and CEI-112G, PCIe Gen 7 (2604); pre- and post-layout. On Xpedition Standard via **token-based** options | read | [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/), [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/), [2025 launch](https://mail.iconnect007.com/article/145432/siemens-democratizes-aidriven-pcb-design-for-small-and-medium-electronics-teams/145429/milaero) |
| C5 | Power integrity / IR drop | Yes, add-on | HyperLynx PI: DC drop with DC Metrics Viewer, DC Shared Return Analysis (2610), AC analysis accuracy improvements (2610), PDN impedance at each power pin with decoupling optimiser, PDN time-domain droop wizard (beta, 2604) | read; checked (physics report) | [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/), [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) |
| C6 | Thermal | Partial | Board-level thermal co-simulation in HyperLynx PI (VX.2.10, pre-2026); no 2026 thermal item | summary | [HyperLynx VX.2.10](https://eda.sw.siemens.com/en-US/pcb/hyperlynx/release-highlights-2-10) |
| C7 | EMC / EMI | Partial | HyperLynx DRC: 90+ rules across SI, PI, EMI and safety (rule checks); Huygens-box export to FEKO for full-wave (2610) | checked (physics report); read | [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) |
| C8 | Creepage / clearance from voltage | Yes | Creepage clearance validation in the Xpedition layout editor, online (net-to-net) and batch (net-class) (2604); HyperLynx DRC Creepage Wizard (2604) | read | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/), [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/) |

Whether the creepage distance is *derived* from working voltage and insulation class, or typed by the user, was not established.

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | Placement planning improvements (2604); "thermal-aware placement" claimed only by a third-party blog. No autonomous AI placement announced | read; summary (third party) | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/), [AtlasPCB](https://atlaspcb.com/blog/ai-pcb-design-tools-landscape-2026-copilot-autonomous-layout/) |
| D2 | Automatic routing | Partial | Sketch routing / sketch planner and trunk router (auto-assisted, user draws paths). "AI to suggest and guide the PCB designer through the routing process" (Nov 2024). The May 2026 blog describes routing automation without calling it AI. Fuse "aids layout". No completion figures from Siemens | summary; read | [Siemens 2014 sketch routing](https://blogs.sw.siemens.com/electronic-systems-design/2014/11/18/sketch-routing-a-new-paradigm/), [Xpedition Standard blog](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/), [Fuse launch](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) |
| D3 | Constraint management | Yes | Multi-user constraint editing | summary | `Generative EDA tool feature spec.md` |
| D4 | Stackup / impedance | Yes | Table stakes; HyperLynx field solvers | summary | physics report |
| D5 | DRC | Yes | Layout DRC plus HyperLynx DRC (electrical, 90+ rules, targeted by design area in 2610) | read; checked | [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) |
| D6 | 3D / MCAD | Yes | MCAD co-design highlighted in Xpedition 2610 | summary | [search snippets of Xpedition 2610 release](https://itbrief.co.uk/story/siemens-releases-next-gen-electronic-systems-design-tools) |
| D7 | Length tuning / diff pairs | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| D8 | HDI / flex / rigid-flex | Yes | IPC-4761 via protection native (2604); Valor profiles for HDI/microvias, flex, rigid-flex; trench vias (2610) | read | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/), [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found | Siemens PCB 2026 release posts |
| E2 | Pin-mux | Not found | — | not found | as E1 |
| E3 | Compiles firmware | Not found | — | not found | as E1 |
| E4 | Protocol stacks | Not found | — | not found | as E1 |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence per decision | Partial | Valor DFSC: pass/fail per IPC profile (Class 1-3, Level A-C) | read | [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |
| F3 | Automated design review | Yes | Schematic Analysis (voltage-aware), HyperLynx DRC, Valor NPI 1,000+ DFM checks, DFSC | read; checked | as above |
| F4 | Datasheet-grounded checks | Partial | Schematic Analysis builds models from manufacturer part numbers; page citations not described | checked (physics report) | [Siemens 2020](https://blogs.sw.siemens.com/electronic-systems-design/2020/06/22/how-can-i-catch-schematic-errors-more-easily/) |
| F5 | Audit trail of AI actions | Partial | Fuse claims role-based access, audit trails, human checkpoints (not yet shipped for PCB) | read | [Fuse launch](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | Copilots answer documentation questions only | read | [HyperLynx 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-hyperlynx-2610/) |
| G2 | Version history | Yes | Xpedition EDM: revisions, check-in/out, approval workflows; web check-out (2604) | read | [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/), [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| G3 | Comments / roles | Yes | Collaboration notes (2604); access control and approvals in EDM; multi-user DFM team layout | read | as G2 |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | CELUS front end outputs a BOM; Valor BOM Manager | read | [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |
| H2 | Live price and stock | Partial | Designer supply-chain client re-engineered (2604); distributors not named | read | [Xpedition 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-xpedition-2604/) |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fabrication outputs | Yes | Blueprint (powered by Valor) generates release documentation; ODB++ (Siemens format) | read; summary | [Xpedition Standard blog](https://blogs.sw.siemens.com/electronic-systems-design/2026/05/18/accelerate-pcb-design-productivity-with-ai-and-intelligent-automation-design-reuse-data-continuity-and-connected-workflows/) |
| H5 | DFM / DFA | Yes | Valor NPI 1,000+ checks; DFSC free in all Valor NPI versions (2610), IPC profiles updated twice a year | read | [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |
| H6 | Order from fab | Not found | Siemens–Xometry partnership seen in search, not tied to PCB ordering | not found | — |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Desktop, with cloud connectivity | read | [Siemens 2024 release](https://news.siemens.com/en-gb/siemens-xpedition-hyperlynx-ng/) |
| I2 | API / CLI / headless | Partial | HyperLynx DRC Python scripts; Valor Python; Fuse uses MCP tool orchestration internally | read; checked | [Fuse launch](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/) |
| I3 | Self-host; certifications | Partial | Desktop/on-prem; cloud data can be geo-located; certifications not checked | read | [Siemens 2024 release](https://news.siemens.com/en-gb/siemens-xpedition-hyperlynx-ng/) |
| I4 | Pricing | Partial | No prices found. PADS Pro Essentials "entry-level"; Xpedition Standard with token-based add-ons; 30-day Xpedition Standard trial; one DDRx licence includes 2 parallel simulations | read | [2025 launch](https://mail.iconnect007.com/article/145432/siemens-democratizes-aidriven-pcb-design-for-small-and-medium-electronics-teams/145429/milaero), [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/) |
| I5 | Who it is sold to | Yes | Enterprise (Xpedition), SMB and startups (PADS Pro Essentials, Xpedition Standard). Named: Leonardo (2024), Samsung and NVIDIA for Fuse | read | as above |
| I6 | Company facts | Partial | Part of Siemens AG; bought ASTER (PCB test) per search | summary | — |
| I7 | Interop | Yes | Native Xpedition/PADS; ODB++; Quilter returns native Xpedition files | read | [Quilter changelog](https://www.quilter.ai/changelog) |
| I8 | Open source | No | Proprietary | inference | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | HyperLynx PI and AMS; creepage checks | read | as C5, C8 |
| J3 | RF / high speed | Yes | SerDes to 112G PAM4, PCIe Gen 7 | read | [HyperLynx 2604](https://blogs.sw.siemens.com/electronic-systems-design/2026/04/27/whats-new-in-hyperlynx-2604/) |
| J4 | Standards support | Yes | IPC-6012/IPC-A-600 class profiles in Valor DFSC; IPC-4761; creepage checks | read | [Valor 2610](https://blogs.sw.siemens.com/electronic-systems-design/2026/10/26/whats-new-in-valor-2610/) |
| J5 | Stated limits | Not found | — | not found | — |

## Siemens' physics, precisely

| What | Engine | When | Included or add-on |
|---|---|---|---|
| Voltage-aware schematic rules (150+) | Xpedition Schematic Analysis | Schematic | Separate product |
| SI (DDR, SerDes, PCIe) | HyperLynx SI | Pre- and post-layout | Separate; tokens on Xpedition Standard |
| DC drop, AC PDN impedance, decap optimisation, time-domain droop (beta) | HyperLynx PI | Post-layout | Separate |
| Electrical rule scan (SI, PI, EMI, safety) and creepage | HyperLynx DRC + Creepage Wizard; Xpedition layout creepage check | Post-layout; online in layout | DRC separate; layout check in Xpedition 2604 |
| Full-wave | HyperLynx Advanced Solvers; FEKO export | Post-layout | Separate |
| DFM / standards | Valor NPI; DFSC | Post-layout | Valor separate; DFSC free inside it |
| AI | Copilots (included), CELUS front end, Fuse agent (forthcoming for PCB) | — | — |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Siemens ahead:** voltage-aware schematic checking across multi-board systems; creepage checks in layout; the full SI/PI/DFM sign-off chain; manufacturing standards profiles.
- **Circuit OS ahead:** generation from English through a requirement IR, with proofs over tolerance boxes rather than rule checks at nominal; firmware generated and compiled; a claim-by-claim report. Siemens' schematic generation is CELUS's block-diagram flow, which picks parts but does not prove anything about them.
- **Comparable:** both check voltage at schematic level. Siemens does it with rules on MPN models; Circuit OS does it with exact graph rules and z3 (`validation/claims.py`, `proof/prover.py`).

## Not verified

- The full Xpedition 2610 release notes (only snippets seen).
- Whether Fuse's PCB layout capabilities have shipped.
- Whether creepage is derived from working voltage and insulation class or entered by the user.
- PADS Professional's own 2026 AI features: no 2026 PADS release post found.
- AI-assisted routing completion figures (55% on 12-layer boards, 40-60% time saved) appear only on AtlasPCB, which looks like AI-assisted content; not in Siemens' post.
