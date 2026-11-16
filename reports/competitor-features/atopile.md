# atopile — feature inventory
Read 2026-11-13. Vendor: atopile (YC W24; founded 2023) · Latest release found: `atopile` 0.15.9 on PyPI, 2026-09-12 ([pypi]) · Earlier teardown: none (one row in `C:\Users\KIIT\cursor-electronics\reports\Generative EDA tool feature spec.md`)

## In one paragraph

atopile is an open-source (MIT) language and compiler for circuit boards. In declarative `.ato` files the designer, or an AI agent, writes modules, interfaces, physical units, tolerances and **assertions**. The compiler "solves constraints, picks parts, runs checks, and updates your KiCad layout" ([readme]). Its solver treats every toleranced value as a set (a range) and simplifies the constraint system symbolically. It reports contradictory constraints and picks discrete parts whose parameters fit the solved ranges ([skill-ato], [solver-summary]). Its users are engineers who want software practice (git, packages, CI) for boards, and increasingly people who drive it with Claude Code or Cursor. The VS Code / Cursor extension now has its own sidebar agent with tools for builds, part search, BOM reports, layout moves and DRC ([skill-agent]). Layout stays in KiCad. There is no SPICE, no firmware and no datasheet-grounded review. Its guarantee is constraint consistency over declared ranges, which is the closest thing in this group to Circuit OS's tolerance-box proofs, but it does not model circuit behaviour.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | Partial | Built-in sidebar agent in the extension turns requests into `.ato` edits through tools; skills for Cursor, Claude Code, Codex, Copilot. Release status of the sidebar agent not confirmed | read (skill file); summary (skills listing) | [skill-agent], [mcpdir] |
| A2 | Structured spec / requirements input | Yes | Requirements as typed parameters with units and tolerances, plus `assert x within 3.3V +/- 5%` | read | [skill-ato], [readme] |
| A3 | Design as code | Yes | `ato` declarative language; open source, MIT | read | [readme], [github] |
| A4 | Imports an existing design | Not found | No KiCad schematic import found; packages come from the registry | not found (README, docs landing) | [readme], [docs] |
| A5 | Requirement kept as its own artifact | Partial | Assertions live in the source next to the design, so a requirement is checkable text, but it is not a separate artifact from the design | inference from [skill-ato] | [skill-ato] |
| A6 | Clarifying questions / refusal | Partial | The agent has a `design_questions` tool to batch design decisions, but is told to "make reasonable assumptions and note them" rather than trickle questions; the solver refuses contradictory constraints | read | [skill-agent], [skill-ato] |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | Partial | The compiler produces the netlist and KiCad layout from code; whether a drawn schematic is produced is not stated on pages read | read (layout); not found (schematic drawing) | [readme] |
| B2 | AI edits inside an existing design | Yes | Sidebar agent edits project files with `project_edit_file` (LINE:HASH anchors), must read before editing and rebuild after | read | [skill-agent] |
| B3 | Part selection with stated reasons | Partial | "Automatic parametric picking of discrete components"; high-risk parts (MCU, PMIC, RF, connectors) locked by LCSC ID or MPN. No per-part reasons | read | [readme], [skill-ato] |
| B4 | Reusable modules / reference designs | Yes | Package registry (packages.atopile.io); agent tools `packages_search`, `packages_install`; stdlib generics | read | [docs], [skill-agent] |
| B5 | ERC, voltage-aware? | Partial | Assertions over toleranced quantities (e.g. a divider output within a band) are checked at build; not a general pin-type ERC. Voltage-awareness only where the designer writes the equation | read (asserts); inference (scope) | [skill-ato] |
| B6 | Hierarchy | Yes | Modules, interfaces, arrays of sub-modules ("layout reuse with arrays") | read | [skill-ato] |
| B7 | Library; symbols/footprints from datasheets | Partial | Parts from LCSC/JLC via `parts_search` / `parts_install`; size not stated; no datasheet-generated footprints found | read (tools); not found (size) | [skill-agent] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Not found | No simulator in README, docs landing or agent tools | not found | [readme], [skill-agent] |
| C2 | Tolerance / Monte Carlo / worst case | Partial | Tolerances are sets; the solver propagates them through equations and checks assertions against the resulting ranges, a set-based worst-case check of declared equations. No Monte Carlo | read (sets, asserts); summary (solver internals) | [skill-ato], [solver-summary] |
| C3 | Formal proof / exhaustive verification | Partial | Symbolic constraint solving over parameter sets with contradiction reporting. It proves consistency of the declared equations, not circuit behaviour; no netlist-derived model | summary (solver: `src/faebryk/core/solver/`); inference (scope) | [solver-summary] |
| C4 | Signal integrity | Not found | — | not found | [readme] |
| C5 | Power integrity | Not found | — | not found | [readme] |
| C6 | Thermal | Not found | — | not found | [readme] |
| C7 | EMC | Not found | — | not found | [readme] |
| C8 | Creepage from voltage | Not found | — | not found | [readme] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | Partial | Agent sets positions with `layout_set_component_position`; no automatic placer stated | read | [skill-agent] |
| D2 | Automatic routing | Not found | Layout is done in KiCad; the build updates `.kicad_pcb` | read (KiCad); not found (router) | [readme] |
| D3 | Constraint management | Partial | Electrical parameter constraints in code; layout rules are KiCad's | inference from [readme] | [readme] |
| D4 | Stackup / controlled impedance | Partial | Stackup referenced as code (e.g. JLCPCB `JLC04161H_3313`); no impedance calculation found | read | [docs] |
| D5 | DRC | Yes (KiCad's) | Agent tool `layout_run_drc`, required after major placement or routing changes | read | [skill-agent] |
| D6 | 3D / MCAD | Not found | — | not found | [readme] |
| D7 | Length tuning / diff pairs | Not found | — | not found | [readme] |
| D8 | HDI / flex | Not found | — | not found | [readme] |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Not found | — | not found (README, agent tools) | [readme], [skill-agent] |
| E2 | Pin-mux | Not found | — | not found | [readme] |
| E3 | Compiles firmware before showing | Not found | — | not found | [readme] |
| E4 | Protocol stacks | Not found | Interfaces (I2C etc.) exist as electrical types, not firmware | inference from [skill-ato] | [skill-ato] |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains why each choice was made | Not found | — | not found | [readme] |
| F2 | Confidence / evidence grading | Not found | — | not found | [readme] |
| F3 | Automated design review | Partial | Build-time assertion checks, `package verify`, duplicate/unused-import detection; "run design checks locally or in CI". A community (unofficial) Claude Code plugin adds a four-agent parallel design review | read (checks, CI); summary (community plugin) | [readme], [releases], [community-skill] |
| F4 | Checks grounded in datasheets | Partial | Agent is told to `web_search` datasheets for unfamiliar or high-risk parts before committing; no citation in findings | read | [skill-agent] |
| F5 | Audit trail of AI actions | Partial | Agent keeps a checklist per turn and a message log (`message_log_query`); designs are in git | read | [skill-agent] |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Sidebar agent; external agents via skills | read | [skill-agent] |
| G2 | Version history / diff / branch | Yes | Git, by design ("version control, and collaboration") | read | [github] |
| G3 | Comments / review / roles | Partial | Through the git host (pull requests); nothing built in found | inference from [github] | [github] |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | `report_bom` | read | [skill-agent] |
| H2 | Live price / stock | Partial | Parts searched from LCSC/JLC catalogue; live stock use in picking not confirmed | read (search); not found (stock gating) | [skill-agent] |
| H3 | Alternates / substitution | Partial | Generic passives re-picked from constraints at build; no substitution check described | inference from [skill-ato] | [skill-ato] |
| H4 | Fabrication outputs | Partial | Agent tools `manufacturing_generate`, `manufacturing_summary`; file formats not listed on pages read | read (tools) | [skill-agent] |
| H5 | DFM | Not found | — | not found | [readme] |
| H6 | Order inside the tool | Not found | — | not found | [readme] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | VS Code / Cursor extension that manages `ato`; browser workspace app.atopile.io ("nothing to install"); CLI | read | [readme], [docs] |
| I2 | API / CLI / headless | Yes | `ato` CLI; checks in CI | read | [readme] |
| I3 | On-prem / certifications | Not found | atopile.com redirects to atopile.io/enterprise; page body did not render | not found (enterprise page empty to fetch) | [enterprise] |
| I4 | Pricing | Partial | Open-source toolchain free (MIT); enterprise offering exists, no prices found | read (MIT); not found (prices) | [github], [enterprise] |
| I5 | Who it is sold to | — | Engineers wanting software workflows for hardware; LinkedIn describes "The AI-native platform for electronic design" | summary | [linkedin] |
| I6 | Company facts | — | YC W24, founded 2023; ~$0.5M convertible note (Apr 2024) per CB Insights; 4.1k GitHub stars; headcount not found | summary (funding); read (stars) | [cbi], [github] |
| I7 | KiCad / Altium / Cadence | Partial | KiCad native (layout file updated even without KiCad installed); no Altium/Cadence | read | [readme] |
| I8 | Open source | Yes | MIT | read | [github] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Not found | — | not found | [readme] |
| J2 | Power electronics | Not found | — | not found | [readme] |
| J3 | RF / high-speed | Not found | — | not found | [readme] |
| J4 | Safety / regulatory | Not found | — | not found | [readme] |
| J5 | Stated limits | Partial | Docs call the platform "pre-release"; v0.14.0 (31 Jan) was a "complete core rewrite"; Python ≥ 3.14 < 3.15 | read | [docs], [releases], [pypi] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **atopile ahead:** arbitrary designs in an open language, a package registry, KiCad layout sync, git and CI as the native workflow, and a large open community (4.1k stars). Circuit OS covers a fixed catalogue of generators (`.claude/CLAUDE.md`, Phase 1 scope plus composition).
- **Close to parity:** both check requirements over tolerance ranges rather than nominal values. atopile checks equations the designer writes. Circuit OS proves properties derived from the design's own netlist with sympy nodal analysis and z3, with exact rational enclosures (`.claude/CLAUDE.md`, `proof/mna.py`, `proof/prover.py`). atopile's check covers the designer's arithmetic. Circuit OS's covers the circuit.
- **Circuit OS ahead:** SPICE through ngspice, firmware that compiles before it is shown, graded claims and consequential explanation, refusal outside the catalogue, and page-cited datasheet figures (`.claude/CLAUDE.md`; `MENTAL_MODEL.md` §4, §10).

## Not verified

- The sidebar agent's release status (stable or preview), and which model it uses.
- Whether part picking gates on live LCSC/JLC stock.
- Fabrication output formats behind `manufacturing_generate`.
- The enterprise offer (atopile.io/enterprise did not render) and any funding after 2024.
- The solver's exact algorithm. Internals are known only from a third-party skill summary of `src/faebryk/core/solver/`.

[pypi]: https://pypi.org/project/atopile/
[readme]: https://cdn.jsdelivr.net/gh/atopile/atopile@main/README.md
[github]: https://github.com/atopile/atopile
[releases]: https://github.com/atopile/atopile/releases
[docs]: https://docs.atopile.io/
[skill-ato]: https://raw.githubusercontent.com/atopile/atopile/main/.claude/skills/ato/SKILL.md
[skill-agent]: https://raw.githubusercontent.com/atopile/atopile/main/.claude/skills/agent/SKILL.md
[solver-summary]: https://smithery.ai/skills/atopile/solver
[community-skill]: https://claudemarket.ai/plugins/mawildoer-atopile-agent-skill/atopile-dev
[mcpdir]: https://mcp.directory/skills/ato-language
[enterprise]: https://atopile.io/enterprise
[linkedin]: https://linkedin.com/company/atopile
[cbi]: https://www.cbinsights.com/company/atopile/financials
