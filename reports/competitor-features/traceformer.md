# Traceformer — feature inventory
Read 2026-11-13 (site) and 2026-11-14 (changelog). Vendor: Traceformer, Inc. (formerly Netlist.io, per a third-party summary) · Latest release found: changelog entry 2026-08-26, adding GPT-5.6 Sol, Claude Opus 5, Claude Fable 5 and Gemini 3.7 Flash as review models ([changelog]) · Earlier teardown: none

## Added because

Traceformer is the cheapest, most self-serve product found that does what AllSpice's DRCY does. It runs an LLM schematic review grounded in datasheets, and its rule that every finding "must cite specific datasheet pages" is strict and published. A finding with no supporting page is filed under "Missing Info" rather than reported ([home]). It is the closest public analogue to Circuit OS's page-cited figure evidence, and it shows the price point of an AI review: $20 a month.

## In one paragraph

Traceformer is a web app. You upload a KiCad project (via an open-source plugin or conversion, KiCad 10 supported since 2026-03-28) or an Altium netlist export, pick subsystems and a review model, fetch datasheets automatically, and step through findings with evidence ([home], [changelog]). It states that it does **not** do ERC, DRC or functional simulation, and that those are still required ([home]). Its guarantee is an **LLM opinion that must cite a datasheet page or abstain**. No accuracy rate is published.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | NL prompt to design | No | Review only | read | [home] |
| A2 | Structured spec input | Partial | Scope a review to selected subsystems | read | [home] |
| A3 | Design as code | No | — | read (scope) | [home] |
| A4 | Imports existing designs | Yes | KiCad project (plugin / KiCad 10 uploads), Altium export script / netlist | read | [home], [changelog] |
| A5 | Requirement as own artifact | Not found | — | not found | [home] |
| A6 | Clarifying questions / refusal | Partial | Warns before a review when selected subsystems lack critical IC datasheets (2026-03-12); unsupported checks go to "Missing Info" | read | [changelog], [home] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic | No | — | read (scope) | [home] |
| B2 | AI copilot in schematic | No | Findings viewer and net viewer, no edits | read | [changelog] |
| B3 | Part selection | No | — | read (scope) | [home] |
| B4 | Reusable modules | No | — | read (scope) | [home] |
| B5 | ERC, voltage-aware? | No (ERC) | "Does not perform electrical rule checking (ERC/DRC)"; datasheet and application-level issues by LLM | read | [home] |
| B6 | Hierarchy | Partial | Multi-subsystem designs; net viewer | read | [changelog] |
| B7 | Library | No | — | read (scope) | [home] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | No | No functional simulation, stated | read | [home] |
| C2 | Tolerance / worst case | Not found | — | not found | [home] |
| C3 | Formal proof | No | LLM review | read (scope) | [home] |
| C4 | SI | Not found | — | not found | [home] |
| C5 | PI | Not found | — | not found | [home] |
| C6 | Thermal | Not found | — | not found | [home] |
| C7 | EMC | Not found | — | not found | [home] |
| C8 | Creepage | Not found | — | not found | [home] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Placement | No | — | read (scope) | [home] |
| D2 | Routing | No | — | read (scope) | [home] |
| D3 | Constraints | No | — | read (scope) | [home] |
| D4 | Stackup | No | — | read (scope) | [home] |
| D5 | DRC | No | Stated: no DRC | read | [home] |
| D6 | 3D | No | — | read (scope) | [home] |
| D7 | Length tuning | No | — | read (scope) | [home] |
| D8 | HDI / flex | No | — | read (scope) | [home] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | — | read (scope) | [home] |
| E2 | Pin-mux | Not found | — | not found | [home] |
| E3 | Compiles firmware | No | — | read (scope) | [home] |
| E4 | Protocol stacks | No | — | read (scope) | [home] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Partial | Explains findings with quotes and evidence; makes no choices | read | [home], [changelog] |
| F2 | Evidence grading | Partial | Verified issue vs "Missing Info"; no confidence score | read | [home] |
| F3 | Automated design review | Yes | LLM review per subsystem; per-review cost preview; user-selectable model (GPT, Claude, Gemini families) | read | [home], [changelog] |
| F4 | Datasheet-grounded (cited pages) | Yes | "Every finding must cite specific datasheet pages as evidence"; "stronger quote, page, and evidence linking" (2026-04-21) | read | [home], [changelog] |
| F5 | Audit trail | Partial | Enterprise: audit logs; issue-report flow for wrong findings (2026-03-28) | read | [home], [changelog] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No | — | read (scope) | [home] |
| G2 | Version history | Partial | Datasheet links kept "across design revisions" (2026-05-17) | read | [changelog] |
| G3 | Comments / roles | Partial | Team workspace; Enterprise custom RBAC, SAML SSO | read | [home] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Not found | — | not found | [home] |
| H2 | Live price | No | — | read (scope) | [home] |
| H3 | Alternates | No | — | read (scope) | [home] |
| H4 | Fab outputs | No | — | read (scope) | [home] |
| H5 | DFM | No | — | read (scope) | [home] |
| H6 | Order | No | — | read (scope) | [home] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | Web app; KiCad plugin / Altium script for export | read | [home] |
| I2 | API / CLI | Not found | GitHub organization linked; no API documented | not found | [home] |
| I3 | On-prem / certifications | Not found | Designs not used for training; certifications not stated | read (training); not found (certs) | [home] |
| I4 | Pricing | Yes | Free $0 (1 review/month, ≤200 parts, ≤10 datasheets); Starter $20/mo ($20 credits, ≤20 datasheets); Team $50/seat/mo (≤1,000 parts, ≤100 datasheets); Enterprise custom; annual −15%. Read 2026-11-13 | read | [home] |
| I5 | Who it is sold to | — | Individual engineers to teams on KiCad/Altium | read | [home] |
| I6 | Company facts | — | Traceformer, Inc.; funding, headcount not found | read (entity); not found (rest) | [home] |
| I7 | Interop | Partial | KiCad, Altium inputs | read | [home] |
| I8 | Open source | Partial | Plugin open source per third-party summary; service proprietary | summary | [hn] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [home] |
| J2 | Power electronics | Not found | — | not found | [home] |
| J3 | RF / high-speed | Not found | — | not found | [home] |
| J4 | Safety / regulatory | Not found | — | not found | [home] |
| J5 | Stated limits | Yes | Component and datasheet caps per plan (200 / 1,000 parts; 10 / 20 / 100 datasheets) | read | [home] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Traceformer ahead:** it reviews any KiCad or Altium design, is self-serve with published prices, and lets the user pick the model.
- **Circuit OS ahead:** its checks are computed, not opined (rules, ngspice, z3 proofs), and it generates the design and firmware (`.claude/CLAUDE.md`). Traceformer itself says ERC, DRC and simulation are still needed.
- **Shared discipline:** "cite or abstain" matches Circuit OS's rule that a figure is trusted only once verified and that an unchecked rule is printed "not assessed" (`.claude/CLAUDE.md` `data/figures.py`; `.claude/rules/simulation.md` X8).

## Not verified

- Accuracy and false-positive rates (none published). The 2026-07-20 entry mentions "reduced false positives on large multi-subsystem designs".
- Funding and team.

[home]: https://traceformer.io/
[changelog]: https://traceformer.io/changelog
[hn]: https://hn.svelte.dev/item/46492601
