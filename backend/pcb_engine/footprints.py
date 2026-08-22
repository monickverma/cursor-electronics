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


def _soic(npins: int, row: float = 5.40, pitch: float = 1.27,
          pad_w: float = 0.60, pad_h: float = 1.50):
    """SOIC, narrow body. Pin order matches _dip: 1..n/2 up the left, then back
    down the right, so pin 1 and pin n sit on the same row."""
    per = npins // 2
    span = (per - 1) * pitch
    out = []
    for i in range(per):
        out.append((str(i + 1), -row / 2, -span / 2 + i * pitch, pad_w, pad_h))
    for i in range(per):
        out.append((str(npins - i), row / 2, -span / 2 + i * pitch, pad_w, pad_h))
    return out, row + pad_w + 0.5, span + pad_h + 0.5


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
    "SOT-23", "SOIC-8", "SOIC-14", "SOIC-16",
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
    (r"DHT(11|22)|AM2302",          "HEADER-4"),
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
    m = re.fullmatch(r"SOIC-?(\d+)", p)
    if m: return f"SOIC-{m.group(1)}"

    
    m = re.search(r"(\d+)-PIN", p)
    if m: return f"HEADER-{m.group(1)}"
    m = re.search(r"SIP-(\d+)", p)
    if m: return f"HEADER-{m.group(1)}"
    m = re.search(r"DIP-(\d+)", p)
    if m: return f"DIP-{m.group(1)}"
    return p


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


PINMAPS = {
    "DIP-28": {
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
    },
    "TO-92": {
        "EMITTER": ["1"], "E": ["1"],
        "BASE": ["2"], "B": ["2"],
        "COLLECTOR": ["3"], "C": ["3"],
    },
    "DO-41": {
        "ANODE": ["1"], "A": ["1"],
        "CATHODE": ["2"], "K": ["2"],
    },
    "RELAY-SRD": {
        "COIL1": ["1"], "COIL_A": ["1"],
        "COIL2": ["2"], "COIL_B": ["2"],
        "COM": ["3"],
        "NC": ["4"],
        "NO": ["5"],
    },
    "HEADER-4": {
        "VCC": ["1"],
        "DATA": ["2"],
        "NC": ["3"],
        "GND": ["4"],
    },
}

# Two-terminal parts are symmetric, so these names only need to be consistent,
# not correct in an absolute sense — except for polarised parts, where pad 1 is
# anode/positive by convention.
_TWO_TERMINAL = {
    "A": ["1"], "B": ["2"],
    "+": ["1"], "-": ["2"],
    "P": ["1"], "N": ["2"],
    "ANODE": ["1"], "CATHODE": ["2"], "K": ["2"],
}
for _pkg in ("0402", "0603", "0805", "1206", "1210", "AXIAL", "RADIAL-2"):
    PINMAPS.setdefault(_pkg, dict(_TWO_TERMINAL))

# NOTE: no PINMAPS entry for SOIC-8. Pin 1 is RO on a MAX485 and an output on an
# op-amp; there is no package-wide truth. build() falls back to free-pad
# assignment and warns, which is the honest behaviour this file already chose
# ("a missing footprint is a question you can ask the user, a wrong footprint is
# a board that arrives unusable"). Per-part pinmaps are the real fix.


def build(ref: str, package: str, netlist_pins: dict[str, str],
          x: float = 0.0, y: float = 0.0, warnings: list[str] | None = None) -> Component:
    """Instantiate a footprint and bind nets to its pins."""
    if warnings is None:
        warnings = []
    if package not in PACKAGES:
        raise KeyError(f"no footprint for package {package!r}")
    pads_rel, cw, ch = PACKAGES[package]()
    
    final_nets: dict[str, str] = {}
    avail_pads = [p[0] for p in pads_rel]
    unmapped_labels = []
    
    mapping = PINMAPS.get(package, {})
    
    for label, net in netlist_pins.items():
        if label in avail_pads:
            final_nets[label] = net
            continue
            
        label_upper = label.upper()
        if label_upper in mapping:
            targets = mapping[label_upper]
            for t in targets:
                if t in avail_pads:
                    final_nets[t] = net
            if len(targets) > 1:
                warnings.append(f"{ref} ({package}): {label_upper} -> pins {targets} (both tied)")
            continue
            
        unmapped_labels.append((label, net))
        
    for label, net in unmapped_labels:
        used = set(final_nets.keys())
        free = [p for p in avail_pads if p not in used]
        if free:
            assigned = free[0]
            final_nets[assigned] = net
            warnings.append(f"{ref} ({package}): assigned unknown pin '{label}' to free pad {assigned}")
        else:
            warnings.append(f"{ref} ({package}): nowhere to connect pin '{label}'")

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
