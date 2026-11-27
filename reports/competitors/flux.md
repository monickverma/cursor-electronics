# Flux — competitor teardown

Written 2026-10-21 by S8 (competitors). Black-box only: public docs, blog, pricing page. This builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"). Labels: **checked** (re-read by a second reader), **read** (primary page opened once), **summary** (search snippet or third party only), **inference**.

Numeric targets are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json` (column `flux`).

## What it computes

Flux is a browser ECAD tool with an AI agent ("Copilot"/Agent).

- **Schematic agent** (read, [Feb 2026 update](https://unified.flux.ai/p/blog/10x-faster-self-correcting-feb-2026-update)): builds schematics, swaps parts, debugs power nets, and runs ERC and DRC "as it works". New ERC reviews were added in February 2026.
- **AI Auto-Layout** (checked, [introduction](https://flux.ai/p/blog/introducing-ai-auto-layout)): **routing only**. The user places the parts first. Announced as a preview in December 2024.
- July 2025 update (read, [blog](https://www.flux.ai/p/blog/ai-auto-layout-just-got-smarter)): nets go into seven priority buckets (High Speed, Analog, Power, Medium Speed, Low Speed, Uncertain, Ground) and route in that order.
- Spring 2026 update (read): "shorter traces, fewer vias", less cleanup. No numbers given.
- **ngspice simulator**, beta, prompt-driven since March 2026 (physics report, checked).
- **Impedance routing**: pre-route width and spacing rules from the stackup (physics report, checked).
- **DRC** categories (read, [DRC blog 2026-03-26](https://flux.ai/p/blog/pcb-design-rule-checking-drc)): trace width, clearance, courtyard, drill/via and annular ring, solder mask, silkscreen. No default values found.

## Method

LLM agent over an ECAD data model, plus a search-based router that improves iteratively and can be stopped at any point (read). Users can lock regions, nets or parts and roll back through version history (summary). Whether the agent writes the netlist directly or through structured edits is not stated.

## Guarantee type

| Output | Rung |
|---|---|
| Schematic and part choice | LLM output, checked by ERC (rule check, pin-level) |
| Routing | Heuristic search |
| DRC | Rule check against user or default rules |
| Simulation | Physics simulation (ngspice), beta |
| Impedance | Pre-route rule; no post-route verification |

No voltage-aware ERC, no layout physics, no proof (physics report; nothing new found).

## Inputs and outputs

- **In:** KiCad, Altium, OrCAD/Allegro, PADS, Xpedition, CADSTAR, Eagle, EasyEDA and Proteus (marketing, summary). A docs FAQ says layout and Gerber import are unsupported, so treat layout import as unconfirmed.
- **Out:** Gerber, drill, BOM, pick-and-place, netlist ([data portability](https://www.flux.ai/docs/reference/data-portability), read). ODB++, IPC-2581, STEP (summary). KiCad export not confirmed.
- **Layers:** up to 8 (physics report).

## Limits

- No automatic placement.
- Router time: "10-15 minutes or even several hours" on complex boards (checked).
- No published completion rate, layer or part limit for auto-layout.
- No mains creepage check found.
- No post-route impedance, SI, PI or thermal analysis.

## Price

Usage is metered in Agent Compute Units (ACUs) (read). Plans Explore, Build, Pro with a 14-day trial; private projects, export and AI need a paid plan. Dollar figures seen only in a snippet: Starter USD 20/month (10 ACUs), Pro USD 142/month per editor, Teams USD 158/month per editor (**summary, unverified**; older third-party figures were USD 15-49).

## Automation

No public API, CLI or headless path found (rests on absence). Everything runs in the browser.

## Their level, as numbers

| Metric | Flux's level | Label |
|---|---|---|
| Routing completion | Not published; router may be stopped early | read |
| Placement | Manual | checked |
| DRC | Rules exist; no default values published | read |
| Vias, length | "Fewer vias, shorter traces" since spring 2026, no numbers | read |
| Decoupling, power width, mains | No numbers published | read (absence) |
| Time | Minutes to several hours for routing | checked |

Flux sets no numeric bar on the layout metrics. Its level on them is below the plan's pass rules, which come from the reference boards and from Quilter.

## How Circuit OS matches or beats it

| Area | Flux | Circuit OS today | Action |
|---|---|---|---|
| Schematic from English | LLM agent edits the design, checked by ERC | LLM writes IntentIR JSON; deterministic generators build the circuit | Ahead on determinism: the LLM never writes the circuit |
| Validation | Pin-level ERC, DRC | z3 proofs of currents over tolerance boxes; exact connectivity on the board | Ahead at schematic level |
| Placement | Manual | Automatic (≤ 40 parts, 2 layers) | Ahead on automation, if the tier A metrics pass |
| Routing | Iterative, minutes to hours | Seconds on DHT22 (2.2 s) | Ahead on time; must reach 100% with 0 shorts (F-0002) |
| SPICE | ngspice beta | ngspice through Celery | Parity |
| Layers | Up to 8 | 2 | Flux ahead |
| Exports | Gerber, BOM, P&P (ODB++ summary) | None yet | S6 export stages needed for parity |
| Version history | Linear, restore | Patch audit trail, no restore | Flux ahead; physics report build item 10 |
| Mains, power width | None found | Decision 12 (2.5 mm); none at layout | Build item 3 beats both |
| API | None | Full HTTP API | Ahead |

## Open questions

- Flux docs pages on DRC and trace width (defaults, fab presets) were not read.
- Real ACU prices need a direct read of the pricing page.
- Whether the agent can now place parts (April and May 2026 updates are known only from a third-party article).
