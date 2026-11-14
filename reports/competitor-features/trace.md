# Trace (buildwithtrace; WishEDA Inc.) — feature inventory
Read 2026-11-14. Vendor: WishEDA Inc. ("© 2026"), backed by Founders Inc · Latest release found: Trace 1.4.0 (GitHub org page; no date shown; trace-public repo updated 2026-05-11, library repos to 2026-10-10) · Earlier teardown: none

**Added by researcher A.** Found via ProtoFlow's comparison page (competitor-authored, so only used as a lead) and confirmed on Trace's own site and GitHub.

## In one paragraph
Trace is an AI-native PCB tool built as a fork of KiCad (GPL-3.0 core, proprietary AI modules): natural-language generation of hierarchical multi-sheet schematics, datasheet parsing and part suggestions with live availability, automated placement on multi-layer boards, freerouting plus a cloud placement-and-routing engine with matched-length tuning (DDR, USB, PCIe), ERC/DRC usable in CI with exit codes, an AI design review against uploaded fab constraints, Gerber/ODB++/IPC-2581 export and one-click ordering through PCBWay and Pikkolo. It has a Plan mode (research, plan, approve, execute) and "TraceRules" for persistent conventions. Priced USD 29.99–169.99/month plus pay-as-you-go credits; claims 4,000+ engineers. Where it stops: no simulation and no firmware found; no published completion or accuracy numbers.

## Features

Source key (read 2026-11-14): [home] https://buildwithtrace.com/ · [price] https://buildwithtrace.com/pricing · [gh] https://github.com/buildwithtrace

| # | Feature | Has it | What exactly | Label | Source |
|---|---|---|---|---|---|
| A1 | Natural-language prompt | Yes | "Generates hierarchical multi-sheet schematics from natural language" | read | [home] |
| A2 | Structured spec | Partial | Plan mode: research, plan, approve, execute | read | [home] |
| A3 | Design as code | No | KiCad fork, graphical | read | [gh] |
| A4 | Imports | Yes | KiCad, Altium, Allegro, PADS; enclosure DXF/STEP; DRC import | read | [home], [price] |
| A5 | Requirement as artifact | Partial | Approved plan; TraceRules persist conventions | read | [home] |
| A6 | Clarifying questions / refusal | Not found | — | not found | — |
| B1 | Schematic from intent | Yes | Multi-sheet with buses, global labels, sub-sheet connectivity | read | [home] |
| B2 | AI edits existing schematic | Yes | Ask/Agent modes on imported projects | read | [price] |
| B3 | Part selection with reasons | Partial | Agents "parse datasheets, suggest components, and check real-time availability"; reasons not described | read | [home] |
| B4 | Reusable modules | Partial | Templates library repo | read | [gh] |
| B5 | ERC | Yes (voltage-aware not found) | ERC/DRC "locally or in CI, with zero-exit-code support" | read | [home] |
| B6 | Hierarchy | Yes | Hierarchical multi-sheet (Ultra plan) | read | [home], [price] |
| B7 | Library | Yes | 30K+ symbols, 24K+ footprints; datasheet parsing | read | [gh] |
| C1–C8 | Simulation and analysis | Not found | No SPICE, SI, PI, thermal, EMC on site | not found ([home]) | — |
| D1 | Automatic placement | Yes | "Automated placement on multi-layer boards" | read | [home] |
| D2 | Automatic routing | Yes | freerouting quick route; cloud placement-and-routing engine (Ultra); no completion figures | read | [gh], [price] |
| D3 | Constraints | Partial | TraceRules; uploaded fab constraints | read | [home] |
| D4 | Stackup | Not found | Multi-layer boards supported | read | [price] |
| D5 | DRC | Yes | KiCad DRC + AI Design Review agent | read | [home], [price] |
| D6 | 3D / MCAD | Yes | STEP, native 3D viewer, enclosure import | read | [home] |
| D7 | Length tuning / diff pairs | Yes | Matched-length tuning for DDR, USB, PCIe (Ultra) | read | [home], [price] |
| D8 | HDI / flex | Not found | — | not found | — |
| E1–E4 | Firmware | Not found | — | not found ([home]) | — |
| F1 | Explains choices | Not found | — | not found | — |
| F2 | Confidence grading | Not found | — | not found | — |
| F3 | Automated review | Yes | Pre-manufacturing AI Design Review against uploaded fab constraints | read | [home] |
| F4 | Datasheet-grounded, cited | Partial | Datasheet parsing; citations not stated | read | [home] |
| F5 | Audit trail | Partial | Audit logs on Enterprise | read | [price] |
| G1 | Conversational edits | Yes | Ask / Agent / Plan modes | read | [price] |
| G2 | Version history | Yes | Local and cloud version control | read | [gh] |
| G3 | Collaboration | Yes | Team workspaces, per-member AI quota | read | [gh], [price] |
| H1 | BOM | Yes | BOM, CPL export with DFM validation | read | [home] |
| H2 | Live price and stock | Yes | JLCPCB, LCSC, DigiKey, Mouser, TI, Amazon, Nexar/Octopart (live pricing on Ultra) | read | [home], [price] |
| H3 | Alternates | Not found | — | not found | — |
| H4 | Fab outputs | Yes | Gerber, drill, BOM, pick-and-place, ODB++, IPC-2581 | read | [home], [gh] |
| H5 | DFM | Yes | DFM validation on export; review against fab constraints | read | [home] |
| H6 | Order inside the tool | Yes | One-click send to PCBWay and Pikkolo; order tracked on dashboard | read | [home] |
| I1 | Form factor | Desktop + CLI | Trace Desktop; Trace CLI repo linked | read | [gh] |
| I2 | API / CLI | Yes | CLI; CI-ready checks; bring-your-own LLM keys | read | [gh], [home] |
| I3 | On-prem / certifications | Partial | Enterprise: private infrastructure, SSO, audit logs, no product-improvement data collection; no certification listed | read | [price] |
| I4 | Pricing | Yes | 7-day trial (card, USD 30 credit); pay-as-you-go from USD 20; Pro USD 29.99/mo (~75 agent requests); Ultra USD 169.99/mo (~425 requests); Enterprise contact | read | [price] |
| I5 | Sold to | — | Students, startups (Stanford, UC Berkeley, Neurex, SuperMicrophone named) | read | [home] |
| I6 | Company facts | — | "4,000+ engineers"; backed by Founders Inc; amount not stated | read | [home] |
| I7 | Interop | Yes | KiCad-native; imports Altium, Allegro, PADS | read | [home] |
| I8 | Open source | Partial | trace-public GPL-3.0 (58 stars); AI modules proprietary | read | [gh] |
| J1–J4 | Industrial, power, RF, safety | Not found | — | not found | — |
| J5 | Stated limits | Not found | — | not found | — |

## Where it is ahead of Circuit OS / where Circuit OS is ahead
Trace ahead: any circuit, multi-layer placement and routing, length tuning, fab outputs and ordering, CI-ready KiCad ERC/DRC.
Circuit OS ahead: simulation (ngspice) and proofs, compiled firmware, consequential explanation, deterministic generation with refusal (`MENTAL_MODEL.md`; `.claude/CLAUDE.md`).

## Not verified
Release dates; routing completion; whether ERC is voltage-aware; funding amount.
