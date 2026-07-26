# Timeline — LAYER 6 (history)

> Append-only. One line per significant event. Answers: "how did we get here?"
> A fresh agent reading this knows the project's full history.

---

## Format
`**YYYY-MM-DD** — [What changed] — [Outcome / why it matters]`

---

## History

**2026-06-01** — Project initialized. Architecture designed (Parser → Netlist Gen → Simulator → Verifier → PCB). ngspice selected as simulator. Python + pytest as the stack. Six-layer brain scaffold added.

**2026-06-01** — Environment setup complete. ngspice installed and verified. pytest running. Git initialized.

**2026-06-02** — NL Parser (`src/parser.py`) completed: 4/4 functions verified done. Handles R, C, L, V, I sources. Normalizes unit prefixes. All parser tests passing.

**2026-06-02** — Netlist Generator (`src/netlist_gen.py`) completed: 3/3 functions verified done. ComponentSpec → valid SPICE netlist. Tested with RC filter, ngspice runs generated netlist.

**2026-06-03** — Simulator wrapper (`src/simulator.py`) started. `run_simulation` and `parse_output` exist but failing due to ngspice convergence on nonlinear netlist. `retry_with_options` and `build_sim_result` not yet implemented.

---

## TEMPLATE — adding an entry

```
**YYYY-MM-DD** — [Concrete change] — [Outcome]
```

Keep entries to 1–2 sentences. Record facts, not summaries. Don't editorialize.
