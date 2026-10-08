"""
Many independent copies of a circuit, one ngspice process.

The oracle for `real_data_check.py` and `build_check_accuracy.py`: ngspice is the
third-party solver the project already trusts (rules/simulation.md), and neither
script may ask the code under test what the answer is. A process costs 0.1–0.4 s on
Windows, so a thousand trials would be minutes of start-up; here each trial is a
renamed copy inside one netlist. Copies share no node (every node, element and model
name gets a `__<copy>` suffix; ground `0` is the only shared node), so they cannot
interact.

    Copy(elements=[("R", "R1", "vin", "vout", 3400.0), ("V", "S", "vin", "0", 5.0), …],
         models={"DLED": (3.2e-19, 2.0)},      # diode model name -> (Is, N)
         probes=["vout"],                      # node voltages to report
         diffs=[("a", "b")],                   # differential probes v(a)-v(b)
         meters=[("vout", None, 10e6)])        # a resistor from node to node/ground

`run_op` → one dict per copy: {"vout": 3.3077, "a-b": 0.259, …}. A run that ngspice
rejects raises `NgspiceError` with its log, never returns partial numbers.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_FALLBACK = r"C:\msys64\ucrt64\bin\ngspice_con.exe"
_PER_PRINT = 24          # vectors per `print`, to keep every command line short


class NgspiceError(RuntimeError):
    pass


def find_ngspice() -> Optional[str]:
    return shutil.which("ngspice_con") or shutil.which("ngspice") or (_FALLBACK if os.path.exists(_FALLBACK) else None)


@dataclass
class Copy:
    elements: List[Tuple]
    models: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    probes: List[str] = field(default_factory=list)
    diffs: List[Tuple[str, str]] = field(default_factory=list)
    meters: List[Tuple[str, Optional[str], float]] = field(default_factory=list)


def _n(node: str, i: int) -> str:
    node = node.lower()
    return "0" if node == "0" else f"{node}__{i}"


def _num(x: float) -> str:
    return repr(float(x))


def netlist_text(copies: Sequence[Copy], title: str = "batch") -> Tuple[str, List[List[Tuple[str, str]]]]:
    """The combined netlist, and for each copy the (label, vector-name) pairs to read back."""
    lines = [f"* {title}"]
    wanted: List[List[Tuple[str, str]]] = []
    for i, c in enumerate(copies):
        for el in c.elements:
            kind, name, a, b, val = el[0], el[1], el[2], el[3], el[4]
            tag = f"{name}__{i}"
            if kind == "R":
                lines.append(f"R_{tag} {_n(a, i)} {_n(b, i)} {_num(val)}")
            elif kind == "C":
                lines.append(f"C_{tag} {_n(a, i)} {_n(b, i)} {_num(val)}")
            elif kind == "V":
                lines.append(f"V_{tag} {_n(a, i)} {_n(b, i)} DC {_num(val)}")
            elif kind == "VAC":
                lines.append(f"V_{tag} {_n(a, i)} {_n(b, i)} DC 0 AC {_num(val)}")
            elif kind == "I":
                # SPICE: current flows from the first node through the source to the second.
                lines.append(f"I_{tag} {_n(a, i)} {_n(b, i)} DC {_num(val)}")
            elif kind == "D":
                lines.append(f"D_{tag} {_n(a, i)} {_n(b, i)} {val}__{i}")
            else:
                raise ValueError(f"unsupported element kind {kind!r}")
        for m, (is_, n) in c.models.items():
            lines.append(f".model {m}__{i} D (Is={is_:.9e} N={n})")
        for j, (a, b, ohm) in enumerate(c.meters):
            lines.append(f"R_METER{j}__{i} {_n(a, i)} {_n(b, i) if b else '0'} {_num(ohm)}")
        def vec(node: str) -> str:
            n = _n(node, i)
            return "0" if n == "0" else f"v({n})"     # ngspice has no vector v(0); ground is the number 0

        w = [(p, f"v({_n(p, i)})") for p in c.probes]
        w += [(f"{a}-{b}", f"({vec(a)}-{vec(b)})") for a, b in c.diffs]
        wanted.append(w)
    return "\n".join(lines), wanted


def run_op(copies: Sequence[Copy], timeout: int = 300) -> List[Dict[str, float]]:
    exe = find_ngspice()
    if exe is None:
        raise NgspiceError("ngspice is not installed")
    body, wanted = netlist_text(copies)
    # `print` of an expression needs a vector it can name; differences go through `let`.
    # Tight convergence: ngspice's default reltol of 1e-3 leaves tens of microvolts on a diode,
    # which would be the oracle's noise, not the code under test's.
    # rshunt: a 1 PΩ leak from every node, so a node nothing holds is finite — and the same 1 PΩ the
    # code under test puts there (`validation/build_check.py::GMIN`), so floating nodes agree.
    ctl: List[str] = [".options reltol=1e-9 vntol=1e-12 abstol=1e-15 rshunt=1e15", ".control", "set noaskquit", "op"]
    reads: List[Tuple[int, str, str]] = []
    k = 0
    for i, w in enumerate(wanted):
        for label, expr in w:
            if expr.startswith("("):
                ctl.append(f"let d{k} = {expr}")
                reads.append((i, label, f"d{k}"))
                k += 1
            else:
                reads.append((i, label, expr))
    names = [r[2] for r in reads]
    for s in range(0, len(names), _PER_PRINT):
        ctl.append("print " + " ".join(names[s:s + _PER_PRINT]))
    ctl += [".endc", ".end"]
    text = body + "\n" + "\n".join(ctl) + "\n"
    with tempfile.TemporaryDirectory(prefix="ngb_") as d:
        cir, log = Path(d, "c.cir"), Path(d, "c.log")
        cir.write_text(text, encoding="utf-8")
        try:
            subprocess.run([exe, "-b", "-o", str(log), str(cir)], capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise NgspiceError(f"ngspice timed out after {timeout}s") from exc
        out = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    values: Dict[str, float] = {}
    for m in re.finditer(r"^\s*([A-Za-z0-9_().\-+*/]+?)\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)\s*$", out, re.M):
        values[m.group(1).lower()] = float(m.group(2))
    results: List[Dict[str, float]] = [dict() for _ in copies]
    missing = []
    for i, label, vec in reads:
        key = vec.lower()
        if key not in values:
            missing.append(vec)
            continue
        results[i][label] = values[key]
    if missing:
        raise NgspiceError(f"ngspice gave no value for {len(missing)} vectors (first: {missing[:3]}):\n{out[-1500:]}")
    return results


def run_ac_cutoff(elements: Sequence[Tuple], out_node: str, f_lo: float = 1.0, f_hi: float = 1e6,
                  timeout: int = 120) -> float:
    """-3 dB frequency of v(out) from an AC sweep of the single VAC source, by ngspice's `.meas`."""
    exe = find_ngspice()
    if exe is None:
        raise NgspiceError("ngspice is not installed")
    lines = ["* ac cutoff"]
    for kind, name, a, b, val in (e[:5] for e in elements):
        if kind == "R":
            lines.append(f"R_{name} {a} {b} {_num(val)}")
        elif kind == "C":
            lines.append(f"C_{name} {a} {b} {_num(val)}")
        elif kind == "VAC":
            lines.append(f"V_{name} {a} {b} DC 0 AC {_num(val)}")
        else:
            raise ValueError(f"unsupported element kind {kind!r}")
    lines += [f".ac dec 400 {f_lo:g} {f_hi:g}", f".print ac vdb({out_node})",
              f".meas ac fc when vdb({out_node})=-3.0102999566 fall=1", ".end"]
    with tempfile.TemporaryDirectory(prefix="ngb_") as d:
        cir, log = Path(d, "c.cir"), Path(d, "c.log")
        cir.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run([exe, "-b", "-o", str(log), str(cir)], capture_output=True, timeout=timeout, check=False)
        out = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    m = re.search(r"^\s*fc\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)", out, re.M)
    if not m:
        raise NgspiceError("no .meas result for fc:\n" + out[-1200:])
    return float(m.group(1))


def run_tran_rise(r_ohm: float, c_farad: float, v_supply: float, timeout: int = 120) -> float:
    """10–90 % rise time of a node released from 0 V into R from the supply with C to ground, by `.meas`."""
    exe = find_ngspice()
    if exe is None:
        raise NgspiceError("ngspice is not installed")
    tau = r_ohm * c_farad
    text = "\n".join([
        "* rise time",
        f"V_S vcc 0 DC {_num(v_supply)}",
        f"R_P vcc data {_num(r_ohm)}",
        f"C_B data 0 {_num(c_farad)}",
        ".ic v(data)=0",
        f".tran {tau / 400:.6e} {tau * 8:.6e} uic",
        ".print tran v(data)",
        f".meas tran tr trig v(data) val={0.1 * v_supply:.9g} rise=1 targ v(data) val={0.9 * v_supply:.9g} rise=1",
        ".end",
    ]) + "\n"
    with tempfile.TemporaryDirectory(prefix="ngb_") as d:
        cir, log = Path(d, "c.cir"), Path(d, "c.log")
        cir.write_text(text, encoding="utf-8")
        subprocess.run([exe, "-b", "-o", str(log), str(cir)], capture_output=True, timeout=timeout, check=False)
        out = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    m = re.search(r"^\s*tr\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)", out, re.M)
    if not m:
        raise NgspiceError("no .meas result for tr:\n" + out[-1200:])
    return float(m.group(1))


if __name__ == "__main__":     # a self-check against closed forms
    import math

    r = run_op([Copy([("V", "S", "vin", "0", 5.0), ("R", "R1", "vin", "vout", 3400.0), ("R", "R2", "vout", "0", 6650.0)],
                     probes=["vout"], meters=[("vout", None, 10e6)]),
                Copy([("V", "S", "vin", "0", 5.0), ("R", "R1", "vin", "vout", 1000.0), ("R", "R2", "vout", "0", 2000.0)],
                     probes=["vout"], diffs=[("vin", "vout")])])
    r2 = 6650.0 * 10e6 / (6650.0 + 10e6)
    want0 = 5.0 * r2 / (3400.0 + r2)
    assert abs(r[0]["vout"] - want0) < 2e-6, (r[0], want0)
    assert abs(r[1]["vout"] - 5.0 * 2 / 3) < 2e-6 and abs(r[1]["vin-vout"] - 5.0 / 3) < 2e-6, r[1]
    fc = run_ac_cutoff([("VAC", "IN", "in", "0", 1.0), ("R", "R", "in", "out", 4700.0), ("C", "C", "out", "0", 1e-7)], "out")
    assert abs(fc - 1 / (2 * math.pi * 4700 * 1e-7)) / fc < 2e-3, fc
    tr = run_tran_rise(5000.0, 100e-12, 5.0)
    assert abs(tr - math.log(9) * 5000 * 100e-12) / tr < 5e-3, tr
    print("ngspice_batch self-check: ok", r[0], r[1], round(fc, 3), tr)
