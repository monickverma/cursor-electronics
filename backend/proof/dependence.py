"""
Which MCU model elements a quantity depends on, and which nodes it measures.

`brain/decisions.md` [2026-09-24] D1, D2, D7: D2 is cited on a claim only where
the real microcontroller can reach it. The first of the three routes is model
dependence — the quantity changes when an MCU model element's value changes —
and it is decided here exactly. The design's own netlist is stamped with every
MCU model element's value as a free symbol, and the quantity's expression is
read for those symbols:

- `R_MCU_<id>`  — the supply-load resistor (`mcu_as_<R>R`)
- `R_PIN_<node>`, `V_PIN_<node>` — the Thevenin output pin (`mcu_pin_thevenin`)

**A diode stands in as a resistor of unknown value.** A diode cannot be
stamped linearly, and it does not need to be: how an operating point moves
when an element moves is the response of the incremental network — the same
network with the diode replaced by its incremental resistance, whatever that
is. The symbolic network *is* that network at every resistance at once, so a
quantity it shows free of an element is free of it at every operating point.
The stand-in can only over-report dependence, never miss it — the safe side
for a defeater.

The other two routes — an MCU pin the netlist does not model on a measured
node, and an assumed pin state — need the design graph, not the netlist, and
live in `validation/claims.py`. This module stays netlist-only.
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import lru_cache
from typing import FrozenSet, List, Sequence, Tuple

import sympy

from proof import mna
from proof.netlist import Element, Netlist, parse

#: Element name prefixes of the MCU's electrical models in a netlist.
MCU_ELEMENT_PREFIXES = ("R_MCU_", "R_PIN_", "V_PIN_")


def is_mcu_element(name: str) -> bool:
    return name.upper().startswith(MCU_ELEMENT_PREFIXES)


def _quantity(quantity: str) -> Tuple[str, List[str]]:
    from proof.prover import _args  # the one grammar; the prover owns it

    return _args(quantity)


def _symbol(name: str) -> sympy.Symbol:
    return sympy.Symbol("DEP_" + re.sub(r"[^A-Za-z0-9_]", "_", name), positive=True)


def _with_stand_ins(netlist: Netlist) -> Tuple[Netlist, dict]:
    """Every diode as a resistor of unknown value, so the network stamps linearly."""
    elements, values = [], {}
    for e in netlist.elements:
        if e.kind == "D":
            elements.append(Element(kind="R", name=e.name, a=e.a, b=e.b, value=Fraction(1)))
            values[e.name] = _symbol(e.name)
        else:
            elements.append(e)
    return Netlist(elements=elements, diode_models=dict(netlist.diode_models), analysis=netlist.analysis), values


def _terminals(netlist: Netlist, name: str) -> Tuple[str, str]:
    e = netlist.element(name)
    return e.a, e.b


def measured_nodes(netlist_text: str, quantity: str, bench: Sequence[str] = ()) -> FrozenSet[str]:
    """The nodes a quantity reads — its probe nodes, or the terminals of the element it is about."""
    netlist = parse(netlist_text).with_bench(list(bench))
    kind, args = _quantity(quantity)
    if kind in ("v", "cutoff"):
        nodes = [args[0]]
    elif kind in ("vdiff", "rth"):
        nodes = list(args[:2])
    elif kind == "rise_time":
        nodes = [args[0]]
    elif kind in ("i", "power", "diode_current"):
        nodes = list(_terminals(netlist, args[0]))
    elif kind == "series_power":
        nodes = list(_terminals(netlist, args[0])) + list(_terminals(netlist, args[1]))
    else:  # pragma: no cover - `_quantity` refuses anything else
        raise ValueError(f"unsupported quantity {quantity!r}")
    return frozenset(n.lower() for n in nodes if n != "0")


@lru_cache(maxsize=4096)
def _reached(netlist_text: str, quantity: str, bench: Tuple[str, ...]) -> Tuple[str, ...]:
    netlist, values = _with_stand_ins(parse(netlist_text).with_bench(list(bench)))
    mcu = {e.name: _symbol(e.name) for e in netlist.elements
           if is_mcu_element(e.name) and e.kind in ("R", "V")}
    values.update(mcu)
    kind, args = _quantity(quantity)
    known = {n.lower() for n in netlist.nodes()} | {"0"}
    probes = {"v": args[:1], "vdiff": args[:2], "rth": args[:2], "cutoff": args[:1], "rise_time": args[:1]}
    for node in probes.get(kind, []):
        if node.lower() not in known:
            raise KeyError(f"{quantity}: no node {node} in the netlist")

    if kind in ("v", "vdiff", "i", "power"):
        system = mna.dc(netlist, values, solver="domain")
        if kind == "v":
            exprs = [system.v(args[0])]
        elif kind == "vdiff":
            exprs = [system.v(args[0]) - system.v(args[1])]
        elif kind == "i":
            exprs = [system.i(args[0])]
        else:
            a, b = _terminals(netlist, args[0])
            exprs = [system.v(a) - system.v(b), values.get(netlist.element(args[0]).name, sympy.Integer(1))]
    elif kind == "rth":
        exprs = [mna.thevenin(netlist, values, args[0], args[1] if len(args) > 1 else "0", solver="domain")[1]]
    elif kind == "cutoff":
        exprs = [mna.transfer(netlist, values, args[0], solver="domain")]
    elif kind == "rise_time":
        node, cap = args
        _, r_th = mna.thevenin(netlist, values, node, "0", remove=[cap], solver="domain")
        exprs = [r_th, values.get(netlist.element(cap).name, sympy.Integer(1))]
    else:  # diode_current, series_power — the Thevenin network the diode sees
        diode = args[0] if kind == "diode_current" else args[1]
        anode, cathode = _terminals(netlist, diode)
        exprs = list(mna.thevenin(netlist, values, anode, cathode, remove=[diode], solver="domain"))
        if kind == "series_power":
            exprs.append(values.get(netlist.element(args[0]).name, sympy.Integer(1)))
    free = set()
    for expr in exprs:
        free |= sympy.sympify(expr).free_symbols
    return tuple(sorted(name for name, sym in mcu.items() if sym in free))


def mcu_elements_reached(netlist_text: str, quantity: str, bench: Sequence[str] = ()) -> Tuple[str, ...]:
    """
    The MCU model elements whose value the quantity depends on, by name.

    Raises `KeyError` for a quantity naming a node or element the netlist does
    not have — a claim declaring something it does not measure is a generator
    bug, surfaced rather than read as independence.
    """
    return _reached(netlist_text, quantity, tuple(bench))
