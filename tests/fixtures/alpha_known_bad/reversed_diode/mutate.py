"""
mutate.py — seed ONE physical defect: a diode fitted the wrong way round.

THE DEFECT
----------
The load-switch board puts a flyback diode D1 across the switched load:

    A (anode)   -> SW_LOAD     the load side
    K (cathode) -> VCC_5V      the rail side

That is right. In steady state Q1 is on, so SW_LOAD sits at about 0.2 V while
the rail is at 5 V: the diode's anode is 4.8 V BELOW its cathode, so it is
reverse biased and carries no current. When Q1 turns off, the load's
inductance drives SW_LOAD up towards the rail; the diode's cathode is on the
rail, so it conducts, clamps SW_LOAD to about -0.7 V, and keeps the
flyback pulse off Q1's collector. That is what a flyback diode is for.

The seed fits it the wrong way round:

    base     A (anode) -> SW_LOAD     K (cathode) -> VCC_5V
    defect   A (anode) -> VCC_5V      K (cathode) -> SW_LOAD

Now the diode conducts in the steady state it was supposed to block. Its
anode is on the 5 V rail and its cathode is on the 0.2 V load node, so it is
forward biased by 4.8 V — five times a 1N4148W's 0.7 V forward drop. The
rail is shorted to the load through the diode: the load sees the full rail
voltage, Q1 no longer switches anything, and the diode itself is destroyed by
the sustained current. And when Q1 turns off, the cathode is now on the load
side, so the diode BLOCKS the flyback instead of clamping it: the inductive
spike goes onto Q1's collector, which is exactly what the diode exists to
prevent. The part that is supposed to protect the transistor destroys it.

WHY THIS BOARD AND NOT THE OTHER ONE
-------------------------------------
The fixture netlist the other cases use (`backend/pcb_engine/netlist_dht22.json`)
is a hand-written board whose D1 is a 1N4007 with its pads named BY NUMBER
("1", "2"). The real generator names a diode's pins by FUNCTION ("A", "K") —
that is how `generators/load_switch.py` writes it, and it is what makes the
second source reachable at all.

This case therefore uses the REAL product output: the `load_switch` generator
runs, `PcbNetlistGenerator` turns the CircuitIR into the netlist the PCB
engine consumes, and `compile_board` routes it. D1 comes out as a 1N4148W-7-F
in SOD-123 with pads named A and K, and `part_pinouts.lookup` resolves it (by
prefix) to KiCad's `Diode:1N4148W`, whose symbol says pad 1 = K, pad 2 = A.

So on this board the verifier's IV.2 check — "every part's pinout agrees with
the KiCad symbol for its part number" — ACTUALLY RUNS. It is not a check that
could not be reached. It runs, and it passes the reversed diode, because of
what it compares. This is the strong form of the finding, and it is why this
case is built on the real board and not on a fixture.

WHAT IV.2 COMPARES, AND WHY THAT IS NOT ENOUGH
-----------------------------------------------
IV.2 asks: does the NET on pad N agree with what the SYMBOL says pad N is?

It finds that D1's netlist names its pins by function, so "A" and "K" are
labels rather than pad numbers. It resolves "A" through the symbol to pad 2
and "K" to pad 1, then checks that pad 2 carries the net the netlist calls
"A" and pad 1 carries the net the netlist calls "K".

On the defective board that is all still true. The board faithfully realises
the defective netlist: pad 2 does carry what "A" carries, and pad 1 does
carry what "K" carries. What changed is WHICH NET each function is on, and
the symbol says nothing about that — a symbol describes a part's terminals,
not what a particular design must connect them to. A datasheet pinout table
answers "which terminal is the cathode"; only the CIRCUIT answers "which net
belongs on the cathode".

That is the whole gap, and it is architectural rather than a missing rule:
the product verifies the board against the netlist it was handed, and the
netlist is the thing that is wrong.

THE TWO ENTRY POINTS
---------------------
`seed_netlist(netlist)`  swaps D1's A and K. Pure data in, pure data out: no
                         imports from `backend/`, no randomness, no
                         wall-clock, no I/O outside its arguments.

`seed(board_json)`       the board-level twin. A faithful board-level swap
                         has to RE-ROUTE (the copper that reaches the anode
                         is rail copper, and after the swap it has to be load
                         copper), so it re-derives the board the way the
                         product does: recover the netlist from the board,
                         apply the same netlist seed, and recompile with
                         `pcb_engine.compile_board`. It therefore returns the
                         same board as `seed_netlist` + compile.

Both are idempotent and deterministic: the same input always gives the same
output, byte for byte.

    python mutate.py          rebuild both boards and prove the difference
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# The defect, stated
# ─────────────────────────────────────────────────────────────────────────────
DEFECT_ID = "reversed_diode"

#: The one component this seed touches.
TARGET_REF = "D1"

#: The design intent for that component, as the generator states it.
#: D1 is a 1N4148W-7-F in SOD-123. `generators/load_switch.py` names the
#: diode's pins by FUNCTION — A for the anode, K for the cathode — and puts
#: the anode on the switched load so the diode is reverse biased in steady
#: state and conducts only while the load's inductance collapses.
DESIGN_PINS: dict[str, str] = {
    "A": "SW_LOAD",     # anode
    "K": "VCC_5V",      # cathode
}

#: The defect: the diode is fitted the wrong way round. The anode now sits
#: on the rail and the cathode on the load, so the diode conducts in the
#: steady state it was supposed to block, and blocks the flyback it was
#: supposed to clamp.
DEFECT_PINS: dict[str, str] = {
    "A": "VCC_5V",      # anode  <-- should be SW_LOAD
    "K": "SW_LOAD",     # cathode <-- should be VCC_5V
}

#: The two pins the seed transposes.
TRANSPOSED_PINS: tuple[str, str] = ("A", "K")

#: The same transposition expressed in the PADS the board ends up with.
#: `footprints.PINMAPS["SOD-123"]` says pad 1 is the cathode (K) and pad 2 is
#: the anode (A) — KiCad's convention and JEDEC's, and the reason the
#: 2026-10-17 fix exists. So the design's "A -> SW_LOAD, K -> VCC_5V"
#: becomes "pad 2 -> SW_LOAD, pad 1 -> VCC_5V" on the board.
#:
#: The board IR names pads by NUMBER, so the board-level twin has to work in
#: this space. Getting this wrong would make the twin seed a different defect
#: from the netlist seed, so it is stated here rather than derived.
DESIGN_PADS: dict[str, str] = {
    "1": "VCC_5V",      # cathode (K)
    "2": "SW_LOAD",     # anode   (A)
}

DEFECT_PADS: dict[str, str] = {
    "1": "SW_LOAD",     # cathode (K) <-- should be VCC_5V
    "2": "VCC_5V",      # anode   (A) <-- should be SW_LOAD
}

Netlist = dict[str, Any]
BoardJson = dict[str, Any]

#: The intent that produces the real board. `load_inductive` is what makes the
#: generator add the flyback diode at all.
BASE_INTENT: dict[str, Any] = {
    "requirements": {
        "function": "load_switch",
        "targets": {"load_current_ma": 30},
        "constraints": {"load_inductive": True},
        "preferences": {},
    },
}

#: Where the artifacts this seed produces live.
FIXTURE_DIR = Path(__file__).resolve().parent
BOARD_BASE = FIXTURE_DIR / "board_base.json"
BOARD_DEFECTIVE = FIXTURE_DIR / "board_defective.json"
NETLIST_BASE = FIXTURE_DIR / "netlist_base.json"
NETLIST_DEFECTIVE = FIXTURE_DIR / "netlist_defective.json"

#: The repository root: tests/fixtures/alpha_known_bad/reversed_diode -> up four.
REPO_ROOT = Path(__file__).resolve().parents[4]


# ─────────────────────────────────────────────────────────────────────────────
# The netlist seed — the primary form
# ─────────────────────────────────────────────────────────────────────────────
def seed_netlist(netlist: Netlist) -> Netlist:
    """Return `netlist` with D1's anode and cathode transposed.

    Idempotent: seeding an already-seeded netlist returns it unchanged.
    Raises ValueError on a netlist that is neither the design nor the defect,
    so a mismatched base is a loud failure and not a silent corruption.
    """
    out = copy.deepcopy(netlist)
    comp = _target_component(out)
    pins = {str(k): v for k, v in (comp.get("pins") or {}).items()}

    if pins == DEFECT_PINS:
        return out                       # already seeded; nothing to do

    if pins != DESIGN_PINS:
        raise ValueError(
            f"{TARGET_REF} is not the {DEFECT_ID} target: its pins are "
            f"{pins!r}, which is neither the design intent {DESIGN_PINS!r} "
            f"nor the seeded defect {DEFECT_PINS!r}. Refusing to seed a "
            f"different design."
        )

    comp["pins"] = dict(DEFECT_PINS)
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
    """Return the routed board that carries the reversed diode.

    The board is re-derived the way the product derives it, so the copper
    and the pad map both carry the fault and the result is the same board
    that `seed_netlist` + `compile_board` produces.
    """
    out = copy.deepcopy(board_json)
    if _board_is_seeded(out):
        return out                        # already seeded; nothing to do

    netlist = netlist_from_board(out)
    defective_netlist = seed_netlist(netlist)
    board = _compile(defective_netlist)
    return json.loads(board.to_json(indent=None))


def _board_is_seeded(board_json: BoardJson) -> bool:
    """Does this board already carry the reversed diode?

    The board names pads by NUMBER, so the test is stated in pad space: the
    cathode's pad carries the load and the anode's pad carries the rail.
    """
    for c in board_json.get("components", []):
        if c.get("ref") != TARGET_REF:
            continue
        pads = {str(p.get("pin")): p.get("net", "") for p in c.get("pads", [])}
        if all(pads.get(pin) == net for pin, net in DEFECT_PADS.items()):
            return True
    return False


def netlist_from_board(board_json: BoardJson) -> Netlist:
    """Recover the netlist a board was compiled from.

    The Board IR carries everything the compiler needed: each component's
    package and part number, and each pad's pin-to-net binding. The ground
    net is the plane layer's net; the power nets are the "power" net class.

    One thing is restored rather than read: D1's pin NAMES. The board names
    its pads by number ("1", "2"), because that is what a footprint has. The
    design named them by function ("A", "K"), because that is what a diode
    has — and the function names are what make the diode's polarity legible
    and what IV.2 resolves against the KiCad symbol. A netlist recovered from
    the board in pad numbers would say "pin 1 carries VCC_5V" and no reader
    could tell whether that is right, because a number says nothing about
    which end of the part it is. So the names come back here, from the same
    convention the generator used: `footprints.PINMAPS["SOD-123"]` puts the
    cathode on pad 1 and the anode on pad 2.
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
        if entry["ref"] == TARGET_REF:
            entry["pins"] = _diode_pins_by_function(pins)
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


def _diode_pins_by_function(pads: dict[str, str]) -> dict[str, str]:
    """D1's pad-to-net map, with the pads renamed the way the diode names them.

    SOD-123: pad 1 is the cathode (K), pad 2 is the anode (A). That is
    KiCad's convention and JEDEC's, and it is the convention
    `backend/pcb_engine/footprints.py` declares in `PINMAPS["SOD-123"]`.
    """
    return {
        "K": pads.get("1", ""),
        "A": pads.get("2", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# The real board — the product's own path from an intent to a routed board
# ─────────────────────────────────────────────────────────────────────────────
def product_netlist() -> Netlist:
    """The netlist the product builds for a 30 mA inductive load switch.

    This is the whole product path, not a fixture: the generator decides the
    design, `PcbNetlistGenerator` translates the CircuitIR into the netlist
    the PCB engine consumes, and the diode's polarity is the generator's
    decision. Seeding the netlist is therefore seeding the DESIGN.
    """
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from core.intent_ir import IntentIR, Producer, Provenance   # noqa: PLC0415
    from generators.load_switch import LoadSwitchGenerator      # noqa: PLC0415
    from generators.netlist.pcb import PcbNetlistGenerator      # noqa: PLC0415
    from generators.realize import realize                      # noqa: PLC0415

    intent = IntentIR(requirements=copy.deepcopy(BASE_INTENT["requirements"]),
                       provenance=Provenance(producer=Producer.FORM))
    ir = realize(LoadSwitchGenerator(), intent)
    return PcbNetlistGenerator().generate(ir)


# ─────────────────────────────────────────────────────────────────────────────
# The proof — run this file to rebuild both boards and show the difference
# ─────────────────────────────────────────────────────────────────────────────
def _verifier():
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from pcb_engine.verify import verify_board        # noqa: PLC0415
    from pcb_engine.board_ir import Board              # noqa: PLC0415
    return verify_board, Board


def _snapshot(report) -> dict[str, tuple[str, str]]:
    return {f.check: (f.status, f.rung) for f in report.findings}


def _d1_pads(board_json: BoardJson) -> dict[str, str]:
    for c in board_json.get("components", []):
        if c.get("ref") == TARGET_REF:
            return {str(p.get("pin")): p.get("net", "") for p in c.get("pads", [])}
    return {}


def main() -> int:
    verify_board, Board = _verifier()
    nl = product_netlist()

    base_board = _compile(nl)
    BOARD_BASE.write_text(base_board.to_json(indent=2), encoding="utf-8")
    NETLIST_BASE.write_text(json.dumps(nl, indent=2) + "\n", encoding="utf-8")

    defective_nl = seed_netlist(nl)
    defective_board = _compile(defective_nl)
    BOARD_DEFECTIVE.write_text(defective_board.to_json(indent=2), encoding="utf-8")
    NETLIST_DEFECTIVE.write_text(json.dumps(defective_nl, indent=2) + "\n", encoding="utf-8")

    # The product's own path: verify each board against the netlist it was
    # compiled from. This is exactly what compile_board does.
    base_rep = verify_board(base_board, nl)
    defect_rep = verify_board(defective_board, defective_nl)

    print("=== BASE board vs its own netlist (the product's path) ===")
    for f in base_rep.findings:
        print(f"  {f.check:<12} {f.status:<8} {f.rung:<9} {f.detail[:110]}")

    print("\n=== DEFECTIVE board vs its own netlist (the product's path) ===")
    for f in defect_rep.findings:
        print(f"  {f.check:<12} {f.status:<8} {f.rung:<9} {f.detail[:110]}")

    base_snap, defect_snap = _snapshot(base_rep), _snapshot(defect_rep)
    print("\n=== DIFFERENCE ===")
    changed = []
    for check in sorted(set(base_snap) | set(defect_snap)):
        b, d = base_snap.get(check), defect_snap.get(check)
        if b != d:
            changed.append(check)
            print(f"  {check}: {b} -> {d}")
    if not changed:
        print("  (no check changed — THE DEFECT IS INVISIBLE TO EVERY CHECK)")

    print(f"\nD1's pads, base      : {_d1_pads(json.loads(BOARD_BASE.read_text(encoding='utf-8')))}")
    print(f"D1's pads, defective : {_d1_pads(json.loads(BOARD_DEFECTIVE.read_text(encoding='utf-8')))}")
    print("  (SOD-123: pad 1 is the cathode K, pad 2 is the anode A)")

    for f in defect_rep.findings:
        if f.check in ("IV.2", "IV.2b"):
            print(f"\n=== {f.check} on the defective board ===")
            print(f"  {f.status} ({f.rung}): {f.detail}")

    # The gate is what the product actually does with the board: emit it, or
    # refuse it.
    print(f"\nThe defective board's gate: {defect_rep.gate()}")
    print("A board whose diode is the wrong way round is EMITTED for fabrication.")

    # The board-level twin returns the same board.
    twin = seed(json.loads(BOARD_BASE.read_text(encoding="utf-8")))
    shipped = json.loads(BOARD_DEFECTIVE.read_text(encoding="utf-8"))
    same = twin == shipped
    print(f"seed(board_base) == board_defective: {same}")

    # Idempotence.
    nl2 = seed_netlist(seed_netlist(nl))
    print(f"seed_netlist is idempotent: {nl2 == defective_nl}")
    twin2 = seed(twin)
    print(f"seed is idempotent: {twin2 == twin}")

    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
