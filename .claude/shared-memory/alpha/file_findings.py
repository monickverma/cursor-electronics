"""
file_findings.py — turn the A1 overlooker runs into product findings.

WHAT THIS IS
------------
The overlookers report what they see. Some of what they see is the seeded
defect — that is the calibration result, and it is scored by
`score_overlooker.py`, not filed here. The rest is a real defect in the
product, seen by an engineer reading a board the product built.

This script files those into `alpha/findings.jsonl`, deduplicated across the
boards. Three of the three boards report the same four things — the ground
zone is never filled, there is no silkscreen, the requested parts are dropped,
the board has no power entry — so those are one finding each, not three.
The board names in the evidence are what make the recurrence visible.

    python .claude/shared-memory/alpha/file_findings.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FINDINGS = REPO / ".claude" / "shared-memory" / "alpha" / "findings.jsonl"

NEW: list[dict] = [
    dict(id="F-0010", stage="A1", parameter=5, severity="critical",
         artifact="artifacts/board_01, artifacts/board_03, artifacts/board_04",
         observed="The ground zone is never filled. Every board the product emits declares a B.Cu zone for net GND but carries ZERO filled_polygon data, so the plane a designer expects to be there is not there: on board_01 GND is five separate copper islands and the exported B_Cu gerber is 3,824 bytes against 79,834 bytes with --check-zones. board_03 F-0003 and board_04 F-0404 report the same thing on their own boards. The board is emitted for fabrication with the ground plane absent.",
         expected="A board handed to a fab carries a filled ground plane, or the export step refills the zones and the refill is what ships.",
         evidence="runs/board_01.jsonl F-0002 (rung exact, own gerber plot); runs/board_03.jsonl F-0003; runs/board_04.jsonl F-0404. Recurs on 3 of 3 boards.",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03/04"),
    dict(id="F-0011", stage="A1", parameter=5, severity="critical",
         artifact="artifacts/board_04",
         observed="The design rules that ship in the .kicad_pro have every manufacturing constraint zeroed: min_clearance 0.0, min_track_width 0.0, min_via_diameter 0.0, min_through_hole_diameter 0.0, min_via_annular_width 0.0, min_copper_edge_clearance 0.0. A DRC run on the shipped project enforces nothing; the numbers that come back are the product's own geometry, not a fab profile's opinion of it.",
         expected="The project file carries a named fab profile's rules - at minimum IPC-2221 class 2 - so that KiCad's DRC says something about manufacturability.",
         evidence="runs/board_04.jsonl F-0405 (rung exact; drc_fab_profile.json and drc_shipped_rules.json in runs/evidence_board_04/)",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 04"),
    dict(id="F-0012", stage="A1", parameter=3, severity="critical",
         artifact="artifacts/board_04",
         observed="U1's footprint (CircuitOS:DIP-28) is Y-MIRRORED relative to KiCad's reference footprint Package_DIP:DIP-28_W7.62mm. Aligning the two pad sets on their centroids and testing all eight planar transforms, the unique exact match is a flip.",
         expected="A DIP-28 footprint must be drawn so that pad 1 is the hole at the notch or pin-1 end and the pad numbering increases counter-clockwise, as KiCad's reference footprint does.",
         evidence="runs/board_04.jsonl F-0402 (rung exact; footprint_orientation_vs_kicad_ref.txt in runs/evidence_board_04/)",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 04"),
    dict(id="F-0013", stage="A1", parameter=5, severity="critical",
         artifact="artifacts/board_04",
         observed="Vias are placed where their drill physically merges with another hole. Two GND vias sit essentially on top of two U1 through-holes (via at 16.6, 21.52 with a 0.4 mm drill against U1 pad 8's 0.8 mm hole at 16.51, 21.59), and two more sit so their drill breaks out of a surface-mount pad they are meant to connect (via at 13.6, 21.52 against Q1 pad 2, a 0.9 x 1.0 mm pad). The drill files merge the holes and the pad's plated barrel is destroyed.",
         expected="A plated via must not be placed within (hole radius + pad hole radius) of a component's plated through-hole, and its drill must stay inside the pad it connects.",
         evidence="runs/board_04.jsonl F-0403 and F-0407 (both rung exact)",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 04"),
    dict(id="F-0014", stage="A1", parameter=5, severity="major",
         artifact="artifacts/board_01, artifacts/board_03, artifacts/board_04",
         observed="The product emits no silkscreen at all. On every board F.SilkS appears only in the layer table; every footprint places its Reference and Value text on F.Fab, and the exported F.Silkscreen and B.Silkscreen gerbers contain zero draw operations. There is no reference designator, no pin-1 mark on U1 or Q1, no cathode band on the diode, and no flat side on the TO-92.",
         expected="Silkscreen carries the refdes, the pin-1 mark and the polarity marks. A board without them is assembled by guesswork, and a reversed 2N2222A swaps E and C and kills the relay drive.",
         evidence="runs/board_01.jsonl F-0008, runs/board_03.jsonl F-0009, runs/board_04.jsonl F-0406. Recurs on 3 of 3 boards.",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03/04"),
    dict(id="F-0015", stage="A1", parameter=1, severity="major",
         artifact="artifacts/board_01, artifacts/board_03, artifacts/board_04",
         observed="The product silently drops parts the request asked for. The request says the board lights an LED on the same board: board_01 and board_03 have eight components and no LED, no LED net and no LED current-limiting resistor. The request says it drives a 30 mA inductive load: board_04 has a two-pin header where the load should be and no load. Nothing refuses, nothing warns, and the design that comes back does not do what was asked.",
         expected="Either the design includes the requested part, or the product refuses with a named reason. A design that silently differs from the request is the worst outcome in the rubric.",
         evidence="runs/board_01.jsonl F-0003, runs/board_03.jsonl F-0004, runs/board_04.jsonl F-0409. Recurs on 3 of 3 boards.",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03/04"),
    dict(id="F-0016", stage="A1", parameter=1, severity="major",
         artifact="artifacts/board_01, artifacts/board_03, artifacts/board_04",
         observed="The boards have no power entry and no way to attach anything. VCC_5V consists only of device pads (C1.1, D1.1, K1.1, R1.1, U1.7, U1.20, U2.1): no connector, no regulator, no jumper, no test point. On board_01 and board_03 the relay's three contact pads carry no net at all, so the relay switches nothing. On board_04 the only connector is a two-pin header on VCC_5V and SW_LOAD.",
         expected="A board that is to be powered and loaded has a power entry and an output terminal, both on connectors at the edge.",
         evidence="runs/board_01.jsonl F-0005 and F-0007, runs/board_03.jsonl F-0005 and F-0006, runs/board_04.jsonl F-0409. Recurs on 3 of 3 boards.",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03/04"),
    dict(id="F-0017", stage="A1", parameter=1, severity="major",
         artifact="artifacts/board_01, artifacts/board_03",
         observed="The MCU cannot be programmed and has no 16 MHz timebase. U1's RESET (pad 1), PD0/RXD (pad 2), PD1/TXD (pad 3), XTAL1 (pad 9) and XTAL2 (pad 10) are all on no net, and the parts list holds no crystal, no load capacitors, no ISP header and no reset switch. With the default CKDIV8 fuse the ATmega328P runs the internal 8 MHz RC divided to 1 MHz, and there is no ISP path to change that.",
         expected="A board carrying an ATmega328P carries the crystal, the reset network and the ISP header, or the product says the design is a programming fixture.",
         evidence="runs/board_01.jsonl F-0006, runs/board_03.jsonl F-0007 and F-0008. Recurs on 2 of 3 boards.",
         rung="evidence", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03"),
    dict(id="F-0018", stage="A1", parameter=3, severity="major",
         artifact="artifacts/board_03",
         observed="U1 (ATMEGA328P-PU) pad 21 is AVCC and carries NO net, while pad 20 (AREF) is tied to VCC_5V and pad 22 (AGND) to GND. The ATmega328P datasheet requires AVCC to be connected to VCC and requires AREF not to be driven above AVCC; AREF tied to VCC with AVCC floating is the wrong order round.",
         expected="AVCC tied to VCC_5V with its own decoupling capacitor at the pin, and AREF either tied to GND through a 100 nF or left unconnected.",
         evidence="runs/board_03.jsonl F-0002 (rung evidence; Microchip ATmega328P pin table)",
         rung="evidence", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 03"),
    dict(id="F-0019", stage="A1", parameter=3, severity="major",
         artifact="artifacts/board_04",
         observed="The footprint the product uses for the transistor, CircuitOS:SOT-23, is not KiCad's reference Package_TO_SOT_SMD:SOT-23. Aligning on centroids and testing all planar transforms, the closest match is a non-standard pin arrangement. The same family of doubt is already open as F-0005: every land pattern in land_patterns.json carries verified: false.",
         expected="A footprint used for a named package must match that package's published land pattern, and the record must say it has been checked.",
         evidence="runs/board_04.jsonl F-0408 (rung evidence)",
         rung="evidence", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 04"),
    dict(id="F-0020", stage="A1", parameter=7, severity="major",
         artifact="artifacts/board_01",
         observed="The board does not obey its own net classes. The Board IR declares a 'power' class (VCC_5V, GND, RELAY_COIL_NEG) with track_width 0.8 and a 'default' class (DHT22_DATA, RELAY_CTRL, TRANSISTOR_BASE) with 0.3, but the emitted copper uses 0.2 mm on the default-class nets and on the relay coil path, which the class says is a power net.",
         expected="The router's emitted width must be at least the width its own net class declares, or the class must be changed to match what the router can do.",
         evidence="runs/board_01.jsonl F-0011 (rung rule check - the class widths are the threshold someone chose)",
         rung="rule check", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 01"),
    dict(id="F-0021", stage="A1", parameter=13, severity="minor",
         artifact="artifacts/board_03",
         observed="The product's own drc_summary.json reports available=true, violations=15, unconnected_items=5, severity_error_violations=0, and carries no pass/fail verdict anywhere. Every one of the 5 unconnected items and both dangling tracks is filed as a warning, so the summary reads like a pass over a board with an open net in it.",
         expected="The DRC summary carries a verdict, and an unconnected item is an error - an open net is not a warning.",
         evidence="runs/board_03.jsonl F-0012 (rung evidence)",
         rung="evidence", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, board 03"),
    dict(id="F-0022", stage="A1", parameter=6, severity="minor",
         artifact="artifacts/board_01, artifacts/board_03",
         observed="There is no decoupling at the MCU. C1 (100 nF) is the board's only capacitor: on board_01 it sits 6.84 mm from the DHT22's VCC pad but 14.54 mm from U1's supply pads; on board_03 its nearest pad is 12.10 mm from U1's VCC pin 7. There is no capacitor on AVCC and none at the DHT22.",
         expected="A decoupling capacitor within a couple of millimetres of the pins it decouples.",
         evidence="runs/board_01.jsonl F-0010, runs/board_03.jsonl F-0010. Recurs on 2 of 3 boards.",
         rung="exact", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03"),
    dict(id="F-0023", stage="A1", parameter=6, severity="major",
         artifact="artifacts/board_01, artifacts/board_03",
         observed="The DHT22's pull-up is on the wrong end of the cable. The request is a DHT22 on a 2 metre cable; the board carries the bare 4-pad sensor soldered onto the PCB with no connector, and the only pull-up on the data line, R1 = 10 kohm, sits on the controller board - 28.4 mm from the sensor pad - not at the sensor end of the run. The 10 kohm value is inside the DHT22's 1 k to 10 k guidance; it is the position that is wrong.",
         expected="The pull-up on a long sensor bus belongs at the sensor end, and the sensor end needs a connector if the sensor is on a cable.",
         evidence="runs/board_01.jsonl F-0011 (sensor on the board), runs/board_03.jsonl F-0011 (rung evidence; Aosong AM2302)",
         rung="evidence", status="open", fixed_by=None, verified_by=None,
         prompt="A1 overlooker run, boards 01/03"),
]


def main() -> int:
    rows = [json.loads(l) for l in FINDINGS.read_text(encoding="utf-8").splitlines() if l.strip()]
    existing = {r["id"] for r in rows}
    added = []
    for row in NEW:
        if row["id"] in existing:
            continue
        row.setdefault("prompt", "")
        rows.append(row)
        added.append(row["id"])
    FINDINGS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print("added:", added)
    print("total findings:", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
