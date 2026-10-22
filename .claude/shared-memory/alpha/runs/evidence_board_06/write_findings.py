import json, sys

PROMPT = ("An Arduino Uno reads a DHT22 sensor on a 2 metre cable with a 100 nF decoupling "
          "capacitor, drives a relay through a 2N2222A, and lights an LED on the same board. "
          "Lay the board out and check it before you would send it to a fab.")
ART = "artifacts/board_06"
EV  = "runs/evidence_board_06/"

F = []
def add(id_, param, sev, obs, exp, ev, rung):
    F.append({"id": id_, "stage": "A1", "prompt": PROMPT, "artifact": ART,
              "parameter": param, "severity": sev, "observed": obs, "expected": exp,
              "evidence": ev, "rung": rung, "status": "open",
              "fixed_by": None, "verified_by": None})

add("F-06-001", 3, "critical",
 "The U1 DIP-28 footprint in board_06.kicad_pcb is the y-MIRROR of a standard DIP-28. Pad 1 sits at local (-3.81, +16.51) where KiCad 10's stock Package_DIP:DIP-28_W7.62mm puts pad 14, and pad 15 sits at (+3.81, +16.51) where stock puts pad 28; board pad N occupies the hole of stock pin 15-N (N<=14) and 43-N (N>=15). No 180-degree rotation reproduces it (a rotation would put pad 1 at x=+3.81, not -3.81), so a DIP-28 cannot be fitted to it. Mapping the ATmega328P-PU leads onto the board holes for both legal insertion orientations: at 0 deg (pin 1 top-left) the chip's VCC (pin 7) falls into board pad 8, net GND, and the chip's GND (pin 8) falls into board pad 7, net VCC_5V; at 180 deg (pin 1 bottom-right) the chip's VCC (pin 7) falls into board pad 22, net GND. In every orientation the 5 V rail is applied to the chip's ground pin. The signal pins move too: board pad 4 (DHT22_DATA) would land on PD5 (pin 11) or PC3/ADC3 (pin 26), and board pad 5 (TRANSISTOR_BASE) on PB7/XTAL2 (pin 10) or PB5/SCK (pin 19).",
 "A DIP-28 footprint must place pin 1 at the top-left with pins 1-14 descending the left row and 15-28 ascending the right row, so the chip's pin 7 (VCC) lands in the board's VCC_5V pad and pin 8 (GND) in the GND pad, whatever orientation it is dropped in.",
 EV + "analysis.txt sections C and D (computed from board_06.kicad_pcb against KiCad 10 stock Package_DIP:DIP-28_W7.62mm); cross-checked with " + EV + "drc_cli.json",
 "exact")

add("F-06-002", 4, "critical",
 "The GND net has no copper. It has 0 tracks and 5 vias, and its only return is a B.Cu zone that was never filled: board_06.kicad_pcb contains 1 (zone) block and 0 filled_polygon blocks. The exported B.Cu gerber holds 55 pad flashes and 7 track draws but 0 G36 regions - the ground pour is simply absent from the fab output. KiCad's own DRC on the shipped file reports 4 unconnected items at severity 'error' and flags all 5 GND vias as 'via_dangling': U1 pad 8 (GND) to via (10.2, 21.72); via (12.6, 35.52) to via (10.2, 21.72); U1 pad 22 (GND) to via (16.6, 21.52); Q1 pad 1 (GND) to via (24.2, 24.12). The five GND pads (C1.2, Q1.1, U1.8, U1.22, U2.4) are five separate copper islands, and the relay's emitter return and the DHT22's return are not the same node as the MCU's.",
 "The ground net must be continuous copper before the board goes to a fab - a filled plane with thermal relief on the GND pads, or routed tracks - so that the DRC unconnected count is zero.",
 EV + "analysis.txt section E; " + EV + "drc_cli.json (my own kicad-cli 10.0.1 run: 4 unconnected items, all severity error); " + EV + "gerbers/board_06-B_Cu.gbl (0 G36 regions)",
 "exact")

add("F-06-003", 4, "critical",
 "The relay's contacts are not in the circuit. K1 pads 3, 4 and 5 carry no net, have no track and no via, and the board contains no connector, header or terminal of any kind - the seven footprint libraries used are RADIAL-2, DO-41, RELAY-SRD, TO-92, AXIAL, DIP-28 and DHT22. Nothing outside the board can reach the relay's contacts, so the relay switches nothing and the board has no output.",
 "The relay's switched contacts must be brought out to a connector, with the contact rating and the no-contact/NC assignment stated.",
 EV + "analysis.txt sections E and G",
 "exact")

add("F-06-004", 3, "major",
 "D1 (1N4007, DO-41) is the flyback diode across the relay coil: D1 pad 1 is on VCC_5V, pad 2 on RELAY_COIL_NEG, while the coil is K1.1 (VCC_5V) to K1.2 (RELAY_COIL_NEG) and the switch node is Q1's collector. The required orientation is cathode at the +5 V rail, anode at the collector. The 1N4007 datasheet (Diodes Inc DS28002, Vishay 88503) states polarity by the cathode band and assigns no pin numbers, and the board ships no band mark - the exported silkscreen has 0 operations (every Reference/Value field is on F.Fab), the DO-41 footprint has no F.SilkS graphics, and no pad anywhere in the board carries a 'pinfunction' attribute. The artifact therefore gives me no way to tell whether board pad 1 is the cathode: under a 'pad 1 = cathode' convention the flyback diode is correct, under 'pad 1 = anode' it is reversed, in which case the diode conducts from the rail into the coil node, the relay is permanently energised and the 2N2222A is bypassed, and when the transistor turns on the diode shorts the rail through Q1.",
 "The cathode band must be marked on the silkscreen and the flyback diode's cathode must be unambiguously on the +5 V rail, so that the part cannot be fitted backwards.",
 EV + "analysis.txt section F; " + EV + "gerbers/board_06-F_Silkscreen.gto (0 D-code operations); board_06.kicad_pcb (0 F.SilkS graphics, 0 pinfunction attributes); Diodes Inc 1N4001-1N4007 DS28002 and Vishay 88503 for the band-is-cathode rule",
 "unknown")

add("F-06-005", 1, "major",
 "The request asks the board to light an LED. The board carries eight parts - U1 ATMEGA328P-PU, U2 DHT22, K1 SRD-05VDC-SL-C, Q1 2N2222A, D1 1N4007, R1 10k, R2 1k, C1 10nF - and no LED and no LED series resistor. board_ir.json lists the same eight components. The design silently omits a requested block; nothing in the artifact says the LED was dropped or refused.",
 "An LED and its current-limiting resistor on a named MCU pin, or a clear refusal naming that the LED could not be laid out.",
 EV + "analysis.txt section G; board_ir.json components list (8 entries, no LED)",
 "exact")

add("F-06-006", 1, "major",
 "The request asked for a 100 nF decoupling capacitor. The only capacitor on the board is C1, whose Value field reads '10nF' and whose MPN is K103K15X7RF53H5 - Vishay BCcomponents K-series, where 103 = 10,000 pF = 10 nF, X7R, 50 V, radial 5 mm lead spacing. The Aosong DHT22/AM2302 datasheet calls for a 100 nF decoupling capacitor between VDD and GND at the sensor. The fitted part is a factor of ten below the value the request named and the datasheet asks for, and the MPN and the board's own Value field agree with each other, so this is a design decision, not a labelling slip.",
 "A 100 nF capacitor at the DHT22's VDD pin, as the request specified.",
 EV + "analysis.txt section G; board_06.kicad_pcb C1 property 'Value' '10nF' and property 'MPN' 'K103K15X7RF53H5'; Vishay 88503 / Digi-Key K103K15X7RF53H5",
 "evidence")

add("F-06-007", 1, "major",
 "The board carries a bare ATMEGA328P-PU and nothing supports it. There is no crystal or oscillator, no RESET pull-up (U1 pad 1, PC6/RESET, has no net and no copper), no local decoupling at U1's VCC, and no supply of its own: every member of the VCC_5V net is a load (U1.7, U1.20, U2.1, K1.1, D1.1, R1.1, C1.1) and there is no regulator, no barrel jack, no header and no USB anywhere on the board, nor an Arduino Uno module footprint. As drawn the board cannot be powered and the MCU has no clock.",
 "An Arduino Uno, or an ATmega328P with its crystal, reset pull-up, local decoupling and a supply/connector, able to run the requested firmware.",
 EV + "analysis.txt sections E and G; board_06.kicad_pcb (U1 pad 1 has no net; no footprint other than the eight listed)",
 "exact")

add("F-06-008", 1, "major",
 "The request describes a DHT22 on a 2 metre cable. The board instead fits the DHT22 module itself on-board (U2 at 10.12, 25.44) and provides no connector or landing pads for an off-board sensor, so the 2 m cable is not represented in copper at all - the long-line rise-time problem that R1 (10k pull-up) exists to solve is not in the layout, and the sensor is placed where the cable should be.",
 "A 2-way (or 4-way) connector for the remote DHT22 with the pull-up at the board end and the rise-time budget for 2 m of cable stated.",
 EV + "analysis.txt section G; board_06.kicad_pcb (no connector footprint; U2 fitted on-board)",
 "exact")

add("F-06-009", 13, "major",
 "The product's own verification report contradicts its own detailed DRC. drc_summary.json says 'violations': 13, 'unconnected_items': 4 and 'severity_error_violations': 0, while drc.json lists four unconnected items each carrying 'severity': 'error'. A board that KiCad rates as having four error-severity opens is summarised as having zero error violations - the error-severity unconnected items are counted as warnings and the summary reads clean. The board therefore ships with a check report that understates it.",
 "The summary must count error-severity unconnected items as errors. A board with four error-severity opens must not be reported as error-free.",
 "drc_summary.json vs drc.json (both in artifacts/board_06/); " + EV + "drc_cli.json (my own kicad-cli 10.0.1 run reproduces 4 unconnected items, all severity error)",
 "exact")

add("F-06-010", 5, "major",
 "The fab's silkscreen is empty. No footprint in board_06.kicad_pcb carries a single F.SilkS graphic - 0 fp_line, 0 fp_text, 0 fp_circle, 0 gr_text - and the 8 fp_poly body outlines are on F.CrtYd (the courtyard layer, which is not printed on the board), while all 25 Reference/Value/MPN properties are on F.Fab, a documentation layer the assembler never sees. The exported board_06-F_Silkscreen.gto is therefore a header with an empty aperture list and no drawing operation of any kind. The board goes to the fab with a blank top legend: no reference designators, no pin-1 marker for the DIP-28, no cathode band for D1, no flat-face marker for the TO-92, no polarity mark for C1, no part outlines. The board also carries 0 'pinfunction' attributes on any pad anywhere, so pad 1 is nowhere defined as emitter, cathode or pin 1 in the data either. Every part on this board has an orientation that only the copper can express.",
 "Reference designators, part outlines, a DIP pin-1 notch, a diode cathode band and a transistor flat-face marker on the silkscreen.",
 EV + "analysis.txt section F; " + EV + "gerbers/board_06-F_Silkscreen.gto (469 bytes: header, empty aperture list, M02, no D-code operations); board_06.kicad_pcb (0 F.SilkS graphics, 0 pinfunction attributes)",
 "exact")

add("F-06-011", 1, "major",
 "The board the product emitted does not match its own source of truth. Every component position in board_06.kicad_pcb equals its board_ir.json position with y -> 45.72 - y: C1 (10.12,10.12) -> (10.12,35.60); D1 (32.98,17.74) -> (32.98,27.98); K1 (36.79,31.71) -> (36.79,14.01); Q1 (30.44,21.55) -> (30.44,24.17); R1 (32.98,13.93) -> (32.98,31.79); R2 (32.98,10.12) -> (32.98,35.60); U2 (10.12,20.28) -> (10.12,25.44); U1 unchanged at the board centre. It is a mirror of the whole board, and the pad layouts are mirrored with it, so U2's pin 1 (VDD) and pin 4 (GND) swap ends, K1's coil pins 1 and 2 swap ends, and U1's DIP-28 is mirrored (F-06-001). board_ir.json is presented as the board's source of truth; it does not describe this board, so anything read from it (placement, panel, assembly drawing, 3D scene, BOM-to-position) is wrong.",
 "The Board IR and the emitted .kicad_pcb must be the same board, so a placement or assembly read from the IR matches the copper.",
 EV + "analysis.txt sections A and B",
 "exact")

add("F-06-012", 6, "minor",
 "C1 is the only capacitor and it is not next to what it decouples: 10.16 mm from the DHT22's VDD pad (U2.1 at 10.12, 29.25; C1.1 at 7.58, 35.60) and about 20 mm from the ATmega328P, which has no decoupling capacitor at all. The DHT22 datasheet puts the decoupling capacitor at the sensor's supply pins, and the MCU needs one on its own VCC/AVCC.",
 "A 100 nF at the DHT22 VDD pin and a 100 nF at the MCU's VCC/AVCC, each within a few millimetres of the pin it decouples.",
 EV + "analysis.txt sections A and E",
 "exact")

add("F-06-013", 13, "minor",
 "The DRC run the product shipped had five checks switched off in its ignored_checks list: missing_courtyard, track_not_centered_on_via, tuning_profile_track_geometries, footprint_filters_mismatch and footprint_type_mismatch - the last being 'Footprint component type doesn't match footprint pads'. Those are the checks that would catch a part/footprint disagreement, which is the class of error this board actually contains. The board's footprints do define courtyards, so the suppression buys nothing here and only hides failures.",
 "The shipped DRC should run the default checks, or the product should state which checks it disabled and why.",
 "drc.json 'ignored_checks' in artifacts/board_06/; " + EV + "drc_cli.json",
 "evidence")

add("F-06-014", 2, "minor",
 "The artifact contains a board, a project, a Board IR and a DRC report - and no schematic, no BOM, no firmware, no SPICE netlist, no simulation result and no explanation. I could not run kicad-cli sch erc (parameter 2), could not compare BOM values against the schematic (parameter 11), could not check the firmware's pins against the copper (parameter 10), could not check the product's SPICE result against a hand calculation (parameter 9), and could not read the explanation (parameter 12). The only verification the board ships with is the DRC report, which is itself wrong about the error count (F-06-009).",
 "A board released for a fab should ship with the schematic it was checked against, so the checks are reproducible by the engineer receiving it.",
 "listing of artifacts/board_06/ (5 files: board_06.kicad_pcb, board_06.kicad_pro, board_06.kicad_prl, board_ir.json, drc.json, drc_summary.json)",
 "unknown")

add("F-06-015", 3, "minor",
 "The TO-92 footprint for Q1 carries no orientation cue: no F.SilkS graphic marking the flat face and no 'pinfunction' attribute on any pad (0 such attributes board-wide), so the only thing that tells the assembler which end is pin 1 is the pad numbering. The 2N2222A in TO-92 is E-B-C read from the front with the flat face toward you and the leads pointing down (ON Semiconductor PN2222A; Micro Commercial Components PN2222A; Diotec 2N2222A), so a transistor fitted with the flat face the other way puts its emitter and collector in each other's holes (E-B-C becomes C-B-E) and the low-side switch becomes a reverse-active device. The board's own net assignment is right for E-B-C - Q1 pad 1 (emitter) is GND, pad 2 (base) is RELAY_CTRL, pad 3 (collector) is RELAY_COIL_NEG - so the copper says one thing and the physical part can be fitted the other way round with nothing on the legend to stop it. Q1's pads are at -2.54, 0 and +2.54 mm, the standard TO-92 pitch, so the error is easy to make.",
 "A flat-face marker on the transistor footprint, or a pad function attribute, so the emitter and collector cannot be transposed.",
 EV + "analysis.txt section B (Q1 pad positions, mirrored/identical check); ON Semiconductor PN2222A datasheet for the EBC pinout; board_06.kicad_pcb Q1 footprint (pads at -2.54/0/+2.54 on 0 net for pad 1, 0 F.SilkS graphics, 0 pinfunction attributes)",
 "evidence")

out = sys.argv[1]
with open(out, "w", encoding="utf-8") as f:
    for r in F:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote", len(F), "findings to", out)
