"""
Stage 4 proofs against an independent oracle: ngspice.

The prover and ngspice share nothing but the netlist text — sympy nodal
analysis and z3 on one side, ngspice's own solver on the other, driven here
through its control language rather than the project's parser. So:

- every value ngspice computes at a corner of a proven box must lie inside
  the proven bounds (at the LED's forward-voltage extremes too);
- every counterexample the prover reports for a wrongly-fitted part must, fed
  back into ngspice, really violate the bound.

The Stage 3 + 4 verification ran this over all 64 grid properties (624
evaluations) and all 64 mutation counterexamples, with no disagreement. This
file keeps it for the five default designs, so CI does not depend on
anyone re-running a script.
"""

import itertools
import math
import os
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction

import pytest

from ai.form_producer import FormProducer
from generators.netlist.models import led_parameters
from generators.netlist.spice import SpiceNetlistGenerator
from generators.registry import default_registry
from proof.prover import check, falsify, mutate

_NGSPICE = (shutil.which("ngspice_con")
            or (r"C:\msys64\ucrt64\bin\ngspice_con.exe"
                if os.path.exists(r"C:\msys64\ucrt64\bin\ngspice_con.exe") else None)
            or shutil.which("ngspice"))
pytestmark = pytest.mark.skipif(_NGSPICE is None, reason="ngspice not installed")

REGISTRY = default_registry()
FORMS = FormProducer(REGISTRY)
DEFAULTS = {
    "low_pass_filter": {"cutoff_hz": 1000, "supply_v": 5},
    "voltage_divider": {"vout_v": 3.3, "supply_v": 5},
    "led_indicator": {"led_current_ma": 10, "supply_v": 5},
    "temperature_humidity_sensor": {"cable_length_m": 5, "supply_v": 5},
    "modbus_rtu_master": {"supply_v": 5},
}


def _spice(lines, control):
    text = ("oracle\n" + "\n".join(lines) + "\n.options reltol=1e-9 abstol=1e-15 vntol=1e-12\n"
            ".control\nset numdgt=12\n" + "\n".join(control) + "\nquit\n.endc\n.end\n")
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        out = subprocess.run([_NGSPICE, "-b", path], capture_output=True, text=True, timeout=60).stdout
    finally:
        os.unlink(path)
    return {m.group(1).lower(): float(m.group(2)) for m in
            (re.match(r"^\s*([\w()#.]+)\s*=\s*([-+0-9.eE]+)", line) for line in out.splitlines()) if m}


def _elements(netlist):
    return [s.strip() for s in netlist.splitlines()
            if s.strip() and not s.strip().startswith("*")
            and not s.strip().lower().startswith((".op", ".ac", ".tran", ".print", ".end"))]


def _set(lines, name, value):
    out = []
    for s in lines:
        parts = s.split()
        if parts[0].lower() == name.lower():
            parts[4 if parts[0][0].upper() in "VI" else 3] = repr(float(value))
            s = " ".join(parts)
        out.append(s)
    return out


def _value(lines, name):
    return float(next(s for s in lines if s.split()[0].upper() == name.upper()).split()[3])


def _led(lines, circuit, which):
    led = next(c for c in circuit.components if c.id == "LED1")
    i_s, _ = led_parameters(led.part_number, which)
    return [re.sub(r"Is=\S+", f"Is={i_s!r}", s) if s.lower().startswith(".model") else s for s in lines]


def _evaluate(quantity, lines):
    kind, args = re.match(r"^(\w+)\((.*)\)$", quantity).groups()
    args = args.split(",")
    if kind in ("v", "vdiff"):
        nodes = args if kind == "vdiff" else args + ["0"]
        v = _spice(lines, ["op", "print " + " ".join(f"v({n})" for n in nodes if n != "0")])
        return v[f"v({nodes[0]})"] - (v[f"v({nodes[1]})"] if nodes[1] != "0" else 0.0)
    if kind == "i":
        return _spice(lines, ["op", f"print i({args[0]})"])[f"i({args[0].lower()})"]
    if kind == "power":
        _, a, b, r = next(s for s in lines if s.split()[0].lower() == args[0].lower()).split()[:4]
        v = _spice(lines, ["op", "print " + " ".join(f"v({n})" for n in (a, b) if n != "0")])
        return ((v.get(f"v({a})", 0.0) if a != "0" else 0.0) - (v.get(f"v({b})", 0.0) if b != "0" else 0.0)) ** 2 / float(r)
    if kind in ("diode_current", "series_power"):
        i = -_spice(lines, ["op", "print i(v_pin_led_ctrl)"])["i(v_pin_led_ctrl)"]
        return i if kind == "diode_current" else i * i * _value(lines, args[0])
    if kind == "rth":
        shorted = [" ".join(s.split()[:3] + ["DC", "0"]) if s[0].upper() == "V" else s for s in lines]
        v = _spice(shorted + [f"I_TEST {args[1]} {args[0]} DC 1"], ["op", f"print v({args[0]}) v({args[1]})"])
        return v[f"v({args[0]})"] - v[f"v({args[1]})"]
    if kind == "cutoff":
        f0 = 1 / (2 * math.pi * _value(lines, "R_R1") * _value(lines, "C_C1"))
        amplitude = float(next(s for s in lines if " AC " in s.upper()).split()[4])
        return _spice(lines, [f"ac dec 20000 {f0 / 100!r} {f0 * 100!r}",
                              f"meas ac fc when vm({args[0]})={amplitude / math.sqrt(2)!r}"])["fc"]
    if kind == "rise_time":
        node, cap = args
        r1, c = _value(lines, "R_R1"), _value(lines, cap)
        final, stop = 5.0 * 1e9 / (1e9 + r1), 20 * r1 * c
        v = _spice(lines + [f".ic v({node})=0"],
                   [f"tran {stop / 200000!r} {stop!r} uic",
                    f"meas tran t10 when v({node})={0.1 * final!r} rise=1",
                    f"meas tran t90 when v({node})={0.9 * final!r} rise=1"])
        return v["t90"] - v["t10"]
    raise ValueError(kind)


def _cases():
    for function, fields in DEFAULTS.items():
        intent = FORMS.build(function, fields)
        g = REGISTRY.dispatch(intent).generator
        circuit = g.generate(intent)
        for spec in g.properties(intent):
            yield pytest.param(circuit, spec, id=spec.id)


def _bounds(spec):
    return (float(Fraction(spec.lo)) if spec.lo is not None else -math.inf,
            float(Fraction(spec.hi)) if spec.hi is not None else math.inf)


@pytest.mark.parametrize("circuit, spec", list(_cases()))
def test_every_corner_of_the_proven_box_is_inside_the_bounds(circuit, spec):
    netlist = SpiceNetlistGenerator().generate(circuit)
    statement, _, result = check(circuit, spec, netlist)
    assert result.status == "proven"
    base = _elements(netlist) + [b.line for b in spec.bench]
    ends = ("min", "max") if spec.quantity.startswith(("diode_current", "series_power")) else (None,)
    lo, hi = _bounds(spec)
    for corner in itertools.product((0, 1), repeat=len(statement.variables)):
        lines = base
        for v, e in zip(statement.variables, corner):
            lines = _set(lines, v.element, Fraction((v.lo, v.hi)[e]))
        for vf in ends:
            value = _evaluate(spec.quantity, _led(lines, circuit, vf) if vf else lines)
            assert lo * (1 - 1e-7) <= value <= hi * (1 + 1e-7) if lo > 0 else lo <= value <= hi * (1 + 1e-7), \
                (spec.id, corner, vf, value, (spec.lo, spec.hi))


@pytest.mark.parametrize("circuit, spec", list(_cases()))
def test_every_counterexample_is_a_real_violation(circuit, spec):
    netlist = SpiceNetlistGenerator().generate(circuit)
    witness = falsify(circuit, spec, netlist)
    assert witness is not None
    lines = _elements(mutate(netlist, witness.element, Fraction(witness.factor))) + [b.line for b in spec.bench]
    for name, value in witness.result.counterexample.items():
        if name not in ("PI", "LN9"):
            lines = _set(lines, name, value)
    if spec.quantity.startswith(("diode_current", "series_power")):
        upper = "<=" in witness.result.detail or "exceeds" in witness.result.detail
        lines = _led(lines, circuit, "min" if upper else "max")
    lo, hi = _bounds(spec)
    value = _evaluate(spec.quantity, lines)
    assert value < lo or value > hi, (spec.id, witness.element, witness.factor, value)
