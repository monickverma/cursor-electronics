# KiCad — feature inventory
Read 2026-11-13. Vendor: the KiCad project (open source, under the Linux Foundation; lead developers also run KiCad Services Corporation) · Latest release found: KiCad 10.0.8 (2026-10-30); 9.0.9 (2026-04-28) on the old branch; KiCad 11 in development, not released · Earlier teardown: `C:\Users\KIIT\cursor-electronics\reports\competitors\kicad.md` (2026-10-21)

## In one paragraph

KiCad is the free, GPL, cross-platform desktop ECAD suite (schematic, PCB, libraries, 3D, ngspice simulation, Gerber/ODB++/IPC-2581) used by hobbyists, startups, universities, CERN and an increasing share of professional teams. It is also the format Circuit OS emits and the judge it grades boards with (`kicad-cli`). It automates outputs, rule checks and exports — `kicad-cli` runs ERC, DRC and every fabrication export headless — but it has **no autorouter, no auto-placement, no AI and no part pricing in core**. Everything "AI" around KiCad in 2026 is third party: a crowded field of community MCP servers (100–219 tools each), Freerouting and DeepPCB routing plugins, and Huaqiu's Chinese KiCad distribution with a built-in "KiCad Copilot". The IPC API (protobuf over NNG) needs a running GUI in 9 and 10; headless API use and plotting/export through it arrive with KiCad 11.

## Features

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt to design | No (core) / Partial (third party) | Nothing in core or in the 10.0 release notes. Community MCP servers let an external LLM drive KiCad; Huaqiu's KiCad distribution adds a Copilot (see I7/group file) | read (absence in 10.0 notes) / summary (third party) | https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ ; https://mcpservers.org/servers/mixelpixx/kicad-mcp-server |
| A2 | Structured form / spec input | No | — | not found (release notes, docs index) | as A1 |
| A3 | Design as code | No (core) | Files are open S-expressions, which code-first tools (atopile, tscircuit, SKiDL) target; KiCad itself is GUI-first | inference (from open format) | https://docs.kicad.org/10.0/en/cli/cli.html |
| A4 | Imports an existing design | Yes | Altium, Eagle, CADSTAR, EasyEDA (earlier); new in 10.0: **Allegro, PADS, gEDA/Lepton** (schematic and/or board). `kicad-cli pcb import` exists | read | https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ ; https://docs.kicad.org/10.0/en/cli/cli.html |
| A5 | Keeps the requirement as an artifact | No | — | not found | — |
| A6 | Clarifying questions / refusal | No | Not an AI product | inference | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates a schematic from intent | No (core) | Third-party: Huaqiu Copilot claims an experimental "natural language to schematic" agent | summary | https://news.pedaily.cn/20260326/126309.shtml |
| B2 | AI copilot inside a schematic | No (core) / Partial (third party) | MCP servers: `mixelpixx/kicad-mcp-server` (~1K stars, 100–122 tools), THEAVI `KiCAD-MCP-Server` v2.7.0 (219 tools, Claude Code plugin install), `mcp-kicad` (IPC-based, needs KiCad 9+ running) | summary | https://mcpservers.org/servers/mixelpixx/kicad-mcp-server ; https://glama.ai/mcp/servers/ercbb/KiCAD-MCP-Server ; https://claudemarketplaces.com/mcp/daedalus/mcp-kicad |
| B3 | Part selection with reasons | No | — | not found | — |
| B4 | Reusable modules | Yes | Design Blocks (9.0, schematic) extended to the PCB editor in 10.0; multi-channel layout replication (9.0) | read | https://www.kicad.org/blog/2025/02/Version-9.0.0-Released/ ; https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ |
| B5 | ERC (voltage-aware?) | Yes, not voltage-aware | Pin-type matrix and power-pin checks; 10.0 adds a warning when dragging a wire would short other wires | read | https://docs.kicad.org/9.0/en/eeschema/eeschema.html (earlier teardown); 10.0 release notes |
| B6 | Hierarchy / multi-sheet | Yes | Hierarchical sheets; design variants (10.0) | read | 10.0 release notes |
| B7 | Library; symbols from datasheets | Partial | Official libraries: 10.0 added 952 symbols, 1,216 footprints, 386 3D models; >78% of footprints generated from data by integrated generators; STEP is the only shipped 3D format. **Total library size not published.** No datasheet-to-symbol in core (Huaqiu's distribution claims image-to-symbol/footprint) | read / not found (total) | 10.0 release notes; https://news.pedaily.cn/20260326/126309.shtml |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes, built in | ngspice embedded in the schematic editor: OP, DC sweep, AC, transient in the UI; noise, pole-zero, transfer function, sensitivity, FFT through directives/internal types. 10.0 lists only "improvements to plotting". Bundled ngspice version not stated. No `kicad-cli` simulate command; `sch export netlist --format spice` exists | read (CLI, release notes) / summary (analysis list) | https://docs.kicad.org/10.0/en/cli/cli.html ; https://docs.kicad.org/doxygen/sim__types_8h_source.html |
| C2 | Tolerance / Monte Carlo / worst case | Partial | Possible only through raw ngspice control scripts (`.control` with loops); no UI | inference (ngspice capability + no UI feature in notes) | https://ngspice.sourceforge.io/ngspice-eeschema.html |
| C3 | Formal proof | No | — | not found | — |
| C4 | Signal integrity | Partial | IBIS models in the simulator; time-domain track tuning and per-layer tuning profiles (10.0); no field solver or SI simulator in core | read (tuning) / read (IBIS, physics report) | 10.0 release notes; physics report |
| C5 | Power integrity / IR drop | No (core) | Third party: KiCad-Parasitics (DC R via ngspice), padne (DC FEM) | read (physics report) | https://github.com/Steffen-W/KiCad-Parasitics |
| C6 | Thermal | No (core) | Third party: ThermalSim plugin | read (physics report) | physics report |
| C7 | EMC / EMI | No | — | not found | — |
| C8 | Creepage from voltage | Partial | Creepage custom-rule constraint since 9.0, user-typed distance; PCB Calculator has an electrical-spacing table by voltage naming no standard. 10.0 adds a graphical rule editor | read | https://www.kicad.org/blog/2025/02/Version-9.0.0-Released/ ; earlier teardown |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | No (meaningful) | Legacy footprint spreading only; no auto-placement in 10.0 notes | read (absence) | 10.0 release notes |
| D2 | Automatic routing | No (core) | Interactive router only (push-and-shove, walkaround). Third party: Freerouting via Plugin and Content Manager (Specctra DSN round-trip); DeepPCB KiCad 10 plugin (GitHub, May 2026, PCM listing pending; vendor claims 95.6% of 27,721 boards reached ≥95% completion) | summary | https://www.github.com/freerouting/freerouting/blob/master/docs/integrations.md ; https://deeppcb.ai/kicad-autorouter-alternative/ |
| D3 | Constraint management | Yes | Netclasses, custom-rule language, component classes (9.0), graphical rule editor (10.0), time-domain constraints (10.0) | read | 9.0 and 10.0 release notes |
| D4 | Stackup / controlled impedance | Partial | Board stackup manager; PCB Calculator transmission-line tool; no field solver | summary (from earlier teardown) | earlier teardown |
| D5 | DRC | Yes, headless | `kicad-cli pcb drc` with JSON output, `--schematic-parity`, `--refill-zones`, `--exit-code-violations` (exit 5); DRC suggested fixes (10.0) | read (CLI docs; run locally in earlier teardown) | https://docs.kicad.org/10.0/en/cli/cli.html |
| D6 | 3D and MCAD | Yes | 3D viewer; `kicad-cli pcb export` to STEP, STPZ, GLB, STL, PLY, BREP, XAO, VRML, U3D, 3D PDF; `pcb render` raytraced PNG/JPG | read | https://docs.kicad.org/10.0/en/cli/cli.html |
| D7 | Length tuning / diff pairs | Yes | Diff-pair routing; time-domain tuning overhaul with per-layer Tuning Profiles (10.0) | read | 10.0 release notes |
| D8 | HDI / flex / rigid-flex | Partial | Pad stacks and via tenting (9.0); microvias supported; no rigid-flex substacks found | read (pad stacks) / not found (rigid-flex) | 9.0 release notes |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | No | No firmware features in core | inference (nothing in 9.0/10.0 release notes or the CLI command list) | 10.0 release notes; CLI docs |
| E2 | Pin-mux / peripheral configuration | No | Pin/gate swap with back-annotation (10.0) is layout swapping, not MCU peripheral configuration | read (swap) / inference | 10.0 release notes |
| E3 | Compiles / tests firmware | No | — | inference (as E1) | — |
| E4 | Protocol stacks | No | — | inference (as E1) | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | No | — | not found | — |
| F2 | Confidence grading | No | — | not found | — |
| F3 | Automated design review | Partial | ERC + DRC + schematic parity; reports in JSON | read | CLI docs |
| F4 | Datasheet-grounded checks | No | — | not found | — |
| F5 | Audit trail of AI actions | No | — | not applicable | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No (core) | Via third-party MCP only | summary | as B2 |
| G2 | Version history, diff, branch | Partial | KiCad 10 has built-in Git support in the project manager: per-file status icons, active branch shown, Version Control menu (10.0.4 added "Amend Last Commit", "Configure Default Remote"). No visual schematic/PCB diff in core | summary | https://docs.kicad.org/10.0/en/kicad/kicad.html ; https://kicad.org/blog/2026/06/KiCad-10.0.4-Release/ |
| G3 | Comments / review / roles | No | Desktop, single user | inference | — |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes | `kicad-cli sch export bom` with presets, fields, grouping, filters; design variants change BOM (10.0) | read | CLI docs |
| H2 | Live price and stock | No (core) | Third-party plugins (e.g. KiCost) and database/HTTP libraries | summary (from memory, unverified) | — |
| H3 | Alternates | No | — | not found | — |
| H4 | Fabrication outputs | Yes, headless | Gerber, drill, ODB++, IPC-2581, IPC-D-356, GenCAD, position files (ASCII/CSV/Gerber), board stats; jobsets run whole output sets from CLI | read | https://docs.kicad.org/10.0/en/cli/cli.html |
| H5 | DFM / DFA | Partial | DRC against fab rules typed or imported as custom rules; no DFM report | inference (from D5) | — |
| H6 | Order inside the tool | No (core) | Fab plugins in the PCM (JLCPCB, PCBWay, Aisler etc.) | summary (not re-read) | — |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Desktop | Windows, macOS, Linux | read (earlier teardown) | — |
| I2 | API / CLI / headless | Yes (CLI) / Partial (API) | `kicad-cli`: `sch erc/export`, `pcb drc/export/import/render`, `sym`, `fp`, `jobset run`. IPC API: protobuf over NNG; **9 and 10 need a running GUI, have no plotting/export, and plugins work only in the PCB editor**; KiCad 11 adds headless mode via kicad-cli, plotting/export, and Schematic Editor plugins. Official Python client: `kicad-python`. No plan for a standalone file library | read | https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/ ; https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/ |
| I3 | On-prem / certifications | Yes (local software) / not applicable | Runs locally; no certifications | inference | — |
| I4 | Pricing | Free | GPL, no paid tiers. Paid support from KiCad Services Corporation (one tier listed at USD 500/year, third-party summary) | read (free) / summary (KSC price) | https://www.kipro-pcb.com/about/ |
| I5 | Sold to | Everyone; hobbyists through professional teams; CERN pays KSC for support | summary | https://kicad.org/blog/2023/09/CERN-Support-Changes |
| I6 | Company facts | 2025 fund drive raised over USD 100,000 from 2,500+ donors (funded KiCad 10); 2025 end-of-year drive ran Jan 2026 with corporate matching (DigiKey match confirmed in 2025; HQ NextPCB listed); NLnet NGI0 Commons Fund grant "KiCad 10" from Aug 2025 for IPC API, schematic, PCB and library work; 7,609 unique commits in 10.0; KiCad Conference Asia 2026 announced 2026-09-16 | read (fund drive, NLnet, commits) / summary (DigiKey, NextPCB) | https://www.kicad.org/blog/2026/01/2025-End-of-Year-Fund-Drive-The-Year-We-Lost-Count/ ; https://nlnet.nl/project/KiCad-10/ ; https://circuitdigest.com/news/digikey-announces-sponsorship-of-kicad-to-support-open-source-eda-development |
| I7 | Interop with Altium, OrCAD/Allegro | Import yes | Imports Altium, Allegro, PADS (10.0), CADSTAR, Eagle; exports netlists for OrCAD PCB2, Allegro, PADS, CADSTAR; no native Altium export | read | CLI docs (netlist formats); 10.0 notes |
| I8 | Open source | Yes, GPL | Code GPL; KSC's modifications also GPLv3 | read (earlier teardown) / summary | https://www.kipro-pcb.com/about/ |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | No | General tool | not found | — |
| J2 | Power electronics | Partial | ngspice; IPC-2221 width calculator | read (earlier teardown) | — |
| J3 | RF / high-speed | Partial | Diff pairs, time-domain tuning, IBIS; no field solver | read | 10.0 notes |
| J4 | Safety / regulatory | Partial | User-typed creepage rule; no standard derivation | read | earlier teardown |
| J5 | Stated limits | None | No board, layer or part limits (free, unrestricted) | inference (no limits stated anywhere read) | — |

## What changed since the 2026-10-21 teardown

- **Point releases**: 10.0.7 (2026-10-07) and **10.0.8 (2026-10-30)** — bug-fix releases; the teardown ran 10.0.1. No new features of interest.
- **IPC API status pinned down** (dev docs): headless use, plotting/export and schematic-editor plugins are KiCad 11 features, not 10. The teardown said "headless planned for 11"; that is now stated on the official page.
- **Built-in Git** in KiCad 10's project manager (status icons, branch, commit actions; 10.0.4 added amend and default remote) — not in the teardown.
- **AI ecosystem grew**: THEAVI MCP server v2.7.0 at 219 tools with a Claude Code plugin; DeepPCB KiCad 10 routing plugin (May 2026); Huaqiu "KiCad Copilot" in a GPL KiCad distribution (March 2026). None is official.
- **Funding facts** added (fund drive, NLnet grant, KSC).

## What the owner's market page gets wrong about this product

KiCad is not on the owner's market page. The page's "SPICE: only you" claim is wrong partly because of KiCad: it embeds ngspice for free (physics report correction, still true). Leaving the free incumbent off the page hides the most common alternative for Circuit OS's hobbyist/maker segment.

## Where it is ahead of Circuit OS / where Circuit OS is ahead

Circuit OS facts from `MENTAL_MODEL.md` (2026-08-22) and `.claude/CLAUDE.md`.

**KiCad ahead:** free and unrestricted; full manual schematic and PCB editing at any size; mature DRC with JSON output and parity checking; every fabrication and 3D export, headless; huge libraries and community; importers for every major tool. Circuit OS's own layout is experimental (2-layer, ≤ 40 parts) and it has no fabrication exports (physics report).

**Circuit OS ahead:** generation from English or a form; voltage/current properties proved over tolerances (`backend/proof/`) against pin-type-only ERC; ngspice runs scheduled and graded automatically with pass/fail at stated tolerance (`backend/simulation/`); firmware that compiles before it is shown; explanations; BOM with dated static prices and optional live Mouser quotes.

**Interoperability (matters most):** Circuit OS writes `.kicad_sch` with net labels and grades boards with `kicad-cli`. KiCad 11's headless IPC API would let Circuit OS edit and export through the API instead of writing files directly. The `mcp-kicad`-style servers show an LLM driving KiCad *directly*, which is the opposite of Circuit OS's "LLM writes IR, compilers write KiCad" rule; that contrast is a selling point if the MCP route produces broken boards (JLCPCB's Altium/EasyEDA agent tests report dozens of mismatches on first check — see `_group-c.md`).

## Not verified

- Total symbol/footprint counts of the official libraries (only per-release additions are published).
- Bundled ngspice version in KiCad 10, and whether S-parameter analysis is exposed in the UI.
- KiCad 11 release date (no date found).
- Live pricing and fab-ordering plugins were not re-read this pass (H2, H6).
- Stackup manager details (D4) and rigid-flex support (D8) were not re-read.
- GitHub star counts and tool counts of MCP servers come from directories, not the repos.
