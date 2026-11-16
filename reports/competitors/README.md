# Competitor matrix

Written 2026-10-21 by S8. One report per product in this folder. Numeric targets per gap metric, with a source and a label for each, are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json` (outside the repo).

| | Quilter | Altium | Flux | Celus | JITX | KiCad | Circuit OS today |
|---|---|---|---|---|---|---|---|
| Input | CAD board file | Manual | Browser ECAD + agent | English | Design code | Manual | English → IntentIR |
| Places parts | Yes | No | No | Floor plan at most | Not found | No | Yes (≤ 40 parts) |
| Routes | Yes, goal 100% | Guided (ActiveRoute) | Yes, minutes to hours | No | Yes (generated) | No (plugin) | Yes, 2 layers |
| Shown boards DRC-clean | Yes (0 errors) | Engineer's job | Not stated | — | Export may fail DRC | Engineer's job | Own 7-rule kernel |
| Layout physics | 8 rule checks, Simbeor, DC IR beta | SI sim, paid Keysight SI/DC PI | None | None | HFSS in the loop | None in core | None |
| Voltage-aware checks | No | No | No | Not stated | User-written | No | z3 proofs (schematic) |
| Creepage from voltage | No (≤ 48 V) | No (user-typed, off) | No | No | No | No (user-typed) | Not yet (F-0004) |
| Headless / API | No | No CI DRC | No | MCP mention | CLI | kicad-cli | HTTP API |
| Price | Per pin, unpublished | ~USD 1-7.5 k/yr (third party) | ACU-metered | Free to user | Free for open HW | Free | — |

Where Circuit OS can be first: creepage derived from voltage and insulation class, and trace width checked against proven currents. Nobody in this set does either. Where it is behind: board size and layer count (Quilter, Altium, Flux), field solvers (Quilter, Altium, JITX), exports (all). Every "match" means "matches on these metrics", never "proven".
