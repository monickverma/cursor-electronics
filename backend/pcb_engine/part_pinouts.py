"""
part_pinouts.py — a part's pinout, read from the KiCad symbol library by part number.

WHY THIS EXISTS
---------------
`footprints.py` and `verify.py` used to share one source for which pin goes on
which pad: `footprints.PINMAPS`, keyed by *package*. A package does not decide a
pinout. In the KiCad 10.0.1 library one SOT-23 footprint carries 39 different
pin assignments across 334 parts, TO-92 carries 30, SOIC-8 carries 298
(`reports/PCB verification implementation plan.md`, stage 1). A pinout written
wrong in PINMAPS was wrong in the generator and in its judge, and passed.

This module is the second witness: the KiCad symbol library, a transcription of
the manufacturer's datasheet made by other people, at another time, reviewed
against KiCad's library conventions. Agreement between it and the generator's
own map is trust level T1 — strong evidence, not proof: the library is itself a
transcription, and no error rate for it is published.

WHAT IT READS
-------------
The `.kicad_sym` files of a KiCad install, read in place at run time and never
copied. The libraries are CC-BY-SA 4.0 with a design exception; reading them to
check a design is inside the exception, redistributing a parsed copy is not
(https://www.kicad.org/libraries/license/). The only thing written to disk is an
index of symbol names to file offsets, kept in the user's cache directory.

Lookup is by orderable part number, in this order:
  1. exact symbol name                          "MAX485E"
  2. KiCad wildcard name ('x' = one character)  "MCP1700x-330xxTT"
  3. longest symbol name that prefixes the part number, where the next character
     of the part number is not a digit         "MMBT2222ALT1G" -> "MMBT2222A"
Symbols named with a package tag ("LM7805_TO220") match on the name before it.
Nothing found is None, never a guess. Two candidates with different pinouts is
an ambiguity, reported as such.

    KICAD_SYMBOL_DIR   the symbols folder, when it is not in a standard place
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Folders a KiCad install puts its symbols in, newest first.
_SEARCH = [
    r"C:\Program Files\KiCad\*\share\kicad\symbols",
    "/usr/share/kicad/symbols",
    "/usr/local/share/kicad/symbols",
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols",
]

# A generic Device symbol ("R", "C", "LED", "D") is a prefix of many part numbers
# and says nothing about any of them. A prefix match must be at least this long
# and contain a digit.
_MIN_PREFIX = 4

_TOP = re.compile(rb'^\t\(symbol "([^"]+)"', re.M)


# ─────────────────────────────────────────────────────────────────────────────
# Finding the library
# ─────────────────────────────────────────────────────────────────────────────
def symbol_dir() -> Path | None:
    env = os.environ.get("KICAD_SYMBOL_DIR")
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    for pattern in _SEARCH:
        hits = sorted(glob.glob(pattern), reverse=True)
        for h in hits:
            if Path(h).is_dir():
                return Path(h)
    return None


def _cache_file(d: Path) -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    tag = hashlib.sha256(str(d.resolve()).encode()).hexdigest()[:12]
    return base / "circuit_os" / f"kicad_sym_index_{tag}.json"


def _stamp(d: Path) -> list:
    return sorted([f.name, f.stat().st_size, int(f.stat().st_mtime)]
                  for f in d.glob("*.kicad_sym"))


@lru_cache(maxsize=4)
def _index(d: Path) -> dict[str, list[tuple[str, int]]]:
    """Symbol name -> [(file name, byte offset)], every top-level symbol in `d`.

    Scanning 230 MB of libraries takes seconds, so the index is cached on disk
    and rebuilt when any library file's size or time changes."""
    stamp = _stamp(d)
    cache = _cache_file(d)
    try:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if saved.get("stamp") == stamp:
            return {k: [tuple(v) for v in vs] for k, vs in saved["index"].items()}
    except (OSError, ValueError, KeyError):
        pass

    index: dict[str, list[tuple[str, int]]] = {}
    for name, _, _ in stamp:
        data = (d / name).read_bytes()
        for m in _TOP.finditer(data):
            index.setdefault(m.group(1).decode("utf-8"), []).append((name, m.start()))
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"stamp": stamp, "index": index}), encoding="utf-8")
    except OSError:
        pass                                      # a read-only home costs time, not truth
    return index


# ─────────────────────────────────────────────────────────────────────────────
# Reading one symbol
# ─────────────────────────────────────────────────────────────────────────────
_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def _parse(text: str):
    """One s-expression, as nested lists of strings. Quoted atoms lose quotes."""
    stack: list[list] = [[]]
    for tok in _TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
            if len(stack) == 1:
                return done
        elif tok.startswith('"'):
            stack[-1].append(tok[1:-1].replace('\\"', '"'))
        else:
            stack[-1].append(tok)
    raise ValueError("unbalanced s-expression")


def _block(path: Path, offset: int) -> list:
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = b""
        depth = 0
        while True:
            more = f.read(65536)
            if not more:
                raise ValueError(f"symbol at {path.name}:{offset} never closes")
            start = len(chunk)
            chunk += more
            for i in range(start, len(chunk)):
                c = chunk[i]
                if c == 0x28:
                    depth += 1
                elif c == 0x29:
                    depth -= 1
                    if depth == 0:
                        return _parse(chunk[:i + 1].decode("utf-8"))


def _child(node: list, key: str) -> list | None:
    for x in node[1:]:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def _properties(node: list) -> dict[str, str]:
    return {x[1]: x[2] for x in node[1:]
            if isinstance(x, list) and len(x) > 2 and x[0] == "property"}


def _pins(node: list) -> dict[str, str]:
    """Pin number -> pin name over every unit of a symbol. A pin drawn in two
    units (a shared supply) keeps the first name seen."""
    out: dict[str, str] = {}

    def walk(n):
        for x in n[1:]:
            if not isinstance(x, list) or not x:
                continue
            if x[0] == "pin":
                name = _child(x, "name")
                num = _child(x, "number")
                if num is not None and len(num) > 1:
                    out.setdefault(num[1], name[1] if name and len(name) > 1 else "")
            elif x[0] == "symbol":
                walk(x)
    walk(node)
    return out


@dataclass(frozen=True)
class Symbol:
    name: str
    library: str                  # file name, e.g. "Interface_UART.kicad_sym"
    pins: dict                    # pin number -> name as written ("~{RE}")
    footprint: str                # default footprint, "" when the library gives none
    datasheet: str
    chain: tuple = ()             # the extends chain, child first
    sha256: str = ""              # of the library file the pins were read from

    def cite(self) -> str:
        via = f" (extends {' -> '.join(self.chain[1:])})" if len(self.chain) > 1 else ""
        return f"KiCad {self.library.removesuffix('.kicad_sym')}:{self.name}{via}"


@lru_cache(maxsize=1024)
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(d: Path, name: str, seen: tuple = ()) -> Symbol | None:
    hits = _index(d).get(name)
    if not hits:
        return None
    lib, off = hits[0]
    node = _block(d / lib, off)
    props = _properties(node)
    parent = _child(node, "extends")
    if parent is not None and len(parent) > 1:
        if parent[1] in seen or len(seen) > 8:
            raise ValueError(f"extends cycle at {name}")
        base = _load(d, parent[1], seen + (name,))
        if base is None:
            return None
        # Pins are inherited; properties are the derived symbol's own. An empty
        # Footprint on MAX485E means "no default", not "the parent's SOIC-8".
        return Symbol(name, lib, dict(base.pins),
                      props.get("Footprint", base.footprint),
                      props.get("Datasheet", base.datasheet),
                      (name,) + base.chain, base.sha256)
    return Symbol(name, lib, _pins(node), props.get("Footprint", ""),
                  props.get("Datasheet", ""), (name,), _sha(d / lib))


# ─────────────────────────────────────────────────────────────────────────────
# Part number -> symbol
# ─────────────────────────────────────────────────────────────────────────────
def _norm_mpn(mpn: str) -> str:
    """Upper case, without the characters ordering codes add and KiCad names
    drop: "MCP1700T-3302E/TT" -> "MCP1700T-3302ETT", "MAX485ECSA+T" -> "MAX485ECSAT"."""
    return re.sub(r"[/+#\s]", "", mpn.upper())


def _base(name: str) -> str:
    """"LM7805_TO220" -> "LM7805"; a name without a package tag is itself."""
    return name.split("_", 1)[0]


def _wild(name: str) -> re.Pattern | None:
    """A pattern for a wildcard part name, or None. Only an 'x' in the part
    name counts: "R_Network_Dividers_x02_SIP" is the generic "R" with a tag, and
    a generic name must not match every part number that starts with R."""
    b = _base(name)
    if "x" not in b or len(b) < _MIN_PREFIX or not any(c.isdigit() for c in b):
        return None
    parts = [re.escape(ch.upper()) if ch != "x" else "[A-Z0-9]" for ch in b]
    return re.compile("".join(parts) + r"(?![0-9])")


@lru_cache(maxsize=4)
def _matchers(d: Path):
    """The index arranged for the three lookups: normalised name -> names,
    wildcard patterns, and the base names long enough to match as prefixes."""
    exact: dict[str, list[str]] = {}
    wild, bases = [], []
    for n in _index(d):
        exact.setdefault(_norm_mpn(n), []).append(n)
        pat = _wild(n)
        if pat is not None:
            wild.append((n, pat))
            continue
        b = _norm_mpn(_base(n))
        if len(b) >= _MIN_PREFIX and any(c.isdigit() for c in b):
            bases.append((n, b))
    return exact, wild, bases


@dataclass
class Lookup:
    mpn: str
    symbol: Symbol | None = None
    how: str = ""                 # "exact" | "wildcard" | "prefix"
    reason: str = ""              # why there is no symbol
    candidates: list = field(default_factory=list)


def lookup(mpn: str, package: str | None = None) -> Lookup:
    """The KiCad symbol for an orderable part number, or why there is none.

    `package` (a footprints.py package name) chooses between symbols that share
    a base name and differ only in package tag, e.g. "LM7805_TO220"."""
    if not mpn:
        return Lookup(mpn, reason="no part number")
    d = symbol_dir()
    if d is None:
        return Lookup(mpn, reason="KiCad symbol library not found "
                                  "(install KiCad or set KICAD_SYMBOL_DIR)")
    exact_names, wild_pats, bases = _matchers(d)
    want = _norm_mpn(mpn)

    exact = exact_names.get(want)
    if exact:
        return _choose(d, mpn, exact, "exact", package)

    wild = [n for n, pat in wild_pats if pat.match(want)]
    prefix = [n for n, b in bases
              if want.startswith(b) and not want[len(b):len(b) + 1].isdigit()]
    if wild:
        return _choose(d, mpn, wild, "wildcard", package)
    if prefix:
        longest = max(len(_norm_mpn(_base(n))) for n in prefix)
        return _choose(d, mpn, [n for n in prefix
                                if len(_norm_mpn(_base(n))) == longest], "prefix", package)
    return Lookup(mpn, reason=f"no KiCad symbol is named for {mpn!r}")


def _choose(d: Path, mpn: str, names: list[str], how: str,
            package: str | None) -> Lookup:
    syms = [s for s in (_load(d, n) for n in sorted(names)) if s is not None]
    if not syms:
        return Lookup(mpn, reason=f"symbol {names[0]!r} could not be read")
    if package and len(syms) > 1:
        fitting = [s for s in syms if footprint_package(s.footprint) == package]
        syms = fitting or syms
    pinouts = {tuple(sorted(s.pins.items())) for s in syms}
    if len(pinouts) > 1:
        return Lookup(mpn, how=how, candidates=[s.cite() for s in syms],
                      reason=f"{len(syms)} KiCad symbols match {mpn!r} with "
                             f"different pinouts: " + ", ".join(s.name for s in syms))
    return Lookup(mpn, symbol=syms[0], how=how, candidates=[s.cite() for s in syms])


# ─────────────────────────────────────────────────────────────────────────────
# Comparing names
# ─────────────────────────────────────────────────────────────────────────────
# Names that mean the same pin. Kept narrow on purpose: a synonym that is too
# generous makes two different pins agree. VIN is a regulator's input, not an
# IC's supply, so it is not with VCC.
_SYNONYMS = [
    {"VCC", "VDD", "V+", "VS", "+VS"},
    {"GND", "VSS", "V-", "GND_PAD"},
    {"VI", "VIN", "IN"},
    {"VO", "VOUT", "OUT"},
    {"K", "CATHODE"},
    {"A", "ANODE"},
    {"B", "BASE"}, {"C", "COLLECTOR"}, {"E", "EMITTER"},
    {"G", "GATE"}, {"S", "SOURCE"}, {"D", "DRAIN"},
    {"DATA", "DQ", "SDA_DATA"},
    {"RESET", "RST"},
]

# Arduino Uno names for ATmega328P port pins, so a netlist written against the
# board ("D13") can be compared with a symbol written against the chip ("PB5").
_ARDUINO_UNO = {
    **{f"D{i}": f"PD{i}" for i in range(8)},
    **{f"D{8 + i}": f"PB{i}" for i in range(6)},
    **{f"A{i}": f"PC{i}" for i in range(6)},
    "D0_RX": "PD0", "D1_TX": "PD1", "RXD": "PD0", "TXD": "PD1",
    "SDA": "PC4", "SCL": "PC5", "XTAL1": "PB6", "XTAL2": "PB7",
    "AVCC": "AVCC", "AREF": "AREF",
}


def norm_name(name: str) -> str:
    """"~{RE}" -> "RE", "V_{IN}" -> "VIN", upper case."""
    return re.sub(r"[~{}_\s]", "", name).upper() if name else ""


_UNO_NORM = {norm_name(k): v for k, v in _ARDUINO_UNO.items()}


def _aliases(kicad_name: str) -> set[str]:
    """Every name a KiCad pin answers to: "PC6/~{RESET}" -> {"PC6", "RESET"}."""
    out = set()
    for part in kicad_name.split("/"):
        n = norm_name(part)
        if n:
            out.add(n)
            for group in _SYNONYMS:
                if n in group:
                    out |= group
    return out


def pads_for(symbol: Symbol, label: str) -> list[str] | None:
    """The pad numbers the KiCad symbol gives a netlist pin label, or None when
    no pin of the symbol answers to it."""
    want = norm_name(label)
    if symbol.name.upper().startswith("ATMEGA328P"):
        want = _UNO_NORM.get(want, want)
    names = {want}
    for group in _SYNONYMS:
        if want in group:
            names |= group
    pads = [num for num, nm in symbol.pins.items() if _aliases(nm) & names]
    return sorted(pads, key=lambda p: (len(p), p)) or None


def footprint_package(fp: str) -> str | None:
    """A KiCad default footprint ("Package_TO_SOT_SMD:SOT-23") as a footprints.py
    package name, or None when this file has no such package."""
    if not fp:
        return None
    name = fp.split(":", 1)[-1].upper()
    rules = [
        (r"^SOT-23(_|$)", "SOT-23"),
        (r"^TO-92", "TO-92"),
        (r"^TO-220-3", "TO-220"),
        (r"^D_SOD-123(_|$)", "SOD-123"),
        (r"^D_DO-41", "DO-41"),
        (r"^SOIC-(\d+)_", None),
        (r"^DIP-(\d+)_", None),
    ]
    for pat, pkg in rules:
        m = re.match(pat, name)
        if m:
            if pkg:
                return pkg
            return ("SOIC-" if name.startswith("SOIC") else "DIP-") + m.group(1)
    m = re.match(r"^(?:R|C|L|LED|D)_(0402|0603|0805|1206|1210)_", name)
    if m:
        return m.group(1)
    return None
