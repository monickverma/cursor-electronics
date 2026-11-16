# Freerouting (and the open autorouter baseline) — feature inventory
Read 2026-11-13. Project: Freerouting (open source, GPL-3.0) · Latest release found: v2.5.0, 5 October 2026 · Earlier teardown: none (Circuit OS's ROADMAP plans to integrate Freerouting; `MENTAL_MODEL.md` §4 notes the current engine is custom, not Freerouting)

## In one paragraph

Freerouting is the free, algorithmic (not AI) autorouter that most open tools and several AI agents call. It reads a Specctra/Electra `.dsn` board and writes a `.ses` session, and it plugs into KiCad (including a KiCad 10+ IPC mode in 2026), Autodesk Fusion, EasyEDA, tscircuit, Target3001! and pcb-rnd. 2026 turned it into a headless service. It now has a REST API (`POST /v1/autoroute`), an MCP server (`autoroute_board`) and an A2A agent card, a JSON DRC (`-drc`, `GET /v1/jobs/{id}/drc`), a deterministic post-route optimiser, native executables without Java (v2.5.0), Docker images and a Python client. The maintainer reports that clean boards rose from 30.9% to 75.0% on a 1,157-board corpus in v2.5.0. It places nothing, computes no physics and knows no impedance. Third-party tests in September 2026 found that OpenAI's "GPT-6 Astra" PCB-layout demo routed through Freerouting, and a JLCPCB test used Freerouting 2.0.1 behind an LLM agent in EasyEDA Pro.

## Features

Main sources (read 2026-11-13): [repository README](https://github.com/freerouting/freerouting) · [releases](https://github.com/freerouting/freerouting/releases) · [NextPCB Astra test, Sept 2026](https://www.nextpcb.com/blog/gpt-6-astra-kicad-pcb-routing-test) · [JLCPCB Astra test, 2026-09-15](https://jlcpcb.com/blog/gpt-6-astra-pcb-design-in-easyeda-pro).

### A. Input and intent

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | No | Router only; LLM agents call it through MCP | read | [releases](https://github.com/freerouting/freerouting/releases) |
| A2 | Structured spec input | Partial | Specctra `.rules` settings uploadable through the REST API (v2.4.1); `-inc` to skip net classes | read | [releases](https://github.com/freerouting/freerouting/releases), [README](https://github.com/freerouting/freerouting) |
| A3 | Design as code | No | — | inference | — |
| A4 | Imports | Yes | Specctra/Electra DSN in, SES out; KiCad IPC mode (KiCad 10+) with DSN fallback | read | [README](https://github.com/freerouting/freerouting), [releases](https://github.com/freerouting/freerouting/releases) |
| A5 | Requirement as artifact | No | — | inference | — |
| A6 | Clarifying / refusal | No | — | inference | — |

### B. Schematic

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| B1-B7 | Schematic generation, copilot, parts, modules, ERC, hierarchy, library | No | Router only; works on a board already placed in a host tool | read | [README](https://github.com/freerouting/freerouting) |

### C. Simulation and analysis

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| C1 | SPICE | No | — | read (scope) | [README](https://github.com/freerouting/freerouting) |
| C2 | Tolerance / MC | No | — | read (scope) | as C1 |
| C3 | Formal proof | No | — | read (scope) | as C1 |
| C4 | Signal integrity | No | No impedance or length model stated | not found | [README](https://github.com/freerouting/freerouting) |
| C5 | Power integrity | No | — | read (scope) | as C1 |
| C6 | Thermal | No | — | read (scope) | as C1 |
| C7 | EMC | No | — | read (scope) | as C1 |
| C8 | Creepage | No | — | read (scope) | as C1 |

### D. PCB layout

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| D1 | Automatic placement | No | SMD fanout pre-pass only (v2.3.0) | read | [releases](https://github.com/freerouting/freerouting/releases) |
| D2 | Automatic routing | Yes | Maze router with optimiser; per-layer bend costs for single-sided boards; layer limit not stated (a >2-layer bug was fixed in v2.2.3). Completion: maintainer reports 75.0% of 1,157 boards clean in v2.5.0 (up from 30.9%). Time: forum report of 10 minutes on a board DeepPCB left unfinished (2023) | read; summary (forum) | [releases](https://github.com/freerouting/freerouting/releases), [EEVblog forum](https://eevblog.com/forum/blog/eevblog-1535-deeppcb-ai-autorouting-tested!/msg4787999) |
| D3 | Constraint management | Partial | Net classes and Specctra rules from the DSN | read | [README](https://github.com/freerouting/freerouting) |
| D4 | Stackup / impedance | No | — | not found | [README](https://github.com/freerouting/freerouting) |
| D5 | DRC | Yes | Built-in DRC with JSON output since v2.2.0; `compact=true` mode for LLMs (v2.5.0) | read | [releases](https://github.com/freerouting/freerouting/releases) |
| D6 | 3D / MCAD | No | — | read (scope) | — |
| D7 | Length / diff pairs | Not found | Not stated on the README | not found | [README](https://github.com/freerouting/freerouting) |
| D8 | HDI / flex | Not found | — | not found | — |

### E. Firmware

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| E1-E4 | Firmware, pin-mux, compile, protocols | No | Out of scope | read (scope) | [README](https://github.com/freerouting/freerouting) |

### F. Explanation, evidence, review

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| F1 | Explains choices | No | — | inference | — |
| F2 | Confidence per decision | Partial | Score: trace length, vias, completion (v2.1.0), exportable as JSON | read | [releases](https://github.com/freerouting/freerouting/releases) |
| F3 | Automated review | Partial | DRC only | read | as F2 |
| F4 | Datasheet checks | No | — | inference | — |
| F5 | Audit trail | Partial | Telemetry distinguishes human and AI-agent users (v2.5.0); rolling logs | read | [releases](https://github.com/freerouting/freerouting/releases) |

### G. Iteration and collaboration

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| G1 | Conversational edits | No | — | inference | — |
| G2 | Version history | No | Host tool's job | inference | — |
| G3 | Comments / roles | No | — | inference | — |

### H. Supply chain and manufacturing

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| H1-H6 | BOM, pricing, alternates, fab outputs, DFM, ordering | No | Router only; host tool exports fab files | read (scope) | [README](https://github.com/freerouting/freerouting) |

### I. Platform and business

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| I1 | Form factor | Yes | Desktop GUI, CLI, Docker, native executables (v2.5.0) | read | [releases](https://github.com/freerouting/freerouting/releases) |
| I2 | API / CLI / headless | Yes | REST API (public beta at api.freerouting.app, keys reviewed weekly; or self-hosted, auth on by default), MCP server, A2A card, Python client on pip, OpenAPI docs | read | [README](https://github.com/freerouting/freerouting), [releases](https://github.com/freerouting/freerouting/releases) |
| I3 | Self-host | Yes | Docker / JRE / native; MCP file access sandboxed (v2.4.1) | read | as I2 |
| I4 | Pricing | Yes | Free | read | [README](https://github.com/freerouting/freerouting) |
| I5 | Who uses it | Yes | KiCad, Fusion, EasyEDA, tscircuit users; LLM agents | read | as I2 |
| I6 | Project facts | Partial | Maintainer has about 4 hours a week; stepped back from leadership in v2.1.0 and sought institutional support; releases every 2-3 months | read | as I2 |
| I7 | Interop | Yes | Any DSN-capable tool | read | [README](https://github.com/freerouting/freerouting) |
| I8 | Open source | Yes | GPL-3.0 | read | [README](https://github.com/freerouting/freerouting) |

### J. Domain coverage

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| J1-J4 | Industrial, power, RF, standards | No | Generic router | inference | — |
| J5 | Stated limits | Not found | No size limits stated | not found | [README](https://github.com/freerouting/freerouting) |

## Other open routers (brief)

- **KiCad's own router** is interactive (push-and-shove, length tuning), not automatic; KiCad dropped its built-in autorouter years ago and relies on Freerouting (from memory, unverified).
- **tscircuit's autorouter** is open source and runs inside its code-first flow (summary, `Generative EDA tool feature spec.md`); it belongs to the code-first group.
- **PCBWorld** (LG AI Research, arXiv 2607.05915, July 2026) is an open KiCad environment and benchmark for routing agents. It has 679 real open-source boards and eight engine-checked metrics; its agents beat grid-action RL and open-loop LLMs, approaching rule-based routers (summary: [arXiv](https://arxiv.org/abs/2607.05915), [GitHub](https://github.com/LGAI-Research/PCBWorld)). DeepPCB claims the top one-attempt score on it ([deeppcb.ai](https://deeppcb.ai/), read).

## Where it is ahead of Circuit OS / where Circuit OS is ahead

- **Freerouting ahead:** multi-layer routing of real boards, a REST/MCP service, JSON DRC, and wide host-tool support. That is exactly what the Circuit OS plan wants to integrate, and v2.5.0's single-call `POST /v1/autoroute` plus deterministic optimiser fit a Celery worker. GPL-3.0 means running it as a separate process (inference, matching how the physics report treats GPL tools).
- **Circuit OS ahead:** placement, intent-derived constraints and an exact connectivity, short and pin check (`pcb_engine/verify.py`). Freerouting places nothing.

## Not verified

- Layer-count ceiling, diff-pair and length-matching support.
- The 75.0% figure's corpus and definition of "clean" (maintainer-reported).
- Release years for v2.0.1 to v2.4.1. The page shows only month and day; v2.5.0's assets carry 2026 timestamps.
