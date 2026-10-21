# Celus — competitor teardown

Written 2026-10-21 by S8 (competitors). Black-box only: celus.io and press. This builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"), which says Celus does no post-layout physics. Labels: **checked**, **read**, **summary**, **inference**.

Numeric targets are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json` (column `celus`).

## What it computes

Celus turns a plain-language requirement into "matched components, block diagrams and working schematics", plus a BOM with supply-chain data and alternates ([celus.io](https://www.celus.io), read).

An Embedded.com article (checked, [embedded.com](https://www.embedded.com/?p=4490751); undated, about 2022) lists the outputs as architecture, ECAD-native schematics, BOM, footprints and a project summary. Its opening also mentions "a PCB floor plan in native EDA formats". The current homepage does not mention layout. Celus does **no routing** found anywhere.

## Method

Machine-learning matching of parts against functional, electrical, environmental, mechanical and cost constraints, from natural-language input (read). The homepage names internal agents "design_checker" and "design_verifier" with no detail, and exposes product data to agents over MCP (read). Its knowledge base of functional blocks ("CUBOs") appears only in press (summary). No ERC or voltage-level check is described.

## Guarantee type

| Output | Rung |
|---|---|
| Architecture and part choice | ML matching; vendor claim only |
| Schematic | Built from reference circuits "matched to your requirements"; no stated check |
| Layout | None (a floor plan at most, per older press) |

No correctness claim, no proof, no simulation found.

## Inputs and outputs

- **In:** plain-language requirements.
- **Out:** a design "opened straight in Altium, Cadence, Siemens, Fusion or KiCad" (read; file formats not stated). Older press lists KiCad, Altium and Eagle (summary).

## Limits

- Typical project 200 to 1,000 components (checked). Larger than Circuit OS's tier A.
- No layout routing, no DRC, no layout physics.
- No unsupported-domain list published.

## Price

"The platform is free to the user" (checked, Embedded.com). Part makers pay for visibility when their parts are chosen. No 2025-2026 tiers found; celus.io/pricing returned 404. Funding: EUR 25 M Series A in 2022, led by Earlybird (summary).

## Automation

MCP access to product data is mentioned on the homepage (read). No public API or CLI documentation found.

## Their level, as numbers

| Metric | Celus's level | Label |
|---|---|---|
| Time to schematic | "Less than an hour" from requirements; minutes for a very simple demo | checked |
| Project size | 200-1,000 components | checked |
| Part database | About 17 M parts (some press: 600 M+) | summary |
| Layout metrics (routing, DRC, vias, area, decoupling, power width, mains) | Not applicable: no layout | read (absence) |

Celus sets no bar on the plan's layout metrics. It sets a bar on **time to schematic** and **breadth** (parts and board size).

## How Circuit OS matches or beats it

| Area | Celus | Circuit OS today | Action |
|---|---|---|---|
| English to schematic | Yes, < 1 h | Yes, seconds, for the five templates and composition blocks | Ahead on time; far behind on breadth |
| Breadth | 200-1,000 parts, 17 M part database | ≤ 40 parts, closed catalogue | Celus ahead. Circuit OS refuses outside its catalogue by design |
| Validation | Unnamed "design_checker" agents | z3 proofs, ERC-level graph rules, ngspice | Ahead: each claim has a rung |
| Layout | Floor plan at most | Placement and routing (experimental) | Ahead, if tier A metrics pass |
| Firmware | None found | Compiled firmware (PlatformIO gate) | Ahead |
| BOM | Supply-chain data, alternates | Static dated prices, optional Mouser; substitutes re-proved | Parity; Circuit OS re-proves substitutes |
| Price | Free to the user | — | Owner decision |

## Open questions

- Whether Celus still exports a floor plan, and in what form.
- What "design_checker" and "design_verifier" check.
- Current pricing, if any.
