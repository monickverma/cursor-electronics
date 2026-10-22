Evidence for the A1 review of artifacts/board_05 (finding file: ..\board_05.jsonl).

All of this is black-box: it comes from the board folder the product emitted
(board_05.kicad_pcb, board_05.kicad_pro, board_ir.json, drc.json, drc_summary.json),
from KiCad 10.0.1 (kicad-cli) opened on those files, and from KiCad's own stock
symbol and footprint libraries used as the datasheet-equivalent reference.

my_drc.json
    My own independent DRC on the delivered board:
    kicad-cli pcb drc --format json --severity-all --units mm
    Result: 13 violations (5 via_dangling, 8 lib_footprint_issues) and
    4 unconnected_items, all of them on GND, all severity "error".
    This reproduces the product's drc.json exactly and shows that
    drc_summary.json's "severity_error_violations": 0 is a summary error.

parse_board.py
    A small s-expression parser for the .kicad_pcb. Prints every footprint's
    ref/value/library/position and every pad's absolute position, size, drill
    and net. Written because KiCad cannot resolve the board's own "CircuitOS"
    footprint library, so the geometry had to be read out of the file text.

pad_net_table.txt
    The output of parse_board.py. This is the authoritative pad/net table
    used by findings F-05-001, 002, 005, 006, 007, 010, 013, 014, 015.

q1_operating_point.py / q1_operating_point.out
    The junction bias of Q1 as the board is actually wired, and the coil
    current the relay needs.
    Model: Ebers-Moll (injection) form with the Early effect - the form that
    is valid for reverse-active operation, which is the regime the as-built
    board is in. IS = 1e-14 A, BF = 250, BR = 6, VAF = 100 V, VAR = 25 V.
    As built (pad1 = emitter on the coil, pad3 = collector on GND):
        V(base) = 0.7318 V, V_BE = -4.2682 V (reverse), V_BC = +0.7318 V
        I(base) = 4.2682 mA (all of it through the forward B-C junction)
        I(emitter) = I(coil) = 0.0000 mA, against 71.4 mA needed to pull in
        V_EBO stress = 4.27 V against a 5 V rating
    Correctly wired (pad3 = collector on the coil): I(coil) = 71.4 mA.
    Model-independent bound: base current is capped at 5 mA by R2 and the
    gain in the reversed configuration is BR, not BF, so the coil can see at
    most BR x I_B = 25.6 mA < 71.4 mA.

q1_as_built.cir, q1_correct_wiring.cir
    ngspice netlists of the board's own Q1 circuit, written for cross-check.
    NOTE: ngspice does not run in this environment (it hangs), so these were
    never executed. The numbers quoted in the findings come from
    q1_operating_point.py, not from these. Treat the .cir files as intent.

gerbers/
    kicad-cli pcb export gerbers output for the delivered board.
    board_05-B_Cu.gbl   - no filled plane; copper spans x 10.12-44.29,
                          y 4.80-39.37 of a 63.5 x 45.72 board
    board_05-F_Cu.gtl
    board_05-F_Silkscreen.gto - 0 draws, 0 flashes: there is no silkscreen
    board_05-F_Mask.gts
    board_05-Edge_Cuts.gm1    - one closed rectangle, 63.5 x 45.72
