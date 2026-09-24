"""
Symbolic modified nodal analysis. Stage 4.

Builds the MNA system of a parsed netlist with sympy — node voltages plus one
branch current per voltage source — where each toleranced part is a symbol
and everything else an exact rational, and solves it. The results are
rational functions of the part values; `prover.py` hands them to z3.

Three views of one network, all from the same stamp:

- `dc()`       — operating point: capacitors open.
- `transfer()` — small-signal V(node) / V_source(ac) in the Laplace variable s.
- `thevenin()` — the source and resistance an element sees, with that element
                 removed (how the LED, the one nonlinear part, is handled).

Diodes cannot be stamped linearly; an analysis that meets one without being
told to remove it raises rather than guessing.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Iterable, List, Mapping, Optional, Tuple

import sympy

from proof.netlist import Element, Netlist

S = sympy.Symbol("s")


def _rational(value: Fraction) -> sympy.Rational:
    return sympy.Rational(value.numerator, value.denominator)


class System:
    """One stamped MNA system. `values` maps element name → sympy value."""

    def __init__(
        self,
        netlist: Netlist,
        values: Mapping[str, sympy.Expr],
        mode: str,
        exclude: Iterable[str] = (),
        zero_sources: bool = False,
        test_current: Optional[Tuple[str, str]] = None,
    ) -> None:
        excluded = {n.lower() for n in exclude}
        elements = [e for e in netlist.elements if e.name.lower() not in excluded]
        for e in elements:
            if e.kind == "D":
                raise ValueError(f"diode {e.name} cannot be stamped linearly; exclude it and use thevenin()")
        nodes: List[str] = []
        for e in elements:
            for n in (e.a, e.b):
                if n != "0" and n not in nodes:
                    nodes.append(n)
        if test_current:
            for n in test_current:
                if n != "0" and n not in nodes:
                    nodes.append(n)
        sources = [e for e in elements if e.kind == "V"]
        self.nodes = nodes
        self.sources = sources
        size = len(nodes) + len(sources)
        G = sympy.zeros(size, size)
        rhs = sympy.zeros(size, 1)
        idx = {n: i for i, n in enumerate(nodes)}

        def value(e: Element) -> sympy.Expr:
            if e.name in values:
                return values[e.name]
            return _rational(e.value)

        def stamp(a: str, b: str, y: sympy.Expr) -> None:
            if a != "0":
                G[idx[a], idx[a]] += y
            if b != "0":
                G[idx[b], idx[b]] += y
            if a != "0" and b != "0":
                G[idx[a], idx[b]] -= y
                G[idx[b], idx[a]] -= y

        for e in elements:
            if e.kind == "R":
                stamp(e.a, e.b, 1 / value(e))
            elif e.kind == "C" and mode == "ac":
                stamp(e.a, e.b, S * value(e))
            elif e.kind == "I":
                current = 0 if zero_sources else value(e)
                if e.a != "0":
                    rhs[idx[e.a]] -= current
                if e.b != "0":
                    rhs[idx[e.b]] += current
        for k, e in enumerate(sources):
            row = len(nodes) + k
            if e.a != "0":
                G[idx[e.a], row] += 1
                G[row, idx[e.a]] += 1
            if e.b != "0":
                G[idx[e.b], row] -= 1
                G[row, idx[e.b]] -= 1
            if zero_sources:
                rhs[row] = 0
            elif mode == "ac":
                rhs[row] = _rational(e.ac or Fraction(0))
            else:
                rhs[row] = _rational(e.value or Fraction(0))
        if test_current:
            a, b = test_current   # 1 A injected into a, out of b
            if a != "0":
                rhs[idx[a]] += 1
            if b != "0":
                rhs[idx[b]] -= 1

        solution = G.LUsolve(rhs)
        self._v = {n: solution[i] for i, n in enumerate(nodes)}
        self._i = {e.name.lower(): solution[len(nodes) + k] for k, e in enumerate(sources)}

    def v(self, node: str) -> sympy.Expr:
        node = node.lower()
        if node == "0":
            return sympy.Integer(0)
        return sympy.cancel(self._v[node])

    def i(self, source: str) -> sympy.Expr:
        """Current into the source's positive terminal (SPICE's sign)."""
        return sympy.cancel(self._i[source.lower()])


def dc(netlist: Netlist, values: Mapping[str, sympy.Expr], exclude: Iterable[str] = ()) -> System:
    return System(netlist, values, mode="dc", exclude=exclude)


def transfer(netlist: Netlist, values: Mapping[str, sympy.Expr], node: str) -> sympy.Expr:
    """V(node) per unit of the AC source, in s. The netlist's AC source drives it."""
    system = System(netlist, values, mode="ac")
    ac_sources = [e for e in netlist.elements if e.kind == "V" and e.ac]
    if len(ac_sources) != 1:
        raise ValueError("a transfer function needs exactly one AC source")
    return sympy.cancel(system.v(node) / _rational(ac_sources[0].ac))


def thevenin(
    netlist: Netlist, values: Mapping[str, sympy.Expr], a: str, b: str, remove: Iterable[str] = ()
) -> Tuple[sympy.Expr, sympy.Expr]:
    """(V_th, R_th) between nodes a and b, with `remove` taken out of the network."""
    open_circuit = System(netlist, values, mode="dc", exclude=remove)
    v_th = sympy.cancel(open_circuit.v(a) - open_circuit.v(b))
    test = System(netlist, values, mode="dc", exclude=remove, zero_sources=True, test_current=(a, b))
    r_th = sympy.cancel(test.v(a) - test.v(b))
    return v_th, r_th
