# KiCad — competitor teardown

Written 2026-10-21 by S8 (competitors). KiCad is open source (GPL), so it is both a competitor and the judge's tool: S2 grades every board with `kicad-cli`. Sources: docs.kicad.org, kicad.org, and the installed `kicad-cli` 10.0.1 run locally. Builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"). Labels: **checked** (here: run on the installed binary, or re-read), **read**, **summary**, **inference**.

Numeric targets are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json` (column `kicad`).

## What it computes

- **DRC** with geometric rules and a custom-rule language; schematic parity; unconnected items.
- **ERC**: pin-type and power-pin checks, no voltage levels ([eeschema](https://docs.kicad.org/9.0/en/eeschema/eeschema.html), read).
- **Creepage** custom-rule constraint since KiCad 9, e.g. `(constraint creepage (min 5mm))`. The user types the distance; it is not derived from voltage ([forum](https://forum.kicad.info/t/how-do-i-use-the-new-creepage-custom-rules-v9-0-0/59328), read; no official docs page found). Early 9.0 had bugs.
- **PCB Calculator**: track width from IPC-2221 (not IPC-2152); an electrical-spacing table by voltage that names no standard ([calculator](https://docs.kicad.org/9.0/en/pcb_calculator/pcb_calculator.html), read).
- **ngspice** simulation, IBIS, ODB++ and IPC-2581 export (physics report).
- KiCad 10.0.0, released 2026-03-20: graphical custom-rule editor, DRC suggested fixes, time-domain track tuning, design variants, Allegro/PADS/gEDA import ([release](https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/), read).

## Method

Manual layout with an interactive router (push-and-shove, walkaround, diff pairs, length and skew tuning). **No built-in autorouter**; Freerouting is a third-party plugin. A footprint auto-place function is still in the 9.0 manual (read).

## Guarantee type

| Output | Rung |
|---|---|
| DRC, creepage, parity | Rule check against user-typed numbers; connectivity and parity are exact on the board data |
| ERC | Rule check, pin type only |
| ngspice | Physics simulation on the schematic |
| Calculator | Empirical (IPC-2221 curve fit) |

## Inputs and outputs

- **In:** KiCad files; imports from Altium, Eagle, CADSTAR, and since 10.0 Allegro, PADS, gEDA.
- **Out:** Gerber, drill, ODB++, IPC-2581, STEP, netlists, DRC/ERC reports.

### `kicad-cli pcb drc` (checked on 10.0.1)

Flags: `--format json|report`, `--severity-all|-error|-warning|-exclusions`, `--schematic-parity`, `--all-track-errors`, `--units`, `--refill-zones`, `--exit-code-violations` (exit code 5 when violations exist; [CLI docs](https://docs.kicad.org/9.0/en/cli/cli.html), read, and seen locally).

JSON top-level keys, seen locally: `$schema`, `coordinate_units`, `date`, `ignored_checks`, `included_severities`, `kicad_version`, `schematic_parity`, `source`, `unconnected_items`, `violations`. Each violation has a `severity` and a `type`.

Run on KiCad's own demo `CM5_MINIMA_3.kicad_pcb` (2026-10-21): 176 violations, of which **4 errors** (2 `copper_edge_clearance`, 2 `courtyards_overlap`) and 172 warnings; 0 unconnected items; 5 schematic-parity entries. **A shipped, fabricated reference board does not have zero DRC findings.** This supports the plan's rule "no more errors than the reference", rather than "0", for references.

## Limits

- No autorouter, no AI.
- No layout physics in core (ThermalSim, KiCad-Parasitics are third-party plugins; physics report).
- Creepage is user-typed and was buggy in early 9.0.
- The IPC API needs a running GUI and cannot plot or export; headless use is planned for KiCad 11 (summary, dev docs).

## Price and automation

Free, GPL (licence page not re-read). Automation: `kicad-cli` (DRC, ERC, exports) works headless today; the IPC API does not yet.

## Default rules (baseline for "out-of-box" DRC)

From the KiCad source header (summary, [doxygen](https://docs.kicad.org/doxygen/board__design__settings_8h_source.html)): minimum track width 0.2 mm, minimum via diameter 0.5 mm, copper-to-edge 0.5 mm. Clearance is set per netclass. The board template shipped with KiCad 10 (`template/API_Series-500`, read locally) uses: min track 0.2 mm, min via diameter 0.4 mm, min through-hole 0.3 mm, min annular ring 0.1 mm, hole clearance 0.25 mm. Use a named fab profile (e.g. JLCPCB) for grading, not these defaults.

## Their level, as numbers

| Metric | KiCad's level | Label |
|---|---|---|
| Netlist parity | `--schematic-parity` reports each mismatch; exact on the data | checked |
| Routing completion | `unconnected_items` count; reference boards: 0 | checked |
| DRC | Reference's own error count (demo: 4 errors, 172 warnings) | checked |
| Creepage | User-typed minimum, any value | read |
| Power trace | IPC-2221 calculator | read |
| Time | Manual layout | inference |

## How Circuit OS matches or beats it

| Area | KiCad | Circuit OS today | Action |
|---|---|---|---|
| Layout | Manual | Automatic (≤ 40 parts, 2 layers) | Ahead on automation, if tier A metrics pass |
| DRC | Full DRC, headless | 7-rule kernel | Use KiCad as second engine: S6 writes `.kicad_pcb`, S2 grades with `kicad-cli`. Disagreement is a finding |
| Parity | `--schematic-parity` | verify.py pin parity (exact) | Parity; cross-check both |
| Creepage | User-typed | Decision 12 (2.5 mm) | Beat: derive from voltage and insulation class (F-0004) |
| Trace width | IPC-2221 calculator, manual | None at layout | Beat: IPC-2152 width from proven currents (build item 3) |
| ERC | Pin type | z3 proofs, graph rules | Ahead |
| Exports | All formats | None | Use kicad-cli for exports (build item 11) |
| Price | Free | — | Circuit OS cannot win on price against free; it wins on automation and proofs |

## Open questions

- Official docs page for the creepage constraint.
- Default netclass clearance in a new 10.0 board.
- Whether 10.0 fixed the 9.0 creepage bugs.
