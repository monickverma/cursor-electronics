# Diode Computers (Zener, pcb, self-serve builder) — feature inventory
Read 2026-11-13. Vendor: Diode Computers, Inc. (Brooklyn, NY) · Latest release found: no dated 2026 product release; diodeinc/pcb repository (MIT, 516 stars when read, no release date shown); skill listing updated 2026-08-05 (third party) · Earlier teardown: none

## In one paragraph
Diode is a design-and-manufacture service built on an open-source design-as-code stack. Its language **Zener** (Starlark, a strict subset of Python) describes schematics as modules, nets and interfaces; its Rust **pcb** CLI builds Zener and generates a KiCad 10 layout file for a human or agent to finish in KiCad. Customers either use a **self-serve** AI agent (input: "a description, block diagram or KiCad project"; instant fab and assembly quotes; manufacturability checks) or the **enterprise** service where Diode's engineers design the board ("from USD 10,000 per design, plus fab"), and Diode sources parts and assembles in-house in Brooklyn. Its showcase boards are serious (10-layer SDR with Zynq UltraScale+ and AD9361; Jetson Orin NX carrier). Where it stops: the agent drafts and reviews; engineers own routing strategy and signal integrity; a read-only AI reviewer ranks findings critical/warning/note; there is no published simulation feature on the vendor site (the blog says modules "can run SPICE simulations automatically", unconfirmed in the README).

## Features

Source key (read 2026-11-13):
[home] https://www.diode.computer/ · [blog] https://blog.diode.computer/llms-full.txt (four posts, undated) ·
[repo] https://github.com/diodeinc/pcb · [anth] https://claude.com/resources/articles/making-claude-a-better-electrical-engineer (2025-12-12) ·
[build] https://build.diode.computer/ (navigation shell only)

### A. Input and intent
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | Yes | Self-serve input: "A description, block diagram or KiCad project" | read | [home] |
| A2 | Structured spec | Partial | Block diagram input; testbenches encode requirements such as "at least 22uF of capacitance between power and ground" | read | [home], [anth] |
| A3 | Design as code | Yes | Zener (Starlark), open source (MIT); modules, interfaces, version control and code review | read | [blog], [repo] |
| A4 | Imports existing design | Yes | KiCad project as input; AI reviewer reads schematics, layouts, Zener, KiCad projects, BOMs | read | [home], [blog] |
| A5 | Requirement as artifact | Partial | Requirement testbenches in the reference-design pipeline; customer-facing traceability not described | read | [anth] |
| A6 | Clarifying questions / refusal | Not found | Reviewer instructed not to "invent findings without evidence" | read (reviewer only) | [blog] |

### B. Schematic
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Schematic from intent | Yes | "Your requirements become a schematic and layout, written as code that our AI agent and engineers can check" | read | [home] |
| B2 | AI edits existing schematic | Yes | Agent skill writes and edits Zener; edits checked in pull requests | read ([anth]); summary (skill listing) | [anth] |
| B3 | Part selection with reasons | Partial | Agent reads datasheets; pcb CLI searches components and datasheets (skill listing); no stated reasons | summary | skill listing via search |
| B4 | Reusable modules | Yes | Zener modules; about 250 reference designs drafted in two weeks; open reference designs (BLDC controller, RP2040 debug probe, CM5 carrier) | read | [blog], [home] |
| B5 | ERC (voltage-aware?) | Partial | Static checks on the full netlist: "power paths, signal direction, floating pins, and miswired rails" | read (blog claim) | [blog] |
| B6 | Hierarchy | Yes | Modules compose hierarchically in code | read | [blog] |
| B7 | Library | Partial | KiCad library as base; internal Registry (not public); "Librarian" and "Parts" sections in the builder | read | [blog], [build] |

### C. Simulation and analysis
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Partial | Blog: "each module can run SPICE simulations automatically", returning gain, bandwidth, stability margins; not in the README or homepage | read (blog); not found ([repo], [home]) | [blog] |
| C2 | Tolerance / Monte Carlo | Not found | — | not found | — |
| C3 | Formal proof | Not found | Testbench assertions on requirements (not proof) | read | [anth] |
| C4 | SI | No (left to engineers) | "Engineers still handle routing strategy and signal integrity" | read | [blog] |
| C5–C8 | PI, thermal, EMC, creepage | Not found | — | not found | — |

### D. PCB layout
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | Claude proposes decoupling-cap placement, groups bulk caps, aligns labels from KiCad board files | read | [blog] |
| D2 | Automatic routing | Not found | Engineers route; `pcb layout` emits `.kicad_pcb` for KiCad | read | [blog], [repo] |
| D3 | Constraints | Not found | — | not found | — |
| D4 | Stackup | Not found | 10-layer showcase boards | read | [home] |
| D5 | DRC | Yes | "Every design is checked against the fab's rules before boards are made" | read | [home] |
| D6 | 3D / MCAD | Not found (KiCad provides) | — | inference from KiCad dependency | [repo] |
| D7–D8 | Length tuning, HDI | Not found | — | not found | — |

### E. Firmware
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Partial | Claude "can draft bring-up firmware"; "not fully solved" | read | [blog] |
| E2–E4 | Pin-mux, compile, protocol stacks | Not found | Enterprise tier includes "hardware bring-up" as a service | read | [home] |

### F. Explanation, evidence, review
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Evidence grading | Partial | Reviewer ranks findings critical / warning / note | read | [blog] |
| F3 | Automated design review | Yes | Read-only AI EE reviewer; found 22 or 24 bugs (figures conflict) in comma.ai's harness challenge and won its USD 1,000 prize | read | [blog] |
| F4 | Datasheet-grounded, cited | Partial | Reviewer reads datasheets; citations not described | read | [blog] |
| F5 | Audit trail | Yes (by construction) | Designs in version control with code review and pull requests | read | [blog], [anth] |

### G. Iteration and collaboration
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Partial | Agent edits Zener on request (self-serve) | inference from [home] + skill listing | — |
| G2 | Version history / diff / branch | Yes | Git: diffs, branches, review | read | [blog] |
| G3 | Review workflow | Yes | Pull-request review; enterprise Slack channel | read | [anth], [home] |

### H. Supply chain and manufacturing
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | Sourcing of every part by Diode | read | [home] |
| H2 | Live price and stock | Partial | Instant fab and assembly quotes; distributors not named | read | [home] |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fab outputs | Yes (via KiCad) | KiCad project; Diode fabricates | inference from [repo] + [home] | — |
| H5 | DFM | Yes | Manufacturability checks before fab | read | [home] |
| H6 | Order inside the tool | Yes | Self-serve quote and order; in-house assembly in Brooklyn, prototype to production | read | [home] |

### I. Platform and business
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Browser + CLI | build.diode.computer; pcb CLI | read | [build], [repo] |
| I2 | API / CLI / headless | Yes | `pcb build`, `pcb layout`; agent skill for Claude | read | [repo] |
| I3 | On-prem / certifications | Not found | — | not found | — |
| I4 | Pricing | Partial | Self-serve: per-order quote; enterprise "From $10,000 per design, plus fab" | read | [home] |
| I5 | Sold to | — | Hardware startups and robotics/defence-adjacent teams (Physical Intelligence, Saronic named in blog) | read | [blog] |
| I6 | Company facts | — | Founded 2024 by Davide Asnaghi and Lenny Khazan; Series A led by a16z, July 2025, reported USD 11.4M; KiCad Platinum Sponsor; headcount 9→13 (Aug 2026, Caplight, third party) | read (a16z, sponsor); summary (amount, headcount) | [home], [blog] |
| I7 | Interop | Yes (KiCad) | Outputs KiCad; requires KiCad 10.x for layout | read | [repo] |
| I8 | Open source | Yes (toolchain) | Zener and pcb under MIT; service and agent proprietary | read | [repo] |

### J. Domain coverage
| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | — |
| J2 | Power electronics | Partial | 3-phase BLDC motor controller reference design | read | [home] |
| J3 | RF / high-speed | Yes (service) | 10-layer SDR 70 MHz–6 GHz; Jetson carrier | read | [home] |
| J4 | Safety standards | Not found | — | not found | — |
| J5 | Stated limits | Not found | — | not found | — |

## What the owner's market page gets wrong about this product
Not on the page. Its relevance: Diode is the closest analogue to Circuit OS's architecture (intent → structured representation → deterministic compiler to KiCad), but with a general-purpose language instead of a closed IR catalogue, and with a factory behind it.

## Where it is ahead of Circuit OS / where Circuit OS is ahead
Diode ahead: open language with any part and any topology; real 10-layer boards built and assembled; fabrication and assembly in-house; git-native review; MIT toolchain that agents already use.
Circuit OS ahead: plain-English to finished design without an engineer in the loop for its catalogue; ngspice through a pipeline and z3 proofs (Diode's SPICE claim is blog-only); compiled firmware gate (`.claude/CLAUDE.md`); consequential explanation; refusal outside scope (`MENTAL_MODEL.md` §3).

## Not verified
- Whether SPICE per module ships in the public toolchain.
- Self-serve agent capabilities (builder page renders only a navigation shell without login).
- Series A amount; any 2026 product release.
