"""
mutate.py — seed ONE physical defect: two pins of a component transposed.

THE DEFECT
----------
Q1 is a 2N2222A NPN transistor in a TO-92 package, wired as a low-side switch
for the relay coil:

    pin 1  emitter     -> GND
    pin 2  base        -> RELAY_CTRL
    pin 3  collector   -> RELAY_COIL_NEG

The seed transposes the emitter and the collector:

    pin 1  emitter     -> RELAY_COIL_NEG
    pin 2  base        -> RELAY_CTRL
    pin 3  collector   -> GND

The transistor is now wired backwards. The relay coil sits between VCC_5V and
RELAY_COIL_NEG, and RELAY_COIL_NEG is now the *emitter*. Drive the base high
and the transistor passes as an emitter follower: the coil sees almost no
voltage across it and the relay never actuates. The part is also running
reverse-active, where a 2N2222A has a fraction of its rated hFE. The board
is silent, undamaged, and completely dead.

This is the defect class the physics report names as the most likely way for
one of our boards to fail: the part is fitted, every pad is connected, every
net is routed, and the pin-to-net map disagrees with the design.

WHY IT IS INVISIBLE TO EVERYTHING THAT IS NOT A PINOUT CHECK
-------------------------------------------------------------
The fault is in the DESIGN, not in the copper. When the defective netlist is
compiled, the router does exactly what it is told: it routes RELAY_COIL_NEG to
pin 1 and GND to pin 3. The result is a board that

    * routes 12 of 12 required connections,
    * has 0 shorts (III.2), 0 opens (III.1), 0 DRC errors,
    * has a clean B.Cu ground pour joining every ground pad, and
    * passes the product's own verification report, which says EMIT.

The one thing wrong with it is that the two pins of one part are the wrong
way round. Only a check that reads the pin-to-net map against the DESIGN
INTENT can see that: verify.py's III.4, "the board's pin-to-net map is the
netlist's", on the exact rung.

WHY THE SEED IS ANCHORED TO THE DESIGN INTENT
----------------------------------------------
A transposition is its own inverse. A `seed` that blindly swapped two pins
would turn a defective board back into a good one on the second call, so it
could not be idempotent, and it could not tell a defective board from a good
one. This seed therefore states, for the one component it touches, what the
design says and what the defect says, and it sets the defect:

    base    -> the design intent (asserted before anything is changed)
    defect  -> the transposed arrangement

Applying the seed to an already-seeded netlist changes nothing. Applying it to
a netlist that is neither the design nor the defect raises, rather than
quietly corrupting something else.

THE TWO ENTRY POINTS
--------------------
`seed_netlist(netlist)`  the primary form. Swaps Q1's pins 1 and 3 in the
                         netlist, so the whole product path carries the fault
                         when the board is recompiled. Pure data in, pure
                         data out: no imports from `backend/`, no randomness,
                         no wall-clock, no I/O outside its arguments.

`seed(board_json)`       the board-level twin. Applies the same transposition
                         to a routed board. Because a faithful board-level
                         swap has to RE-ROUTE (the copper that reaches the
                         emitter is ground copper, and after the swap it has
                         to be coil-negative copper), it re-derives the board
                         the way the product does: recover the netlist from
                         the board, apply the same netlist seed, and recompile
                         with `pcb_engine.compile_board`. It therefore returns
                         the same board as `seed_netlist` + compile, and it
                         needs `backend/` on the path for that one step.

Both are idempotent. Both are deterministic: the same input always gives the
same output, byte for byte.

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
DEFECT_ID = "swapped_pins"

#: The one component this seed touches.
TARGET_REF = "Q1"

#: The design intent for that component, as the base netlist states it.
#: Q1 is a 2N2222A in TO-92: pad 1 = emitter, pad 2 = base, pad 3 = collector
#: (footprints.PART_PINMAPS -> _BJT_EBC, and KiCad's PN2222A symbol agrees:
#: 1 = E, 2 = B, 3 = C). The base netlist names the pads by number, so these
#: ARE the pad numbers.
DESIGN_PINS: dict[str, str] = {
    "1": "GND",              # emitter
    "2": "RELAY_CTRL",       # base
    "3": "RELAY_COIL_NEG",   # collector
}

#: The defect: the emitter and the collector are transposed. The base is
#: untouched. The part now switches the coil from its emitter, so it never
#: turns the relay on.
DEFECT_PINS: dict[str, str] = {
    "1": "RELAY_COIL_NEG",   # emitter  <-- should be GND
    "2": "RELAY_CTRL",       # base
    "3": "GND",              # collector <-- should be RELAY_COIL_NEG
}

#: The two pins the seed transposes.
TRANSPOSED_PINS: tuple[str, str] = ("1", "3")

Netlist = dict[str, Any]
BoardJson = dict[str, Any]

#: The base netlist this seed is written against, relative to the repository
#: root. It is a file the repository already had; this seed does not change
#: it.
BASE_NETLIST_REL = Path("backend") / "pcb_engine" / "netlist_dht22.json"

#: Where the boards this seed produces live.
FIXTURE_DIR = Path(__file__).resolve().parent
BOARD_BASE = FIXTURE_DIR / "board_base.json"
BOARD_DEFECTIVE = FIXTURE_DIR / "board_defective.json"

#: The repository root: tests/fixtures/alpha_known_bad/swapped_pins -> up four.
REPO_ROOT = Path(__file__).resolve().parents[4]


# ─────────────────────────────────────────────────────────────────────────────
# The netlist seed — the primary form
# ─────────────────────────────────────────────────────────────────────────────
def seed_netlist(netlist: Netlist) -> Netlist:
    """Return `netlist` with Q1's emitter and collector transposed.

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
    """Return the routed board that carries the transposed pins.

    The board is re-derived the way the product derives it, so the copper and
    the pad map both carry the fault and the result is the same board that
    `seed_netlist` + `compile_board` produces.
    """
    out = copy.deepcopy(board_json)
    if _board_is_seeded(out):
        return out                        # already seeded; nothing to do

    netlist = netlist_from_board(out)
    defective_netlist = seed_netlist(netlist)
    board = _compile(defective_netlist)
    return json.loads(board.to_json(indent=None))


def _board_is_seeded(board_json: BoardJson) -> bool:
    for c in board_json.get("components", []):
        if c.get("ref") != TARGET_REF:
            continue
        pads = {str(p.get("pin")): p.get("net", "") for p in c.get("pads", [])}
        if all(pads.get(pin) == net for pin, net in DEFECT_PINS.items()):
            return True
    return False


def netlist_from_board(board_json: BoardJson) -> Netlist:
    """Recover the netlist a board was compiled from.

    The Board IR carries everything the compiler needed: each component's
    package and part number, and each pad's pin-to-net binding. The ground
    net is the plane layer's net; the power nets are the "power" net class.
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
    return json.loads((REPO_ROOT / BASE_NETLIST_REL).read_text(encoding="utf-8"))


def _verifier():
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from pcb_engine.verify import verify_board        # noqa: PLC0415
    from pcb_engine.board_ir import Board              # noqa: PLC0415
    return verify_board, Board


def _snapshot(report) -> dict[str, tuple[str, str]]:
    return {f.check: (f.status, f.rung) for f in report.findings}


def main() -> int:
    verify_board, Board = _verifier()
    nl = base_netlist()

    base_board = _compile(nl)
    BOARD_BASE.write_text(base_board.to_json(indent=2), encoding="utf-8")

    defective_nl = seed_netlist(nl)
    defective_board = _compile(defective_nl)
    BOARD_DEFECTIVE.write_text(defective_board.to_json(indent=2), encoding="utf-8")

    # The design intent is the netlist the board is supposed to be built from.
    base_rep = verify_board(base_board, nl)
    defect_rep = verify_board(defective_board, nl)

    print("=== BASE board vs design-intent netlist ===")
    for f in base_rep.findings:
        print(f"  {f.check:<12} {f.status:<8} {f.rung:<9} {f.detail[:110]}")

    print("\n=== DEFECTIVE board vs design-intent netlist ===")
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
        print("  (no check changed — THE SEED IS NOT VISIBLE)")

    for f in defect_rep.findings:
        if f.check == "III.4":
            print("\n=== III.4 on the defective board ===")
            print(f"  {f.status}: {f.detail}")

    ok = (base_snap.get("III.4", ("", ""))[0] == "pass"
          and defect_snap.get("III.4", ("", ""))[0] == "fail"
          and changed == ["III.4"])
    print(f"\nIII.4 pass on base, fail on defective, and ONLY III.4 changed: {ok}")

    # The product's own report, on the defective netlist, is a FALSE PASS.
    self_rep = verify_board(defective_board, defective_nl)
    self_failed = [f.check for f in self_rep.failed()]
    print(f"The product's own verification of the defective board against the "
          f"defective netlist: failed checks = {self_failed or 'none'} "
          f"(gate: {self_rep.gate()[1]})")

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

    return 0 if (ok and same) else 1


if __name__ == "__main__":
    raise SystemExit(main())
