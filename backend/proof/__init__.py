"""
The proof compiler. PHASE_2_PLAN_v2.md §5 Stage 4.

Properties about a realised design, proved from its own SPICE netlist:
`netlist` parses it, `mna` does symbolic nodal analysis, `brackets` encloses
the transcendentals, `properties` states and back-translates what is proved,
and `prover` decides it with z3 inside a refine loop that cannot change a
frozen property. Decisions: `brain/decisions.md` [2026-09-23] Stage 4.
"""
