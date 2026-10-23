# JITX — competitor teardown

Written 2026-10-21 by S8 (competitors). Black-box only: jitx.com, docs.jitx.com, PyPI. This builds on `reports/Physics layout validation - what the market does and what Circuit OS can build.md` (the "physics report"). Labels: **checked**, **read**, **summary**, **inference**.

Numeric targets are in `C:\Users\KIIT\cursor-electronics-alpha\corpus\targets.json` (column `jitx`).

## What it computes

JITX is board design as code. The designer, or "your approved AI", edits the design code; JITX generates schematic, pin assignments, fencing and routing ([jitx.com](https://jitx.com), read). Current package: Python, `jitx` 4.4.3 on [PyPI](https://pypi.org/project/jitx/), Python ≥ 3.12 (read). Older docs use Stanza syntax.

The physics report checked one capability: JITX sets up and dispatches Ansys HFSS runs from requirements and feeds the results into the next code edit. Its homepage example is a PCIe gen-7 BGA launch at 56 GHz to -30 dB return loss in five HFSS runs. That is a vendor example; the physics is HFSS's.

No named autorouter or automatic placement was found on read pages. A docs snippet mentions an `assign-pins` step before "automatic placement" (summary).

## Method

Deterministic code generation from a design program, plus an external field solver (HFSS, licensed separately) in the loop. A **check framework** lets the designer write boolean checks (`pcb-check`) and run them into a report; the tutorial example checks AEC-Q200 ratings on passives ([docs](https://docs.jitx.com/reference/statements/checkstmt/index.html), summary).

## Guarantee type

| Output | Rung |
|---|---|
| Generated design | Deterministic from code; correct as the code is |
| User checks | Rule check, written by the user |
| HFSS results | Physics simulation (full-wave), by Ansys |

No proof is claimed. The docs warn that "Altium DRC errors may occur after exporting" (summary).

## Inputs and outputs

- **In:** design code (Python).
- **Out:** `jitx design export --to` KiCad, Altium (.PcbDoc/.SchDoc, Altium 18-22.8), EDX, XML, ODB, STEP; BOM as xlsx or tsv (read, PyPI). Gerber is not listed; it comes from the CAD tool after export.

## Limits

- Layer counts and board class are not stated.
- The designer writes code: the input is not English.
- Exported boards may fail the target tool's DRC.
- HFSS needs its own Ansys licence (inference from the physics report).

## Price

Two plans ([pricing](https://jitx.com/pricing), read): **Free and Open**, for open-source designs under CERN OHL-Permissive v2, with KiCad and Altium integration; **Enterprise**, quote-only, for proprietary designs, PLM, Siemens Xpedition and air-gapped installs. No USD figures.

## Automation

A CLI covers build, find, export and BOM, "a good fit for … headless and CI environments" ([CLI docs](https://docs.jitx.com/en/latest/getting-started/cli/index.html), read). Builds need a running JITX launcher, or `--dry`. JITX is the only product in this set besides KiCad and Circuit OS with a documented headless path.

## Their level, as numbers

| Metric | JITX's level | Label |
|---|---|---|
| SI (RF launch) | -30 dB return loss, -40 dB mode conversion at 56 GHz, 5 HFSS runs (vendor example) | checked |
| Routing completion, DRC, vias, area, decoupling, power width, mains, time | No numbers published | read (absence) |

JITX sets a bar only far above tier A (56 GHz SI). On the plan's tier A metrics it publishes nothing. Its level there is the reference board.

## How Circuit OS matches or beats it

| Area | JITX | Circuit OS today | Action |
|---|---|---|---|
| Input | Design code | English → IntentIR JSON | Ahead on accessibility; JITX ahead on expressiveness |
| Determinism | Code → design, deterministic | IR → compilers, deterministic | Parity: same architecture idea. Circuit OS adds a requirement layer the LLM fills, then refuses outside the catalogue |
| Checks | User-written boolean checks | z3 proofs over tolerance boxes, claims with rungs, built in | Ahead: checks are derived, not hand-written |
| Field solver | HFSS in the loop | None | JITX ahead; out of scope for tier A (physics report build item 8 is the escalation lane) |
| Headless | CLI, CI-ready | HTTP API | Parity |
| Export | KiCad, Altium, ODB, STEP | None yet | S6 export stages for parity |
| Firmware | None found | Compiled firmware | Ahead |
| Price | Free for open hardware | — | Owner decision |

## Open questions

- Whether JITX places parts automatically and how complete its routing is on small boards.
- Whether its check library includes voltage or derating checks out of the box.
- Layer and size limits.
