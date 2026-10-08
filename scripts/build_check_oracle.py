"""
The build check's arithmetic, checked against ngspice.

    python scripts/build_check_oracle.py [design ...]

For every hypothesis (the design and each listed fault) and every reading, the build
check claims an interval: the range that reading can take with every part in its box
and the rail anywhere in its design range. This script asks ngspice — a different
solver, written by other people — for the same readings, and holds the claim to both
halves of what it says:

  * **exact at the corners.** ngspice, run at every corner of the box (each toleranced
    resistor at its low and high end, the rail at both ends, the LED's saturation current
    at both ends), must give the interval's endpoints: the minimum over corners equals the
    lower bound and the maximum equals the upper, to ngspice's print precision.
  * **nothing outside.** Random interior points (resistors uniform in their boxes, the rail
    uniform in its range, the LED's saturation current log-uniform) must never fall outside
    the interval. This is what "every extreme sits at a corner" rests on; one point outside
    would refute it.

A voltage is read the way the meter reads it: with its input resistance across the probed
nodes. A resistance is read the way an ohmmeter reads it: the powered parts gone, a test current
pushed into one net and out of the other, the answer V/I — and anything above the meter's top
range is OL.
"""

from __future__ import annotations

import itertools
import math
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for _k, _v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
               "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(_k, _v)

import ngspice_batch as ng  # noqa: E402
from validation.build_check import Analysis, BuildModel, Hypothesis, Meter, Probe  # noqa: E402

TEST_AMPS = 1e-3


def to_copy(a: Analysis, h: Hypothesis, rvals: Dict[str, float], supply: float, is_value, probe: Probe) -> ng.Copy:
    """One board, one reading: the netlist of this hypothesis with these values, read through this probe."""
    m = a.model
    if probe.kind == "r":
        els: List[Tuple] = [("R", e.name, e.a, e.b, float(rvals.get(e.name, e.value)))
                            for e in h.netlist.elements if e.kind == "R" and e.name in a.physical]
        els.append(("I", "TEST", probe.b, probe.a, TEST_AMPS))          # b → source → a: injected into a
        return ng.Copy(els, {}, diffs=[(probe.a, probe.b)])
    els = []
    models: Dict[str, Tuple[float, float]] = {}
    for e in h.netlist.elements:
        if e.kind == "R":
            els.append(("R", e.name, e.a, e.b, float(rvals.get(e.name, e.value))))
        elif e.kind == "V":
            v = supply if (e.name == m.supply_source or e.name in m.follow) else float(e.value)
            els.append(("V", e.name, e.a, e.b, v))
        elif e.kind == "D":
            is_, n = h.netlist.diode_models[e.model]
            models[e.model] = (float(is_) if is_value is None else is_value, float(n))
            els.append(("D", e.name, e.a, e.b, e.model))
    cp = ng.Copy(els, models, meters=[(probe.a, probe.b, a.meter.input_ohm)])
    if probe.b is None:
        cp.probes = [probe.a]
    else:
        cp.diffs = [(probe.a, probe.b)]
    return cp


def observed(a: Analysis, probe: Probe, value: float) -> float:
    """What the meter shows for what ngspice measured: volts as they are; ohms as V/I, OL above the top range."""
    return a.meter.observe_ohm(value / TEST_AMPS) if probe.kind == "r" else value


def _close(x: float, y: float, rel: float = 2e-6, ab: float = 3e-6) -> bool:
    if math.isinf(x) or math.isinf(y):
        return x == y
    return abs(x - y) <= ab + rel * max(abs(x), abs(y))


def check_hypothesis(a: Analysis, hid: str, n_samples: int, rng: random.Random) -> Dict[str, float]:
    h = a.hyps[hid]
    s_lo, s_hi = a.model.supply_range
    v_names = [n for n, (lo, hi) in h.boxes.items() if lo != hi and any(r[0] == n for r in h.struct.res)]
    r_names = [n for n, (lo, hi) in h.boxes.items() if lo != hi and n in h.rnet.names]
    is_box = a.model.diode_is.get(h.struct.diodes[0][0]) if h.struct.diodes else None
    corner_cases, sample_cases = [], []
    for pi, probe in enumerate(a.probes):
        names = r_names if probe.kind == "r" else v_names
        ends = [(float(h.boxes[n][0]), float(h.boxes[n][1])) for n in names]
        supplies = (s_lo, s_hi) if probe.kind == "v" else (0.0,)
        is_pts = list(is_box) if (is_box and probe.kind == "v") else [None]
        for combo in itertools.product(*ends):
            for s in supplies:
                for is_ in is_pts:
                    corner_cases.append((pi, to_copy(a, h, dict(zip(names, combo)), s, is_, probe)))
        for _ in range(n_samples):
            rv = {n: rng.uniform(lo, hi) for n, (lo, hi) in zip(names, ends)}
            s = rng.uniform(s_lo, s_hi) if probe.kind == "v" else 0.0
            is_ = math.exp(rng.uniform(math.log(is_box[0]), math.log(is_box[1]))) if (is_box and probe.kind == "v") else None
            sample_cases.append((pi, to_copy(a, h, rv, s, is_, probe)))
    res = ng.run_op([c for _, c in corner_cases] + [c for _, c in sample_cases])
    worst_corner, worst_outside = 0.0, 0.0
    by_probe: Dict[int, List[float]] = {}
    for (pi, _), r in zip(corner_cases, res[:len(corner_cases)]):
        by_probe.setdefault(pi, []).append(observed(a, a.probes[pi], next(iter(r.values()))))
    for pi, probe in enumerate(a.probes):
        lo, hi = a.interval(hid, probe, s_lo, s_hi)
        got = by_probe[pi]
        for want, have in ((lo, min(got)), (hi, max(got))):
            if not _close(want, have):
                worst_corner = max(worst_corner, math.inf if math.isinf(want) or math.isinf(have)
                                   else abs(want - have) - (3e-6 + 2e-6 * max(abs(want), abs(have))))
    for (pi, _), r in zip(sample_cases, res[len(corner_cases):]):
        probe = a.probes[pi]
        v = observed(a, probe, next(iter(r.values())))
        lo, hi = a.interval(hid, probe, s_lo, s_hi)
        if math.isinf(v):
            if not math.isinf(hi):
                worst_outside = math.inf
            continue
        tol = 3e-6 + 2e-6 * max(abs(lo), abs(v)) if not math.isinf(lo) else 0.0
        if v < lo - tol or (not math.isinf(hi) and v > hi + tol):
            worst_outside = max(worst_outside, (lo - v) if v < lo else (v - hi))
    return {"corner_excess_v": worst_corner, "outside_v": worst_outside,
            "corners": len(corner_cases), "samples": len(sample_cases)}


def run(models: Dict[str, BuildModel], n_samples: int = 12, meter: Meter = Meter(), seed: int = 20261008,
        kinds: Sequence[str] = ("v", "r")) -> Dict[str, Dict]:
    out = {}
    for name, model in models.items():
        a = Analysis(model, meter, kinds=kinds)
        rng = random.Random(seed)
        worst_c = worst_o = 0.0
        corners = samples = 0
        bad = []
        for hid in a.hyps:
            r = check_hypothesis(a, hid, n_samples, rng)
            worst_c = max(worst_c, r["corner_excess_v"])
            worst_o = max(worst_o, r["outside_v"])
            corners += r["corners"]
            samples += r["samples"]
            if r["corner_excess_v"] > 0 or r["outside_v"] > 0:
                bad.append((hid, r))
        out[name] = {"hypotheses": len(a.hyps), "readings": len(a.probes), "corner_runs": corners,
                     "sample_runs": samples, "worst_corner_excess_v": worst_c, "worst_outside_v": worst_o,
                     "mismatches": bad}
    return out


def standard_models() -> Dict[str, BuildModel]:
    import bench_template as bt
    from ai.form_producer import FormProducer
    from generators.registry import default_registry

    reg = default_registry()
    out = {}
    for name, (fn, fields) in bt.STANDARD.items():
        intent = FormProducer(reg).build(fn, fields)
        gen = reg.dispatch(intent).generator
        out[name] = BuildModel.from_circuit(gen.generate(intent))
    return out


if __name__ == "__main__":
    want = sys.argv[1:]
    sys.argv = sys.argv[:1]
    models = {k: v for k, v in standard_models().items() if not want or k in want}
    res = run(models)
    for name, r in res.items():
        print(f"{name:16s} {r['hypotheses']:3d} hypotheses × {r['readings']} readings: "
              f"{r['corner_runs']} corner + {r['sample_runs']} interior ngspice points — "
              f"worst corner miss {r['worst_corner_excess_v']:.2e}, worst point outside {r['worst_outside_v']:.2e}"
              f"  {'OK' if not r['mismatches'] else 'MISMATCH ' + str([m[0] for m in r['mismatches']][:6])}")
