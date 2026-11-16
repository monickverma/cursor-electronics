# Cadence Allegro X AI, OrCAD X and AuraStack — feature inventory
Read 2026-11-13 and 2026-11-14. Vendor: Cadence Design Systems · Latest release found: AuraStack AI Super Agent on Allegro AI Studio, announced 2026-07-15, "scheduled to become available later in 2026"; OrCAD X / Allegro X 25.1 is the newest layout release confirmed by search (no 2026 release notes were readable) · Earlier teardown: none (Cadence sections in `reports/Physics layout validation - what the market does and what Circuit OS can build.md` and `C:\Users\KIIT\cursor-electronics\reports\Generative EDA tool feature spec.md`)

## In one paragraph

Cadence sells a full schematic-to-fabrication ECAD stack. OrCAD X serves small and mid-sized teams: Capture schematic, PSpice and the "Presto" layout editor. Allegro X is the enterprise layout platform. The checking is sold as separate products: Sigrity X (SI, PI, IR drop), Celsius (thermal), Clarity (3D full-wave) and PSpice Advanced Analysis (Monte Carlo, smoke). Its AI is in layout. **Allegro X AI**, announced April 2023, generates placement, power and ground plane pours, and critical-net routes in the cloud for small-to-medium boards, and Cadence says it checks the results with SI and PI analysis. **AuraStack**, announced 15 July 2026, is a multi-agent layer over Allegro, Sigrity X, Celsius and Clarity that coordinates planning, placement, routing, verification, multiphysics analysis and manufacturing prep, with up to "15X" productivity claimed. It was not yet generally available on the dates found. Cadence's physics is the real sign-off-grade kind (field solvers, FEA/CFD), but inside OrCAD X Professional only impedance and coupling run without an extra licence; IR drop, crosstalk, reflection and return-path analysis need Sigrity X Aurora. No Cadence product takes English and returns a design, and Cadence publishes no method behind its multipliers.

## Features

Cadence's own pages (cadence.com, community.cadence.com) returned HTTP 403 to the fetch tool on 2026-11-13, so most Cadence facts here are **summary** (search snippets of Cadence pages, press wire copies, reseller pages) or carried from the earlier checked report. Table-stakes ECAD rows cite the internal `Generative EDA tool feature spec.md` (a researched report, labelled summary).

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Not found | AuraStack is described as agents coordinating the flow; no prompt-to-design capability stated. Allegro X AI starts from a placed-out schematic with stackup and constraints | summary | [Converge Digest, 2026-07-16](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| A2 | Structured spec input | Yes | Allegro X AI: user defines stackup, power requirements and constraints, selects power/ground layers, then generation starts. Constraint Manager in Allegro | summary | [search: Cadence Allegro X AI page snippets](https://resources.pcb.cadence.com/blog/2024-generative-ai-for-pcb-design-with-allegro-x-ai) |
| A3 | Design as code | Partial | SKILL scripting in Allegro (from memory, unverified) | summary (from memory, unverified) | — |
| A4 | Imports existing designs | Yes | Imports from rival formats (industry-wide trend); KiCad 10 in turn imports Allegro | summary | `Generative EDA tool feature spec.md` |
| A5 | Requirement as its own artifact | Not found | — | not found | searched Cadence AI press coverage |
| A6 | Clarifying questions / refusal | Not found | — | not found | as A5 |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | Not found | No schematic generation announced for Allegro X AI or AuraStack | not found | [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| B2 | AI copilot in schematic | Not found | — | not found | as B1 |
| B3 | Part selection with reasons | Partial | Live BOM grades supply risk from Sourcengine data; not AI part selection | summary | [EMA Live BOM](https://www.ema-eda.com/products/orcad/features/real-time-supply-chain-analysis-livebom/) via `Generative EDA tool feature spec.md` |
| B4 | Reusable modules | Yes | Hierarchical blocks / reuse (table stakes) | summary | `Generative EDA tool feature spec.md` |
| B5 | ERC (voltage-aware?) | Partial | ERC is standard; whether System Capture has voltage-aware rules is not established. PSpice "Smoke" compares simulated stresses with derated maximum ratings (simulation, not rule) | summary | [EMA PSpice smoke](https://www.ema-eda.com/how-to-page/how-to-analyze-component-stress-with-pspice/) via physics report |
| B6 | Hierarchy / multi-sheet | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| B7 | Library; footprints from datasheets | Not found | Not checked this pass | not found | — |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes | PSpice (DC, AC, transient) in OrCAD X | read (reseller) | [GoEngineer OrCAD X](https://www.goengineer.com/en-us/cadence/orcad-x) |
| C2 | Tolerance / Monte Carlo / worst case | Yes, add-on tier | PSpice Advanced Analysis (smoke, Monte Carlo, sensitivity) listed in OrCAD X Professional Plus | read (reseller) | [GoEngineer OrCAD X](https://www.goengineer.com/en-us/cadence/orcad-x) |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Yes, partly add-on | **During layout (in-design):** impedance and coupling are included in OrCAD X Professional and up (sources disagree on whether crosstalk is too); reflection and crosstalk need a **Sigrity X Aurora** licence (Allegro X Venture includes them, with Aurora installed). **Sign-off:** Sigrity X, Clarity 3D full-wave FEM (correlated to 50 GHz on one IEEE P370 fixture). AuraStack draws on Sigrity X | summary | [Cadence OrCAD X 25.1 FAQ (snippet)](https://resources.pcb.cadence.com/webinars/what-s-new-in-orcad-x-25-1-faq), [EMA Aurora](https://www.ema-eda.com/sigrity-aurora), physics report |
| C5 | Power integrity / IR drop | Yes, add-on | IR drop "within OrCAD X PCB Layout you will need a Sigrity X Aurora license". Sign-off: Sigrity PowerSI (PDN impedance, cavity resonance), OptimizePI (decaps), PowerDC (DC IR with electro-thermal co-sim) | summary (Aurora); checked (PowerSI etc., physics report 2026-10-16) | [OrCAD X 25.1 FAQ (snippet)](https://resources.pcb.cadence.com/webinars/what-s-new-in-orcad-x-25-1-faq), physics report |
| C6 | Thermal | Yes, add-on | Celsius FEA + CFD thermal; Celsius co-simulation listed in OrCAD X Professional Plus | read (reseller); checked (physics report) | [GoEngineer OrCAD X](https://www.goengineer.com/en-us/cadence/orcad-x) |
| C7 | EMC / EMI | Partial | PowerSI near- and far-field radiation; AuraStack names electromagnetic analysis | checked (physics report); summary | physics report, [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| C8 | Creepage from voltage | Not found | Not found for Allegro/OrCAD X in this pass | not found | searched Cadence release coverage |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Yes | Allegro X AI generative placement in the cloud (OnCloud), "days to minutes" claimed; "AI-Powered placement & Fanout assistance" listed for OrCAD X (tier not shown). Feb 2026 EMA webinar title cites a "new placement optimization engine, constraint and rule driven" | summary; read (reseller) | [BusinessWire 2023-04-06](https://www.businesswire.com/news/home/20230406005098/en), [GoEngineer](https://www.goengineer.com/en-us/cadence/orcad-x), [EMA webinar PDF](https://www.ema-eda.com/wp-content/uploads/2026/02/OrCAD-X-6-Things-Lurking-Webinar.pdf) (title only) |
| D2 | Automatic routing | Partial | Allegro X AI routes **critical nets** and generates power/ground pours; Allegro X AI Advanced Substrate Router (25.1) is for packages (APD Professional/Expert). No layer count, completion rate or time published; ">10X" turnaround (2023) and "up to 15X" productivity (AuraStack, 2026) are vendor claims without a method | summary | [BusinessWire 2023](https://www.businesswire.com/news/home/20230406005098/en), [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| D3 | Constraint management | Yes | Allegro Constraint Manager; Allegro X AI takes constraints as input | summary | `Generative EDA tool feature spec.md` |
| D4 | Stackup and controlled impedance | Yes | In-design impedance analysis included from OrCAD X Professional | summary | [OrCAD X 25.1 FAQ (snippet)](https://resources.pcb.cadence.com/webinars/what-s-new-in-orcad-x-25-1-faq) |
| D5 | DRC | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| D6 | 3D / MCAD | Yes | Table stakes (STEP out) | summary | `Generative EDA tool feature spec.md` |
| D7 | Length tuning / diff pairs | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| D8 | HDI / flex / rigid-flex | Yes | Allegro supports HDI and rigid-flex (from memory, unverified) | summary (from memory, unverified) | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found | Cadence PCB AI coverage searched |
| E2 | Pin-mux | Not found | — | not found | as E1 |
| E3 | Compiles firmware | Not found | — | not found | as E1 |
| E4 | Protocol stacks | Not found | — | not found | as E1 |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence per decision | Not found | — | not found | — |
| F3 | Automated design review | Partial | DRC, in-design SI/PI "exploration", AuraStack "verification" agent (not yet available) | summary | [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| F4 | Datasheet-grounded checks | Not found | — | not found | — |
| F5 | Audit trail of AI actions | Not found | — | not found | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | — | not found | — |
| G2 | Version history | Yes | OnCloud data management, 10 GB (Standard) or 50 GB storage | read (reseller) | [GoEngineer](https://www.goengineer.com/en-us/cadence/orcad-x) |
| G3 | Comments / roles | Partial | Cloud collaboration (OnCloud); details not read | summary | [EE Journal OrCAD X 2023](https://www.eejournal.com/industry_news/cadence-unveils-next-generation-ai-driven-orcad-x-delivering-up-to-5x-faster-pcb-design-and-enabled-with-cadence-oncloud) |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | Table stakes | summary | `Generative EDA tool feature spec.md` |
| H2 | Live price and stock | Yes | Live BOM, Sourcengine data | summary | [EMA Live BOM](https://www.ema-eda.com/products/orcad/features/real-time-supply-chain-analysis-livebom/) |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fabrication outputs | Yes | Gerber, ODB++, IPC-2581, placement (table stakes) | summary | `Generative EDA tool feature spec.md` |
| H5 | DFM / DFA | Partial | Geometric DFM rules; AuraStack names "manufacturing preparation" | summary | physics report, [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| H6 | Order from fab | Not found | — | not found | — |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Desktop, with OnCloud cloud services; Allegro X AI computes in Cadence's cloud | summary | [BusinessWire 2023](https://www.businesswire.com/news/home/20230406005098/en) |
| I2 | API / CLI / headless | Partial | Sigrity/Allegro scripting exists; no AI API found | summary (from memory, unverified) | — |
| I3 | Self-host; certifications | Partial | Desktop installs on-prem; OnCloud for cloud. Certifications not checked | not found (certifications) | — |
| I4 | Pricing | Partial | OrCAD X Standard on the EMA store: ranges seen from $1,392 to $8,260 per licence option, a $1,000 first-year offer (dates of cached pages unclear). Professional and Professional Plus: "Get pricing". Standard perpetual, Professional time-based, Professional Plus cloud (SUL). Allegro X AI and AuraStack prices not published | summary (EMA ranges); read (tiers) | [EMA OrCAD X Standard](https://www.ema-eda.com/store/pcb-products/orcad-x-standard/), [GoEngineer](https://www.goengineer.com/en-us/cadence/orcad-x) |
| I5 | Who it is sold to | Yes | OrCAD X: SMB and independent engineers; Allegro X and AuraStack: enterprise. AuraStack collaborators named: NVIDIA, TSMC, Socionext, FORVIA HELLA, Schneider Electric | summary | [Converge Digest](https://convergedigest.com/cadence-launches-ai-super-agent-for-pcb-and-advanced-packaging/) |
| I6 | Company facts | Partial | Public EDA vendor; no PCB-specific user counts found | not found | — |
| I7 | Interop | Yes | Native Allegro/OrCAD; Quilter and DeepPCB both read Allegro; KiCad 10 imports Allegro | summary | `Generative EDA tool feature spec.md` |
| I8 | Open source | No | Proprietary | inference | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | PSpice, PowerDC electro-thermal | checked (physics report) | physics report |
| J3 | RF / high speed | Yes | Sigrity, Clarity to 50 GHz on a published fixture | checked (physics report) | physics report |
| J4 | Standards support | Not found | — | not found | — |
| J5 | Stated limits | Partial | Allegro X AI aimed at "small-to-medium PCBs"; no numbers | summary | [Cadence Allegro X AI page snippet](https://newstaging.cadence.com/p_r_e_view/home/tools/pcb-design-and-analysis/allegro-x-ai.html) |

## Cadence's physics, precisely (for the C and D comparison)

| What | Engine | When | Included or add-on |
|---|---|---|---|
| Impedance, coupling | Sigrity X in-design | During layout | Included from OrCAD X Professional / Allegro X Designer |
| Crosstalk, reflection, return path, IR drop | Sigrity X Aurora | During layout | Aurora licence (included in Allegro X Venture) |
| PDN impedance, resonance, radiation; decap optimisation; DC IR + thermal | PowerSI, OptimizePI, PowerDC | Post-layout sign-off | Separate Sigrity X products |
| Board thermal | Celsius (FEA + CFD) | Post-layout | Separate; co-sim in OrCAD X Professional Plus |
| 3D full-wave | Clarity | Post-layout | Separate |
| Circuit stress, Monte Carlo | PSpice Advanced Analysis | Schematic | OrCAD X Professional Plus |
| AI placement / pours / critical nets | Allegro X AI | Before detailed routing; "checked afterwards with SI and PI" | Inside Allegro X platform (no separate price found) |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

Circuit OS side: `MENTAL_MODEL.md` §4; the code table in the physics report.

- **Cadence ahead:** every physics domain in C (field solvers, thermal FEA/CFD, PDN impedance), production-grade layout of any size, HDI and rigid-flex, fabrication outputs. AI placement and pours exist; an agentic flow over its own sign-off solvers is announced.
- **Circuit OS ahead:** English to a requirement IR to a validated circuit with firmware; z3 proofs over tolerance boxes (PSpice Monte Carlo samples where Circuit OS proves); a per-claim graded report; refusal of out-of-scope requests. No Cadence product found does any of these.

## Not verified

- Anything on cadence.com itself (403). The licensing split (impedance and coupling included, the rest on Aurora) comes from search snippets of Cadence FAQs, which disagree on crosstalk.
- AuraStack's general availability date: "later in 2026" per press; an analyst says September 2026; no shipping confirmation found.
- Any 2026 (26.x) release notes for OrCAD X or Allegro X.
- Whether Allegro X AI is a separate licence.
- Creepage checks in Allegro or OrCAD X.
