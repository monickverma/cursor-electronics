# Vision — LAYER 1

> What this project is, why it exists, and what success looks like.
> Manual, rarely changes. Read by every session.

---

## What is this project?

An **AI Electronics Engineer** — a system that converts natural language descriptions
into complete engineering outputs: schematics, SPICE netlists, ngspice simulations,
verification results, BOM, and PCB layout. With special support for HVAC /
refrigeration system simulation.

## Why does it exist?

The gap between an engineer's intent ("design a buck converter") and a verified
simulation is currently filled with manual work: writing netlists by hand, running
tools separately, debugging convergence failures, cross-checking results. This
system removes that gap.

## End goal — concrete success scenario

User says:
> "Design a 5V buck converter for 2A load, 90% efficiency target."

System produces:
- SPICE netlist
- ngspice transient simulation (convergence confirmed)
- Efficiency and ripple analysis
- Component BOM with values
- PCB layout file (KiCad compatible)
- Short engineering summary explaining decisions

For HVAC:
> "Simulate a basic refrigeration loop with R-410A refrigerant, superheat 8°C."

System produces:
- Component-modeled circuit (compressor, condenser, evaporator, expansion valve)
- Thermal + electrical co-simulation
- Verification that superheat target is met
- Diagnosis if it isn't

## Hard success criteria

- [ ] Natural language → verified simulation in under 60 seconds
- [ ] Handles passive components, MOSFETs, op-amps, basic HVAC components
- [ ] Simulation convergence rate > 90% without manual intervention
- [ ] Outputs are directly usable (netlists run in ngspice without edits)
- [ ] HVAC components (compressor, condenser, evaporator) fully modeled

## Users

- Electronics engineers wanting simulation acceleration
- HVAC system designers (refrigerant circuit simulation)
- Engineering students learning circuit + thermal design

## What this is NOT

- Not a replacement for human judgment on safety-critical designs
- Not a general-purpose code generator
- Not a visual schematic editor (text/API first)
