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
}


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
    }
}


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

    pads = [Pad(ref, pin, x + px, y + py, pw, ph,
                final_nets.get(pin, ""), shape="th")
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
