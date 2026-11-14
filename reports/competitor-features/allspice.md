# AllSpice (with DRCY) — feature inventory
Read 2026-11-13. Vendor: AllSpice.io · Latest release found: DRCY "Under the hood" post updated 2026-10-29 ([drcy-hood]); DRCY paper arXiv:2603.15672, 2026-03-13 ([paper]) · Earlier teardown: none

## In one paragraph

AllSpice is "git for hardware". It gives revision control, visual diffs, design reviews and release automation over native ECAD files (Altium, KiCad, OrCAD, Allegro System Capture, DeHDL, DxDesigner), sold to enterprise hardware teams with SOC 2 Type 2 and a self-hosted tier ([home], [drcy-hood]). Its AI agent **DRCY** runs a first-pass schematic review. It reads the native schematic, fetches each part's datasheet, checks connections pin by pin and against operating limits, and posts findings as review comments, each citing the datasheet page it came from ([drcy-hood], [paper]). It does not generate or change designs, simulate, or review layout. Its guarantee is an **LLM opinion with a citation**: a multi-agent, multi-run consensus by Anthropic models by default, with no published precision or recall, and "Some findings will be wrong" ([drcy-hood], [paper-html]). Deterministic checks are separate, in AllSpice Actions (CI built on GitHub Actions) that users write.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No | Review and collaboration platform; DRCY Chat answers questions but does not design | read (inference from product scope) | [ai-agent] |
| A2 | Structured spec input | Partial | Teams load their own review checklists and an optional `DRCY.md` repository file as review context | read | [drcy-hood], [learn] |
| A3 | Design as code | No | Works on native ECAD files | read | [drcy-hood] |
| A4 | Imports existing designs | Yes | Native schematics from Altium, KiCad, OrCAD, Allegro System Capture, DeHDL, DxDesigner; no export step | read | [drcy-hood], [ai-agent] |
| A5 | Requirement as own artifact | Not found | — | not found | [home] |
| A6 | Clarifying questions / refusal | Not found | Interactive real-time discussion during review is "planned but not yet available" | read | [drcy-hood] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic | No | Reviews only | read | [drcy-hood] |
| B2 | AI copilot inside an existing schematic | Partial | DRCY Chat explains circuits, traces nets, locates components, generates reports and tables; it does not edit the schematic | read | [learn], [ai-agent] |
| B3 | Part selection with reasons | No | Not a design tool; "BOM intelligence" and COGS reports from DigiKey / SiliconExpert data | read | [ai-agent], [home] |
| B4 | Reusable modules | Not found | — | not found | [home] |
| B5 | ERC, voltage-aware? | Partial | DRCY flags voltage mismatches, pin swaps, polarity, pull-up values, interface configuration (I2C, USB, clocks) by LLM reasoning against datasheets: a voltage-aware *opinion*, not a rule engine | read | [ai-agent], [drcy-hood] |
| B6 | Hierarchy | Yes (read) | DRCY sees nets, components, properties, hierarchy, connectivity | read | [drcy-hood] |
| B7 | Library | No | Not a library tool | inference from scope | [home] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | — | not found (home, ai-agent, hood post) | [home] |
| C2 | Tolerance / worst case | Partial | "Derating analysis" named as a DRCY capability; method not described | read (claim only) | [ai-agent] |
| C3 | Formal proof | No | Paper and posts describe LLM agents with consensus; no proof claimed | read | [paper] |
| C4 | SI | No | DRCY "cannot check … trace widths, clearances, impedance" | read | [drcy-hood] |
| C5 | PI | Not found | — | not found | [drcy-hood] |
| C6 | Thermal | Partial | Example finding: regulator thermal pad needs via stitching the footprint lacks (LLM finding) | summary | [search-drcy] |
| C7 | EMC | Partial | "Missing ESD protection" listed as an example catch | read | [ai-agent] |
| C8 | Creepage | Not found | — | not found | [ai-agent] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | No | Not a layout tool; layout files are versioned and diffed (e.g. `.kicad_pcb`) | read | [home] |
| D2 | Automatic routing | No | Not a layout tool | read (inference from scope) | [home] |
| D3 | Constraint management | No | Not a layout tool | read (inference from scope) | [home] |
| D4 | Stackup / controlled impedance | No | DRCY "cannot check … impedance" | read | [drcy-hood] |
| D6 | 3D view / MCAD exchange | Not found | — | not found | [home] |
| D7 | Length tuning / diff pairs | No | Not a layout tool | read (inference from scope) | [home] |
| D8 | HDI / flex | No | Not a layout tool | read (inference from scope) | [home] |
| D5 | DRC | Partial | DRCY does not do layout review ("reviews schematics only"); the AI-agent page lists DFM/DFA checks "that reference IPC or ISO standards" and cross-referencing of layouts and BOMs, which conflicts with the hood post | read (both pages; they disagree) | [drcy-hood], [ai-agent] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | Out of scope; "misconfigured registers" listed as a review catch | read | [ai-agent] |
| E2 | Pin-mux | Partial | Reviews pin usage and interface configuration against datasheets | read | [ai-agent] |
| E3 | Compiles firmware | No | — | inference from scope | [home] |
| E4 | Protocol stacks | No | — | inference from scope | [home] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Partial | Explains what a part or net does when asked (e.g. why a diode protects a rail during hot-plug); does not justify design choices it made, because it makes none | read | [home] |
| F2 | Confidence / evidence grading | Partial | Findings link to "the datasheet section, pin requirement, or constraint that triggered them"; severity not described; no confidence score; multi-run consensus in the pipeline | read | [ai-agent], [paper] |
| F3 | Automated design review | Yes | Five-agent pipeline: netlist augmentation, component grouping, parallel datasheet retrieval with self-evaluation, per-group review agents run *k* times, consensus, error grouping. Checklist built from each part's datasheet plus team checklists and "patterns from past reviews". 10-page schematic with 50–100 unique parts in under 20 minutes. No accuracy, precision or false-positive figures published | read | [paper], [paper-html], [drcy-hood] |
| F4 | Checks grounded in datasheets (cited pages) | Yes | "Every finding cites the datasheet page it came from" (e.g. 310 nF placed vs 10 µF required, datasheet page 3). Datasheet source order: repo uploads, attribute links, internal part API, manufacturer / DigiKey | read (citations); summary (source order) | [drcy-hood], [search-pinscope] |
| F5 | Audit trail of AI actions | Yes | Findings are review comments alongside humans'; engineers escalate, resolve or mark wrong with a reason that carries into later reviews; "complete auditability" | read | [drcy-hood], [home] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No | Chat answers; no edits | read | [learn] |
| G2 | Version history, diff, branch, restore | Yes | Git-based revision control with visual diffs and history for native ECAD files | read | [home] |
| G3 | Comments / review workflow / roles | Yes | Comments on source files, approvals, milestones, per-unit permissions, Jira integration | read | [home] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Partial | BOM cross-referencing and COGS reports; release packages | read | [home], [ai-agent] |
| H2 | Live price / stock | Partial | COGS reports pulling from DigiKey, SiliconExpert "or other data sources" | read | [home] |
| H3 | Alternates | Not found | — | not found | [home] |
| H4 | Fabrication outputs | Partial | Automated release packages via Actions; formats depend on the ECAD tool | read (release packages); inference (formats) | [home] |
| H5 | DFM / DFA | Partial | Claimed on AI-agent page ("reference IPC or ISO standards"); hood post says DFM is out of scope | read (conflicting) | [ai-agent], [drcy-hood] |
| H6 | Order from fab | Not found | — | not found | [home] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | Browser hub (managed cloud) plus a local sync client | read | [home], [drcy-hood] |
| I2 | API / CLI / headless | Yes | Actions built on GitHub Actions (`py-allspice`); DRCY runs as a CI/CD action on design review | read (Actions); summary (GitHub-Actions base) | [home], [paper], [actions] |
| I3 | On-prem / certifications | Yes | SOC 2 Type 2, SOC 3; Enterprise Self-Hosted tier; GovCloud option for ITAR-controlled designs; data on AWS US by default; customer data not used to train models | read (SOC, self-host); summary (GovCloud) | [home], [ai-agent], [onprem] |
| I4 | Pricing | Partial | All plans Enterprise, demo required: Core (revision control + DRCY), Partner (+ automations, FDE), Strategic, Self-Hosted; priced by team size, automation access, "AI review credits". No figures. Read 2026-11-13 | read | [home] |
| I5 | Who it is sold to | — | Enterprise hardware teams (EE, PCB, firmware) | read | [home] |
| I6 | Company facts | — | $15M Series A, 2025-06-24, led by Rethink Impact; ~$25M total. Customers reported: Blue Origin, Bose; logos Molex, Tools for Humanity | summary | [funding] |
| I7 | Interop | Yes | Altium, KiCad, OrCAD, Allegro System Capture, DeHDL, DxDesigner; PLM with an API | read | [drcy-hood], [home] |
| I8 | Open source | No | Proprietary hub; `py-allspice` client library exists | read (client); inference (hub) | [home] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [ai-agent] |
| J2 | Power electronics | Partial | Regulator feedback-divider error example (flagged a divider not producing the labelled 1.8 V, suggested an E96 value) | read | [lessons] |
| J3 | RF / high-speed | Not found | — | not found | [ai-agent] |
| J4 | Safety / regulatory | Partial | DFM/DFA findings "reference IPC or ISO standards" | read | [ai-agent] |
| J5 | Stated limits | Yes | Schematics only; no layout review; no real-time discussion yet; "doesn't replace engineering judgement" | read | [drcy-hood], [learn] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **AllSpice ahead:** it reviews *any* customer schematic in six native formats, with datasheet retrieval at scale and enterprise collaboration (git, diffs, roles, SOC 2, self-hosting, GovCloud). Circuit OS reviews only designs its own generators produce, and has a backend patch audit trail but no diff or rollback UI (`reports/Physics layout validation - what the market does and what Circuit OS can build.md`, "What Circuit OS actually has today").
- **Circuit OS ahead:** a different kind of guarantee. Its checks are computed: exact graph rules, ngspice, and z3 proofs over tolerance boxes. Each claim is graded, and an unchecked rule is printed "not assessed" rather than passed (`.claude/rules/simulation.md` X8; `.claude/CLAUDE.md` `validation/claims.py`, `proof/`). DRCY's are LLM opinions with citations and no published error rate. Circuit OS also generates the design and the firmware.
- **Both cite datasheets:** Circuit OS records a page-cited provenance for every figure a claim reads, and treats it as trusted only once a person has verified it (`.claude/CLAUDE.md`, `data/figures.py`, `figure_evidence.json`, `figure_verifications.json`). DRCY cites a page per finding. Circuit OS's citation is on the input figure. DRCY's is on the output opinion.

## Not verified

- The full DRCY checks table on the hood post is an image and could not be read.
- Whether DFM/DFA is in DRCY's scope today: the AI-agent page and the hood post disagree.
- The number of consensus runs (*k*) and the models in production ("Anthropic models of different strengths" by default).
- Prices and AI-credit sizes.
- Whether Actions run on the GovCloud and self-hosted deployments.

[home]: https://allspice.io/
[ai-agent]: https://allspice.io/ai-agent
[drcy-hood]: https://www.allspice.io/post/under-the-hood-how-drcy-reviews-your-schematics
[learn]: https://learn.allspice.io/docs/drcy-ai-design-review
[lessons]: https://allspice.io/post/using-ai-in-schematic-design-reviews-what-we-learned-and-what-surprised-us
[paper]: https://arxiv.org/abs/2603.15672
[paper-html]: https://arxiv.org/html/2603.15672
[search-drcy]: https://pcdandf.com/pcdesign/index.php/editorial/menu-new-indust-prod/19087-allspice-io-releases-drcy-ai-design-review-agent
[search-pinscope]: https://allspice.io/post/how-to-run-an-ai-design-review-for-hardware-with-drcy
[actions]: https://learn.allspice.io/docs/how-does-allspice-actions-work
[onprem]: https://learn.allspice.io/docs/can-i-host-allspice-on-premise
[funding]: https://www.engineering.com/allspice.io-raises-15m-to-launch-ai-for-hardware-teams/
