# Altium — competitor teardown

Written 2026-10-21 by S8 (competitors). Black-box only: public docs and product pages. This builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"), whose Altium table is checked and not repeated in full. Labels: **checked**, **read**, **summary** (search snippet or third-party only), **inference**.

Numeric targets are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json`. Altium is a manual tool, so "Altium's level" means the board an engineer produces with it, plus Altium's own checks. In the benchmark this is the reference layout.

## What it computes

From the physics report (checked): impedance from the Layer Stack Manager (Simbeor 2D solver); built-in reflection and crosstalk simulation; SPICE3f5 mixed simulation; paid Keysight SI (open beta) and Power Analyzer (DC only); third-party EMI; pin-type ERC; geometric design rules; Altium 365 design compare.

New this cycle:

- **Creepage Distance rule** (checked, [docs](https://www.altium.com/documentation/altium-designer/pcb-electrical-rule-creepage-distance)). It measures between chosen nets across the board surface, through unplated holes and cutouts, and around the board edge. The user types the distance. Voltage is not used. It is **off by default** for online and batch DRC. It reports only the first violation per net pair (read).
- **Default clearance** in a new board: 10 mil (0.254 mm) for all object pairs (checked, same page). Default track width and via size were not found.
- **IPC-2152 calculator** that pushes widths into rules (summary, [Altium resources](https://resources.altium.com/p/using-ipc-2152-calculator-designing-standards)).

## Method

Interactive layout by an engineer. Two routing aids:

- **ActiveRoute**: a guided router for selected nets. It cannot place vias (fan-out first), skips power nets and nets with more than 20 pins, and publishes no completion figure ([docs](https://www.altium.com/documentation/altium-designer/activeroute-ad), read).
- **Situs**: a topological autorouter that maps the relative positions of obstacles (summary, CircuitMaker docs). No completion figure published.

No native AI placement or routing was found as of 2026-10-21 (summary). Altium's agentic work is in the Altium 365 Requirements Portal, which manages requirements and is not documented as checking board geometry (summary).

## Guarantee type

| Output | Rung |
|---|---|
| Layout | Human work; no automated claim |
| DRC, creepage, manufacturing rules | Rule check against numbers the user types |
| Impedance, SI, Keysight SI/PI | Physics simulation |
| ERC | Rule check, pin type only; no voltage or current awareness |

## Inputs and outputs

- **In:** native schematic and PCB documents; KiCad import through an extension, up to KiCad 8.x (summary).
- **Out:** Gerber, Gerber X2, NC drill, ODB++, IPC-2581 rev A/B through Output Jobs (summary).

## Limits

- No board thermal solver, no placement score, no feedback from simulation to layout (physics report).
- AC power integrity not native; Power Analyzer is DC only (checked).
- Creepage is not derived from voltage, insulation class or pollution degree, and is off by default.
- No documented headless or CI path for DRC. The Altium 365 API is GraphQL over workspace data (projects, releases, libraries); an MCP server for Altium Designer is listed as "coming soon". Designer scripting is DelphiScript (summary).

## Price

No official list price could be read (altium.com pricing returned 403). Third-party figures, **summary only**: Altium Develop about USD 995/year per workspace plus USD 995 per author; Designer seats about USD 3,500-7,500/year; Agile and Enterprise quote-only. Keysight SI add-on INR 112,565/year on the India store (physics report). Confirm with Altium sales before quoting.

## Automation

Output Jobs automate release packages from inside the GUI. The 365 API reads and writes workspace data. No public route runs DRC, SI or PI from a pipeline (rests on absence).

## Their level, as numbers

| Metric | Altium's level | Label |
|---|---|---|
| Netlist parity | Exact (ECO-synchronised reference) | inference |
| Routing completion | 100% on the reference; no autorouter figure published | read |
| DRC | The reference's own count; out-of-box clearance 10 mil | checked |
| Board area, vias, length, decoupling | The reference board's values; no Altium guidance numbers | read (absence) |
| Power trace | IPC-2152 width from the calculator; example 1 A at 1 oz, 10 °C rise ≈ 10 mil | summary |
| Mains clearance | Whatever the engineer typed, if the rule was switched on | checked |
| Time | Manual; Quilter quotes 428 h for its 843-part board | checked |

## How Circuit OS matches or beats it

| Area | Today | To match | To beat |
|---|---|---|---|
| Layout | Automatic, 2 layers, ≤ 40 parts, experimental | Reference metrics on tier A: area ≤ 1.3×, vias and length ≤ 1.5× (plan §6) | Seconds instead of hours (DHT22: 2.2 s) |
| DRC | Own 7-rule kernel | kicad-cli DRC, 0 errors, ≤ reference (S6) | Rules derived from the fab profile, not typed |
| Creepage | Decision 12: 2.5 mm | Altium's rule is manual and off by default | Derive it from working voltage, insulation class and pollution degree; on by default; ≥ 5.0 mm reinforced at 250 V (F-0004, needs safety review) |
| Voltage/current | z3 proofs at schematic level | Altium ERC has none | Already ahead at schematic level; layout-level width check is build item 3 |
| Trace width | Not checked | IPC-2152 at the current | Current comes from the proof, not a guess |
| DC IR drop | None | Build item 4 ≈ Keysight Power Analyzer (paid) | Free and in the pipeline |
| AC PDN | None | Altium has none native | Build item 5 |
| Pinout | verify.py against the KiCad library | Altium has none | Already ahead |
| Export | None yet | ODB++, IPC-2581, Gerber via kicad-cli (build item 11) | — |
| SI simulation | None | Altium ahead | Out of scope for tier A; escalation lane is build item 8 |
| Automation | Full HTTP API | Altium has no CI DRC | Already ahead |

Rung note: "matches Altium" means "matches the reference layout on these metrics", never "proven".

## Open questions

- Official 2026 prices for Designer, Develop and Agile.
- Default track width and via size in a new Altium board.
- Whether the Layer Stack Manager solver ships in every tier.
- Whether Altium Designer will ship AI placement or routing in 2026 (none found).
