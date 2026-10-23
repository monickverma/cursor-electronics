"""
footprints.py — the missing layer between a netlist and a board.

Circuit OS knows `U1 = ATMEGA328P-PU` and which nets land on which pins. It does
NOT know that a DIP-28 is two rows of fourteen pads on 2.54 mm pitch, 7.62 mm
apart, drilled 0.8 mm. Nothing can be laid out until someone supplies that, and
until now "someone" was me, by hand.

This file is that lookup, in two halves:

  PACKAGES   package name -> pad geometry generator
  guess()    manufacturer part number -> package name
  normalize_package() package name alias -> canonical package name

`guess()` is a heuristic and it is meant to be. It covers the parts a hobby-tier
generator actually emits, and it returns None rather than a wrong answer when it
does not recognise something — a missing footprint is a question you can ask the
user, a wrong footprint is a board that arrives unusable.

For production, point this at KiCad's footprint library instead. It is free,
enormous, and already maps most of these part numbers. The interface below is
deliberately the same shape so that swap is local.
"""
from __future__ import annotations

import re
from board_ir import Component, Pad

MM = 2.54
TH_PAD = 1.3          # 0.8 mm drill + 0.25 mm annular ring — see circuit_os_board
TH_RING = 0.25        # every through-hole pad here is its drill plus this ring


def th_drill(w: float, h: float) -> float:
    """The finished hole of a through-hole pad, by the convention every
    generator in this file follows: pad = drill + 2 x TH_RING. The Board IR
    carries no drill, so the KiCad writer asks here rather than guessing."""
    return round(min(w, h) - 2 * TH_RING, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Pad generators. Each returns (pads_relative_to_origin, courtyard_w, courtyard_h)
# ─────────────────────────────────────────────────────────────────────────────
def _dip(npins: int, row: float = 7.62, pad: float = TH_PAD):
    per = npins // 2
    span = (per - 1) * MM
    out = []
    for i in range(per):                       # pins 1..per go up the left side
        out.append((str(i + 1), -row / 2, -span / 2 + i * MM, pad, pad))
    for i in range(per):                       # then back down the right side
        out.append((str(npins - i), row / 2, -span / 2 + i * MM, pad, pad))
    return out, row + 3.4, span + 3.0


def _inline(npins: int, pitch: float = MM, pad: float = TH_PAD,
            vertical: bool = False):
    span = (npins - 1) * pitch
    out = []
    for i in range(npins):
        o = -span / 2 + i * pitch
        out.append((str(i + 1), 0.0 if vertical else o, o if vertical else 0.0,
                    pad, pad))
    w = pad + 1.6 if vertical else span + pad + 1.6
    h = span + pad + 1.6 if vertical else pad + 1.6
    return out, w, h


def _axial(body: float = 10.16, pad: float = TH_PAD):
    return _inline(2, pitch=body, pad=pad)


def _relay_srd():
    """SRD-05VDC-SL-C: 5 pins, coil pair on one side, contacts on the other."""
    out = [("1", -7.5, -5.0, 1.6, 1.6), ("2", -7.5, 5.0, 1.6, 1.6),
           ("3", 7.5, -5.0, 1.6, 1.6), ("4", 7.5, 0.0, 1.6, 1.6),
           ("5", 7.5, 5.0, 1.6, 1.6)]
    return out, 20.0, 16.0


def _chip(span: float, pad_w: float, pad_h: float):
    """Two-terminal SMD chip (0402/0603/0805/1206/1210).

    `span` is pad centre-to-centre. Geometry is IPC-7351B nominal (density
    level B) — the same numbers KiCad's Resistor_SMD library uses, so swapping
    this file for the real KiCad library later will not move any part."""
    out = [("1", -span / 2, 0.0, pad_w, pad_h),
           ("2",  span / 2, 0.0, pad_w, pad_h)]
    return out, span + pad_w + 0.5, pad_h + 0.5


def _sot23():
    """SOT-23: pins 1 and 2 on one side at 0.95 mm pitch, pin 3 opposite."""
    out = [("1", -0.95, -1.10, 0.90, 1.00),
           ("2",  0.95, -1.10, 0.90, 1.00),
           ("3",  0.00,  1.10, 0.90, 1.00)]
    return out, 3.30, 3.70


def _sod123():
    """SOD-123, KiCad Diode_SMD:D_SOD-123 pad geometry. Pad 1 is the cathode —
    the banded end — as in KiCad's and the JEDEC convention for SMD diodes."""
    return _chip(3.27, 0.91, 1.22)


def _dht22():
    """DHT22 / AM2302: four 2.54 mm pins in a row, under a 15.1 x 7.7 mm body.

    Same pads as HEADER-4, but the courtyard covers the body. As a bare header
    the placer saw a 3 x 9 mm part and tucked passives under a sensor that
    stands 25 mm tall — found by drawing the board in 3D (scene3d.py)."""
    pads, _, _ = _inline(4, vertical=True)
    return pads, 7.7 + 0.5, 15.1 + 0.5


def _soic(npins: int, row: float = 5.40, pitch: float = 1.27,
          pad_len: float = 1.50, pad_wid: float = 0.60):
    """SOIC, narrow body. Pin order matches _dip: 1..n/2 up the left, then back
    down the right, so pin 1 and pin n sit on the same row.

    Pads are long across the row (x) and narrow along the pitch (y). Until the
    2026-10-12 review they were the other way round: 1.5 mm tall on a 1.27 mm
    pitch, so neighbouring pads overlapped and every SOIC pin was shorted to the
    next one."""
    per = npins // 2
    span = (per - 1) * pitch
    out = []
    for i in range(per):
        out.append((str(i + 1), -row / 2, -span / 2 + i * pitch, pad_len, pad_wid))
    for i in range(per):
        out.append((str(npins - i), row / 2, -span / 2 + i * pitch, pad_len, pad_wid))
    return out, row + pad_len + 0.5, span + pad_wid + 0.5


PACKAGES = {
    "DIP-8":    lambda: _dip(8),
    "DIP-14":   lambda: _dip(14),
    "DIP-16":   lambda: _dip(16),
    "DIP-28":   lambda: _dip(28),
    "DIP-40":   lambda: _dip(40, row=15.24),
    "TO-92":    lambda: _inline(3),
    "TO-220":   lambda: _inline(3, pitch=2.54, pad=1.5),
    "DO-41":    lambda: _axial(10.16),
    "AXIAL":    lambda: _axial(10.16),
    "RADIAL-2": lambda: _inline(2, pitch=5.08),
    "RELAY-SRD": _relay_srd,
    "DHT22":    _dht22,
    "HEADER-2": lambda: _inline(2, vertical=True, pad=1.5),
    "HEADER-3": lambda: _inline(3, vertical=True, pad=1.5),
    "HEADER-4": lambda: _inline(4, vertical=True, pad=1.5),
    "HEADER-5": lambda: _inline(5, vertical=True, pad=1.5),
    "HEADER-6": lambda: _inline(6, vertical=True, pad=1.5),

    # ── Surface mount ────────────────────────────────────────────────────────
    # Added 2026-08-22. Their absence meant every 0402 passive in all five
    # example IRs was dropped by from_netlist() — IR_003 and IR_004 compiled to
    # completely empty boards. See tests/test_pcb_placement.py.
    "0402":     lambda: _chip(0.95, 0.60, 0.65),
    "0603":     lambda: _chip(1.55, 0.85, 0.95),
    "0805":     lambda: _chip(1.90, 1.05, 1.40),
    "1206":     lambda: _chip(3.00, 1.15, 1.80),
    "1210":     lambda: _chip(3.00, 1.15, 2.70),
    "SOT-23":   _sot23,
    "SOD-123":  _sod123,
    "SOIC-8":   lambda: _soic(8),
    "SOIC-14":  lambda: _soic(14),
    "SOIC-16":  lambda: _soic(16),
}

# Pads on these are surface features: single layer, no barrel. The router treats
# shape == "th" as reachable from every layer (router.py), and DRC skips the
# layer check for it (kernel.py) — so calling an SMD pad through-hole would let
# the router approach it from the bottom copper, which on a real board is a
# connection to nothing.
SMD_PACKAGES = frozenset({
    "0402", "0603", "0805", "1206", "1210",
    "SOT-23", "SOD-123", "SOIC-8", "SOIC-14", "SOIC-16",
})


# ─────────────────────────────────────────────────────────────────────────────
# MPN -> package
# ─────────────────────────────────────────────────────────────────────────────
_RULES: list[tuple[str, str]] = [
    (r"ATMEGA(328|168|88)\w*-PU",   "DIP-28"),
    (r"ATMEGA(32|16|8)A?-PU",       "DIP-40"),
    (r"ATTINY85\w*-PU",             "DIP-8"),
    (r"NE555|LM358|LM393|TL072",    "DIP-8"),
    (r"^2N\d{4}|^BC\d{3}|^PN2222",  "TO-92"),
    (r"^1N4\d{3}|^1N5\d{3}",        "DO-41"),
    (r"^LM78\d\d|^LM317",           "TO-220"),
    (r"^CFR-|^MFR-|CARBON|METAL.?FILM", "AXIAL"),
    (r"^SRD-\d+VDC",                "RELAY-SRD"),
    (r"DHT(11|22)|AM2302",          "DHT22"),
    (r"^K\d+K\d+X7R|CERAMIC.?DISC", "RADIAL-2"),
    (r"^ECA-|ELECTROLYTIC",         "RADIAL-2"),
]


def normalize_package(pkg: str | None) -> str | None:
    if not pkg: return None
    p = pkg.upper().replace(" ", "-")
    if "RELAY" in p: return "RELAY-SRD"
    if "DO-35" in p or "DO-41" in p: return "DO-41"
    if "AXIAL" in p: return "AXIAL"
    if "RADIAL" in p: return "RADIAL-2"
    if "TO-92" in p or "TO92" in p: return "TO-92"

    # Chip sizes, with or without an R/C/L prefix: "0402", "R0402", "C0603".
    m = re.fullmatch(r"[RCL]?(0201|0402|0603|0805|1206|1210)", p)
    if m: return m.group(1)
    if p in ("SOT23", "SOT-23"): return "SOT-23"
    if p in ("SOD123", "SOD-123"): return "SOD-123"
    m = re.fullmatch(r"SOIC-?(\d+)", p)
    if m: return f"SOIC-{m.group(1)}"

    
    m = re.search(r"(\d+)-PIN", p)
    if m: return f"HEADER-{m.group(1)}"
    m = re.search(r"SIP-(\d+)", p)
    if m: return f"HEADER-{m.group(1)}"
    m = re.search(r"DIP-(\d+)", p)
    if m: return f"DIP-{m.group(1)}"
    return p


# Packages that name one part rather than a shape. When the part number says
# DHT22, the netlist's generic "4-pin SIP" must not hide the sensor's body.
PART_SPECIFIC = frozenset({"DHT22", "RELAY-SRD"})


def guess(mpn: str, npins: int | None = None) -> str | None:
    """Best-effort package from a part number. None when unsure — never a guess
    that would silently produce the wrong pad geometry."""
    if not mpn:
        return None
    m = mpn.upper().strip()
    for pat, pkg in _RULES:
        if re.search(pat, m):
            return pkg
    if npins:                                   # last resort: a bare header
        key = f"HEADER-{npins}"
        if key in PACKAGES:
            return key
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Pin label -> pad. Per part first, per package only where the package decides.
# ─────────────────────────────────────────────────────────────────────────────
# A package does not decide a pinout: in the KiCad library one SOT-23 footprint
# carries 39 pin assignments, TO-92 30, SOIC-8 298 (reports/PCB verification
# implementation plan.md, stage 1). So three-terminal and multi-pin parts are
# mapped by part number. Each map below is transcribed by hand from the part's
# datasheet; verify.py checks it against the KiCad symbol for the same part
# number, a transcription made by other people (part_pinouts.py).
_ATMEGA328P_DIP28 = {
        "VCC": ["7", "20"],
        "GND": ["8", "22"],
        "AVCC": ["20"],
        "AREF": ["21"],
        "D0": ["2"], "RXD": ["2"],
        "D1": ["3"], "TXD": ["3"],
        "D2": ["4"],
        "D3": ["5"],
        "D4": ["6"],
        "D5": ["11"],
        "D6": ["12"],
        "D7": ["13"],
        "D8": ["14"],
        "D9": ["15"],
        "D10": ["16"],
        "D11": ["17"],
        "D12": ["18"],
        "D13": ["19"],
        "A0": ["23"],
        "A1": ["24"],
        "A2": ["25"],
        "A3": ["26"],
        "A4": ["27"], "SDA": ["27"],
        "A5": ["28"], "SCL": ["28"],
        "RESET": ["1"],
        "XTAL1": ["9"],
        "XTAL2": ["10"],
        "D0_RX": ["2"], "D1_TX": ["3"],
}

_BJT_EBC = {"E": ["1"], "EMITTER": ["1"], "B": ["2"], "BASE": ["2"],
            "C": ["3"], "COLLECTOR": ["3"]}
_BJT_CBE = {"C": ["1"], "COLLECTOR": ["1"], "B": ["2"], "BASE": ["2"],
            "E": ["3"], "EMITTER": ["3"]}
_BJT_BEC = {"B": ["1"], "BASE": ["1"], "E": ["2"], "EMITTER": ["2"],
            "C": ["3"], "COLLECTOR": ["3"]}
_FET_GSD = {"G": ["1"], "GATE": ["1"], "S": ["2"], "SOURCE": ["2"],
            "D": ["3"], "DRAIN": ["3"]}
# MAX481E/MAX483E/MAX485E/MAX487E and MAX3485E share one 8-pin order.
_RS485_8 = {"RO": ["1"], "RE": ["2"], "~RE": ["2"], "DE": ["3"], "DI": ["4"],
            "GND": ["5"], "A": ["6"], "B": ["7"], "VCC": ["8"]}

# (part-number pattern, package, map). The package is part of the key: the same
# die in another package is another pinout (ATmega328P-PU vs -AU).
PART_PINMAPS: list[tuple[str, str, dict]] = [
    (r"^ATMEGA328P?-PU?$",                      "DIP-28", _ATMEGA328P_DIP28),
    (r"^(PN2222A?|2N2222A?|2N3904|2N3906|S8050)", "TO-92", _BJT_EBC),
    (r"^(BC54[6-9]|BC337|BC327|BC55[6-9])",     "TO-92",  _BJT_CBE),
    (r"^(MMBT2222A?|MMBT3904|MMBT3906|BC84[6-9]|BC81[78])", "SOT-23", _BJT_BEC),
    (r"^(2N7002|BSS138|BSS84|AO340[01]A?)",     "SOT-23", _FET_GSD),
    (r"^MAX(48[1357]E|3485E?)",                 "SOIC-8", _RS485_8),
    (r"^MAX(48[1357]E|3485E?)",                 "DIP-8",  _RS485_8),
]

PINMAPS = {
    # Diodes: pad 1 is the cathode, in every package. That is KiCad's convention
    # (Diode:1N4148W and Diode:1N4007 both read 1 = K, 2 = A) and JEDEC's for the
    # banded end. Until 2026-10-17 DO-41 and the chip packages put the anode on
    # pad 1, which reversed every such diode the moment a board met a KiCad
    # footprint.
    "SOD-123": {
        "K": ["1"], "CATHODE": ["1"], "A": ["2"], "ANODE": ["2"],
    },
    "DO-41": {
        "K": ["1"], "CATHODE": ["1"], "A": ["2"], "ANODE": ["2"],
    },
    "RELAY-SRD": {
        "COIL1": ["1"], "COIL_A": ["1"],
        "COIL2": ["2"], "COIL_B": ["2"],
        "COM": ["3"],
        "NC": ["4"],
        "NO": ["5"],
    },
    "DHT22": {
        "VCC": ["1"], "DATA": ["2"], "NC": ["3"], "GND": ["4"],
    },
    "HEADER-4": {
        "VCC": ["1"],
        "DATA": ["2"],
        "NC": ["3"],
        "GND": ["4"],
    },
}

# Two-terminal parts. A resistor's or capacitor's terminals only need names that
# land consistently; "+" is pad 1 by convention. A diode's or LED's do not: pad 1
# is the cathode, as above, so a part whose labels name a cathode reads "A" as
# its anode (pad 2), not as terminal A (pad 1).
_TWO_TERMINAL = {
    "A": ["1"], "B": ["2"],
    "+": ["1"], "-": ["2"],
    "P": ["1"], "N": ["2"],
    "CATHODE": ["1"], "K": ["1"], "ANODE": ["2"],
}
_POLAR_TWO_TERMINAL = {"K": ["1"], "CATHODE": ["1"], "A": ["2"], "ANODE": ["2"]}
_TWO_TERMINAL_PACKAGES = ("0402", "0603", "0805", "1206", "1210", "AXIAL", "RADIAL-2")
for _pkg in _TWO_TERMINAL_PACKAGES:
    PINMAPS.setdefault(_pkg, dict(_TWO_TERMINAL))

# NOTE: no package-wide map for SOIC-8, SOT-23 or TO-92. Pin 1 is RO on a MAX485
# and an output on an op-amp; a SOT-23 is a transistor, a regulator or a diode in
# four different orders. A part with no map in PART_PINMAPS has no declared
# pinout, and its named pins are left unconnected rather than guessed.


def pin_map(package: str, mpn: str | None = None,
            labels=()) -> tuple[dict[str, list[str]], str]:
    """The label -> pads map for one part, and where it came from.

    Returns (map, source): source is "part:<pattern>" for a per-part map,
    "package:<name>" for a package-wide one, or "" when nothing is declared."""
    m = (mpn or "").upper().strip()
    for pat, pkg, mapping in PART_PINMAPS:
        if pkg == package and m and re.search(pat, m):
            return mapping, f"part:{pat}"
    mapping = PINMAPS.get(package)
    if mapping is None:
        return {}, ""
    if package in _TWO_TERMINAL_PACKAGES and \
            {str(l).upper() for l in labels} & {"K", "CATHODE"}:
        return _POLAR_TWO_TERMINAL, f"package:{package} (polarised)"
    return mapping, f"package:{package}"


def resolve(package: str, netlist_pins: dict[str, str], mpn: str | None = None
            ) -> tuple[dict[str, str], list[str], list[str], str]:
    """Bind netlist pin labels to pads. One function, so the generator and the
    verifier's parity check cannot drift apart.

    Returns (pad -> net, unresolved labels, collisions, map source). A label is
    a literal pad number, or a name a declared map gives a pad. Anything else is
    unresolved: it is NOT placed on a free pad. Until 2026-10-17 it was, in
    netlist order, which compiled a MAX485 or an unmapped SOT-23 into a board
    wired by luck (reports/PCB verification implementation plan.md, decision 9).
    """
    if package not in PACKAGES:
        raise KeyError(f"no footprint for package {package!r}")
    avail = [p[0] for p in PACKAGES[package]()[0]]
    mapping, source = pin_map(package, mpn, netlist_pins)

    nets: dict[str, str] = {}
    unresolved: list[str] = []
    collisions: list[str] = []

    def put(pad: str, net: str, label: str):
        if pad in nets and nets[pad] != net:
            collisions.append(f"'{label}' -> pad {pad} already carries "
                              f"'{nets[pad]}' (now '{net}')")
        nets[pad] = net

    for label, net in netlist_pins.items():
        if label in avail:
            put(label, net, label)
            continue
        targets = [t for t in mapping.get(label.upper(), []) if t in avail]
        if targets:
            for t in targets:
                put(t, net, label)
            continue
        unresolved.append(label)
    return nets, unresolved, collisions, source


def build(ref: str, package: str, netlist_pins: dict[str, str],
          x: float = 0.0, y: float = 0.0, warnings: list[str] | None = None,
          mpn: str | None = None) -> Component:
    """Instantiate a footprint and bind nets to its pins."""
    if warnings is None:
        warnings = []
    pads_rel, cw, ch = PACKAGES[package]() if package in PACKAGES else (None, 0, 0)
    final_nets, unresolved, collisions, _ = resolve(package, netlist_pins, mpn)
    mapping, _ = pin_map(package, mpn, netlist_pins)
    for label in netlist_pins:
        targets = mapping.get(label.upper(), [])
        if label not in final_nets and len(targets) > 1:
            warnings.append(f"{ref} ({package}): {label.upper()} -> pins {targets} (both tied)")
    for label in unresolved:
        warnings.append(f"{ref} ({package}{', ' + mpn if mpn else ''}): no declared "
                        f"pinout for pin '{label}' — left unconnected, not guessed")
    for c in collisions:
        warnings.append(f"{ref} ({package}): {c}")

    shape = "rect" if package in SMD_PACKAGES else "th"
    pads = [Pad(ref, pin, x + px, y + py, pw, ph,
                final_nets.get(pin, ""), shape=shape)
            for (pin, px, py, pw, ph) in pads_rel]
    return Component(ref, x, y, courtyard_w=cw, courtyard_h=ch, pads=pads)


def pin_count(package: str) -> int:
    return len(PACKAGES[package]()[0])


if __name__ == "__main__":
    for mpn in ["ATMEGA328P-PU", "2N2222A", "1N4007", "CFR-25JB-52-10K",
                "SRD-05VDC-SL-C", "DHT22", "K104K15X7RF53H5", "MYSTERY-PART"]:
        pkg = guess(mpn)
        n = pin_count(pkg) if pkg else 0
        print(f"  {mpn:22s} -> {str(pkg):12s} {n:2d} pads")
