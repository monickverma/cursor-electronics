"""
Reading a design's SPICE netlist back into elements. Stage 4.

The proof compiler proves properties of **the netlist ngspice is given** — the
artifact the design actually ships as — so it parses the text
`generators/netlist/spice.py` emits rather than re-deriving elements from
CircuitIR a second way. Only the forms that emitter produces are accepted;
anything else raises, because a line the prover silently skipped would be a
component the proof silently ignored.

Values are exact `Fraction`s. `1.0000000000000001e-07` is read as the rational
the float denotes, not rounded to 100n: the proof is about the netlist as
written, digit for digit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

_SUFFIX = {"T": 12, "G": 9, "MEG": 6, "K": 3, "M": -3, "U": -6, "N": -9, "P": -12, "F": -15}
_NUMBER = re.compile(r"^([+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)(MEG|[TGKMUNPF])?$", re.IGNORECASE)


def spice_value(text: str) -> Fraction:
    """`1G` → 10⁹, `4.7k` → 4700, `1e-07` → exactly the float's rational."""
    m = _NUMBER.match(text.strip())
    if not m:
        raise ValueError(f"not a SPICE number: {text!r}")
    number = m.group(1).lower()
    if "e" in number:
        # Exactly the decimal written, never via a float.
        mantissa, exponent = number.split("e")
        base = Fraction(mantissa) * (Fraction(10) ** int(exponent))
    else:
        base = Fraction(number)
    suffix = (m.group(2) or "").upper()
    return base * (Fraction(10) ** _SUFFIX[suffix]) if suffix else base


@dataclass(frozen=True)
class Element:
    kind: str                 # R, C, V, I, D
    name: str                 # as written, e.g. R_R1
    a: str                    # first node (lowercase; "0" is ground)
    b: str
    value: Optional[Fraction] = None   # R ohms, C farads, V/I DC value
    ac: Optional[Fraction] = None      # AC magnitude of a source
    model: Optional[str] = None        # diode model name


@dataclass
class Netlist:
    elements: List[Element] = field(default_factory=list)
    diode_models: Dict[str, Tuple[Fraction, Fraction]] = field(default_factory=dict)  # name -> (Is, N)
    analysis: Optional[str] = None     # "op", "ac", "tran"

    def element(self, name: str) -> Element:
        for e in self.elements:
            if e.name.lower() == name.lower():
                return e
        raise KeyError(f"no element {name} in the netlist")

    def nodes(self) -> List[str]:
        seen: List[str] = []
        for e in self.elements:
            for n in (e.a, e.b):
                if n != "0" and n not in seen:
                    seen.append(n)
        return seen

    def with_bench(self, lines: List[str]) -> "Netlist":
        """A copy with test-bench elements appended (CI probes, loads)."""
        extra = parse("\n".join(lines + [".end"]), allow_partial=True)
        return Netlist(
            elements=self.elements + extra.elements,
            diode_models={**self.diode_models, **extra.diode_models},
            analysis=self.analysis,
        )


_MODEL = re.compile(r"^\.model\s+(\S+)\s+D\s*\((.*)\)\s*$", re.IGNORECASE)


def _model_params(body: str) -> Tuple[Fraction, Fraction]:
    params = {}
    for token in body.split():
        if "=" in token:
            key, value = token.split("=", 1)
            params[key.strip().lower()] = spice_value(value)
    return params.get("is", Fraction(1, 10**14)), params.get("n", Fraction(1))


def parse(text: str, allow_partial: bool = False) -> Netlist:
    netlist = Netlist()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        low = line.lower()
        if low.startswith(".model"):
            m = _MODEL.match(line)
            if not m:
                raise ValueError(f"unsupported model line: {line!r}")
            netlist.diode_models[m.group(1).upper()] = _model_params(m.group(2))
            continue
        if low.startswith(".op"):
            netlist.analysis = "op"
            continue
        if low.startswith(".ac"):
            netlist.analysis = "ac"
            continue
        if low.startswith(".tran"):
            netlist.analysis = "tran"
            continue
        if low.startswith((".print", ".end", ".options", ".temp")):
            continue
        parts = line.split()
        kind = parts[0][0].upper()
        name, a, b = parts[0], parts[1].lower(), parts[2].lower()
        if kind in ("R", "C"):
            netlist.elements.append(Element(kind, name, a, b, value=spice_value(parts[3])))
        elif kind in ("V", "I"):
            # "V_X n 0 DC 5.0" or "V_X n 0 AC 5.0"
            mode = parts[3].upper() if len(parts) > 3 else "DC"
            val = spice_value(parts[4]) if len(parts) > 4 else Fraction(0)
            if mode == "DC":
                netlist.elements.append(Element(kind, name, a, b, value=val))
            elif mode == "AC":
                netlist.elements.append(Element(kind, name, a, b, value=Fraction(0), ac=val))
            else:
                raise ValueError(f"unsupported source form: {line!r}")
        elif kind == "D":
            netlist.elements.append(Element("D", name, a, b, model=parts[3].upper()))
        else:
            raise ValueError(f"element kind {kind!r} is not supported by the prover: {line!r}")
    for e in netlist.elements:
        if e.kind == "D" and e.model not in netlist.diode_models and not allow_partial:
            raise ValueError(f"diode {e.name} uses undefined model {e.model}")
    return netlist
