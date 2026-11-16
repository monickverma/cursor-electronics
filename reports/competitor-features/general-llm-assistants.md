# General LLM assistants as the substitute — feature inventory
Read 2026-11-13 and 2026-11-14. Vendor: OpenAI (ChatGPT, Codex), Anthropic (Claude, Claude Code), Google (Gemini), plus open-source KiCad MCP servers and agent skills · Latest release found: per tool, below · Earlier teardown: none (vision.md row "ChatGPT/Claude: hallucinates circuit values, no simulation, no files, no validation")

## In one paragraph

The real substitute for Circuit OS is a frontier chat model or coding agent (Claude Code, Codex, Cursor, Gemini CLI) with tools attached. It works with KiCad through an MCP server, or writes a design-as-code language (atopile, tscircuit, JITX, SKiDL, Diode's Zener), or runs open review skills such as kicad-happy, or drives a firmware simulator through Wokwi's MCP server ([kicad-mcp], [kicad-happy], [wokwi-mcp]). With those tools the assistant can produce real files and run real ERC, DRC and ngspice. The vision.md line "no simulation, no files, no validation" is therefore **out of date as written**. What the assistant still lacks is any guarantee of its own. Every check is one the agent chose to run, or not. Datasheet facts come from the model's reading, with no recorded provenance. Published 2026 benchmarks show free-form generation rarely passes all checks: 8.15% best pass rate on 300 board-level tasks ([hwe]). Pass rates jump when a model is boxed into a schema and judged by a deterministic verifier: 81.3% on 227 tasks ([pcbschemagen]).

## Benchmarks and evaluations (2025–2026), with numbers

| Study | Task | Result | How judged | Label | Source |
|---|---|---|---|---|---|
| HWE-Bench (Qiu, Xiao, Pan; arXiv 2603.18102, 2026-03-18) | Board-level schematic from functional requirements + datasheets; 300 tasks, 8 domains, 2,914 IC datasheets | Best model **8.15%** overall pass; models "lack physical intuition" | Static electrical rules, then a circuit simulator | read (abstract) | [hwe] |
| PCBSchemaGen (Zou et al.; arXiv 2602.00510, v2 2026-06-17) | Schematic code synthesis, 227 real-IC tasks, 22 domains | **81.3%** average pass with a frozen Gemma-4-31B; a prompting-only baseline on the same model "collapses on hard system-level designs" | Datasheet-derived schema + deterministic 5-layer verifier + Thompson-sampling refinement | read (abstract) | [pcbschemagen] |
| NetlistBench (Ma et al.; arXiv 2608.12197, 2026-08-12, MLCAD 2026) | Recognising and editing SPICE netlists; 2,342 cases, 24 task families, 6 non-thinking LLMs | Local edits **96–100%**; device addition **41–83%**; equivalence judgement **49–90%**; accuracy falls sharply as edit sequences lengthen | Structural checks | read (abstract) | [netlistbench] |
| Long-Horizon Analog Design Bench (arXiv 2609.33356, 2026-09-27) | 50 transistor-level analog/mixed-signal tasks, 15 agent configs, 2,250 two-hour attempts | Full-spec pass **8.0%–78.0%**; most failures pass legality but fail electrical acceptance ("electrical closure" is the dominant failure) | ngspice / SKY130 acceptance tests | read (abstract) | [longhorizon] |
| Diode × Anthropic (Claude blog, 2025-12-12) | Chip reference designs in the Zener language | Sonnet 4.5 preferred **8/10**; 60/40 vs Opus 4; 82/18 vs Sonnet 4; test-set size not stated. Failure modes: missing datasheet nuances, misreading schematic images, misusing Zener | Requirement-level testbench + blind engineer preference | read | [claude-blog] |
| Qiao & Dick (arXiv 2608.25217, v2 2026-10-27) | Pre-schematic interface-compatibility checking from datasheets | **97.5%** accuracy on 7 designs / 34 datasheets; 8.6× smaller context than upload-and-query | LLM extracts properties; *generated deterministic scripts* do the arithmetic | read (abstract) | [qiao] |
| PCB-QA (arXiv 2606.23704) | Question answering over schematics/netlists | One model **93%** with a JSON netlist format | QA accuracy | summary | [pcbqa] |
| E-Sharp "Can AI Really Review a Schematic?" (Electronic Design, 2026-11-10; vendor author) | Review of a commercial board | 16 rule hits → 6 relevant → **4 genuine defects** (2 blocking); one rule fired 4× with 3 false positives. A large board (5,418 parts, 7,094 nets) needed 3.5M–11M tokens against a 1M context | Engineer adjudication | read | [esharp] |
| OmniLayout, PCBWorld (arXiv 2607.03261, 2607.05915) | Placement; routing via KiCad with DRC feedback | LLMs place parts poorly; agents acting through KiCad's engine with DRC feedback route better than open-loop LLMs | — | summary (from `Generative EDA tool feature spec.md`) | [spec] |

**What the numbers say:** a deterministic checker plus a constrained output format is the variable that matters, not the model. That is Circuit OS's architecture (LLM → JSON IR → deterministic compilers). The 2026 benchmarks now support it with numbers.

## Features (frontier assistant + common open tools, as of 2026-11)

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | NL prompt to design | Yes | Any chat or agent; quality per benchmarks above | read | [hwe] |
| A2 | Structured spec input | Partial | Only if the user supplies one (e.g. a schema as in PCBSchemaGen) | read | [pcbschemagen] |
| A3 | Design as code | Yes (via tools) | atopile, tscircuit, JITX, SKiDL and Zener all ship agent skills | read | see `atopile.md`, `tscircuit.md`, `jitx.md`; [zener] |
| A4 | Imports existing designs | Yes (via tools) | KiCad MCP servers read and write KiCad 9+ projects | summary | [kicad-mcp] |
| A5 | Requirement as own artifact | No | Requirement lives in chat; nothing enforces it later | inference from the absence of any such mechanism in the tools above | [kicad-mcp] |
| A6 | Clarifying questions / refusal | Partial | Models ask questions at their own discretion; no catalogue to refuse against | inference | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1 | Generates schematic | Yes (via tools) | Through KiCad MCP or a code language; best 8.15% fully correct unassisted on HWE-Bench | read / summary | [hwe], [kicad-mcp] |
| B2 | AI edits in existing schematic | Yes (via MCP) | mixelpixx server: 100–122 tools by version; its own notes say the schematic workflow "was completely broken in previous versions"; live UI sync experimental | summary | [kicad-mcp] |
| B3 | Part selection with reasons | Partial | Model gives reasons in prose; unverified; hallucinated pinouts are a reported failure mode | summary | [stationx] |
| B4 | Reusable modules | Partial | Through the code-language registries | read | see `atopile.md` |
| B5 | ERC, voltage-aware? | Partial | KiCad ERC via MCP (pin-type only); kicad-happy adds derating, regulator Vout from dividers (~65 Vref families), I2C rise time | summary (MCP); read (kicad-happy) | [mcp-python], [kicad-happy] |
| B6 | Hierarchy | Yes (via KiCad) | — | inference | — |
| B7 | Library; parts from datasheets | Partial | kicad-happy extracts structured specs from datasheet PDFs (96% download success across 240+ makers claimed), quality-scored | read | [kicad-happy] |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | Yes (via tools) | kicad-happy generates testbenches and runs ngspice / LTspice / Xyce, comparing results with calculated values; ~49 built-in op-amp models | read | [kicad-happy] |
| C2 | Tolerance / Monte Carlo | Partial | kicad-happy: Monte Carlo and what-if sweeps | read | [kicad-happy] |
| C3 | Formal proof | No | None found in any assistant or tool | not found (all sources here) | — |
| C4 | SI | Not found | — | not found | — |
| C5 | PI | Not found | — | not found | — |
| C6 | Thermal | Partial | kicad-happy junction-temperature estimates | read | [kicad-happy] |
| C7 | EMC | Partial | kicad-happy: 44 EMC rule checks against FCC/CISPR/automotive/military | read | [kicad-happy] |
| C8 | Creepage | Partial | KiCad 9 creepage DRC, reachable through MCP | summary | [spec] |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Placement | Partial | Via MCP; benchmarks find LLM placement poor | summary | [spec], [mcp-python] |
| D2 | Routing | Partial | Via MCP / KiCad tools; DRC-in-the-loop agents route better | summary | [spec] |
| D3 | Constraints | Partial | KiCad rules via MCP | inference | — |
| D4 | Stackup | Partial | KiCad stackup via MCP | inference | — |
| D5 | DRC | Yes (via MCP) | ERC and DRC through `mcp-server-kicad` | summary | [mcp-python] |
| D6 | 3D | Yes (via MCP) | 3D model export | summary | [mcp-python] |
| D7 | Length tuning | Not found | — | not found | — |
| D8 | HDI / flex | Not found | — | not found | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1 | Generates firmware | Yes | Coding agents write firmware freely | inference (general capability) | — |
| E2 | Pin-mux | Partial | Only as good as the model's reading of the schematic; no tie to the netlist unless a tool supplies it | inference | — |
| E3 | Compiles / tests before showing | Partial | A coding agent can run the compiler; Wokwi CLI's experimental MCP server (`wokwi-cli mcp`) lets agents run simulations and tests; nothing forces it | read | [wokwi-mcp] |
| E4 | Protocol stacks | Yes | Libraries the agent chooses | inference | — |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | Yes | Prose explanation on request; not checked | inference | — |
| F2 | Evidence grading | No | No model-native grading; kicad-happy marks findings datasheet-backed only when a scored extraction supports them | read (kicad-happy) | [kicad-happy] |
| F3 | Automated design review | Partial | kicad-happy design review and fab release gate; validation corpus of 5,857 repos checks **stability, not correctness** (its own words) | read | [kicad-happy] |
| F4 | Datasheet-grounded (cited) | Partial | Only with tools; general models lose table structure from PDFs and tend to answer without evidence (E-Sharp) | read | [esharp] |
| F5 | Audit trail | Partial | Chat / agent transcript | inference | — |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | Yes | Native; but NetlistBench shows accuracy falls as edit sequences lengthen | read | [netlistbench] |
| G2 | Version history | Partial | Via git if the user uses it | inference | — |
| G3 | Comments / roles | No | — | inference | — |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1 | BOM | Yes (via tools) | KiCad BOM via MCP; kicad-happy BOM skill | summary / read | [mcp-python], [kicad-happy] |
| H2 | Live price / stock | Partial | kicad-happy skills for DigiKey, Mouser, LCSC, element14 (user's API keys) | read | [kicad-happy] |
| H3 | Alternates | Partial | Model suggestions; unchecked | inference | — |
| H4 | Fab outputs | Yes (via MCP) | Gerber export | summary | [mcp-python] |
| H5 | DFM | Partial | kicad-happy 8-category fab release gate | read | [kicad-happy] |
| H6 | Order | Partial | kicad-happy JLCPCB / PCBWay workflow skills | read | [kicad-happy] |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | — | Chat apps, CLI agents, IDE plugins + local KiCad | inference | — |
| I2 | API / headless | Yes | Model APIs; kicad-happy as GitHub Action | read | [kicad-happy] |
| I3 | On-prem / certifications | Partial | Enterprise model plans; open tools self-hosted | inference | — |
| I4 | Pricing | — | Model subscriptions; tools free (MIT). Not tabulated here | inference | — |
| I5 | Who uses it | — | Everyone; the default substitute | inference | — |
| I6 | Company facts | — | n/a | — | — |
| I7 | Interop | Yes | KiCad first; Altium/Cadence only via exports | summary | [kicad-mcp] |
| I8 | Open source | Partial | MCP servers and kicad-happy MIT; models closed (except open weights such as Gemma) | read / summary | [kicad-happy], [mcp-python] |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1 | Industrial interfaces | Partial | Whatever the model knows; kicad-happy has 40 domain detectors (RF, Ethernet, motor drivers, BMS…) | read | [kicad-happy] |
| J2 | Power electronics | Partial | Same; unverified | read | [kicad-happy] |
| J3 | RF / high-speed | Partial | Same | read | [kicad-happy] |
| J4 | Safety / regulatory | Partial | EMC pre-compliance rules in kicad-happy | read | [kicad-happy] |
| J5 | Stated limits | Yes | Context windows: a large board needs 3.5M–11M tokens vs a 1M window | read | [esharp] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Assistant ahead:** unlimited breadth, no catalogue, zero switching cost, and an open tool ecosystem (MCP, skills) that now reaches ERC, DRC, ngspice with Monte Carlo, Gerber and ordering.
- **Circuit OS ahead:** the guarantee is structural, not discretionary. The model writes only the requirement, and a retry may add a value but never rewrite what was asked (`.claude/rules/code-style.md`, "Retry"). Generators are deterministic. Every implemented rule runs on every design and an unchecked one prints "not assessed" (`.claude/rules/simulation.md` X8). Properties are proved over tolerance boxes, and firmware is shown only once it compiles (`.claude/CLAUDE.md`). The benchmarks above (8.15% free-form vs 81.3% schema + verifier) are the quantitative case for that design.
- **Correction to vision.md:** "no simulation, no files, no validation" should read "simulation, files and checks only when the agent chooses to run them, with no record of what was not checked and no proof".

## Not verified

- The specific frontier models in each benchmark (HWE-Bench and NetlistBench abstracts do not name them).
- MCP server reliability on non-trivial schematics. The listings are aggregator pages, so read each repository before relying on it.
- Whether ChatGPT's or Gemini's sandboxes can run ngspice natively (not tested; no login).

[hwe]: https://arxiv.org/abs/2603.18102
[pcbschemagen]: https://arxiv.org/abs/2602.00510
[netlistbench]: https://arxiv.org/abs/2608.12197
[longhorizon]: https://arxiv.org/abs/2609.33356
[claude-blog]: https://claude.com/blog/making-claude-a-better-electrical-engineer
[qiao]: https://arxiv.org/abs/2608.25217
[pcbqa]: https://arxiv.org/abs/2606.23704
[esharp]: https://www.electronicdesign.com/55417978
[spec]: C:\Users\KIIT\cursor-electronics\reports\Generative EDA tool feature spec.md
[kicad-mcp]: https://glama.ai/mcp/servers/@mixelpixx/KiCAD-MCP-Server/blob/bce60eb0fcb8797530914d361e3120c6014db9d5/README.md
[mcp-python]: https://enterprisedna.co/directories/mcp/productofamerica-mcp-server-kicad
[kicad-happy]: https://cdn.jsdelivr.net/gh/aklofas/kicad-happy@main/README.md
[wokwi-mcp]: https://docs.wokwi.com/wokwi-ci/mcp-support
[zener]: https://github.com/diodeinc/pcb
[stationx]: https://app.stationx.net/articles/ai-pcb-design
