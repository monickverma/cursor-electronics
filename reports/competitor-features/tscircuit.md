# tscircuit — feature inventory
Read 2026-11-13. Vendor: tscircuit Inc. · Latest release found: not dated on pages read; autorouter benchmark run of 105 scenarios dated 2026-03-14 in a PR ([bench]) · Earlier teardown: none (one row in `C:\Users\KIIT\cursor-electronics\reports\Generative EDA tool feature spec.md`)

## In one paragraph

tscircuit writes circuit boards as React/TypeScript (TSX) components that compile to "Circuit JSON". It is MIT-licensed, with a browser playground, a `tsci` CLI, a package registry and in-tool ordering from JLCPCB ([home], [docs], [order]). It is built to be written by AI agents: a "tscircuit skill" gives Claude Code, Codex or custom agents the context to write circuits, and its docs prescribe a build, inspect and fix loop with `tsci check placement` ([home], [ai]). It has its own autorouter ("sub-second routing on 4-layer boards"), beta automatic placement (flex, grid, pack), and SPICE elements (DC operating point, DC sweep, AC sweep, transient) on a selectable engine (`spicey` by default, ngspice, `pcb_spice` with IBIS) ([home], [layout], [spice], [transient]). It stops short of firmware, datasheet-grounded review and any tolerance analysis. Its checks are geometric (placement, DRC) plus whatever simulation the author sets up.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Partial | Through an external agent with the tscircuit skill; no built-in chat product found | read | [home], [ai] |
| A2 | Structured spec input | Partial | Props on TSX elements (values, footprints, layout props); no requirement object | read | [docs] |
| A3 | Design as code | Yes | TSX / TypeScript → Circuit JSON; open (MIT) | read | [home] |
| A4 | Imports existing designs | Yes | Imports KiCad files natively; `tsci import --jlcpcb` for parts | read | [home], [ai] |
| A5 | Requirement as own artifact | Not found | — | not found | [docs] |
| A6 | Clarifying questions / refusal | Not found | — | not found | [ai] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic from intent | Yes | Schematic, PCB and 3D rendered from code on each save | read | [home] |
| B2 | AI edits in an existing design | Partial | An agent edits the TSX; the docs advise "one focused change at a time" | read | [ai] |
| B3 | Part selection with reasons | Partial | "Automatic part selection … from real-time supplier availability"; no reasons | read | [home] |
| B4 | Reusable modules | Yes | Package registry (registry.tscircuit.com); 50+ reference boards | read | [docs], [home] |
| B5 | ERC, voltage-aware? | Partial | Netlist review and connectivity checks in the AI workflow; voltage-aware ERC not found | read (connectivity); not found (voltage) | [ai] |
| B6 | Hierarchy | Yes | React component composition (inference); subcircuits | inference from [home] | [home] |
| B7 | Library; footprints from datasheets | Partial | JLCPCB and KiCad footprints, Footprinter strings; "Verified Chips Program" (no detail); no datasheet-generated footprints found | read | [docs], [home] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes | `<analog.dcoperatingpointsimulation>`, DC sweep, AC sweep, transient; engines `spicey` (default), `ngspice`, `pcb_spice`; homepage says WebAssembly ngspice, `tsci simulate` | read | [spice], [transient], [home] |
| C2 | Tolerance / Monte Carlo | Partial | `<analog.sweepparameter>` for repeated runs; no Monte Carlo or tolerance analysis found | read | [transient] |
| C3 | Formal proof | Not found | — | not found | [docs] |
| C4 | SI | Partial | `pcb_spice` engine with IBIS pin states and PCB channel sections, "declared for an external runner and aren't executed during rendering" | read | [transient] |
| C5 | PI | Not found | — | not found | [docs] |
| C6 | Thermal | Not found | — | not found | [docs] |
| C7 | EMC | Not found | — | not found | [docs] |
| C8 | Creepage | Not found | — | not found | [docs] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | `pcbFlex`, `pcbGrid`, `pcbPack` (pack "to minimize space while avoiding overlaps"); beta, "Many changes are on the way!" | read | [layout] |
| D2 | Automatic routing | Yes | Own autorouter: "Sub-second routing on 4-layer boards"; open benchmark suite (105 scenarios, March 2026); no completion rate published | read (claim); summary (benchmark) | [home], [bench] |
| D3 | Constraint management | Partial | Layout props; `<drccheck />` element exists (contents not read) | read (titles) | [layout] |
| D4 | Stackup / impedance | Partial | `pcb_spice` takes relative permittivity; no impedance calculator found | read | [transient] |
| D5 | DRC | Partial | `tsci check placement` (overlaps, off-board parts, courtyard, missing connections); `<drccheck />` | read | [ai], [layout] |
| D6 | 3D / MCAD | Yes | 3D view; STEP and GLB export | read | [docs] |
| D7 | Length tuning / diff pairs | Not found | — | not found | [docs] |
| D8 | HDI / flex | Not found | — | not found | [docs] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found (home, docs index) | [home], [docs] |
| E2 | Pin-mux | Not found | — | not found | [docs] |
| E3 | Compiles firmware | Not found | — | not found | [docs] |
| E4 | Protocol stacks | Not found | — | not found | [docs] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Not found | — | not found | [docs] |
| F2 | Confidence / evidence grading | Not found | — | not found | [docs] |
| F3 | Automated design review | Partial | Visual diffs of schematic in GitHub pull requests "with approvals, comments, and rollback"; placement check | read | [home], [ai] |
| F4 | Datasheet-grounded checks | Not found | — | not found | [ai] |
| F5 | Audit trail of AI actions | Partial | Code in git, PR review | read | [home] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Partial | Via external agents | read | [ai] |
| G2 | Version history / diff | Yes | Git, with visual diffs in GitHub | read | [home] |
| G3 | Comments / review / roles | Partial | Through GitHub PRs | read | [home] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | BOM in the fabrication zip | read | [docs] |
| H2 | Live price / stock | Partial | "real-time supplier availability" for part selection; JLCPCB search | read | [home], [ai] |
| H3 | Alternates | Not found | — | not found | [docs] |
| H4 | Fabrication outputs | Yes | Gerbers, BOM, pick-and-place; panelization; KiCad, DSN, STEP, GLB, SPICE export | read | [docs] |
| H5 | DFM | Not found | — | not found | [docs] |
| H6 | Order inside the tool | Yes | Order button, quotes, Stripe checkout; "JLCPCB is the only available vendor" | read | [order] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | Browser playground plus local CLI (`tsci dev`) | read | [docs] |
| I2 | API / CLI | Yes | `tsci` CLI; `@tscircuit/core`, `eval`, `runframe` packages | read | [home] |
| I3 | On-prem / certifications | Partial | Runs locally (open source); "tscircuit Enterprise" link without detail; certifications not found | read | [home] |
| I4 | Pricing | Partial | Open source free; pricing page body did not render; Enterprise and Professional Support unpriced | read (MIT); not found (prices) | [home], [pricing] |
| I5 | Who it is sold to | — | Software-minded hardware developers and AI-agent builders | inference from [home] | [home] |
| I6 | Company facts | — | tscircuit Inc., hiring EE, compiler and autorouting engineers; ~2.1k GitHub stars; funding not found | read (stars, hiring); not found (funding) | [home] |
| I7 | Interop | Partial | KiCad import and PCM export; DSN (Specctra) export; Altium/Cadence not found | read | [home] |
| I8 | Open source | Yes | MIT | read | [home] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [docs] |
| J2 | Power electronics | Not found | — | not found | [docs] |
| J3 | RF / high-speed | Partial | IBIS channel experiments in `pcb_spice` | read | [transient] |
| J4 | Safety / regulatory | Not found | — | not found | [docs] |
| J5 | Stated limits | Partial | Layout algorithms beta; JLCPCB only vendor | read | [layout], [order] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **tscircuit ahead:** any circuit in code, an autorouter claimed for 4 layers, Gerber, pick-and-place and panel output, and in-tool ordering. Circuit OS has no Gerber export and its board engine is experimental, 2-layer (`reports/Physics layout validation - what the market does and what Circuit OS can build.md`, "What Circuit OS actually has today").
- **Circuit OS ahead:** a requirement is materialized before the design and requests outside the catalogue are refused. Simulation is graded against the requirement at 15% tolerance and properties are proved over tolerance boxes, where tscircuit only runs the simulation the author writes. Firmware compiles before it is shown, and every component choice gets a consequential explanation (`.claude/CLAUDE.md`; `.claude/rules/simulation.md`; `MENTAL_MODEL.md` §10).

## Not verified

- The autorouter's completion rate on its own benchmark.
- Whether `spicey` is a full SPICE implementation, and how it compares with ngspice.
- Enterprise pricing, funding and headcount.

[home]: https://tscircuit.com/
[docs]: https://docs.tscircuit.com/
[ai]: https://docs.tscircuit.com/guides/circuit-generation/generating-circuit-boards-with-ai
[spice]: https://docs.tscircuit.com/category/spice-simulation
[transient]: https://docs.tscircuit.com/elements/analog-transientsimulation
[layout]: https://docs.tscircuit.com/guides/tscircuit-essentials/automatic-pcb-layout
[order]: https://docs.tscircuit.com/guides/ordering-prototypes
[pricing]: https://tscircuit.com/pricing
[bench]: https://github-users.yhajoa.workers.dev/tscircuit/tscircuit-autorouter/pull/663
