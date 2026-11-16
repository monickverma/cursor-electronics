# Cadstrom — feature inventory
Read 2026-11-13. Vendor: Cadstrom (Montréal; "Made in Canada") · Latest release found: no dated release on the site; © 2026 ([home]) · Earlier teardown: none (one paragraph in `reports/Physics layout validation - what the market does and what Circuit OS can build.md`)

## In one paragraph

Cadstrom sells automated validation of schematics, and claims layouts too, for teams designing medical, industrial and consumer hardware ([home]). You upload Altium, OrCAD/Cadence, Xpedition/Siemens, KiCad or Fusion 360 project files. Its "Sigma Engine" reads the schematic and datasheets and checks voltage compatibility between interfacing parts, bus wiring and address conflicts (I2C/SPI/UART), logic polarity and open-drain use, ratings and margins, pin assignments and value discrepancies. It returns a severity-ranked "Design Analysis Report" in which "every finding comes with the evidence behind it" ([home]). Its method is stated as "AI + deterministic validation", with "expert-system rules and simulation that confirm what it finds", and, in the seed announcement, "first-principles understanding of physics" ([home], [seed]). No public technical documentation says which rules exist, what is simulated, or how often findings are wrong. The guarantee therefore stands as **AI plus rules, vendor-described**. It does not generate designs, firmware or BOMs.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | NL prompt to design | No | Validation only; contrasts itself with design and simulation tools | read | [home] |
| A2 | Structured spec input | Not found | "Design intent" is checked, but no spec input format is described | not found | [home] |
| A3 | Design as code | No | Native ECAD files | read | [home] |
| A4 | Imports existing designs | Yes | FAQ: "Altium, Cadence, Siemens, and KiCad project files"; hero also lists OrCAD, Xpedition, Fusion 360 | read | [home] |
| A5 | Requirement as own artifact | Not found | — | not found | [home] |
| A6 | Clarifying questions / refusal | Partial | Validates designs "at whatever stage", without every part fully specified | read | [home], [pricing] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic | No | — | read (scope) | [home] |
| B2 | AI copilot in schematic | No | Report, not in-editor edits | read (scope) | [home] |
| B3 | Part selection | No | — | read (scope) | [home] |
| B4 | Reusable modules | No | — | read (scope) | [home] |
| B5 | ERC, voltage-aware? | Yes (claimed) | "Voltage compatibility between interfacing components", "critical voltage domain mismatch", "maximum rating exceeded", logic polarity, open-drain | read | [home] |
| B6 | Hierarchy | Not found | — | not found | [home] |
| B7 | Library | No | — | read (scope) | [home] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Partial | "simulation that confirm[s] what it finds"; engine and analyses not named | read (claim only) | [home] |
| C2 | Tolerance / margins | Partial | "Component ratings and margins" checked; method not stated | read | [home] |
| C3 | Formal proof | Not found | — | not found | [home] |
| C4 | SI | Partial | "signal integrity" in a mobile graphic of seven areas; no detail | read (claim only) | [home] |
| C5 | PI | Partial | "power" in the same graphic | read (claim only) | [home] |
| C6 | Thermal | Partial | "thermal" in the same graphic | read (claim only) | [home] |
| C7 | EMC | Not found | — | not found | [home] |
| C8 | Creepage | Not found | — | not found | [home] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Placement | No | — | read (scope) | [home] |
| D2 | Routing | No | — | read (scope) | [home] |
| D3 | Constraints | No | — | read (scope) | [home] |
| D4 | Stackup / impedance | Not found | — | not found | [home] |
| D5 | DRC | Not found | Layout validation is claimed in third-party summaries; not on pages read | summary | [drcy-related] |
| D6 | 3D | No | — | read (scope) | [home] |
| D7 | Length tuning | No | — | read (scope) | [home] |
| D8 | HDI / flex | No | — | read (scope) | [home] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | — | read (scope) | [home] |
| E2 | Pin-mux | Partial | Checks "component pin and signal assignments" and clock domains | read | [home] |
| E3 | Compiles firmware | No | — | read (scope) | [home] |
| E4 | Protocol stacks | Partial | Checks bus wiring and address conflicts for I2C, SPI, UART (electrical, not firmware) | read | [home] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Partial | Explains findings with evidence; does not make design choices | read | [home] |
| F2 | Confidence / evidence grading | Partial | Severity labels: critical, high, medium, warning; sample report with 23 anomalies; no confidence score | read | [home] |
| F3 | Automated design review | Yes | "Thousands of electrical details checked automatically", "every iteration"; hybrid AI + rules + simulation | read | [home] |
| F4 | Datasheet-grounded (cited pages) | Partial | AI "reads your schematic and datasheets"; findings carry evidence; page-level citation not stated | read | [home] |
| F5 | Audit trail of AI | Not found | — | not found | [home] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No | — | read (scope) | [home] |
| G2 | Version history | Partial | Validates "every iteration"; no version UI described | read | [home] |
| G3 | Comments / roles | Not found | — | not found | [home] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Not found | — | not found | [home] |
| H2 | Live price | Not found | — | not found | [home] |
| H3 | Alternates | Not found | — | not found | [home] |
| H4 | Fab outputs | No | — | read (scope) | [home] |
| H5 | DFM | Not found | — | not found | [home] |
| H6 | Order | No | — | read (scope) | [home] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | Browser app (app.cadstrom.io), secure cloud | read | [pricing], [home] |
| I2 | API / CLI | Not found | — | not found | [home] |
| I3 | On-prem / certifications | Partial | "SOC 2 compliant, externally audited", end-to-end encryption, "AI never trains on IP", deletion on request; cloud only on pages read | read | [home] |
| I4 | Pricing | Partial | "Get Started for FREE"; no tiers or figures. Read 2026-11-13 | read | [pricing] |
| I5 | Who it is sold to | — | Medical, industrial and consumer device teams and design firms | read | [home] |
| I6 | Company facts | — | $6.8M seed, 2024-12-19, led by Bison Ventures, with Innovation Endeavors and AI2 Incubator ($650K pre-seed earlier). Customers shown: Texas Instruments, StarFish Medical, Lunar Energy, Puzzle Medical Devices, Tomorrow Lab, Igor Institute, SGW Designworks. Co-founders Margot Blouin (CEO), Scott Bright (COO) | read (seed release, site) | [seed], [home] |
| I7 | Interop | Yes | Altium, OrCAD, Xpedition, KiCad, Fusion 360 inputs | read | [home] |
| I8 | Open source | No | — | inference (SaaS) | [home] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Partial | "Proven on … industrial designs"; RS-485 or 4–20 mA not named | read | [home] |
| J2 | Power electronics | Not found | — | not found | [home] |
| J3 | RF / high-speed | Not found | — | not found | [home] |
| J4 | Safety / regulatory | Not found | Medical customers, but no standard (e.g. IEC 60601) named | not found | [home] |
| J5 | Stated limits | Not found | — | not found | [home] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Cadstrom ahead:** it checks any customer design in five ECAD formats, with named enterprise and medical customers and SOC 2. Circuit OS checks only designs from its own generators.
- **Circuit OS ahead:** its rules, proofs and ngspice results are inspectable code with a stated rung per claim (`.claude/CLAUDE.md`, `validation/claims.py`, `proof/`). Cadstrom's rules and simulation are undocumented. Circuit OS also generates the design, firmware and BOM.
- **Overlap to note for the owner's page:** Cadstrom sells exactly the "voltage/current rule checks" and "plain-English validation report" rows. Those cells are not "only you" (already recorded in the physics report's corrections).

## Not verified

- Which checks are deterministic and which are AI, and what the simulation is.
- Layout validation (claimed by third parties, not seen on the site).
- Accuracy or false-positive rates.
- Pricing beyond the free entry point.

[home]: https://www.cadstrom.io/
[pricing]: https://www.cadstrom.io/pricing
[seed]: https://www.businesswire.com/news/home/20241219491407/en/Cadstrom-Raises-$6.8M-in-Seed-Funding-to-Streamline-Validation-for-Electronic-Hardware-Design
[drcy-related]: https://arxiv.org/html/2603.15672
