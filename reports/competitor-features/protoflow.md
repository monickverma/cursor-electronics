# ProtoFlow — feature inventory
Read 2026-11-14. Vendor: ProtoFlow LLC (founder Rishik Boddeti, per its own comparison page) · Latest release found: version 3.2.3 named on the benchmarks page (undated); "Free AI Part Generator" banner; changelog did not render · Earlier teardown: none

**Added by researcher A.** Found through JLCPCB's "AI Tools for PCB Design" list (2026-09-28, updated 2026-11-09). Nearly every fact below is ProtoFlow's own claim; there are few independent reviews (ProtoFlow says so itself).

## In one paragraph
ProtoFlow is a desktop EDA application (Windows, macOS, Linux) with AI built in: describe a circuit in plain language and it drafts an editable schematic with real LCSC/JLCPCB, DigiKey and Mouser parts; an AI Copilot edits inside the editor; "ProtoFlow Studio" places and routes a board from a brief. It also embeds ngspice (operating point, transient, AC, DC sweep), ERC/DRC, Git with branches and diffs, KiCad/Altium/EAGLE/PADS/EDIF import and export, Gerber X2 and JLCPCB-formatted fab files, a CLI and MCP. It is priced like a consumer AI tool (free tier; USD 19.99–199.99/month). It claims "20k+ engineers". Its benchmarks are the most concrete numbers in this group: 99/99 small and 30/30 medium boards of LG AI Research's PCBWorld-Bench routed KiCad-clean with Claude Opus 5.5, and a 2-layer, 372-connection board routed 100% with 0 DRC errors in 42 min 47 s. Where it stops: no firmware, no SI, no proof or tolerance analysis found; AI requests go to hosted models; checks are ERC/DRC/SPICE run by the user or agent.

## Features

Source key (read 2026-11-14): [home] https://www.protoflow.ai/ · [bench] https://www.protoflow.ai/benchmarks · [docs] https://www.protoflow.ai/docs · [price] https://www.protoflow.ai/pricing · [cmp] https://www.protoflow.ai/compare/best-ai-schematic-generator (ProtoFlow-authored, reviewed 2026-10-26) · [jlc] https://jlcpcb.com/blog/ai-tools-for-pcb-design

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | Yes | "Describe the circuit in plain language and AI generates the schematic with real parts" | read | [home] |
| A2 | Structured spec | Partial | Plan mode (Pro and up) | read | [price] |
| A3 | Design as code | No / Not found | Graphical editor with Git | inference | [docs] |
| A4 | Imports existing design | Yes | KiCad, Altium, EAGLE, EDIF projects | read | [home], [cmp] |
| A5 | Requirement as artifact | Not found | — | not found | — |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |
| B1 | Schematic from intent | Yes | AI drafts editable schematic; "Five circuit-design tasks … accepted on owner review" | read | [home], [bench] |
| B2 | AI edits existing schematic | Yes | AI Copilot inside the editor; "50+ AI tools" | read | [docs] |
| B3 | Part selection with reasons | Partial | Real parts from JLCPCB, DigiKey, LCSC, Mouser; reasons not described | read | [home] |
| B4 | Reusable modules | Not found | — | not found | — |
| B5 | ERC (voltage-aware?) | Yes (voltage-aware not found) | ERC, DRC, "topology analysis"; BLE schematic: 0 ERC errors, 3 explained warnings | read | [docs], [bench] |
| B6 | Hierarchy | Not found | — | not found | — |
| B7 | Library from datasheets | Yes | AI Component Lab: symbol + footprint "from a part name, datasheet, or pinout image"; 10–70 part-generator units/month by plan | read | [docs], [price] |
| C1 | SPICE | Yes | ngspice from the schematic: OP, transient, AC, DC sweep, waveform viewer; "simulation verification" on Pro | read | [home], [docs], [price] |
| C2 | Tolerance / Monte Carlo | Not found | — | not found | — |
| C3 | Formal proof | Not found | — | not found | — |
| C4 | Signal integrity | No | Its own comparison page lists no SI analysis | read | [cmp] |
| C5–C8 | PI, thermal, EMC, creepage | Not found | — | not found | — |
| D1 | Automatic placement | Yes | "Auto-place components"; Studio places and routes from a brief | read | [docs], [cmp] |
| D2 | Automatic routing | Yes | PCBWorld-Bench: 99/99 small boards KiCad-clean (median 32 s), 30/30 medium-board attempts within 30 min, router-only baseline 0.919/0.900; Rodeostat 2-layer, 372/372 connections, 0 DRC errors, 42 min 47 s; 4-layer 203-part reference design with 0 DRC errors. Vendor-run; benchmark undated; ProtoFlow's PCBBench is a "provisional pilot" | read | [bench] |
| D3 | Constraint management | Not found | Layer filters and router presets only | read | [home] |
| D4 | Stackup / impedance | Not found | — | not found | — |
| D5 | DRC | Yes | DRC plus a JLCPCB audit before ordering | read | [home] |
| D6 | 3D / MCAD | Yes | Live 3D view; STEP export | read | [home] |
| D7–D8 | Length tuning, HDI | Not found | — | not found | — |
| E1–E4 | Firmware | Not found | — | not found ([home], [docs]) | — |
| F1 | Explains choices | Partial | "Explained warnings" in the benchmark schematic | read | [bench] |
| F2 | Confidence grading | Not found | — | not found | — |
| F3 | Automated review | Partial | ERC/DRC/SPICE "before you commit"; JLCPCB audit | read | [home] |
| F4 | Datasheet-grounded, cited | Not found | — | not found | — |
| F5 | Audit trail | Partial | Git history | read | [docs] |
| G1 | Conversational edits | Yes | Copilot chat | read | [docs] |
| G2 | Version history / diff / branch | Yes | "Full Git integration with branching, diff viewer, and GitHub support" | read | [docs] |
| G3 | Collaboration | Yes | Live collaboration (Pro and up) | read | [price] |
| H1 | BOM | Yes | BOM and JLCPCB-format BOM/placement | read | [home] |
| H2 | Live price and stock | Partial | Parts from four distributors; live stock not stated | read | [home] |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fab outputs | Yes | Gerber X2, Excellon drill, BOM, placement, STEP | read | [home], [cmp] |
| H5 | DFM | Partial | JLCPCB audit before ordering | read | [home] |
| H6 | Order inside the tool | Partial | Implied by the JLCPCB audit "before ordering"; ordering flow not described | inference from [home] | — |
| I1 | Form factor | Desktop | Windows, macOS, Linux; AI requests go to hosted models | read | [cmp] |
| I2 | API / CLI | Yes | CLI and MCP listed; AI builds via the user's own Claude Code or Codex (Max) | read | [home], [price] |
| I3 | On-prem / certifications | Partial | Projects stay local; Enterprise: SSO/SAML, private model and data isolation; no certification listed; AI training on prompts on by default unless opted out (EU/UK opted out) | read | [price], [cmp] |
| I4 | Pricing | Yes | Free USD 0 (5 basic + 10 pro AI messages/day); Pro USD 19.99/mo; Max USD 39.99/mo; Ultra 10x USD 199.99/mo; Enterprise custom; top-ups 10 credits per USD 1 | read | [price] |
| I5 | Sold to | — | Individual engineers, students, small teams; logos Logitech, Honda, Samsung | read | [home] |
| I6 | Company facts | — | "20k+ engineers"; funding not found | read | [home] |
| I7 | Interop | Yes | Exports KiCad, Altium, EAGLE, PADS, EDIF | read | [home] |
| I8 | Open source | No / Not found | — | not found | — |
| J1–J4 | Industrial, power, RF, safety | Not found | — | not found | — |
| J5 | Stated limits | Partial | Free plan: "no project or complexity cap" | read | [price] |

## Where it is ahead of Circuit OS / where Circuit OS is ahead
ProtoFlow ahead: any circuit; placement and routing with published (vendor-run) completion numbers, up to 4-layer examples; fab outputs; ECAD import/export; Git diffs and branches; a free tier. Circuit OS's board is experimental, 2-layer, ≤ 40 parts, without Gerber export (physics report table; `MENTAL_MODEL.md` §4).
Circuit OS ahead: deterministic generation from a requirement IR with refusal; z3 proofs and graded claims; compiled firmware; consequential explanation (`MENTAL_MODEL.md` §3, §10; `.claude/CLAUDE.md`). ProtoFlow's SPICE matches Circuit OS's ngspice, so SPICE is not a differentiator here either.

## Not verified
Changelog and release dates; funding; whether the PCBWorld-Bench run is reproducible by third parties; voltage awareness of ERC; ordering flow.
