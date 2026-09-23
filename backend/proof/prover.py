"""
Compiling a property against a design, and deciding it. Stage 4.

    PropertySpec ──compile──▶ Statement (frozen, hashed, English)
                               + Problem  (obligations, derived from the Statement)
                                     │
                          refine loop: strategies ──▶ ProofResult
                          (each result must be for the frozen hashes, or it raises)

**Compile.** The design's netlist is parsed (plus any bench elements the
property adds), every toleranced part becomes a variable over its box, and
symbolic nodal analysis gives the quantity as a rational function of those
variables. π and logarithms enter as rigorous rational brackets.

**Obligations.** Each property becomes one or two inequalities "∀ box: e ≥ b"
or "e ≤ b". z3 is asked for a counterexample to each; UNSAT is a proof.
Reductions that need a precondition — the LED's monotone reduction needs
R_th > 0 and V_th > 0 — carry it as a *lemma*, proved the same way; a failed
lemma makes the result `unknown`, never `proven`.

**A refutation is certified, never inferred.** An obligation with a bracket
in it is a relaxation: a z3 counterexample can sit inside the bracket's slack
(a π a hair off π), so it carries a *refuter* — the same inequality with every
bracket collapsed to its adverse end — and only a counterexample to that is
reported as one. The LED dissipation proof goes through a current bound, so a
point where the bound fails is not yet a point where the dissipation does; a
witness check evaluates the dissipation there exactly. What cannot be
certified either way is `unknown`.

**The refine loop cannot weaken a frozen property.** Strategies run in order —
direct decision, then box bisection when z3 says *unknown*. Each returns the
hash of the statement it proved, the hash of every obligation it discharged,
and a *certificate*: for each obligation, the boxes it was decided UNSAT on.
The loop trusts none of it. It checks the hashes against ones it computed
before any strategy ran; it checks the certificate's boxes tile the frozen
box exactly (inside it, interiors disjoint, volumes summing to its volume);
and it re-decides every certificate box itself against the frozen
obligation. A strategy that proves anything else — a looser bound, one
obligation fewer, a smaller box — raises `FrozenPropertyViolation`. Stage 4's
adversarial weakening gate is that exception. (Found by the Stage 3 + 4
verification: the loop once checked hashes only, and a strategy that decided
the nominal point alone was accepted as a proof over the whole box.)

**Every denominator is proved non-zero.** z3 reads x/0 as an unconstrained
value, so a quantity whose denominator could vanish in the box could be
"proved" by that value. Each distinct denominator becomes a lemma, decided
like any other; if it fails, the property is `unknown`.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import sympy
import z3
from pydantic import BaseModel, ConfigDict

from core.ir_schema import CircuitIR, ComponentType
from data.component_constraints import get_constraints
from generators.netlist.models import MODEL_MCU_PIN, MODEL_MCU_SUPPLY
from proof import brackets, mna
from proof.netlist import Netlist, parse
from proof.properties import PropertySpec, Statement, Variable, back_translate, si

#: Exact thermal voltage at ngspice's 27 °C: k and q are exact SI constants.
VT = Fraction("1.380649e-23") * Fraction("300.15") / Fraction("1.602176634e-19")
Z3_TIMEOUT_MS = 5000
BISECT_DEPTH = 4

#: The quantities a PropertySpec may name.
QUANTITIES = ("v", "vdiff", "i", "power", "series_power", "rth", "cutoff", "diode_current", "rise_time")


class FrozenPropertyViolation(Exception):
    """A refine strategy returned a result for something other than the frozen property."""


class Obligation(BaseModel):
    """∀ variables in their boxes (and bracket variables in theirs): expr OP bound."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    label: str
    expr: str                      # sympy srepr, so the obligation is data
    op: str                        # "ge" | "le" | "gt" | "ne"
    bound: str                     # sympy srepr
    brackets: Tuple[Tuple[str, str, str], ...] = ()   # (name, lo, hi) as exact fraction strings
    lemma: bool = False
    #: A counterexample to an exact obligation is a counterexample to the
    #: property. One with a bracket or an enclosure in it is not, by itself.
    exact: bool = True
    #: For an inexact obligation: an inequality whose counterexample *does*
    #: certify the property false — brackets collapsed to their adverse ends.
    refute: Optional["Obligation"] = None

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()


Obligation.model_rebuild()


class SeriesPowerWitness(BaseModel):
    """
    What it takes to certify P = I²·R > P_max at one point, exactly: with
    c = ⌈√(P_max/R)⌉, show g(c) < V_th, so I > c and I²·R > P_max. I_s is
    taken *inside* its box, at the high-current end.
    """

    model_config = ConfigDict(frozen=True)

    r_th: str                      # srepr
    v_th: str                      # srepr
    resistance: str                # srepr: the symbol, or the exact value
    p_max: str                     # exact fraction string
    nvt: str
    is_inner: str


class Problem(BaseModel):
    model_config = ConfigDict(frozen=True)

    obligations: Tuple[Obligation, ...]
    method: str                    # z3_unsat | sound_enclosure
    witness: Optional[SeriesPowerWitness] = None


class ProofResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    property_id: str
    statement_hash: str
    status: str                    # proven | refuted | unknown
    method: str
    strategy: str
    discharged: Tuple[str, ...] = ()      # obligation hashes
    counterexample: Optional[Dict[str, str]] = None
    detail: str = ""
    #: Per discharged obligation hash, the boxes it was decided UNSAT on —
    #: each box as ((variable, lo, hi), …) with exact fraction strings.
    certificate: Tuple[Tuple[str, Tuple[Tuple[Tuple[str, str, str], ...], ...]], ...] = ()


# ── Boxes: what each part may be ─────────────────────────────────────────────

_CAP_CODES = {"F": Fraction(1, 100), "G": Fraction(2, 100), "J": Fraction(5, 100),
              "K": Fraction(10, 100), "M": Fraction(20, 100)}


def resistor_tolerance(part: str) -> Tuple[Fraction, str]:
    m = re.match(r"^RC\d{4}([FJ])R", part or "")
    if m:
        return (Fraction(1, 100), "1% resistor") if m.group(1) == "F" else (Fraction(5, 100), "5% resistor")
    return Fraction(5, 100), "untabulated resistor, taken as 5%"


def capacitor_tolerance(part: str) -> Tuple[Fraction, str]:
    m = re.match(r"^CL\d\d[A-Z]\d{3}([A-Z])", part or "")
    if m and m.group(1) in _CAP_CODES:
        tol = _CAP_CODES[m.group(1)]
        return tol, f"{int(tol * 100)}% capacitor"
    return Fraction(20, 100), "untabulated capacitor, taken as 20%"


def part_value(value: Fraction) -> Fraction:
    """
    The part a netlist value stands for: the value to 12 significant figures.
    The SPICE writer prints 47 nF as 4.7000000000000004e-08 — binary noise, not
    a part — and a tolerance box centred on the noise would print as
    "42.31 nF" in the sentence a person signs. The box is the part's.
    """
    if value == 0:
        return value
    rounded = Decimal(value.numerator) / Decimal(value.denominator)
    exponent = rounded.adjusted() - 11
    return Fraction(rounded.quantize(Decimal(1).scaleb(exponent)))


def _symbol(name: str) -> sympy.Symbol:
    return sympy.Symbol(re.sub(r"[^A-Za-z0-9_]", "_", name), positive=True)


def part_variables(circuit: CircuitIR, netlist: Netlist, bench) -> Tuple[Dict[str, Variable], bool, Tuple[str, ...]]:
    """Every toleranced element as a Variable, plus datasheet use and MCU models."""
    components = {c.id: c for c in circuit.components}
    out: Dict[str, Variable] = {}
    datasheet = False
    models: List[str] = []
    for e in netlist.elements:
        name = e.name
        if e.kind == "R" and name.upper().startswith("R_MCU_"):
            models.append(MODEL_MCU_SUPPLY)
            continue
        if e.kind == "R" and name.upper().startswith("R_PIN_"):
            node = name[len("R_PIN_"):].lower()
            driver = next((c for c in circuit.connections if c.node_id.lower() == node
                           and components.get(c.component_id) is not None
                           and components[c.component_id].type == ComponentType.MICROCONTROLLER), None)
            table = (get_constraints(components[driver.component_id].part_number) or {}).get(
                "gpio_output_resistance_ohm") if driver else None
            if table:
                out[name] = Variable(element=name, label=f"{driver.component_id} pin resistance",
                                     lo=str(Fraction(str(table["min"]))), hi=str(Fraction(str(table["max"]))),
                                     nominal=str(e.value), units="ohm", basis="datasheet V_OH figure")
                datasheet = True
            models.append(MODEL_MCU_PIN)
            continue
        if e.kind in ("R", "C") and "_" in name:
            cid = name.split("_", 1)[1]
            comp = components.get(cid)
            if comp is None:
                continue          # R_TIE_, R_LOAD_ and other model elements are exact
            tol, basis = (resistor_tolerance(comp.part_number) if e.kind == "R"
                          else capacitor_tolerance(comp.part_number))
            nominal = part_value(e.value)
            lo, hi = nominal * (1 - tol), nominal * (1 + tol)
            if not lo <= e.value <= hi:  # pragma: no cover - part_value moves a value by 1e-12
                raise ValueError(f"{name}: netlist value {e.value} lies outside its own tolerance box")
            out[name] = Variable(element=name, label=cid, lo=str(lo), hi=str(hi), nominal=str(e.value),
                                 units="ohm" if e.kind == "R" else "F", basis=basis)
    for b in bench:
        element = netlist.element(b.name)
        if b.lo is not None and b.hi is not None:
            lo, hi = Fraction(b.lo), Fraction(b.hi)
        elif b.tolerance is not None:
            lo, hi = element.value * (1 - Fraction(b.tolerance)), element.value * (1 + Fraction(b.tolerance))
        else:
            continue
        out[b.name] = Variable(element=b.name, label=b.label or b.describe, lo=str(lo), hi=str(hi),
                               nominal=str(element.value), units="ohm" if element.kind == "R" else "F",
                               basis=b.basis or "test bench")
    return out, datasheet, tuple(dict.fromkeys(models))


def _conditions(netlist: Netlist) -> List[str]:
    out = []
    for e in netlist.elements:
        if e.kind != "V":
            continue
        if e.name.upper().startswith("V_PIN_"):
            out.append(f"the MCU pin driving {e.a.replace('_src', '').upper()} high at {si(e.value, 'V')}")
        elif e.ac:
            out.append(f"{e.a.upper()} driven by the AC source")
        elif e.value:
            out.append(f"{e.a.upper()} held at {si(e.value, 'V')}")
    return out


# ── Compile ──────────────────────────────────────────────────────────────────

def _expr(text: str) -> sympy.Expr:
    """An obligation's expression back from its srepr — our own data, never user input."""
    return sympy.sympify(text)


def _r(value) -> sympy.Rational:
    f = Fraction(value)
    return sympy.Rational(f.numerator, f.denominator)


def _args(quantity: str) -> Tuple[str, List[str]]:
    m = re.match(r"^(\w+)\((.*)\)$", quantity.replace(" ", ""))
    if not m or m.group(1) not in QUANTITIES:
        raise ValueError(f"unsupported quantity {quantity!r}")
    return m.group(1), [a for a in m.group(2).split(",") if a]


class DiodeBox(BaseModel):
    """
    A tabulated LED's saturation-current box. `outer` ends enclose the true
    ends (for proofs); `inner` ends lie inside the true box (for certified
    counterexamples). They differ by the width of an exp() bracket.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    anode: str
    cathode: str
    n: Fraction
    n_model: Fraction
    is_lo_outer: Fraction
    is_lo_inner: Fraction
    is_hi_outer: Fraction
    is_hi_inner: Fraction


def _diode_box(circuit: CircuitIR, netlist: Netlist, diode_name: str) -> DiodeBox:
    """The I_s box of a tabulated LED, from its datasheet forward-voltage range."""
    element = netlist.element(diode_name)
    cid = diode_name.split("_", 1)[1]
    comp = next(c for c in circuit.components if c.id == cid)
    table = get_constraints(comp.part_number) or {}
    if "forward_voltage_v" not in table:
        raise ValueError(f"{cid} ({comp.part_number}) has no tabulated forward voltage to box")
    n = Fraction(str(table.get("ideality", 2.0)))
    i_test = Fraction(str(table["test_current_ma"])) / 1000
    vf = table["forward_voltage_v"]
    # Is falls as Vf rises. Outward: the smallest Is from the largest Vf.
    e_max = brackets.expm1_ratio(Fraction(str(vf["max"])), n * VT)
    e_min = brackets.expm1_ratio(Fraction(str(vf["min"])), n * VT)
    _, n_model = netlist.diode_models[element.model]
    return DiodeBox(anode=element.a, cathode=element.b, n=n, n_model=n_model,
                    is_lo_outer=i_test / e_max[1], is_lo_inner=i_test / e_max[0],
                    is_hi_outer=i_test / e_min[0], is_hi_inner=i_test / e_min[1])


def compile_statement(circuit: CircuitIR, spec: PropertySpec, netlist_text: str) -> Tuple[Statement, Problem]:
    netlist = parse(netlist_text).with_bench([b.line for b in spec.bench])
    variables, datasheet, models = part_variables(circuit, netlist, spec.bench)
    symbols = {name: _symbol(name) for name in variables}
    kind, args = _args(spec.quantity)
    obligations: List[Obligation] = []
    method = "z3_unsat"
    uses_pi = False
    witness: Optional[SeriesPowerWitness] = None

    def bound_obligations(expr, extra=(), adverse=None):
        """
        expr ≥ lo and/or expr ≤ hi. `adverse` maps each bracket name to the
        end that makes a violation certain — (end for the lo side, end for the
        hi side) — for a quantity monotone in its bracket variable.
        """
        out = []
        for op, bound, side in (("ge", spec.lo, 0), ("le", spec.hi, 1)):
            if bound is None:
                continue
            refute = None
            if extra:
                collapsed = expr
                for name, lo, hi in extra:
                    end = (lo, hi)[adverse[name][side]]
                    collapsed = collapsed.subs(sympy.Symbol(name, positive=True), _r(end))
                refute = Obligation(label=f"certified: {spec.quantity} {op} bound", expr=sympy.srepr(collapsed),
                                    op=op, bound=sympy.srepr(_r(bound)))
            out.append(Obligation(label=f"{spec.quantity} {'>=' if op == 'ge' else '<='} {bound}",
                                  expr=sympy.srepr(expr), op=op, bound=sympy.srepr(_r(bound)),
                                  brackets=extra, exact=not extra, refute=refute))
        return out

    if kind in ("v", "vdiff", "i", "power"):
        if any(e.kind == "D" for e in netlist.elements):
            # Removing the diode would analyse a different circuit. A linear
            # quantity on a nonlinear network is refused, not approximated.
            raise ValueError(f"{spec.quantity} is linear, and this circuit has a diode; "
                             f"use diode_current() or series_power()")
        system = mna.dc(netlist, symbols)
        if kind == "v":
            expr = system.v(args[0])
        elif kind == "vdiff":
            expr = system.v(args[0]) - system.v(args[1])
        elif kind == "i":
            expr = system.i(args[0])
        else:
            element = netlist.element(args[0])
            resistance = symbols.get(element.name, _r(element.value))
            expr = (system.v(element.a) - system.v(element.b)) ** 2 / resistance
        obligations += bound_obligations(sympy.cancel(expr))
    elif kind == "rth":
        _, r_th = mna.thevenin(netlist, symbols, args[0], args[1] if len(args) > 1 else "0")
        obligations += bound_obligations(r_th)
    elif kind == "cutoff":
        h = mna.transfer(netlist, symbols, args[0])
        num, den = sympy.fraction(sympy.together(h))
        den_poly = sympy.Poly(sympy.expand(den), mna.S)
        if sympy.Poly(sympy.expand(num), mna.S).degree() != 0 or den_poly.degree() != 1:
            raise ValueError("cutoff() is defined for first-order low-pass transfer functions only")
        d1, d0 = den_poly.coeff_monomial(mna.S), den_poly.coeff_monomial(1)
        pi_lo, pi_hi = brackets.pi()
        uses_pi = True
        fc = d0 / (2 * sympy.Symbol("PI", positive=True) * d1)
        extra = (("PI", str(pi_lo), str(pi_hi)),)
        obligations.append(Obligation(label="pole is in the left half plane", expr=sympy.srepr(d0 / d1),
                                      op="gt", bound=sympy.srepr(sympy.Integer(0)), lemma=True))
        # f_c falls as PI rises: "f_c < lo" is certain if it holds at the
        # smallest PI; "f_c > hi" if it holds at the largest.
        obligations += bound_obligations(sympy.cancel(fc), extra, adverse={"PI": (0, 1)})
    elif kind == "rise_time":
        node, cap = args
        _, r_th = mna.thevenin(netlist, symbols, node, "0", remove=[cap])
        c = symbols.get(cap, _r(netlist.element(cap).value))
        l9_lo, l9_hi = brackets.ln(Fraction(9))
        expr = sympy.Symbol("LN9", positive=True) * r_th * c
        # t_r rises with LN9: "t < lo" is certain at its largest, "t > hi" at its smallest.
        obligations += bound_obligations(expr, (("LN9", str(l9_lo), str(l9_hi)),), adverse={"LN9": (1, 0)})
    elif kind in ("diode_current", "series_power"):
        d_name = args[0] if kind == "diode_current" else args[1]
        box = _diode_box(circuit, netlist, d_name)
        if box.n_model != box.n:
            raise ValueError(f"{d_name}: netlist ideality {box.n_model} is not the tabulated {box.n}")
        v_th, r_th = mna.thevenin(netlist, symbols, box.anode, box.cathode, remove=[d_name])
        datasheet = True
        nvt = _r(box.n * VT)
        obligations.append(Obligation(label="Thevenin resistance seen by the diode is positive",
                                      expr=sympy.srepr(r_th), op="gt", bound=sympy.srepr(sympy.Integer(0)), lemma=True))
        obligations.append(Obligation(label="Thevenin voltage seen by the diode is positive",
                                      expr=sympy.srepr(v_th), op="gt", bound=sympy.srepr(sympy.Integer(0)), lemma=True))

        zero = sympy.srepr(sympy.Integer(0))

        def g_minus_vth(c: Fraction, is_value: Fraction, which: int) -> str:
            """g(c) − V_th with ln(1 + c/I_s) at its lower (0) or upper (1) bracket end."""
            return sympy.srepr(nvt * _r(brackets.ln(1 + c / is_value)[which]) + _r(c) * r_th - v_th)

        def current_le(c: Fraction, certify: bool = True) -> Obligation:
            # I ≤ c  ⇐  g(c) ≥ V_th at the largest I_s, ln at its lower end.
            # Refuted for certain where g(c) < V_th with I_s inside its box and
            # ln at its upper end.
            refute = (Obligation(label=f"certified: diode current > {c}",
                                 expr=g_minus_vth(c, box.is_hi_inner, 1), op="ge", bound=zero)
                      if certify else None)
            return Obligation(label=f"diode current <= {c}", expr=g_minus_vth(c, box.is_hi_outer, 0),
                              op="ge", bound=zero, exact=False, refute=refute)

        def current_ge(c: Fraction) -> Obligation:
            # I ≥ c  ⇐  g(c) ≤ V_th at the smallest I_s, ln at its upper end.
            return Obligation(label=f"diode current >= {c}", expr=g_minus_vth(c, box.is_lo_outer, 1),
                              op="le", bound=zero, exact=False,
                              refute=Obligation(label=f"certified: diode current < {c}",
                                                expr=g_minus_vth(c, box.is_lo_inner, 0), op="le", bound=zero))

        if kind == "diode_current":
            if spec.lo is not None:
                obligations.append(current_ge(Fraction(spec.lo)))
            if spec.hi is not None:
                obligations.append(current_le(Fraction(spec.hi)))
        else:
            # P = I²·R ≤ c²·R ≤ P_max with I ≤ c proved: sound, not complete.
            method = "sound_enclosure"
            resistor = netlist.element(args[0])
            r_var = variables.get(resistor.name)
            r_hi = Fraction(r_var.hi) if r_var else resistor.value
            p_max = Fraction(spec.hi)
            c = _floor_sqrt(p_max / r_hi)
            # I > c is not P > P_max, so this bound is refuted only through
            # the witness below — never through its own counterexample.
            obligations.append(current_le(c, certify=False))
            r_sym = symbols.get(resistor.name, _r(resistor.value))
            obligations.append(Obligation(label=f"({c})^2·R <= P_max", expr=sympy.srepr(_r(c) ** 2 * r_sym),
                                          op="le", bound=sympy.srepr(_r(p_max))))
            witness = SeriesPowerWitness(r_th=sympy.srepr(r_th), v_th=sympy.srepr(v_th),
                                         resistance=sympy.srepr(r_sym), p_max=str(p_max),
                                         nvt=str(box.n * VT), is_inner=str(box.is_hi_inner))
    else:  # pragma: no cover - _args already refused it
        raise ValueError(kind)

    obligations = _denominator_lemmas(obligations) + obligations
    used = set()
    for ob in obligations:
        used |= {s.name for s in _expr(ob.expr).free_symbols}
    relevant = [variables[name] for name in variables if symbols[name].name in used]
    conditions = _conditions(netlist)
    if kind in ("diode_current", "series_power"):
        # The forward-voltage spread is part of the domain even though it
        # enters as a bracket rather than a box variable: the signer reads it.
        comp = next(c for c in circuit.components if c.id == d_name.split("_", 1)[1])
        vf = get_constraints(comp.part_number)["forward_voltage_v"]
        test_ma = get_constraints(comp.part_number)["test_current_ma"]
        conditions.append(f"{comp.id}'s forward voltage anywhere in its datasheet range of "
                          f"{vf['min']}–{vf['max']} V at {test_ma} mA")
    english = back_translate(spec, relevant, conditions)
    statement = Statement(spec=spec, variables=tuple(relevant), conditions=tuple(conditions), english=english,
                          uses_pi=uses_pi, bracketed=kind in ("cutoff", "rise_time", "diode_current", "series_power"),
                          datasheet=datasheet or spec.datasheet_bound, mcu_models=models)
    return statement, Problem(obligations=tuple(obligations), method=method, witness=witness)


def _denominator_lemmas(obligations: List[Obligation]) -> List[Obligation]:
    """One lemma per distinct symbolic denominator, in obligations and their refuters: it is never zero."""
    seen, out = set(), []
    for ob in obligations + [o.refute for o in obligations if o.refute is not None]:
        _, den = sympy.fraction(sympy.together(_expr(ob.expr)))
        if not den.free_symbols:
            continue
        key = sympy.srepr(den)
        if key in seen:
            continue
        seen.add(key)
        names = {s.name for s in den.free_symbols}
        out.append(Obligation(label=f"denominator {den} is never zero over the box", expr=key, op="ne",
                              bound=sympy.srepr(sympy.Integer(0)),
                              brackets=tuple(b for b in ob.brackets if b[0] in names), lemma=True))
    return out


def _floor_sqrt(x: Fraction, digits: int = 9) -> Fraction:
    """The largest multiple of 10^-digits whose square is ≤ x. Exact."""
    scale = 10 ** digits
    target = x * scale * scale
    lo, hi = 0, 1
    while Fraction(hi * hi) <= target:
        hi *= 2
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if Fraction(mid * mid) <= target:
            lo = mid
        else:
            hi = mid
    return Fraction(lo, scale)


def _ceil_sqrt(x: Fraction, digits: int = 9) -> Fraction:
    """The smallest multiple of 10^-digits whose square is ≥ x. Exact."""
    root = _floor_sqrt(x, digits)
    return root if root * root >= x else root + Fraction(1, 10 ** digits)


# ── Deciding one obligation ──────────────────────────────────────────────────

def _to_z3(expr: sympy.Expr, env: Dict[str, z3.ArithRef]):
    if expr.is_Symbol:
        return env[expr.name]
    if expr.is_Integer:
        return z3.RealVal(int(expr))
    if expr.is_Rational:
        return z3.Q(int(expr.p), int(expr.q))
    if expr.is_Add:
        out = _to_z3(expr.args[0], env)
        for a in expr.args[1:]:
            out = out + _to_z3(a, env)
        return out
    if expr.is_Mul:
        out = _to_z3(expr.args[0], env)
        for a in expr.args[1:]:
            out = out * _to_z3(a, env)
        return out
    if expr.is_Pow and expr.exp.is_Integer:
        base, k = _to_z3(expr.base, env), int(expr.exp)
        power = base
        for _ in range(abs(k) - 1):
            power = power * base
        return power if k > 0 else 1 / power
    raise ValueError(f"cannot translate {expr!r} to z3")


def decide(ob: Obligation, box: Dict[str, Tuple[Fraction, Fraction]]):
    """('unsat' | 'sat' | 'unknown', counterexample for people, exact point)."""
    expr = _expr(ob.expr)
    bound = _expr(ob.bound)
    solver = z3.Solver()
    solver.set("timeout", Z3_TIMEOUT_MS)
    env: Dict[str, z3.ArithRef] = {}
    for name in sorted(s.name for s in expr.free_symbols):
        var = z3.Real(name)
        env[name] = var
        bracket = next(((Fraction(lo), Fraction(hi)) for n, lo, hi in ob.brackets if n == name), None)
        lo, hi = bracket if bracket else box[name]
        solver.add(var >= z3.Q(lo.numerator, lo.denominator), var <= z3.Q(hi.numerator, hi.denominator))
    e, b = _to_z3(expr, env), _to_z3(bound, env)
    solver.add({"ge": e < b, "le": e > b, "gt": e <= b, "ne": e == b}[ob.op])
    verdict = solver.check()
    if verdict == z3.unsat:
        return "unsat", None, None
    if verdict == z3.sat:
        model = solver.model()
        values = {n: model.eval(v, model_completion=True) for n, v in env.items()}
        point = {n: value.as_fraction() for n, value in values.items() if z3.is_rational_value(value)}
        return "sat", {n: _show(value) for n, value in values.items()}, point
    return "unknown", None, None


def _show(value) -> str:
    """A model value to six significant figures — not six decimal places."""
    if z3.is_rational_value(value):
        f = value.as_fraction()
        return f"{float(f):.6g}"
    return f"{float(value.as_decimal(30).rstrip('?')):.6g}"


def _certify_power(witness: SeriesPowerWitness, point: Dict[str, Fraction]) -> bool:
    """Whether P > P_max at this point, exactly (see SeriesPowerWitness)."""
    subs = {sympy.Symbol(n, positive=True): _r(v) for n, v in point.items()}
    try:
        resistance = Fraction(str(_expr(witness.resistance).subs(subs)))
        r_th = Fraction(str(_expr(witness.r_th).subs(subs)))
        v_th = Fraction(str(_expr(witness.v_th).subs(subs)))
    except (ValueError, TypeError):
        return False               # a symbol the point does not fix
    if resistance <= 0 or r_th < 0:
        return False
    c = _ceil_sqrt(Fraction(witness.p_max) / resistance)
    _, ln_hi = brackets.ln(1 + c / Fraction(witness.is_inner))
    return Fraction(witness.nvt) * ln_hi + c * r_th - v_th < 0


def _witness_points(point: Optional[Dict[str, Fraction]], box) -> List[Dict[str, Fraction]]:
    """The failing point (completed from the box's low ends), then every corner."""
    from itertools import product

    names = sorted(box)
    candidates = []
    if point:
        candidates.append({n: point.get(n, box[n][0]) for n in names})
    for ends in product((0, 1), repeat=len(names)):
        candidates.append({n: box[n][e] for n, e in zip(names, ends)})
    return candidates


# ── Strategies and the refine loop ───────────────────────────────────────────

class Strategy:
    name = "strategy"

    def run(self, statement: Statement, problem: Problem, box) -> ProofResult:  # pragma: no cover
        raise NotImplementedError


def _box_key(box) -> Tuple[Tuple[str, str, str], ...]:
    return tuple((name, str(lo), str(hi)) for name, (lo, hi) in sorted(box.items()))


def _verdict(statement, problem, box, strategy_name, decide_fn) -> ProofResult:
    """
    Decide every obligation with `decide_fn`, which returns (outcome, shown,
    point) — or, for a strategy that splits the box, a fourth element: the
    sub-boxes it decided UNSAT. Those go into the certificate.
    """
    discharged = []
    certificate = []
    for ob in problem.obligations:
        decided = decide_fn(ob, box)
        outcome, shown, point = decided[:3]
        if outcome == "unsat":
            covered = decided[3] if len(decided) > 3 else [box]
            discharged.append(ob.hash)
            certificate.append((ob.hash, tuple(_box_key(b) for b in covered)))
            continue

        def result(status: str, detail: str, counterexample=None) -> ProofResult:
            return ProofResult(property_id=statement.spec.id, statement_hash=statement.hash, status=status,
                               method=problem.method, strategy=strategy_name, discharged=tuple(discharged),
                               counterexample=counterexample, detail=detail, certificate=tuple(certificate))

        if ob.lemma:
            return result("unknown", f"lemma not established: {ob.label}")
        if outcome == "unknown":
            return result("unknown", f"{ob.label}: solver returned unknown")
        if ob.exact:
            return result("refuted", f"{ob.label}: counterexample found", shown)
        if ob.refute is not None:
            r_outcome, r_shown = decide_fn(ob.refute, box)[:2]
            if r_outcome == "sat":
                return result("refuted", f"{ob.label}: counterexample found, certified outside "
                                         f"the bracket slack", r_shown)
        if problem.witness is not None:
            for candidate in _witness_points(point, box):
                if _certify_power(problem.witness, candidate):
                    return result("refuted", f"{statement.spec.quantity} exceeds {statement.spec.hi} W at this "
                                             f"point, certified with the LED at its lowest forward voltage",
                                  {n: f"{float(v):.6g}" for n, v in candidate.items()})
        return result("unknown", f"{ob.label}: not established, and no counterexample could be certified")
    return ProofResult(property_id=statement.spec.id, statement_hash=statement.hash, status="proven",
                       method=problem.method, strategy=strategy_name, discharged=tuple(discharged),
                       detail=f"{len(discharged)} obligation(s) UNSAT over the box",
                       certificate=tuple(certificate))


class Direct(Strategy):
    name = "direct"

    def run(self, statement, problem, box):
        return _verdict(statement, problem, box, self.name, decide)


class Bisect(Strategy):
    """On *unknown*, split the widest variable and require every half to be UNSAT."""

    name = "bisect"

    def run(self, statement, problem, box):
        def split_decide(ob, sub, depth=0):
            outcome, witness, point = decide(ob, sub)
            if outcome == "unsat":
                return outcome, None, None, [sub]
            if outcome == "sat" or depth >= BISECT_DEPTH or not sub:
                return outcome, witness, point, []
            widest = max(sub, key=lambda k: (sub[k][1] - sub[k][0]) / max(abs(sub[k][1]), Fraction(1, 10**30)))
            lo, hi = sub[widest]
            mid = (lo + hi) / 2
            leaves = []
            for half in ({**sub, widest: (lo, mid)}, {**sub, widest: (mid, hi)}):
                outcome, witness, point, covered = split_decide(ob, half, depth + 1)
                if outcome != "unsat":
                    return outcome, witness, point, []
                leaves += covered
            return "unsat", None, None, leaves
        return _verdict(statement, problem, box, self.name, split_decide)


DEFAULT_STRATEGIES: Tuple[Strategy, ...] = (Direct(), Bisect())


def prove(statement: Statement, problem: Problem,
          strategies: Sequence[Strategy] = DEFAULT_STRATEGIES) -> ProofResult:
    """Run strategies in order; every result must be for the frozen statement."""
    frozen_statement = statement.hash
    frozen_obligations = {ob.hash for ob in problem.obligations}
    box = {_symbol(v.element).name: (Fraction(v.lo), Fraction(v.hi)) for v in statement.variables}
    result: Optional[ProofResult] = None
    for strategy in strategies:
        result = strategy.run(statement, problem, dict(box))
        if result.statement_hash != frozen_statement:
            raise FrozenPropertyViolation(
                f"strategy {strategy.name!r} returned a result for a different statement "
                f"({result.statement_hash[:12]} ≠ frozen {frozen_statement[:12]}) — a frozen property "
                f"cannot be changed by the refine loop"
            )
        if not set(result.discharged) <= frozen_obligations:
            raise FrozenPropertyViolation(
                f"strategy {strategy.name!r} discharged obligations that are not the frozen property's"
            )
        if result.status == "proven" and set(result.discharged) != frozen_obligations:
            raise FrozenPropertyViolation(
                f"strategy {strategy.name!r} reported a proof without discharging every obligation"
            )
        if result.status == "proven" and not _certificate_holds(result, problem, box, strategy.name):
            # Not a violation: z3 could not re-decide a box in time. A proof
            # the loop cannot confirm is not a proof.
            result = result.model_copy(update={
                "status": "unknown", "detail": "the proof's certificate could not be re-checked"})
        if result.status != "unknown":
            return result
    return result


def _certificate_holds(result: ProofResult, problem: Problem, frozen: Dict[str, Tuple[Fraction, Fraction]],
                       strategy: str) -> bool:
    """
    Check a proof's certificate against the frozen problem. Raises
    `FrozenPropertyViolation` on anything a strategy could use to weaken the
    property; returns False only when z3 cannot re-decide a box.
    """
    obligations = {ob.hash: ob for ob in problem.obligations}
    certificate = dict(result.certificate)
    if set(certificate) != set(obligations):
        raise FrozenPropertyViolation(f"strategy {strategy!r}: the certificate does not cover every obligation")
    confirmed = True
    for h, boxes in certificate.items():
        parsed = [{name: (Fraction(lo), Fraction(hi)) for name, lo, hi in b} for b in boxes]
        _check_tiling(parsed, frozen, strategy)
        for b in parsed:
            outcome = decide(obligations[h], b)[0]
            if outcome == "sat":
                raise FrozenPropertyViolation(
                    f"strategy {strategy!r}: {obligations[h].label} is not UNSAT on a certificate box — "
                    f"the proof does not hold over part of the frozen box")
            if outcome == "unknown":
                confirmed = False
    return confirmed


def _check_tiling(boxes: List[Dict[str, Tuple[Fraction, Fraction]]],
                  frozen: Dict[str, Tuple[Fraction, Fraction]], strategy: str) -> None:
    """
    The boxes cover the frozen box exactly: each inside it, interiors pairwise
    disjoint, volumes summing to its volume. A closed union with the full
    volume and no gap of positive measure is the whole box.
    """
    def fail(why: str):
        raise FrozenPropertyViolation(f"strategy {strategy!r}: the certificate {why} — a proof over less "
                                      f"than the frozen box is not a proof of the frozen property")

    if not boxes:
        fail("is empty")
    live = [n for n, (lo, hi) in frozen.items() if lo < hi]
    for b in boxes:
        if set(b) != set(frozen):
            fail("ranges over different variables")
        for name, (flo, fhi) in frozen.items():
            lo, hi = b[name]
            if not (flo <= lo <= hi <= fhi):
                fail(f"reaches outside the frozen range of {name}")
            if flo == fhi and (lo, hi) != (flo, fhi):
                fail(f"moves the fixed value of {name}")

    def volume(b) -> Fraction:
        v = Fraction(1)
        for n in live:
            v *= b[n][1] - b[n][0]
        return v

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if all(max(boxes[i][n][0], boxes[j][n][0]) < min(boxes[i][n][1], boxes[j][n][1]) for n in live):
                fail("counts part of the box twice")
    if sum((volume(b) for b in boxes), Fraction(0)) != volume(frozen):
        fail("leaves part of the frozen box undecided")


# ── The entry point, cached ──────────────────────────────────────────────────

@lru_cache(maxsize=4096)
def _cached(circuit_json: str, spec_json: str, netlist_text: str):
    circuit = CircuitIR.model_validate_json(circuit_json)
    spec = PropertySpec.model_validate_json(spec_json)
    statement, problem = compile_statement(circuit, spec, netlist_text)
    return statement, problem, prove(statement, problem)


def check(circuit: CircuitIR, spec: PropertySpec, netlist_text: Optional[str] = None):
    """(Statement, Problem, ProofResult) for one property of one design."""
    from generators.netlist.spice import SpiceNetlistGenerator

    text = netlist_text if netlist_text is not None else SpiceNetlistGenerator().generate(circuit)
    # The cache key is what a proof reads: the netlist, the parts and how they
    # connect. Identity and bookkeeping — which lineage, which revision, what
    # is claimed — change nothing proved, and keying on them made every new
    # intent re-prove an identical circuit.
    stripped = circuit.model_copy(update={
        "validation_coverage": None, "circuit_id": _ANONYMOUS, "version": 1, "generator": None, "intent": "",
    })
    return _cached(stripped.model_dump_json(), spec.model_dump_json(), text)


_ANONYMOUS = "00000000-0000-0000-0000-000000000000"


def mutate(netlist_text: str, element: str, factor: Fraction) -> str:
    """
    The netlist with one element's value scaled — a wrong part fitted, or a
    rail at the wrong voltage. R and C carry their value in field 4; a DC
    source ("V_X n 0 DC 5") in field 5.
    """
    from proof.netlist import spice_value

    out = []
    found = False
    for line in netlist_text.splitlines():
        parts = line.split()
        if parts and parts[0].lower() == element.lower():
            index = 4 if parts[0][0].upper() in ("V", "I") else 3
            parts[index] = repr(float(spice_value(parts[index]) * factor))
            line = " ".join(parts)
            found = True
        out.append(line)
    if not found:
        raise KeyError(f"no element {element} to mutate")
    return "\n".join(out)


def mutation_candidates(statement: Statement, netlist_text: str) -> List[str]:
    """Every design part the property ranges over, plus every DC source the design holds."""
    bench = {b.name.lower() for b in statement.spec.bench}
    names = [v.element for v in statement.variables if v.element.lower() not in bench]
    names += [e.name for e in parse(netlist_text).elements if e.kind == "V" and e.value]
    return list(dict.fromkeys(names))


#: Wrong values the mutation test fits. ×10⁻³ and ×10³ are a wrong multiplier
#: letter — 1k for 1M — the classic wrong part; ×½ and ×2 a wrong neighbour.
MUTATION_FACTORS: Tuple[Fraction, ...] = (Fraction(1, 1000), Fraction(1, 10), Fraction(1, 2),
                                          Fraction(2), Fraction(10), Fraction(1000))


class Mutation(BaseModel):
    model_config = ConfigDict(frozen=True)

    element: str
    factor: str
    result: ProofResult


def falsify(circuit: CircuitIR, spec: PropertySpec, netlist_text: Optional[str] = None) -> Optional[Mutation]:
    """
    The first wrong value that refutes the property, or None if none does.
    Stage 4's mutation gate: a property no wrong part can break says nothing.
    """
    from generators.netlist.spice import SpiceNetlistGenerator

    text = netlist_text if netlist_text is not None else SpiceNetlistGenerator().generate(circuit)
    statement, _, _ = check(circuit, spec, text)
    for element in mutation_candidates(statement, text):
        for factor in MUTATION_FACTORS:
            _, _, result = check(circuit, spec, mutate(text, element, factor))
            if result.status == "refuted":
                return Mutation(element=element, factor=str(factor), result=result)
    return None
