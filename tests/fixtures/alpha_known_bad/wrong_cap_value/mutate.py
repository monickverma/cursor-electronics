"""
mutate.py — seed ONE physical defect: the decoupling capacitor carries the
wrong capacitance.

THE DEFECT
----------
C1 is the ATmega's bypass capacitor: 100 nF, X7R, on VCC_5V to GND, right at
the MCU's supply pin. The design states it as the KEMET ceramic disc
K104K15X7RF53H5 — "104" is the EIA code for 100 000 pF, i.e. 100 nF.

The seed changes the part to K103K15X7RF53H5 — "103" is the EIA code for
10 000 pF, i.e. 10 nF. Same package, same dielectric, same tolerance letter,
same everything a board cares about except the one number that matters:

    base     K104K15X7RF53H5   100 nF   25 V   X7R
    defect   K103K15X7RF53H5    10 nF   50 V   X7R

Both are RADIAL-2, 5.08 mm pitch, through-hole. The board that comes out is
copper-for-copper the same board: the same two pads, the same tracks, the
same vias, the same placement, the same 12 required connections all routed.
Only the part that is soldered into those two pads is different, and it is
wrong by a factor of ten.

WHAT THE DEFECT COSTS IN PHYSICS
--------------------------------
A bypass capacitor does two jobs, and the 100 nF figure is the number that
lets it do them.

It supplies the fast edges. Every time the ATmega's output pins switch, the
current they draw comes out of the local rail, and the rail is a loop of
copper with inductance in it. A few millimetres of trace has roughly 50-100 nH
of it. The di/dt on an output edge is steep — the ATmega's edge rate is a
few ns — and the voltage that inductance raises across the supply pins is
L·di/dt. The bypass capacitor is what absorbs that edge locally, so the
current never has to travel the whole rail.

It filters the rail. The rail's own noise, plus whatever the board's digital
edges couple into it, has to go somewhere. The capacitor's impedance on the
rail is 1/(2·pi·f·C), and at the tens of kHz to MHz of switching noise on a
5 V rail a 100 nF X7R presents a few ohms while a 10 nF presents ten times
that.

Ten times too little capacitance on the supply pin is a real failure and a
quiet one. The board does not refuse to start; it starts, and the ATmega
runs, and the DHT22 reads, and the relay clicks. But the MCU's supply rail
is now ringing and drooping on every digital edge, and the margin that the
100 nF was bought to provide is gone. The ATmega328P's own supply is 4.75 V
to 5.25 V, and rail transients that exceed that window are outside the part's
specified operating conditions, which is exactly the class of fault that
produces the "works on the bench, fails in the enclosure" report: a board
that is fine on an open bench and unreliable next to a relay, a long DHT22
cable, or a switching supply.

This is why the case is NOT critical. A wrong pinout (swapped_pins) or a
reversed diode kills the board every time. A wrong bypass value produces a
board that works most of the time and fails under conditions nobody writes
down. It is a real defect, and it is a much quieter one.

WHY NO CHECK SEES IT
--------------------
The fault is a VALUE, and the product has no check that reads one. That is
not a claim about this one board; it is what the code says, and the run at
the bottom of this file measures it.

The copper is untouched. The board's connectivity is untouched: III.1 (every
required connection is made), III.2 (no two nets share a piece of copper),
III.3 and III.4 (the pin-to-net map is the netlist's), II.1-II.3 (placement
and courtyards) and IV.1 (land patterns) all read the board's GEOMETRY and
the netlist's PINS, and every one of them is as satisfied as it was before.
The value is in neither.

IV.2, the check that compares a part's pinout against the KiCad symbol for
its part number, cannot reach it either. part_pinouts.lookup() finds no
symbol named for 'K103K15X7RF53H5' — or for 'K104K15X7RF53H5', the correct
part — so the check reports "no part could be compared" and stays at the
unknown rung. A symbol describes a part's TERMINALS; it says nothing about
how many farads a capacitor holds. Closing the symbol lookup would not
close this case.

And the value, in the one place the product does read it, is read as a
STRING. `data/parts.py::capacitor()` is the authority on a tabulated
passive's figures, and it is keyed on the Samsung CL-series part numbers
(CL05B104KO5NNNC for 100 nF, CL05B103KB5NNNC for 10 nF). The KEMET K-series
part numbers this board uses are in neither that table nor
component_db.json, so `capacitor('K103K15X7RF53H5')` returns None and
`capacitor('K104K15X7RF53H5')` returns None. The product cannot read the
value of its own capacitor off its own part number, because the part number
it chose is one nothing has a record of. That is the same data gap as
F-0005 (every land pattern carries verified: false), stated in a different
place: the drawing knows the part number and no figure.

`component_constraints.py` does carry a `decoupling_cap_nf: 100` for the
MAX485 and MAX3485 — and nothing reads it. Grep the repository: the key is
defined twice and consumed nowhere. The requirement that the bypass be
100 nF exists as a number in a dictionary that no code path reaches.

So the defect passes, and the product's own gate says emit. That is the
finding, and it is the same architectural gap as F-0008 (reversed_diode) and
F-S0-0001 (swapped_pins): compile_board calls verify_board(board, netlist)
with the SAME netlist it just compiled from, so the verifier can only ever
answer "is this board what I was told to build", never "is what we were told
to build right". Here the thing we were told to build is wrong in a way no
check reads.

WHERE THE FAULT IS VISIBLE — THE ARTIFACT THAT CARRIES IT
----------------------------------------------------------
This case is seeded in the NETLIST, and the fault IS carried on the board,
so the board-level twin is a real twin and not a no-op. The chain, measured
at the bottom of this file:

    netlist.json           the BASE netlist: C1 = K104K15X7RF53H5, 100nF
    netlist_defective.json the SEEDED netlist: C1 = K103K15X7RF53H5, 10nF
    board_base.json        C1.attrs = {"package": "RADIAL-2",
                                      "mpn":   "K104K15X7RF53H5",
                                      "value": "100nF"}
    board_defective.json   C1.attrs = {"package": "RADIAL-2",
                                      "mpn":   "K103K15X7RF53H5",
                                      "value": "10nF"}
    the 3D scene           the component's "mpn" field

A reader detects it in the BOARD, in the component's attrs: the base board
says C1 is a K104K15X7RF53H5 worth 100nF, the defective board says
K103K15X7RF53H5 worth 10nF. Nothing else on the board moves — the tracks,
the vias, the pads and the placement are byte-identical between the two
boards, and the 3D scene shows the same two pads and the same body.

Note what the board does NOT carry. The rendered SVG does not print the
value (nor the MPN), and the 3D scene carries the MPN but not the value
string. So an engineer looking at the picture sees nothing wrong; an
engineer reading the board IR sees it in one line. In the full product the
same number reaches the BOM, because PcbNetlistGenerator copies
comp.value onto the netlist component and the BOM compiler copies comp.value
onto the row — so a BOM read against the requirement is where the fault is
most legible to a person.

THE TWO ENTRY POINTS
--------------------
`seed_netlist(netlist)`  the primary form. Sets C1's part number and value
                         in the netlist. Pure data in, pure data out: no
                         imports from `backend/`, no randomness, no
                         wall-clock, no I/O outside its arguments.

`seed(board_json)`       the board-level twin. Because the fault IS carried
                         on the board, the twin can be a faithful IN-PLACE
                         edit rather than a recompile: it sets C1's attrs to
                         the defective part number and value and leaves every
                         other byte of the board alone. That is not a
                         shortcut — it is exactly the board the product
                         emits, because `from_netlist` copies the netlist's
                         part number and value onto the component's attrs and
                         changes nothing else. The run at the bottom of this
                         file checks that the twin equals
                         `seed_netlist` + `compile_board`, byte for byte.

Both are idempotent and deterministic: the same input always gives the same
output, byte for byte.

    python mutate.py          rebuild both boards and prove the difference
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# The defect, stated
# ─────────────────────────────────────────────────────────────────────────────
DEFECT_ID = "wrong_cap_value"

#: The one component this seed touches.
TARGET_REF = "C1"

#: The design intent, as the base netlist states it.
#:
#: K104K15X7RF53H5 is a KEMET ceramic disc, radial, 5.08 mm pitch. The EIA
#: three-digit code in the part number carries the value: "104" = 100 000 pF
#: = 100 nF, "103" = 10 000 pF = 10 nF. Both are X7R, both are K (the
#: tolerance letter, ±10%), and the trailing "5" is the 50 V-rated series
#: option the disc is bought in.
DESIGN_MPN = "K104K15X7RF53H5"
DESIGN_VALUE = "100nF"

#: The defect: the same part, a decade less of it. The value code changes
#: from 104 to 103; the package, the dielectric, the tolerance and the
#: voltage rating are unchanged, which is exactly why nothing downstream
#: notices.
DEFECT_MPN = "K103K15X7RF53H5"
DEFECT_VALUE = "10nF"

#: The value the requirement asks for, stated independently of both part
#: numbers so that a reader can check the seed against the requirement
#: rather than against the seed.
REQUIRED_NF = 100.0

Netlist = dict[str, Any]
BoardJson = dict[str, Any]

#: Where the artifacts this seed produces live.
#:
#: `netlist.json` is the BASE netlist — the design intent — exactly as it is
#: in the copper-defect cases, so every case in this set can be read the same
#: way. `netlist_defective.json` is the seeded defect, and it is there
#: because this is a NETLIST-level defect: the calibration harness judges
#: each board against the netlist it was compiled from, so a defect that
#: lives in the netlist has to ship both. (A copper defect ships one
#: netlist, because both its boards were compiled from the same one.)
FIXTURE_DIR = pathlib.Path(__file__).resolve().parent
BOARD_BASE = FIXTURE_DIR / "board_base.json"
BOARD_DEFECTIVE = FIXTURE_DIR / "board_defective.json"
NETLIST = FIXTURE_DIR / "netlist.json"
NETLIST_DEFECTIVE = FIXTURE_DIR / "netlist_defective.json"

#: The base netlist this seed is written against, relative to the repository
#: root. It is a file the repository already had; this seed does not change
#: it, and the shipped netlist_base.json is a copy of it.
BASE_NETLIST_REL = pathlib.Path("backend") / "pcb_engine" / "netlist_dht22.json"

#: The repository root: tests/fixtures/alpha_known_bad/wrong_cap_value -> up four.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


# ─────────────────────────────────────────────────────────────────────────────
# The netlist seed — the primary form
# ─────────────────────────────────────────────────────────────────────────────
def seed_netlist(netlist: Netlist) -> Netlist:
    """Return `netlist` with C1's part number and capacitance changed.

    Idempotent: seeding an already-seeded netlist returns it unchanged.
    Raises ValueError on a netlist that is neither the design nor the defect,
    so a mismatched base is a loud failure and not a silent corruption.
    """
    out = copy.deepcopy(netlist)
    comp = _target_component(out)
    mpn = str(comp.get("mpn", ""))
    value = comp.get("value")

    if mpn == DEFECT_MPN and value == DEFECT_VALUE:
        return out                       # already seeded; nothing to do

    if not (mpn == DESIGN_MPN and (value is None or value == DESIGN_VALUE)):
        raise ValueError(
            f"{TARGET_REF} is not the {DEFECT_ID} target: it is "
            f"{mpn!r} / {value!r}, which is neither the design intent "
            f"({DESIGN_MPN!r} / {DESIGN_VALUE!r}) nor the seeded defect "
            f"({DEFECT_MPN!r} / {DEFECT_VALUE!r}). Refusing to seed a different "
            f"design."
        )

    comp["mpn"] = DEFECT_MPN
    comp["value"] = DEFECT_VALUE
    return out


def _target_component(netlist: Netlist) -> dict:
    for c in netlist.get("components", []):
        if c.get("ref") == TARGET_REF:
            return c
    raise ValueError(f"no component with ref {TARGET_REF!r} in the netlist")


# ─────────────────────────────────────────────────────────────────────────────
# The board-level twin
# ─────────────────────────────────────────────────────────────────────────────
def seed(board_json: BoardJson) -> BoardJson:
    """Return the board whose C1 carries the wrong capacitance.

    The fault IS carried on the board, so the twin is a faithful in-place
    edit: C1's attrs become the defective part number and value, and every
    other byte of the board is left alone. That is not a shortcut — it is
    exactly the board the product emits, because `from_netlist` copies the
    netlist's part number and value onto the component's attrs and changes
    nothing else. `__main__` below checks that claim by compiling the
    defective netlist and comparing, byte for byte.
    """
    out = copy.deepcopy(board_json)
    if _board_is_seeded(out):
        return out                        # already seeded; nothing to do

    comp = _target_component_board(out)
    attrs = dict(comp.get("attrs") or {})
    if attrs.get("mpn") != DESIGN_MPN:
        raise ValueError(
            f"{TARGET_REF} on the board is {attrs.get('mpn')!r}, not the design "
            f"intent {DESIGN_MPN!r}. Refusing to seed a different design."
        )
    attrs["mpn"] = DEFECT_MPN
    attrs["value"] = DEFECT_VALUE
    comp["attrs"] = attrs
    return out


def _board_is_seeded(board_json: BoardJson) -> bool:
    """Does this board already carry the wrong capacitance?"""
    for c in board_json.get("components", []):
        if c.get("ref") != TARGET_REF:
            continue
        attrs = c.get("attrs") or {}
        if attrs.get("mpn") == DEFECT_MPN and attrs.get("value") == DEFECT_VALUE:
            return True
    return False


def _target_component_board(board_json: BoardJson) -> dict:
    for c in board_json.get("components", []):
        if c.get("ref") == TARGET_REF:
            return c
    raise ValueError(f"no component with ref {TARGET_REF!r} on the board")


def netlist_from_board(board_json: BoardJson) -> Netlist:
    """Recover the netlist a board was compiled from.

    The Board IR carries everything the compiler needed: each component's
    package, part number and value, and each pad's pin-to-net binding. The
    ground net is the plane layer's net; the power nets are the "power" net
    class.
    """
    components = []
    for c in board_json.get("components", []):
        pins = {str(p.get("pin")): p.get("net", "")
                for p in c.get("pads", []) if p.get("net")}
        if not pins:
            continue
        entry: dict[str, Any] = {"ref": c.get("ref"), "pins": pins}
        attrs = c.get("attrs") or {}
        for key in ("mpn", "package", "type", "value"):
            val = attrs.get(key)
            if val:
                entry[key] = val
        components.append(entry)

    ground = "GND"
    power: list[str] = []
    for layer in board_json.get("layers", []):
        if layer.get("plane_net"):
            ground = layer["plane_net"]
    for nc in board_json.get("net_classes", []):
        if nc.get("name") == "power":
            power = [n for n in nc.get("nets", []) if n]
    if not power:
        power = [ground]

    return {
        "name": board_json.get("name", "board"),
        "board": {"width": board_json.get("outline_w", 60.0),
                  "height": board_json.get("outline_h", 45.0),
                  "layers": len(board_json.get("layers", []))},
        "ground_net": ground,
        "power_nets": power,
        "components": components,
    }


def _compile(netlist: Netlist):
    """Compile a netlist to a routed board, importing the product's compiler."""
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from pcb_engine.compile_board import compile_board   # noqa: PLC0415
    return compile_board(netlist).board


# ─────────────────────────────────────────────────────────────────────────────
# The proof — run this file to rebuild both boards and show the difference
# ─────────────────────────────────────────────────────────────────────────────
def base_netlist() -> Netlist:
    """The base netlist, with C1's value stated.

    The product's own netlist for this board names C1's part number but not
    its value, because `netlist_dht22.json` is a hand-written fixture. The
    design intent is 100 nF — `generators/arduino_parts.py::decoupling()`
    emits value="100nF" with part_number="CL05B104KO5NNNC", and the KEMET
    part this board uses is the same 100 nF in a different package. The
    value is therefore added to the base netlist here, so that the base
    board and the defective board differ in a VALUE and in nothing else.
    """
    nl = json.loads((REPO_ROOT / BASE_NETLIST_REL).read_text(encoding="utf-8"))
    comp = _target_component(nl)
    comp["mpn"] = DESIGN_MPN
    comp["value"] = DESIGN_VALUE
    return nl


def _verifier():
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from pcb_engine.verify import verify_board        # noqa: PLC0415
    return verify_board


def _snapshot(report) -> dict[str, tuple[str, str]]:
    return {f.check: (f.status, f.rung) for f in report.findings}


def _c1_attrs(board_json: BoardJson) -> dict:
    for c in board_json.get("components", []):
        if c.get("ref") == TARGET_REF:
            return c.get("attrs") or {}
    return {}


def _c1_from_netlist(nl: Netlist) -> dict:
    for c in nl.get("components", []):
        if c.get("ref") == TARGET_REF:
            return c
    return {}


def main() -> int:
    verify_board = _verifier()

    nl = base_netlist()
    base_board = json.loads(_compile(nl).to_json())
    BOARD_BASE.write_text(json.dumps(base_board, indent=2) + "\n", encoding="utf-8")
    NETLIST.write_text(json.dumps(nl, indent=2) + "\n", encoding="utf-8")

    defective_nl = seed_netlist(nl)
    defective_board = json.loads(_compile(defective_nl).to_json())
    BOARD_DEFECTIVE.write_text(json.dumps(defective_board, indent=2) + "\n",
                                encoding="utf-8")
    NETLIST_DEFECTIVE.write_text(json.dumps(defective_nl, indent=2) + "\n",
                                  encoding="utf-8")

    # The product's own path: each board judged against the netlist it was
    # compiled from.
    base_rep = verify_board(_compile(nl), nl)
    defect_rep = verify_board(_compile(defective_nl), defective_nl)

    print("=== BASE board vs its own netlist (the product's path) ===")
    for f in base_rep.findings:
        print(f"  {f.check:<12} {f.status:<8} {f.rung:<9} {f.detail[:104]}")

    print("\n=== DEFECTIVE board vs its own netlist (the product's path) ===")
    for f in defect_rep.findings:
        print(f"  {f.check:<12} {f.status:<8} {f.rung:<9} {f.detail[:104]}")

    base_snap, defect_snap = _snapshot(base_rep), _snapshot(defect_rep)
    changed = sorted(c for c in set(base_snap) | set(defect_snap)
                     if base_snap.get(c) != defect_snap.get(c))
    print("\n=== DIFFERENCE ===")
    if changed:
        for check in changed:
            print(f"  {check}: {base_snap.get(check)} -> {defect_snap.get(check)}")
    else:
        print("  (no check changed — THE DEFECT IS INVISIBLE TO EVERY CHECK)")

    # The second measurement: the defective board judged against the DESIGN
    # INTENT. This is the check a design-intent check would make, and the
    # board that survives it is a board the product would ship.
    intent_rep = verify_board(_compile(defective_nl), nl)
    print("\n=== the defective board judged against the DESIGN INTENT ===")
    print(f"  failed checks: {[f.check for f in intent_rep.failed()] or 'none'} "
          f"(gate: {intent_rep.gate()[1]})")

    print("\n=== WHERE THE FAULT IS VISIBLE ===")
    print(f"  netlist.json (base)    C1: mpn={_c1_from_netlist(nl).get('mpn')!r} "
          f"value={_c1_from_netlist(nl).get('value')!r}")
    print(f"  netlist_defective.json C1: mpn={_c1_from_netlist(defective_nl).get('mpn')!r} "
          f"value={_c1_from_netlist(defective_nl).get('value')!r}")
    print(f"  board_base.json       C1.attrs: {_c1_attrs(base_board)}")
    print(f"  board_defective.json  C1.attrs: {_c1_attrs(defective_board)}")
    print(f"  the geometry is identical: tracks "
          f"{base_board['tracks'] == defective_board['tracks']}, vias "
          f"{base_board['vias'] == defective_board['vias']}, pads "
          f"{all(a['pads'] == b['pads'] for a, b in zip(base_board['components'], defective_board['components']))}")

    # The board-level twin returns the same board as seed_netlist + compile.
    twin = seed(json.loads(BOARD_BASE.read_text(encoding="utf-8")))
    shipped = json.loads(BOARD_DEFECTIVE.read_text(encoding="utf-8"))
    same = twin == shipped
    print(f"\nseed(board_base) == board_defective: {same}")

    # Idempotence.
    nl2 = seed_netlist(seed_netlist(nl))
    print(f"seed_netlist is idempotent: {nl2 == defective_nl}")
    twin2 = seed(twin)
    print(f"seed is idempotent: {twin2 == twin}")

    print(f"\nThe defective board's gate: {defect_rep.gate()}")
    print("A board with the wrong bypass capacitance is EMITTED for fabrication.")

    return 0 if (not changed and same) else 1


if __name__ == "__main__":
    raise SystemExit(main())
