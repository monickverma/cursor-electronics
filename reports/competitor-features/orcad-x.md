# OrCAD X (Capture, PSpice, editions) — feature inventory
Read 2026-11-13/14. Vendor: Cadence Design Systems · Latest release found: OrCAD X / Allegro X 25.1 (announced 2025-10-29; ISR #1 2025-12-12); OrCAD Xplore announced 2026-11-09 · Earlier teardown: none

**Scope split with researcher B.** This file owns schematic capture, PSpice and OrCAD X pricing tiers. Layout (Presto / Classic PCB editors), Allegro X AI placement and Sigrity are researcher B's Cadence coverage; layout rows below give only what was seen in passing and point there.

## In one paragraph

OrCAD X is Cadence's mid-market PCB suite: OrCAD X Capture (schematic, CIS part management, Live BOM), PSpice (the industry-standard SPICE with a large vendor model library) and the Presto/Classic PCB editors, with an OrCAD X Workspace in the cloud. It is sold in three editions — **Standard** (perpetual, individuals), **Professional** (term, small teams; adds PSpice, Live BOM, constraint management, Sigrity X SI/PI) and **Professional Plus** (adds **PSpice Advanced Analysis: Smoke, Monte Carlo, Sensitivity**, plus MATLAB/Simulink and Celsius thermal co-simulation). No list prices are published. The verification feature most relevant to Circuit OS is **PSpice Smoke**, which compares simulated stresses against each component's safe operating limits — a simulated version of the voltage/current rating checks the owner's page credits only to Circuit OS. Cadence's newest launch, **OrCAD Xplore** (2026-11-09), adds natural-language AI for component research, selection, replacement and sourcing inside Capture, with DigiKey purchasing.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Partial (components only) | OrCAD Xplore: natural-language AI for component research, selection, replacement and sourcing; not prompt-to-schematic | read (press release) | https://finviz.com/news/419720/cadence-orcad-xplore-design-platform-unifies-design-component-intelligence-and-procurement-to-accelerate-electronics-system-development (2026-11-09) |
| A2 | Structured spec input | Not found | — | not found | — |
| A3 | Design as code | No | Capture TCL scripting exists | summary (from memory, unverified) | — |
| A4 | Imports a design | Yes | Standard importers (Altium, PADS, EAGLE etc.) | summary (from memory, unverified) | — |
| A5 | Requirement artifact | Not found | — | not found | — |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Not found | Xplore is about components, not topology | read (scope of release) | as A1 |
| B2 | AI copilot in schematic | Partial | Xplore NL component assistant inside Capture; 2023 launch promised a "generative AI design assistant" (layout-side) | read / summary | as A1 ; https://www.goengineer.com/en-us/cadence/orcad-x |
| B3 | Part selection with reasons | Partial | Xplore shows lifecycle, availability, price, lead time, compliance and qualified alternatives with manufacturer content (TI, ST, Murata, Molex, DigiKey); reasoning output not described | read | as A1 |
| B4 | Reusable modules / reference designs | Yes | Manufacturer reference designs in Xplore; hierarchical blocks in Capture | read (Xplore) | as A1 |
| B5 | ERC (voltage-aware?) | Partial | Capture DRC is pin-type based (from memory, unverified); **voltage/current/power stress is checked by PSpice Smoke** against safe operating limits (Professional Plus) | summary | https://resources.pcb.cadence.com/blog/2025-advanced-pspice-features-for-circuit-analysis (search snippet) |
| B6 | Hierarchy / variants | Yes | BOM variants, groups and subgroups in Capture CIS 25.1 guide | read | https://resources.pcb.cadence.com/orcad-x-technical-docs-source/orcad-x-public-release-notes |
| B7 | Library | Yes | Ultra Librarian 16M+ symbols/footprints/3D models in Xplore; PSpice model library ~33,000 parts (reseller figure for PSpice Designer Plus) | read | as A1 ; https://www.ema-eda.com/store/pcb-products/pspice-designer-plus/ |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes (Professional and up) | PSpice analog/mixed-signal: DC, AC, noise, transient, auto-convergence, behavioural models, IBIS, Probe | read (reseller) | https://www.ema-eda.com/store/pcb-products/pspice-designer-plus/ ; https://www.goengineer.com/en-us/cadence/orcad-x |
| C2 | Monte Carlo / worst case | Yes (Professional Plus) | PSpice Advanced Analysis: Monte Carlo (statistical, tolerances), Sensitivity, Optimizer, Smoke; "yield" and "reliability" analysis named by reseller | read (reseller) / summary (Cadence blog) | https://www.goengineer.com/en-us/cadence/orcad-x ; https://resources.pcb.cadence.com/blog/2025-advanced-pspice-features-for-circuit-analysis |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | Yes (Professional) | Sigrity X in-design SI/PI — researcher B's scope | read (reseller) | https://www.goengineer.com/en-us/cadence/orcad-x |
| C5 | Power integrity | Yes (Professional) | Sigrity X PI — researcher B | read (reseller) | as C4 |
| C6 | Thermal | Yes (Professional Plus) | Celsius Thermal co-simulation | read (reseller) | as C4 |
| C7 | EMC / EMI | Not found | — | not found | — |
| C8 | Creepage from voltage | Not found | — | not found | — |

### D. PCB layout (researcher B owns this; passing facts only)

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Yes (edition not confirmed) | "AI-Powered placement & Fanout assistance" in the edition matrix | read (reseller) | https://www.goengineer.com/en-us/cadence/orcad-x |
| D2 | Automatic routing | See researcher B | — | — | — |
| D3 | Constraint management | Yes (Professional) | Constraint Manager | read (reseller) | as D1 |
| D4 | Stackup / impedance | See researcher B | — | — | — |
| D5 | DRC | Yes | DesignTrue DFM: ~100 rules (Standard), 3,000+ (Professional) | read (reseller) | as D1 |
| D6 | 3D / MCAD | See researcher B | — | — | — |
| D7 | Length tuning | See researcher B | — | — | — |
| D8 | HDI / flex | See researcher B | — | — | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | PSpice "Plus" lists SystemC/C++ modelling and HW/SW co-simulation — simulation of code, not generation | read (reseller) | https://www.ema-eda.com/store/pcb-products/pspice-designer-plus/ |
| E2 | Pin-mux | Not found | — | not found | — |
| E3 | Compiles / tests firmware | Partial | HW/SW co-simulation (SystemC/C++) in PSpice Designer Plus | read (reseller) | as E1 |
| E4 | Protocol stacks | Not found | — | not found | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence grading | Not found | — | not found | — |
| F3 | Automated review | Yes | Smoke (stress vs safe operating limits), DRC, DFM rules | summary / read | as B5, D5 |
| F4 | Datasheet-grounded checks | Partial | Smoke uses model-embedded rating parameters; page citation not found | inference (from Smoke description) | — |
| F5 | Audit trail of AI actions | Not found | — | not found | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | — | not found | — |
| G2 | Version history | Yes | OrCAD X Workspace handles versioning and library sync | read (reseller) | https://www.goengineer.com/en-us/cadence/orcad-x |
| G3 | Comments / roles | Yes (Professional) | Shared workspaces; Symphony multi-designer layout | read (reseller) | as G2 |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | Basic BOM (Standard); Live BOM (Professional) | read (reseller) | as G2 |
| H2 | Live price and stock | Yes (Professional) | Live BOM: real-time pricing, availability, EOL; Xplore integrates DigiKey | read | as G2 ; as A1 |
| H3 | Alternates | Partial | "Qualified alternatives" in Xplore; checking method not stated | read | as A1 |
| H4 | Fabrication outputs | See researcher B | — | — | — |
| H5 | DFM | Yes | DesignTrue DFM checks | read (reseller) | as D5 |
| H6 | Order inside the tool | Partial (parts) | Xplore shopping cart buys the BOM through DigiKey; no fab ordering found | read | as A1 |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Desktop + cloud workspace | Editors local; OrCAD X Workspace cloud; single-user licences on up to 5 devices | read (reseller) | as G2 |
| I2 | API / CLI | Partial | Capture TCL, SKILL on layout side | summary (from memory, unverified) | — |
| I3 | On-prem / certifications | Not found (for OrCAD X) | Cadence OnCloud platform | summary | https://www.eejournal.com/industry_news/cadence-unveils-next-generation-ai-driven-orcad-x-delivering-up-to-5x-faster-pcb-design-and-enabled-with-cadence-oncloud |
| I4 | Pricing | Not published. Third-party: Standard **USD 1,280/year** single user via Cadence OnCloud (FitGap); "from USD 1,500/user/year" (Capterra, edition unstated); "USD 107/month" (SourceForge). Professional and Professional Plus: quote only. Reseller promotion up to 30% off for switchers until 2026-08-31. Read 2026-11-13 | summary | https://us.fitgap.com/products/004753/orcad-pcb-designer ; https://www.capterra.com/p/10015795/OrCAD-X/ ; https://softprom.com/orcad-x-special-offer |
| I5 | Sold to | Individuals (Standard) to small teams (Professional); Xplore for individuals and small teams | read | as A1 ; as G2 |
| I6 | Company facts | Cadence (public); see researcher B | — | — |
| I7 | KiCad / Altium interop | Not found (KiCad) | Altium imports OrCAD (variants since Altium 26.9) | read (Altium side) | https://www.altium.com/documentation/altium-designer/new |
| I8 | Open source | No | — | — |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Yes (simulation) | PSpice is widely used for power stages; Smoke checks derating | summary | as C2 |
| J3 | RF / high-speed | Yes | Sigrity X (researcher B) | read (reseller) | as C4 |
| J4 | Safety / regulatory | Partial | Smoke derating; compliance data in Xplore | summary / read | as B5, A1 |
| J5 | Stated limits | Not found | — | not found | — |

## What the owner's market page gets wrong (indirectly)

OrCAD X is not on the page. Its existence weakens two "only you" cells: **voltage/current rule checks** (PSpice Smoke checks every component's simulated stress against its ratings, in Professional Plus) and **tolerance analysis** (PSpice Monte Carlo and Sensitivity).

## Where it is ahead of Circuit OS / where Circuit OS is ahead

**OrCAD X ahead:** PSpice Smoke and Monte Carlo on arbitrary circuits with a large vendor model library; SI/PI/thermal co-simulation; Live BOM; manufacturer content from TI, ST, Murata; mature capture and layout.

**Circuit OS ahead:** generates the circuit; *proves* bounds over the whole tolerance box (z3 over tolerance boxes, `backend/proof/`) where Monte Carlo samples it; graded claims and refusals; compiled firmware; consequential explanations; free-tier economics for small users.

## Not verified

- Any list price on cadence.com (datasheet page returned 403; no public prices).
- Whether Standard includes any PSpice.
- Which edition includes AI-powered placement.
- Whether a 2026 OrCAD X release (after 25.1) exists — none found.
- OrCAD Xplore pricing and availability.
- Capture ERC behaviour and import formats (from memory).
