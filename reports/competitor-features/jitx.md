# JITX — feature inventory
Read 2026-11-13. Vendor: JITX Inc. (Berkeley / San Jose) · Latest release found: `jitx` 4.6.x Python packages, agent skills `jitx-skills` 1.8.1, in the agent app note "Last updated on Nov 10, 2026" ([agent]) · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\jitx.md` (2026-10-21)

## In one paragraph

JITX is board design as code. The engineer, or "your approved AI", writes and edits a Python design program that states requirements, constraints, stackups and parts as parametric queries. A licensed native runtime turns it into a schematic, pin assignments and a routed layout. The runtime includes a topological autorouter, SI routing that meets timing, skew and insertion-loss constraints, and an HFSS loop for RF and high-speed structures ([home], [autorouter], [si]). Buyers are aerospace, defence and large-OEM hardware teams: the homepage shows Honeywell Aerospace, Lockheed Martin and OpenAI ([home]). It automates the parts of a design that can be written as rules and constraints. It does not take English requirements, write firmware, explain choices, or ground checks in datasheets. Its checks are rule checks the designer writes, constraint satisfaction inside the router, and full-wave simulation through Ansys. No proof is claimed.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Partial | No built-in prompt box. An external agent with the JITX skills installed edits the design through the terminal; "AI writes the code" | read | [home], [agent] |
| A2 | Structured spec / requirements input | Yes | Requirements, constraints, stackups and rules are expressed in Python; parts are parametric queries such as `Resistor(resistance=10 * kohm, tolerance=AtMost(1 * pct))` | read | [home], [parts] |
| A3 | Design as code | Yes | Python (≥ 3.12), `jitx` 4.6.x; earlier versions used the Stanza DSL; moved to Python in 2025-Q4 per one profile. Closed: needs a licensed native runtime (`jitx runtime install`) | read (Python, runtime); summary (switch date) | [agent], [ieee-profile] |
| A4 | Imports an existing design | Not found | Pricing page lists "KiCad and Altium integration" without saying the direction; no import command in the CLI export reference | not found (pricing, export reference) | [pricing], [export] |
| A5 | Requirement kept as its own artifact | Partial | Requirements live as code in the design repository, but not as a separate spec object traced to results | inference from [home] | [home] |
| A6 | Asks clarifying questions / refuses out of scope | Not found | — | not found (home, docs index, agent note) | [docs] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | Yes | "generates routing, fencing, pin assignments, and schematic output" from the design code | read | [home] |
| B2 | AI edits inside an existing design | Yes | `jitx design session` + `jitx design exec` let an agent inspect and change a live design (placement edits via `rd.layout.place()`); edits to the runtime layout do not rewrite Python source | read | [agent] |
| B3 | Part selection with stated reasons | Partial | Ordered provider chain (company database → CSV of preferred parts → ideal placeholder parts); first provider with a match wins, best-ranked part used; `parts.lock.json` pins choices. No prose reason per part | read | [parts] |
| B4 | Reusable modules / reference designs | Yes | Docs ship "reusable components, substrates, and patterns" and a complete example design | read | [docs] |
| B5 | ERC, voltage-aware? | Partial | Built-in checks for voltage input/output correctness, pull-ups and rated temperature, driven by toleranced voltage properties on nets; passive derating needs rated values entered. Source is older (Stanza-era) tutorial pages | summary | [check-quickstart] |
| B6 | Hierarchy / multi-sheet | Yes | "Design Hierarchy" concept page | read (title) | [essentials] |
| B7 | Library size; symbols/footprints from datasheets | Not found | No database size stated; a CSV `datasheet` column is copied onto the component but not queried | read (absence on parts page) | [parts] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Partial | `spice` statement attaches ngspice-syntax models to components and compiles a global netlist; no built-in runner or analysis types found. Docs warn some manufacturer models "are incorrect" | summary | [spice] |
| C2 | Tolerance / Monte Carlo / worst case | Partial | Net voltages are toleranced values checked against part ratings (rule check over a range, not Monte Carlo) | summary | [check-quickstart] |
| C3 | Formal proof / exhaustive verification | Not found | No proof claimed; earlier teardown found none | not found (home, docs index) | [home] |
| C4 | Signal integrity | Yes | Impedance-keyed routing structures, diff pairs, `TimingConstraint`, `TimingDifferenceConstraint` (skew), `InsertionLossConstraint`; the router evaluates them continuously and reports unsatisfied ones. HFSS loop: PCIe gen-7 launch at 56 GHz to −30 dB RL in 5 HFSS runs (vendor example) | read | [si], [home] |
| C5 | Power integrity / IR drop | Partial | Homepage says the closed loop "extends to SPICE, power, and thermal analysis"; no doc page found | read (claim only) | [home] |
| C6 | Thermal | Partial | Same homepage claim; no doc page found | read (claim only) | [home] |
| C7 | EMC / EMI | Not found | — | not found (home, essentials index) | [essentials] |
| C8 | Creepage / clearance from voltage | Not found | — | not found | [essentials] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | Agent-driven placement scripts (`place_component.py`, `batch_place.py`); no automatic placer documented. IEEE Spectrum profile says JITX "places parts" | read (scripts); summary (profile) | [agent], [ieee] |
| D2 | Automatic routing | Yes | Topological autorouter: press Q to find "as many legal routes … as possible"; works one layer at a time; heuristic, NP-hard, may give up; no completion rate or time published | read | [autorouter] |
| D3 | Constraint management | Yes | Layout Constraints, Design Constraints and SI Constraints pages; constraints are code | read | [essentials], [si] |
| D4 | Stackup and controlled impedance | Yes | "Substrate & Stackup"; routing structures selected by impedance value | read | [essentials], [si] |
| D5 | DRC | Partial | Issues list with `satisfied` flags; docs say fab spacing rules "are not fully enforced between same-net copper" — run the fab's DRC on exports | read | [si] |
| D6 | 3D view / MCAD exchange | Partial | STEP export | read | [export] |
| D7 | Length tuning / differential pairs | Yes | Router adds deskew bumps and serpentine "signal tuning" to meet timing; `DifferentialRoutingStructure` + `ConstrainDiffPair` | read | [si] |
| D8 | HDI / flex / rigid-flex | Not found | — | not found (essentials index) | [essentials] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | Not mentioned on home or docs index | not found | [home], [docs] |
| E2 | Pin-mux / peripheral configuration | Yes | MCU pin functions declared as `@provide` options (e.g. RP2040 I2C0 SDA on GPIO 0, 4, 8 …); consumers `require()` an interface; "JITX resolves the choice when the routes select physical pads" | read | [pins] |
| E3 | Compiles / tests firmware before showing it | Not found | — | not found | [home] |
| E4 | Protocol stacks | Not found | — | not found | [home] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains why each choice was made | Not found | — | not found (home, parts, agent note) | [parts] |
| F2 | Confidence / evidence grading per decision | Not found | Issues carry `satisfied` and `checks_complete` flags (pass/fail, not graded evidence) | read | [agent] |
| F3 | Automated design review | Partial | `rd.issues()` returns error count, issue text and a `checks_complete` flag; user-written `pcb-check` statements; the agent note says these checks "do not replace schematic review, signal-integrity validation, or manufacturing review" | read | [agent], [checkstmt] |
| F4 | Checks grounded in datasheets (cited pages) | Not found | — | not found | [parts] |
| F5 | Audit trail of AI actions | Partial | Code edits are versionable; runtime layout edits by the agent are not written back to source and "failed edits are not rolled back" | read | [agent] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Partial | Through an external agent; the task author restricts what it may change | read | [agent] |
| G2 | Version history, diff, branch, restore | Partial | Design is code in git; `parts.lock.json` committed so builds reproduce | read (lockfile); inference (git) | [parts] |
| G3 | Comments / review workflow / roles | Not found | — | not found | [docs] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Partial | BOM as xlsx/tsv in the 2026-10-21 teardown (PyPI, read then); the current CLI export reference lists no BOM command | read (absence now) | [export], earlier teardown |
| H2 | Live price and stock | No | Stock is handled by curating the CSV or a company provider; "Live pricing and stock: not covered" | read | [parts] |
| H3 | Alternates / substitution | Partial | `parts-check` flags ideal parts and pinned parts the current source no longer supplies; no automatic substitution | read | [parts] |
| H4 | Fabrication outputs | Partial | `legacy-odb++`, `legacy-step`, `legacy-kicad`, `legacy-edx`, experimental XML; Gerber not listed (comes from the CAD tool after export) | read | [export] |
| H5 | DFM / DFA | Partial | Manufacturing rules, vias, clearances encoded in design files; fab DRC still needed on exports | read | [home], [si] |
| H6 | Order from a fab inside the tool | Not found | — | not found | [pricing] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Desktop | Local Python + native runtime + optional board editor; "runs on your local computer" | read | [home], [agent] |
| I2 | API, CLI, headless | Yes | `jitx` CLI (build, export, session, exec); experimental `jitx.run` API; no MCP server needed | read | [agent], [export] |
| I3 | On-prem / certifications | Partial | Enterprise: locally hosted, air-gapped install. SOC 2 / ITAR / FedRAMP not stated | read | [pricing] |
| I4 | Pricing | Yes | Free and Open: free indefinitely for designs under CERN OHL-Permissive v2. Enterprise: "Program and Enterprise Pricing", no figures. Read 2026-11-13 | read | [pricing] |
| I5 | Who it is sold to | — | Expert hardware teams in aerospace/defence and large OEMs; founder: not a "push button AI expert to make my whole design for me" (DesignCon 2025 interview) | read (logos); summary (quote) | [home], [iconnect] |
| I6 | Company facts | — | $12M Series A led by Sequoia, Sept 2022 (YC, FundersClub, Liquid 2); no later round found. Logos: Honeywell Aerospace, Lockheed Martin, OpenAI, Northrop Grumman, HP. Headcount not found | summary (funding); read (logos) | [seriesA], [home] |
| I7 | Interop with KiCad / Altium / OrCAD-Allegro | Partial | KiCad export; Altium and KiCad "integration" on both plans; Siemens Xpedition and PLM on Enterprise; Cadence not listed | read | [pricing], [export] |
| I8 | Open source / licence | No | Proprietary runtime; the free tier requires the *design* to be open (CERN OHL-P v2) | read | [pricing] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [home] |
| J2 | Power electronics | Not found | — | not found | [home] |
| J3 | RF / high-speed | Yes | 56 GHz PCIe gen-7 launch example; SI constraint system; fibre weave, oxide and roughness modelling mentioned | read | [home], [si] |
| J4 | Safety / regulatory standards | Partial | Tutorial check example tests AEC-Q200 ratings on passives (user-written check) | summary | [checkstmt] |
| J5 | Stated limits | Not found | Layer counts, board size and part limits not stated; autorouter works one layer at a time | read (router); not found (limits) | [autorouter] |

## What changed since the 2026-10-21 teardown

- Package moved from `jitx` 4.4.3 to the 4.6.x line, and JITX now documents an **agent workflow**. Any terminal agent with `jitx-skills` 1.8.1 drives a live design session, and JITX says no MCP server is needed. The app note is dated 2026-11-10 ([agent]).
- The open question "does JITX route automatically" is answered. A topological autorouter exists, works one layer at a time and publishes no completion rate ([autorouter]). No automatic placer is documented.
- The CLI export reference now lists `legacy-kicad`, `legacy-edx`, `legacy-odb++`, `legacy-step` and an experimental XML export. Altium and BOM export, which the teardown read on PyPI, are not on that page ([export]).
- SI is a full constraint system (timing, skew, insertion loss) enforced inside the router, beyond the HFSS example ([si]).

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **JITX ahead:** routed, constraint-driven layout with SI tuning and an HFSS loop. Circuit OS's board engine is experimental: 2-layer, at most 40 parts, behind a flag, with no physics in its layout checks (`reports/Physics layout validation - what the market does and what Circuit OS can build.md`, "What Circuit OS actually has today"). JITX also exports to ODB++, STEP and KiCad, has an enterprise and air-gapped deployment, and has defence and aerospace logos.
- **Circuit OS ahead:** English or a form goes into a requirement IR that the LLM fills, and requests outside the catalogue are refused (`.claude/CLAUDE.md`, `ai/intent_producer.py`, `ai/form_producer.py`). Circuit OS proves properties with z3 over tolerance boxes and grades each claim, where JITX checks voltages over a range with user-written rules (`.claude/CLAUDE.md`, `proof/`, `validation/claims.py`). It writes firmware for the Uno, ESP32 and Black Pill and shows it only once it compiles (`.claude/CLAUDE.md`, `firmware/compile_gate.py`). It gives a consequential explanation of each choice (`MENTAL_MODEL.md` §10). It also records datasheet-figure provenance with page-cited evidence (`data/figures.py`, `figure_evidence.json`).
- **Same idea:** both make the design deterministic from a text artifact. JITX's artifact is a design program written by a person or an agent. Circuit OS's is a requirement, and the design is derived from it.

## Not verified

- Whether the Python-era runtime still ships the Stanza-era built-in voltage, pull-up and derating checks (B5, C2 rest on older tutorial pages).
- Whether a SPICE runner is bundled, or only netlist export (C1).
- Power and thermal analysis beyond the homepage sentence (C5, C6).
- Current BOM and Altium export paths (H1, I7).
- Headcount, revenue, and any funding after 2022.

[home]: https://www.jitx.com/
[pricing]: https://www.jitx.com/pricing
[docs]: https://docs.jitx.com/en/latest/
[agent]: https://docs.jitx.com/en/latest/app-notes/interactive-design-session.html
[export]: https://docs.jitx.com/en/latest/getting-started/cli/export-reference.html
[essentials]: https://docs.jitx.com/en/latest/essentials/index.html
[autorouter]: https://docs.jitx.com/en/latest/essentials/physical_design/autorouter.html
[parts]: https://docs.jitx.com/en/latest/essentials/design/parts.html
[pins]: https://docs.jitx.com/en/latest/essentials/design/pin_assignment.html
[si]: https://docs.jitx.com/en/latest/essentials/SI/constraints.html
[spice]: https://docs.jitx.com/reference/statements/cstmt/spice.html
[check-quickstart]: https://docs.jitx.com/tutorials/quickstart-check-a-design.html
[checkstmt]: https://docs.jitx.com/reference/statements/checkstmt/index.html
[seriesA]: https://www.jitx.com/blog/series-a-announcement
[ieee]: https://spectrum.ieee.org/startup-jitx-uses-ai-to-automate-complex-circuit-board-design
[ieee-profile]: https://yespress.io/jitx.md
[iconnect]: https://iconnect007.com/article/144168/new-eda-tool-company-embraces-ai-and-code/144165/ein
