# Component ablation: does Circuit OS notice when a part is missing or shorted?

*Sketch, 2026-10-21. Code: `backend/validation/ablation.py`. Tests: `tests/test_ablation.py` (7 pass).*

## The idea

Topology optimisation takes material away from a structure and re-simulates to see what carries
load. Here the same idea is applied to a circuit: each part is taken out, or shorted, and the
design is checked again by two judges.

| Judge | What it is | Question it answers |
|---|---|---|
| **ngspice** | the M1 adapter's measurement (`grid_adapters.py`) on the faulted design | Did the physics change by more than 15%? |
| **the claims** | `assess()` on the faulted design | Does any claim now say **fails**? |

The faults:

- **open**: the part and its connections are removed, as if left off the board or with a cracked joint.
- **short**: a two-terminal part becomes 1 mΩ, as with a solder bridge or a capacitor that fails short.

Possible outcomes per fault:

- **needed, and caught**: the physics changed and a claim now says fails.
- **needed, NOT caught**: the physics changed and nothing told the user. These are the gaps.
- **caught, physics unchanged**: a rule failed, but the measured quantity didn't move.
- **unused in the model**: neither judge reacted. The part is redundant *in what we model*,
  which is not the same as redundant on the board.

A claim that only weakens (`holds` becoming `holds_defeasible`) or goes quiet (becoming `not_assessed`)
does not count as caught.

## First run: 6 generators, 43 faults, 10 gaps (now 4)

**Update, same day:** `rule.no_rail_short` (`validation/rule_engine.py::find_rail_shorts`) closes the
six rail-short gaps (C1 short on the four MCU designs, D1 short and J1 short on the load switch). The
four rows still open are pinned in `tests/test_ablation.py::test_the_remaining_gaps_are_pinned`.

| Generator | Fault | ngspice | Why nothing fails |
|---|---|---|---|
| ~~four MCU designs~~ | ~~bypass **C1 short**~~ | the rail into 1 mΩ, about 5 kA | **closed** by `rule.no_rail_short` |
| rc_lowpass | C1 short | no cutoff left | `proof.rc.cutoff` goes to *not_assessed* instead of *fails* |
| led_indicator | **LED1 short** | LED current 10 → 16 mA | The LED proofs go quiet (no diode left to solve) |
| ~~load_switch~~ | ~~**D1 (flyback) short**~~ | about 4.7 kA through the switch | **closed** by `rule.no_rail_short` |
| load_switch | J1 (load) open (~~short~~ closed) | load current 56 mA → 0 | The load isn't on any claim's path |
| dht22_node | U1 (MCU) open | rail current 52 → 2 mA | Only rail current moved; no claim measures it |

Also unused in the model, as expected: bypass capacitors when open (nothing simulates supply
noise), the D1 flyback diode when open (no inductive transient is simulated), RS-485 R4 (a logic
pull-down; the DC test doesn't model the pin floating), and the DHT22 sensor body.

## What the gaps suggest (not built)

1. ~~**A rail-short rule.**~~ **Done.** A supply rail that reaches ground, or another rail, through
   resistors under 1 Ω or any ideal source other than its own supply fails. It's a graph check on the
   design's own netlist, and it closed 6 of the 10 gaps.
2. **A proof that can't compile should fail when its subject is missing.** Today it says
   *not_assessed*. If the part the proof is about is gone, that's a fail, not an unknown.
3. **Rail-current claims.** Several faults only show up as supply current. A "board draws ≤ X mA"
   claim would catch them.
4. **Opt-in to CI.** Pin the gap list (the test already pins two rows) so closing a gap turns a test
   red until someone updates it, instead of changing silently.

## Your point: board faults that short traces

Yes, and it's the same harness, one level down. Today `pcb_engine/verify.py` finds shorts
that **are already** on the board (copper touching). It doesn't ask "**if** these two traces
bridge, what happens?", and nothing checks whether a trace can carry its current.

| Extension | How | Needs field simulation? |
|---|---|---|
| **Neighbour-net shorts** | From the Board IR, list every pair of nets whose copper comes within, say, 2× clearance (the likely solder-bridge pairs). Merge each pair in the netlist, re-run ngspice, and report which bridges are destructive (rail to ground, 5 V into a 3.3 V pin) and which are harmless. Spend the clearance budget on the destructive pairs. | No: geometry plus ngspice |
| **Trace current vs width** | ngspice already gives branch currents. Compare each net's current with its trace width using the IPC-2152 charts (temperature rise for a given width, copper weight and current). | No: a table lookup |
| **Fault current vs trace** | Combine the two: in a shorted fault, does the trace act as a fuse before the regulator limits the current? | No for a first cut; a thermal solver later |
| **Real heat spreading / EM** | Thermal FEM or PyPEEC for hot spots, crosstalk and parasitics | Yes, the open PyPEEC item |

The first two give most of the value with tools we already trust. Field solvers come later, once
there's a board where they would change a decision.

## Not done

- Not hooked into CI, the API or the UI; it's a module and a test.
- One grid point per generator (the middle of each axis). It doesn't sweep, and has no boards beyond
  the defaults.
- Only shorts across a single part. Bridges between two arbitrary nets, the PCB case above, aren't built.
- `build_check.py` already lists opens and shorts for **diagnosing** a person's build. The two lists of
  faults could share code. They're separate for now because they answer different questions.
