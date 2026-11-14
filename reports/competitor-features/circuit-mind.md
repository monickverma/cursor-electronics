# Circuit Mind (ACE, AVE, ELIXIR) — feature inventory
Read 2026-11-13. Vendor: Circuit Mind Limited (London) · Latest release found: AVE (Agentic Verification Engine), launched 2026-10-29, with a USD 25M financing announced 2026-10-28 · Earlier teardown: none (mentioned in the physics report: "generates stress, derating, power and FMECA reports")

## In one paragraph
Circuit Mind sells an enterprise "electronics design intelligence" platform with three applications. **ACE** (Automated Circuit Engineering) takes a block diagram plus requirements and, using what the vendor calls deterministic, physics-based, patented algorithms over "Digital Twins" of tens of thousands of datasheets, selects parts from the customer's approved lists and generates several schematic options optimised for cost, size and power, with a BOM, power analysis, derating analysis, interface control document and FMEA template, exported into Altium, Cadence (OrCAD, System Capture) or Siemens Xpedition. **AVE** (new, 2026-10-29) is a swarm of agents that reviews any schematic, including hand-drawn ones, against datasheets, application notes and the company's own checklists and design rules, self-critiques its findings, and links each to datasheet evidence. **ELIXIR** generates symbol, footprint and parameters from a datasheet. It is sold to large OEMs (BAE Systems, Emerson, Legrand, Schneider Electric) with on-prem and air-gapped options. Where it stops: block-diagram input rather than plain English, no simulation, no layout, no firmware, no published pricing; the "provable accuracy" behind ACE is not documented publicly.

## Features

Source key (read 2026-11-13):
[home] https://www.circuitmind.io/ (©2026) · [plat] https://www.circuitmind.io/platform ·
[ave] https://iconnect007.com/article/152189/circuit-mind-launches-aipowered-pcb-design-verification-platform/152186/design (trade press relaying the 2026-10-29 Globe Newswire release) ·
[fund] https://iconnect007.com/article/152182/circuit-mind-announces-25m-in-funding-to-accelerate-the-rise-of-electronic-design-intelligence/152179/pcb (2026-10-28) ·
[sacra] https://sacra.com/c/circuit-mind/ (search snippet only)

### A. Input and intent
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Not found | ACE starts "from a simple block diagram" and engineering requirements; no free-text prompt documented | read | [plat], [home] |
| A2 | Structured form / spec input | Yes | Block diagram + requirements; customer AML, preferred parts, stock, negotiated pricing as inputs | read | [home], [plat] |
| A3 | Design as code | Not found | — | not found ([plat]) | — |
| A4 | Imports existing design | Yes (for review) | AVE reviews schematics "exported from your ECAD system" or from ACE; formats not stated | read | [home], [plat] |
| A5 | Requirement kept as artifact | Partial | Block diagram and requirements drive generation; Interface Control Document produced. Traceability not described | read | [home] |
| A6 | Clarifying questions / refusal | Not found | — | not found ([plat]) | — |

### B. Schematic
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Yes | Functional schematic with supporting circuitry, multiple options optimised for cost, size, power; uses the customer's symbol/footprint libraries, net naming and drawing standards | read | [home], [plat] |
| B2 | AI inside an existing schematic | Partial | AVE reviews existing schematics (flags, does not edit) | read | [plat] |
| B3 | Part selection with reasons | Partial | "Deterministic, physics-based algorithms and component digital twins"; method and justification not shown | read | [home], [plat] |
| B4 | Reusable modules | Yes | Customer "validated design blocks" calibrate the platform | read | [plat] |
| B5 | ERC (voltage-aware?) | Yes (AVE) | AVE flags incorrect pin connections, voltage violations, interface incompatibilities, missing supporting circuitry; traces every connection and bus | read | [home], [ave] |
| B6 | Hierarchy / multi-sheet | Not found | — | not found | — |
| B7 | Library; from datasheets | Yes | ELIXIR: datasheet → symbol, footprint, parameters; tens of thousands of datasheets as Digital Twins | read | [plat] |

### C. Simulation and analysis
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | — | not found ([home], [plat]) | — |
| C2 | Tolerance / worst case | Partial | Derating analysis (component stress vs ratings); no Monte Carlo found | read | [home], [plat] |
| C3 | Formal proof | Not found | "Provable accuracy" / "self-verifying algorithms" claimed; no method published | read (claim only) | [plat] |
| C4 | Signal integrity | Not found | — | not found | — |
| C5 | Power integrity | Partial | Power analysis (budget), not PDN or IR drop | read | [home] |
| C6 | Thermal | Not found | — | not found ([plat]) | — |
| C7 | EMC | Not found | — | not found | — |
| C8 | Creepage from voltage | Not found | — | not found | — |

### D. PCB layout
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1–D8 | Placement, routing, constraints, stackup, DRC, 3D, length tuning, HDI | Not found | Layout not addressed on any page; funding release says the money will expand the platform "into other stages of the design lifecycle" | read (absence) | [home], [plat], [ave] |

### E. Firmware
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1–E4 | Firmware, pin-mux, compile, protocol stacks | Not found | — | not found ([home], [plat]) | — |

### F. Explanation, evidence, review
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains each choice | Partial | Trade studies across options; per-part reasons not shown | read | [home] |
| F2 | Confidence / evidence grading | Partial | AVE QA pass "critiquing every finding so only the ones that hold up are reported"; no grade scale described | read (trade press) | [ave] |
| F3 | Automated design review | Yes | AVE against datasheets, app notes, checklists, design rules; ACE produces derating, power, FMEA template | read | [plat], [ave] |
| F4 | Datasheet-grounded checks, cited | Yes | Each AVE issue linked "to its component, connection, and datasheet evidence"; page-level citation not stated | read | [home] |
| F5 | Audit trail | Not found | — | not found | — |

### G. Iteration and collaboration
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Not found | — | not found | — |
| G2 | Version history | Not found | — | not found | — |
| G3 | Review workflow | Partial | "Your team makes the final call on every flag" | read | [plat] |

### H. Supply chain and manufacturing
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM in minutes | read | [home] |
| H2 | Live price and stock | Partial | Uses customer stock and negotiated pricing; ERP and supply-chain integration; distributors not named | read | [home], [plat] |
| H3 | Alternates | Partial | Options optimised for cost/size/power and supply availability (search snippet); substitute checking not described | read; summary | [plat] |
| H4–H6 | Fab outputs, DFM, ordering | Not found | — | not found | — |

### I. Platform and business
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Browser / enterprise deploy | ace.circuitmind.io login; managed cloud, private cloud, on-prem, air-gapped | read | [home] |
| I2 | API / CLI | Not found | PLM, ERP and ECAD integrations named; no API docs | read (absence) | [home], [plat] |
| I3 | On-prem / certifications | Yes | On-prem and air-gapped; AVE can run on the customer's own LLMs; Cyber Essentials Plus; no training on customer data | read | [home] |
| I4 | Pricing | Not found | No pricing page | not found ([home]) | — |
| I5 | Sold to | — | Enterprise electronics teams; defence (BAE Systems), industrial (Emerson, Schneider, Legrand), design houses (Design 1st, Nextech, APAG Cosyst) | read | [home], [fund] |
| I6 | Company facts | — | USD 25M announced 2026-10-28 (USD 18.5M Series A led by Norwest + previously unannounced seed led by Third Prime), total USD 33.4M; CEO Tomide Adesanmi; LANL case study: one design in four hours vs two weeks (peer-reviewed per vendor; paper not found); claims 25% BOM cost reduction, 30%+ fewer respins | read (trade press) | [fund], [home] |
| I7 | Interop | Yes | Export to Altium, OrCAD, Cadence System Capture, Siemens Xpedition; formats not named. No KiCad found | read | [home], [plat] |
| I8 | Open source | No | Proprietary | inference | — |

### J. Domain coverage
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Partial | Industrial customers (Emerson PSS, Schneider); no rule library for RS-485/4–20 mA published | inference from customer list | [home], [fund] |
| J2 | Power electronics | Not found | Power analysis is budget-level | read | [home] |
| J3 | RF / high-speed | Not found | — | not found | — |
| J4 | Safety / regulatory | Partial | FMEA template and derating (reliability practice), no standard named | read | [home] |
| J5 | Stated limits | Not found | — | not found | — |

## What the owner's market page gets wrong about this product
Circuit Mind is not on the page; the physics report already flagged that it should be. Its rows would read: natural-language input **not found** (block diagram), schematic **Yes**, component selection **Yes**, voltage/current rule checks **Yes** (AVE "voltage violations"), derating and FMEA **Yes**, private component libraries **Yes** (AML, customer libraries, ELIXIR), on-prem **Yes**. That breaks the page's "Only you" on voltage/current rule checks and on datasheet-grounded checking.

## Where it is ahead of Circuit OS / where Circuit OS is ahead
Circuit Mind ahead: reviews any existing schematic (Circuit OS checks only what it generated); datasheet-to-library generation; derating and FMEA reports; enterprise deployment (on-prem, air-gapped); named enterprise and defence customers; exports to the major commercial ECAD tools (Circuit OS: net-label `.kicad_sch`, `MENTAL_MODEL.md` §4).

Circuit OS ahead: plain-English input; ngspice simulation and z3 proofs over tolerance boxes, with each claim's method stated (physics report table) where Circuit Mind publishes no method for "provable accuracy"; firmware compiled before display (`.claude/CLAUDE.md`); experimental board layout; published, inspectable design (the repo).

## Not verified
- The LANL peer-reviewed study (searched, not found).
- What "deterministic, physics-based" selection actually computes; how options are scored.
- AVE input formats, pricing, and whether its findings carry datasheet page numbers.
- Whether ACE's derating uses simulation or hand formulas.
