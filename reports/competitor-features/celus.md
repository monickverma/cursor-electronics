# CELUS (CELUS Design Platform / Design Assistant) — feature inventory
Read 2026-11-13. Vendor: CELUS GmbH (Munich; also Porto, Austin) · Latest release found: agentic Design Assistant workflow, beta (announced 2026-10-29); Mouser pricing in the BOM (2026-11-05); release notes 2026.10.14 · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\celus.md` (2026-10-21)

## In one paragraph
CELUS is a browser platform that turns a requirement conversation into an architecture (block diagram), resolves each block to a "CUBO" (a pre-built, manufacturer- or CELUS-engineered functional circuit with its parts), and emits a reference schematic and BOM as a native project for Altium, KiCad, Fusion/Eagle, Siemens and (beta) OrCAD X. Its business model is two-sided: engineers use the platform, and component makers (NXP, RECOM, Alif, BrainChip, Variscite, SomDevices, Ambient Scientific in 2026) pay to have their parts and reference designs matched into designs. Since 2026-10-29 an agentic Design Assistant (beta) writes an "Intent Document" and plan, waits for the engineer's approval, cites a datasheet for every component recommendation, and checks the result against the Intent Document. Where it stops: no simulation of any kind, no layout (the KiCad/Altium export includes a board file but the user places parts), no firmware, rule-based port-type checks only, and breadth is bounded by the CUBO library, which users cannot extend themselves.

## Features

Source key (all read 2026-11-13):
[home] https://www.celus.io/ (page dated 2026-11-12) · [news] https://www.celus.io/news ·
[agent] https://www.celus.io/news/celus-brings-ai-agents-to-architecture-and-component-decisions-in-electronics-design (2026-10-29) ·
[feb] https://www.celus.io/news/from-rough-idea-to-validated-schematic-how-ai-transforms-component-selection (2026-02-12) ·
[mar] https://www.celus.io/news/transforming-customer-engagement-and-design-experience (2026-03-09) ·
[mouser] https://www.celus.io/news/celus-and-mouser (2026-11-05) · [kb] https://www.celus.io/knowledge ·
[val] https://celus.io/knowledge/interfaces-ports-specs-and-connection-validation · [exp] https://celus.io/knowledge/complete-your-project ·
[mcp] https://celus.io/knowledge/claude-connector · [rn1014] https://celus.io/knowledge/2026.10.14 · [rn0708] https://celus.io/knowledge/2026.07.08 ·
[about] https://www.celus.io/about

### A. Input and intent
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Yes | Design Assistant takes "requirements, sketches, or vague goals"; works on phones since 2026-10 | read | [feb], [rn1014] |
| A2 | Structured form / spec input | Yes | Guided questions on interfaces, power budget, cost, compliance recorded in an Intent Document; project requirements editable (also via MCP) | read | [agent], [mcp] |
| A3 | Design as code | No / Not found | Block-diagram canvas and CUBO library; no language | not found ([kb]) | — |
| A4 | Imports existing design | Partial | "Improved KiCad import and export" (release notes 2026-08-19); scope of import not stated | read (KB index) | [kb] |
| A5 | Requirement kept as own artifact | Yes | Intent Document with step-by-step plan; the assistant checks the design against it and flags unmet requirements | read | [agent] |
| A6 | Clarifying questions / refusal | Yes (questions); Partial (refusal) | Asks questions "until the design intent is complete"; nothing runs until the engineer approves the plan. A block "can resolve without a matching CUBO" when no validated CUBO covers it; since 2026-10 "designs without a valid solution return suggestions instead of a timeout" | read | [home], [agent], [kb], [rn1014] |

### B. Schematic
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Yes | Block diagram → CUBOs resolved → reference schematic + BOM | read | [home], [agent] |
| B2 | AI edits inside an existing schematic | Partial | Editable blocks, CUBO lock/unlock, component replacement; "CELUS CAD edits" mentioned (2026-10); AI edits a CELUS project, not an arbitrary imported schematic | read | [mcp], [rn1014] |
| B3 | Part selection with reasons | Yes | Each component recommendation "links to the datasheet behind it" (agentic beta); parts recommender works against specs, stock, lifecycle; component data from Accuris (ex-IHS Markit) | read | [agent], [home], [kb] |
| B4 | Reusable modules / reference designs | Yes | CUBOs (smallest reusable functional block) authored by CELUS and manufacturers; reference projects searchable; module suggestions replacing several blocks (2026-10). Users cannot create their own CUBOs, only request them | read | [kb], [rn1014] |
| B5 | ERC (voltage-aware?) | Partial | Rule-based port-type matching (I2C to I2C, SPI needs supply + CS GPIO); I2C blocks must have "compatible supply voltages". No general ERC or power-budget check described; warnings "over the coming months" (Feb 2026) | read | [val], [feb] |
| B6 | Hierarchy / multi-sheet | Partial | Blocks and modules; multi-sheet output not documented | inference from [kb] block/module model | [kb] |
| B7 | Library; symbols/footprints from datasheets | Partial | "Millions of components" (meta description); CUBO library; component data from Accuris; editable .lbr export to Fusion. No datasheet-to-footprint generation found. Older press: about 17 M parts (summary) | read (home meta); summary (count) | [home], [kb] |

### C. Simulation and analysis
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | No simulation on any page read | not found ([home], [agent], [kb]) | — |
| C2 | Tolerance / Monte Carlo | Not found | — | not found (same) | — |
| C3 | Formal proof | Not found | — | not found (same) | — |
| C4 | Signal integrity | Not found | — | not found | — |
| C5 | Power integrity | Not found | Intent captures "power budget" but no check described | read (absence) | [agent] |
| C6 | Thermal | Not found | — | not found | — |
| C7 | EMC / EMI | Not found | — | not found | — |
| C8 | Creepage / clearance from voltage | Not found | — | not found | — |

### D. PCB layout
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | No | KiCad/Altium packages include a board file, but "it is time for you to place components on the PCB board" | read | [exp] |
| D2 | Automatic routing | Not found | — | not found ([exp], [kb]) | — |
| D3 | Constraint management | Not found | — | not found | — |
| D4 | Stackup / impedance | Not found | — | not found | — |
| D5 | DRC | Not found | — | not found | — |
| D6 | 3D / MCAD | Not found | Layout preview in CUBO view (2025) only | read (KB index) | [kb] |
| D7 | Length tuning / diff pairs | Not found | — | not found | — |
| D8 | HDI / flex | Not found | — | not found | — |

### E. Firmware
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found ([home], [agent], [kb]) | — |
| E2 | Pin-mux / peripheral config | Partial | Port/interface assignment on links ("only interfaces common to the connected functionalities can be assigned", 2025-10); GPIO as SPI chip select | read | [val], [kb] |
| E3 | Compiles / tests firmware | Not found | — | not found | — |
| E4 | Protocol stacks | Not found | — | not found | — |

### F. Explanation, evidence, review
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains why each choice was made | Partial | Datasheet link per recommendation; answers questions about BOM alternatives "with citations" | read | [agent], [feb] |
| F2 | Confidence / evidence grading | Not found | — | not found ([agent]) | — |
| F3 | Automated design review | Partial | Agent checks design against the Intent Document and proposes fixes for reported errors; named agents design_checker and design_verifier (no checks described) | read | [agent], [home] |
| F4 | Datasheet-grounded checks with cited pages | Partial | Citations to the datasheet or specification per recommendation; page-level citation not stated | read | [agent] |
| F5 | Audit trail of AI actions | Partial | Plan approval gate; MCP changes need user confirmation. No log of AI actions documented | read | [agent], [mcp] |

### G. Iteration and collaboration
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Engineer can "stop, redirect, or edit at any step"; Claude connector edits blocks and links | read | [agent], [mcp] |
| G2 | Version history / diff | Partial | Project clone via MCP; no version history found | read (clone); not found (history) | [mcp] |
| G3 | Comments / review / roles | Not found | — | not found ([kb] index) | — |

### H. Supply chain and manufacturing
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM spreadsheet, CSV with extra component information | read | [mcp], [kb] |
| H2 | Live price and stock | Yes | Mouser price breaks, stock, order quantity, line total, packaging, plus manufacturer lead time (2026-11-05); Mouser only distributor named | read | [mouser] |
| H3 | Alternates / substitution | Yes | Alternatives for passive, electromechanical and interconnect parts; agent ranks substitutes for costly or long-lead parts by price, lead time or preferred supplier; EOL recovery "proposes alternatives from your catalog". How a substitute is checked electrically is not described | read | [feb], [agent], [home] |
| H4 | Fab outputs | No / Not found | Outputs are ECAD projects, PDF report, BOM; no Gerber | read (absence) | [exp], [kb] |
| H5 | DFM / DFA | Not found | — | not found | — |
| H6 | Order from fab | Not found | — | not found | — |

### I. Platform and business
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Browser | app.celus.io; phone support (2026-10); embedded "Design Platform Experience" on NXP.com (2026-09-17) | read | [home], [rn1014], [news] |
| I2 | API / CLI / headless | Partial | MCP: manufacturer product data reaches agents over MCP; Claude connector to create projects, edit block diagrams, resolve CUBOs, generate schematic PDFs, BOMs and CAD packages (writes need confirmation). No public REST API found | read | [home], [mcp] |
| I3 | On-prem / certifications | Not found | — | not found ([about], [home]) | — |
| I4 | Pricing | Partial | No pricing page. AI Credits introduced 2026-07-08 and "can be purchased directly in the Design Assistant" (2026-10-14); amounts not stated. Earlier: "free to the user" (Embedded.com, about 2022); manufacturers pay | read (credits); summary (free model) | [rn0708], [rn1014] |
| I5 | Sold to | — | Hardware engineers (users) and component manufacturers/distributors (payers): NXP, RECOM, Alif, BrainChip, Variscite, SomDevices, Ambient Scientific, AGS Devices, Atlantik Elektronik | read | [news], [home] |
| I6 | Company facts | — | Founded 2018 in Munich by Tobias, Alexander Pohl and André Alcalde; funding and headcount not on site (earlier teardown: EUR 25 M Series A 2022, summary) | read | [about] |
| I7 | Interop KiCad/Altium/OrCAD | Yes | Altium project (.PrjPCB with schematic and board), KiCad v7–v9 project (.kicad_sch + empty .kicad_pcb), Fusion/Eagle .sch and .lbr, Siemens Xpedition, OrCAD X XML (beta, 2026-06-29) | read | [exp], [agent], [kb] |
| I8 | Open source | No | Proprietary SaaS | inference | — |

### J. Domain coverage
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | No RS-485 / 4–20 mA content found; possible as CUBOs | not found ([kb]) | — |
| J2 | Power electronics | Partial | RECOM power designs added as CUBOs (2026-10-13) | read (news index) | [news] |
| J3 | RF / high-speed | Partial | SoM and edge-AI processor CUBOs (NXP i.MX, μSMARC); no SI | read (news index) | [news] |
| J4 | Safety / regulatory | Partial | Intent capture asks about "compliance"; no standards check | read | [agent] |
| J5 | Stated limits | Partial | Bounded by CUBO coverage; KiCad v7–v9 only; earlier teardown: typical project 200–1,000 components | read; checked (earlier) | [kb], [exp] |

## What changed since the 2026-10-21 teardown
- **Agentic Design Assistant (beta, 2026-10-29):** Intent Document, plan approval before work, datasheet citation per component, check against the Intent Document, ranked substitutes. The teardown's "unnamed design_checker" now has a described behaviour (check against stated intent), though the rules are still not published.
- **Mouser pricing and stock in the BOM (2026-11-05).**
- **Claude MCP connector** (KB page, 2026-11-12) with write actions — the teardown had only "MCP access to product data".
- **Exports clarified:** the KiCad and Altium packages contain a board file, but placement is manual. The open question "does Celus still export a floor plan" is answered: an unplaced board file, not a floor plan.
- **Validation clarified:** rule-based port-type and interface checks, including a supply-compatibility rule for I2C.
- **Pricing:** AI Credits are now purchasable (2026-10-14). "Free to the user" is no longer the whole picture.

## What the owner's market page gets wrong about this product
| Row | Page implies | Evidence (2026-11-13) |
|---|---|---|
| Component selection with justification | Only you / Celus partial | Celus cites the datasheet behind every recommendation (beta). Circuit OS's edge is consequential explanation, not justification as such |
| Confidence scores | Only you | Not found at Celus — holds as "not found" |
| Stateful diff-and-patch editing | Only you | Celus has editable blocks and conversational redirection; no patch/diff found. Holds |
| Traceable requirement / audit trail | Only you | Celus keeps an Intent Document and checks the design against it — the nearest analogue to Circuit OS's IntentIR in this group |
| BOM with live pricing | — | Celus: Mouser live since 2026-11-05 — same distributor as Circuit OS's optional pricing |
| Private component libraries | — | Celus EOL recovery uses "alternatives from your catalog", implying a customer catalogue; users cannot author CUBOs |
| SPICE, firmware, PCB | Celus no | Correct as "not found" |

## Where it is ahead of Circuit OS / where Circuit OS is ahead
Circuit OS side cites `MENTAL_MODEL.md` and `.claude/CLAUDE.md`.

CELUS ahead:
- Breadth: any function covered by a CUBO, millions of parts, SoMs and processors; Circuit OS has five templates plus composition blocks and refuses the rest (`MENTAL_MODEL.md` §3–4).
- Native ECAD handoff to Altium, KiCad, Fusion, Xpedition, OrCAD X; Circuit OS exports only a net-label `.kicad_sch` (`MENTAL_MODEL.md` §4).
- Manufacturer partnerships and an embedded presence on NXP.com: distribution Circuit OS does not have.
- Datasheet citation per component recommendation.

Circuit OS ahead:
- Physics: ngspice simulation and z3 proofs over tolerances; CELUS has no simulation found.
- Firmware compiled before it is shown; CELUS has none.
- Experimental placement and routing; CELUS hands an unplaced board.
- Retry rule: Circuit OS forbids the model rewriting the requirement to fit (`.claude/rules/code-style.md`); CELUS returns "suggestions" when no solution exists — whether those alter the requirement is not stated.

## Not verified
- Price of AI Credits and any plan structure.
- What design_checker and design_verifier check beyond the port rules and the Intent Document comparison.
- Library size today (millions per meta description; no number).
- Whether KiCad import brings in an existing schematic for AI editing.
- Funding since 2022; headcount; security certifications.
