"""
How accurate is the build check? Measured, with ngspice as the board.

    python scripts/build_check_accuracy.py [--trials N] [--json out.json] [design ...]

No hardware is involved and none is claimed: the "board" is ngspice, a solver that shares
no code with `validation/build_check.py`. For every design the check lists faults for, and
for each one, `N` random builds are made: every part drawn uniformly inside its tolerance
box, the rail drawn inside its design range, the LED's saturation current drawn inside its
datasheet box; the fault is wired into the netlist; ngspice reads each probe through the
meter's 10 MΩ input; and the meter adds error inside its stated accuracy and rounds to its
resolution. The check is then given only what a person would give it — the rail and the
readings its own plan asks for — and its verdict is scored against what was actually built.

What is measured (nothing is assumed):

  correct builds       how often it says "as designed"; how often it names a fault that is
                       not there; how often it says "unexplained" — the case that reopens D1
                       against a model that was never wrong.
  detectable faults    how often it notices; how often it names exactly the fault built;
                       how often the readings fit several faults and it lists them all; how
                       often it names the wrong one.
  blind faults         the ones the check said no DC reading can see: does it stay quiet, as it
                       said it would? Counting these as misses would be counting its honesty
                       against it; counting them as passes would be dishonest — so they are
                       reported on their own line.
  guarantee replay     for every detectable fault, every corner of its tolerance box × the rail
                       at both ends and its middle × the meter's error pushed as far toward the
                       correct build as its accuracy allows: the verdict must never be "as
                       designed". This is the claim in the module docstring, attacked.
  outside the claim    parts twice as loose as stated; a meter twice as bad as stated; faults
                       nobody listed (a part 1.25× or 0.8× its value, two faults at once). The
                       guarantee does not cover these — the rates say what happens anyway.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for _k, _v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
               "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(_k, _v)

import ngspice_batch as ng  # noqa: E402
from build_check_oracle import TEST_AMPS, standard_models, to_copy  # noqa: E402
from proof.netlist import Element, Netlist  # noqa: E402
from validation.build_check import (Analysis, BuildModel, Hypothesis, Meter, Probe, VT,  # noqa: E402
                                    _Struct)

CORPUS = ROOT / "backend" / "data" / "reference_designs.json"


# ── The reference designs as build models ────────────────────────────────────

def _led_is(vf: float, n: float, if_ref_a: float) -> float:
    return if_ref_a / math.expm1(vf / (n * VT))


def reference_models() -> Dict[str, BuildModel]:
    corp = json.loads(CORPUS.read_text(encoding="utf-8"))
    out: Dict[str, BuildModel] = {}
    for entry in corp["designs"]:
        if not any(e["kind"] == "V" for e in entry["elements"]):
            continue                                      # nothing to power: a bare network has no DC reading
        var = {k: v[len(v) // 2] for k, v in (entry.get("variants") or {}).items()}
        supply = entry["supply_v"]
        els: List[Element] = []
        boxes: Dict[str, Tuple[Fraction, Fraction]] = {}
        parts: List[str] = []
        diode_is: Dict[str, Tuple[float, float]] = {}
        models: Dict[str, Tuple[Fraction, Fraction]] = {}
        supply_el = None
        for e in entry["elements"]:
            k = e["kind"]
            if k == "V":
                els.append(Element("V", e["id"], e["a"], "0", value=Fraction(str(supply["nominal"]))))
                supply_el = e
            elif k in ("R", "C"):
                raw = e.get("ohm") if k == "R" else e.get("farad")
                if isinstance(raw, str) and raw.startswith("$"):
                    raw = var[raw[1:]]
                val = Fraction(str(raw))
                els.append(Element(k, e["id"], e["a"], e["b"], value=val))
                if e["id"] == "RP":                       # the MCU pin's output resistance: a model, not a part
                    boxes[e["id"]] = (val / 2, val * 3 / 2)
                else:
                    tol = Fraction(str(e.get("tol", 0.0)))
                    boxes[e["id"]] = (val * (1 - tol), val * (1 + tol))
                    parts.append(e["id"])
            elif k == "LED":
                led = corp["leds"][e["led"]]
                name = "D_" + e["led"].upper()
                n = led["n"]
                i_ref = led["if_ref_ma"] / 1000
                models[name] = (Fraction(_led_is(led["vf_typ_v"], n, i_ref)), Fraction(n))
                els.append(Element("D", e["id"], e["a"], e["b"], model=name))
                parts.append(e["id"])
                diode_is[e["id"]] = (_led_is(led["vf_max_v"], n, i_ref), _led_is(led["vf_min_v"], n, i_ref))
        nl = Netlist(elements=els, diode_models=models, analysis="op")
        supply_node = supply_el["a"]
        touched = {n for e in els if e.name in parts for n in (e.a, e.b)}
        probes = tuple(n for n in nl.nodes() if n in touched and n != supply_node)
        nets = tuple(sorted(set(nl.nodes()))) + ("0",)
        cond = ("the logic level is driven high by the firmware",) if any(e["kind"] == "LED" for e in entry["elements"]) else ()
        out[entry["id"]] = BuildModel(nl, boxes, tuple(parts), {p: p for p in parts}, nets, probes, supply_node,
                                      supply_el["id"], (supply["min"], supply["max"]), (), diode_is, cond)
    return out


# ── Building and reading a board ─────────────────────────────────────────────

def sample(a: Analysis, h: Hypothesis, rng: random.Random, tol_scale: float = 1.0) -> Tuple[Dict[str, float], float, Optional[float]]:
    names = [n for n, (lo, hi) in h.boxes.items() if lo != hi and any(r[0] == n for r in h.struct.res)]
    rv = {}
    for n in names:
        lo, hi = float(h.boxes[n][0]), float(h.boxes[n][1])
        if hi / lo > 1.5:                                  # a wrong-value range: a mistake is as likely at 2× as at 10×
            rv[n] = math.exp(rng.uniform(math.log(lo), math.log(hi)))
            continue
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * tol_scale
        rv[n] = rng.uniform(mid - half, mid + half)
    s_lo, s_hi = a.model.supply_range
    s = rng.uniform(s_lo, s_hi)
    is_ = None
    if h.struct.diodes:
        box = a.model.diode_is.get(h.struct.diodes[0][0])
        if box:
            is_ = math.exp(rng.uniform(math.log(box[0]), math.log(box[1])))
    return rv, s, is_


def read(meter: Meter, true: float, rng: random.Random, scale: float = 1.0) -> float:
    """A reading inside the stated accuracy (gain and digits), then rounded to the range's resolution."""
    res = meter.resolution(true)
    err = scale * (meter.gain * abs(true) * rng.uniform(-1, 1) + (meter.digits - 0.5) * res * rng.uniform(-1, 1))
    return round((true + err) / res) * res


def read_ohms(meter: Meter, true: float, rng: random.Random, scale: float = 1.0) -> float:
    """An ohm-range reading inside the stated accuracy, rounded to the range's resolution; OL above the top."""
    if true > meter.overload_ohm:
        return math.inf
    res = meter.r_resolution(true)
    err = scale * (meter.r_gain * true * rng.uniform(-1, 1) + (meter.r_digits - 0.5) * res * rng.uniform(-1, 1))
    v = max(0.0, round((true + err) / res) * res)
    return v if v <= meter.overload_ohm else math.inf


def simulate(a: Analysis, h: Hypothesis, builds: Sequence[Tuple[Dict[str, float], float, Optional[float]]],
             keys: Optional[Sequence[str]] = None) -> List[Dict[str, float]]:
    """
    True values of the readings in `keys` (default: every one), plus the rail, for each build — by ngspice.
    A voltage is what the meter sees through its input resistance; a resistance is the true ohms, however large.
    """
    by_key = {p.key: p for p in a.probes}
    probes = [by_key[k] for k in (keys if keys is not None else by_key)]
    probes = probes + [Probe(a.model.supply_node)]
    copies = [to_copy(a, h, rv, s, is_, p) for rv, s, is_ in builds for p in probes]
    res = ng.run_op(copies)
    out = []
    for i in range(len(builds)):
        row = {}
        for j, p in enumerate(probes):
            raw = next(iter(res[i * len(probes) + j].values()))
            row[p.key] = raw / TEST_AMPS if p.kind == "r" else raw
        out.append(row)
    return out


def verdict_for(a: Analysis, true: Dict[str, float], keys: Sequence[str], rng: random.Random, meter_scale: float = 1.0):
    by_key = {p.key: p for p in a.probes}
    readings = {}
    for k in keys:
        readings[k] = (read_ohms if by_key[k].kind == "r" else read)(a.meter, true[k], rng, meter_scale)
    if any(by_key[k].kind == "v" for k in keys):
        sn = a.model.supply_node
        readings[sn] = read(a.meter, true[sn], rng, meter_scale)
    return a.diagnose(readings)


def adversarial_reading(a: Analysis, true: Dict[str, float], plan_keys: Sequence[str], sign_s: int) -> Dict[str, float]:
    """Every reading pushed as far toward the correct build as the meter's accuracy allows."""
    sn = a.model.supply_node
    by_key = {p.key: p for p in a.probes}
    readings = {}
    s_lo, s_hi = a.model.supply_range
    if any(by_key[k].kind == "v" for k in plan_keys):
        vs = true[sn] + sign_s * a.meter.uncertainty(true[sn])
        s_lo, s_hi = a._supply_box(vs)
        readings[sn] = vs
    for k in plan_keys:
        p = by_key[k]
        if p.kind == "r":
            t = true[k]
            if t > a.meter.overload_ohm:
                readings[k] = math.inf
                continue
            lo, hi = a.interval("as-designed", p)
            u = a.meter.r_uncertainty(t)
            mid = lo if math.isinf(hi) else (lo + hi) / 2
        else:
            lo, hi = a.interval("as-designed", p, s_lo, s_hi)
            t = true[k]
            u = a.meter.uncertainty(t)
            mid = (lo + hi) / 2
        if t < lo:
            r = min(t + u, mid)
        elif t > hi:
            r = max(t - u, mid)
        else:
            r = t
        readings[k] = r
    return readings


# ── The experiment ───────────────────────────────────────────────────────────

def classify(truth_listed: bool, truth_id: Optional[str], v) -> str:
    if truth_id is None:                                  # a correct build, or one the check says is invisible
        if v.status == "unexplained":
            return "false_unexplained" if v.reopens_d1 else "false_part_off"
        return {"as_designed": "correct", "fault": "false_fault", "inconclusive": "inconclusive"}[v.status]
    if v.status in ("as_designed", "inconclusive"):
        return "missed"
    if v.status == "unexplained":
        return "unexplained_d1" if v.reopens_d1 else "unexplained_part_off"
    if truth_id in v.consistent_faults:
        return "exact" if len(v.consistent_faults) == 1 else "ambiguous"
    return "misnamed"


def run_design(name: str, model: BuildModel, n: int, seed: int, meter: Meter,
               kinds: Sequence[str] = ("v", "r")) -> Dict[str, Any]:
    a = Analysis(model, meter, kinds=kinds)
    rng = random.Random(f"{seed}:{name}:{''.join(kinds)}")
    sep = a.detecting()
    plan = a.plan()
    iplan = a.plan(identify=True)
    plan_keys = [p.key for p in plan]
    id_keys = [p.key for p in iplan]
    all_keys = [p.key for p in a.probes]
    detectable = [f for f in a.faults if not f.dc_equivalent and sep.get(f.id)]
    blind = [f for f in a.faults if f.dc_equivalent or not sep.get(f.id)]
    res: Dict[str, Any] = {"kinds": "".join(kinds), "faults": len(a.faults), "detectable": len(detectable),
                           "blind": len(blind), "plan": [p.text() for p in plan], "identify_plan": [p.text() for p in iplan],
                           "plan_size": len(plan) + (1 if any(p.kind == "v" for p in plan) else 0),
                           "identify_size": len(iplan) + (1 if any(p.kind == "v" for p in iplan) else 0),
                           "probes_available": len(a.probes),
                           "meter": f"±({meter.gain * 100:g}% + {meter.digits} digits) V, ±({meter.r_gain * 100:g}% + {meter.r_digits} digits) Ω"}

    def trials(h: Hypothesis, count: int, tol_scale: float = 1.0):
        return [sample(a, h, rng, tol_scale) for _ in range(count)]

    # correct builds
    for label, keys, tol_scale, mscale in (("correct_detect", plan_keys, 1.0, 1.0), ("correct_identify", id_keys, 1.0, 1.0),
                                           ("correct_all", all_keys, 1.0, 1.0),
                                           ("correct_loose_parts_2x", id_keys, 2.0, 1.0), ("correct_bad_meter_2x", id_keys, 1.0, 2.0)):
        builds = trials(a.h0, max(n * 8, 100), tol_scale)
        true = simulate(a, a.h0, builds, keys)
        cnt = Counter(classify(False, None, verdict_for(a, t, keys, rng, mscale)) for t in true)
        res[label] = {"n": len(true), **cnt}

    # detectable faults: the plan's readings, and every reading
    tallies = {"detectable_detect": (Counter(), defaultdict(Counter), []), "detectable_identify": (Counter(), defaultdict(Counter), []),
               "detectable_all": (Counter(), defaultdict(Counter), [])}
    for f in detectable:
        h = a.hyps[f.id]
        true = simulate(a, h, trials(h, n))
        for t in true:
            for label, keys in (("detectable_detect", plan_keys), ("detectable_identify", id_keys), ("detectable_all", all_keys)):
                cnt, per, sizes = tallies[label]
                v = verdict_for(a, t, keys, rng)
                c = classify(True, f.id, v)
                cnt[c] += 1
                per[f.kind][c] += 1
                if v.status == "fault":
                    sizes.append(len(v.consistent_faults))
    for label, (cnt, per, sizes) in tallies.items():
        res[label] = {"n": sum(cnt.values()), **cnt, "by_kind": {k: dict(v) for k, v in per.items()},
                      "mean_candidates": (sum(sizes) / len(sizes)) if sizes else None,
                      "within_3_candidates": (sum(1 for x in sizes if x <= 3) / len(sizes)) if sizes else None}

    # how far off must a resistor be? (the sensitivity of the plan, per part)
    res["sensitivity"] = {model.label(p): {"high": a.min_detectable_factor(p, "high", probes=iplan),
                                           "low": a.min_detectable_factor(p, "low", probes=iplan)}
                          for p in model.parts if model.netlist.element(p).kind == "R"}

    # blind faults: staying quiet is what was promised
    cnt = Counter()
    for f in blind:
        h = a.h0 if f.dc_equivalent else a.hyps[f.id]
        true = simulate(a, h, trials(h, n), id_keys)
        for t in true:
            cnt[classify(False, None, verdict_for(a, t, id_keys, rng))] += 1
    res["blind_plan"] = {"n": sum(cnt.values()), **cnt}

    # the guarantee, attacked: every corner of the fault's box, the rail at 3 points, errors pushed toward the design
    broken, replayed = [], 0
    for f in detectable:
        h = a.hyps[f.id]
        names = [x for x, (lo, hi) in h.boxes.items() if lo != hi and (any(r[0] == x for r in h.struct.res) or x in h.rnet.names)]
        ends = [(float(h.boxes[x][0]), float(h.boxes[x][1])) for x in names]
        is_pts: Tuple[Optional[float], ...] = (None,)
        if h.struct.diodes and h.struct.diodes[0][0] in model.diode_is:
            is_pts = tuple(model.diode_is[h.struct.diodes[0][0]])
        supplies = a.supply_points if any(p.kind == "v" for p in plan) else (a.supply_points[1],)
        builds = []
        for combo in itertools.product(*ends):
            for s in supplies:
                for is_ in is_pts:
                    builds.append((dict(zip(names, combo)), s, is_))
        true = simulate(a, h, builds, plan_keys)
        for t in true:
            for sign in (-1, 1):
                v = a.diagnose(adversarial_reading(a, t, plan_keys, sign))
                replayed += 1
                if v.status in ("as_designed", "inconclusive"):
                    broken.append((f.id, v.status))
    res["guarantee_replay"] = {"readings_replayed": replayed, "violations": len(broken), "first": broken[:5]}

    # outside the claim: faults nobody listed
    unlisted = Counter()
    base = {e.name: e for e in model.netlist.elements}
    r_parts = [p for p in model.parts if base[p].kind == "R"]
    for p in r_parts:
        for factor in (Fraction(5, 4), Fraction(4, 5)):
            els = [Element("R", e.name, e.a, e.b, value=e.value * factor) if e.name == p else e for e in model.netlist.elements]
            nl = Netlist(elements=els, diode_models=model.netlist.diode_models, analysis="op")
            boxes = dict(model.boxes)
            lo, hi = boxes[p]
            boxes[p] = (lo * factor, hi * factor)
            h = Hypothesis(f"{p}x{factor}", "unlisted", nl, boxes, _Struct(nl, model.supply_source, model.follow), None, a.physical)
            true = simulate(a, h, trials(h, max(n // 2, 8)), id_keys)
            for t in true:
                unlisted["near_miss_value:" + classify(True, "none", verdict_for(a, t, id_keys, rng))] += 1
    pairs = [(f1, f2) for f1, f2 in itertools.combinations(
        [f for f in a.faults if f.kind in ("open", "short", "wrong_value") and f.elements[0] in r_parts], 2)
        if f1.elements != f2.elements]
    rng.shuffle(pairs)
    for f1, f2 in pairs[:40]:
        els = []
        for e in model.netlist.elements:
            src = f1 if e.name in f1.elements else f2 if e.name in f2.elements else None
            els.append(next((x for x in src.netlist.elements if x.name == e.name), e) if src else e)
        nl = Netlist(elements=els, diode_models=model.netlist.diode_models, analysis="op")
        boxes = {k: v for k, v in model.boxes.items() if k not in f1.elements + f2.elements}
        for f in (f1, f2):
            for k in f.elements:
                if k in f.boxes:
                    boxes[k] = f.boxes[k]
        h = Hypothesis(f"{f1.id}+{f2.id}", "unlisted", nl, boxes, _Struct(nl, model.supply_source, model.follow), None, a.physical)
        true = simulate(a, h, trials(h, max(n // 4, 4)), id_keys)
        for t in true:
            v = verdict_for(a, t, id_keys, rng)
            truth = {f1.id, f2.id}
            if v.status in ("as_designed", "inconclusive"):
                c = "missed"
            elif v.status == "unexplained":
                c = "unexplained_d1" if v.reopens_d1 else "unexplained_part_off"
            elif truth & set(v.consistent_faults):
                c = "names_one_of_the_two"
            else:
                c = "misnamed"
            unlisted["two_faults:" + c] += 1
    res["unlisted"] = dict(unlisted)
    return res


def pct(x: int, n: int) -> str:
    return f"{100 * x / n:.1f}%" if n else "—"


def summarise(name: str, r: Dict[str, Any]) -> str:
    L = [f"\n### {name}   [{r['faults']} listed faults: {r['detectable']} detectable, {r['blind']} blind; meter {r['meter']}]",
         f"  detect plan   ({r['plan_size']} readings): {r['plan']}",
         f"  identify plan ({r['identify_size']} readings): {r['identify_plan']}"]
    for key, label in (("correct_detect", "detect  "), ("correct_identify", "identify"), ("correct_all", "all     ")):
        c = r[key]
        L.append(f"  correct builds, {label} readings n={c['n']:4d}: as designed {pct(c.get('correct', 0), c['n'])}, "
                 f"named a fault {pct(c.get('false_fault', 0), c['n'])}, charged to D1 {pct(c.get('false_unexplained', 0), c['n'])}, "
                 f"said a part is off {pct(c.get('false_part_off', 0), c['n'])}, inconclusive {pct(c.get('inconclusive', 0), c['n'])}")
    for key, label in (("detectable_detect", "detect  "), ("detectable_identify", "identify"), ("detectable_all", "all     ")):
        d = r[key]
        L.append(f"  detectable faults, {label} readings n={d['n']:4d}: noticed {pct(d['n'] - d.get('missed', 0), d['n'])}, "
                 f"named exactly {pct(d.get('exact', 0), d['n'])}, listed among several {pct(d.get('ambiguous', 0), d['n'])}, "
                 f"wrong name {pct(d.get('misnamed', 0), d['n'])}, charged to D1 {pct(d.get('unexplained_d1', 0), d['n'])}, "
                 f"part-off {pct(d.get('unexplained_part_off', 0), d['n'])}, "
                 f"missed {pct(d.get('missed', 0), d['n'])}"
                 + (f"; suspects named: mean {d['mean_candidates']:.1f}" if d.get("mean_candidates") else ""))
    b = r["blind_plan"]
    if b["n"]:
        L.append(f"  faults no reading is guaranteed to separate  n={b['n']:4d}: the check stayed quiet {pct(b.get('correct', 0), b['n'])}, "
                 f"caught them anyway {pct(b['n'] - b.get('correct', 0), b['n'])}")
    sv = r.get("sensitivity") or {}
    if sv:
        L.append("  a resistor must be this far off before the identify plan can tell (high / low): " + "; ".join(
            f"{k} {('>' + format(v['high'], 'g') + '×') if v['high'] else 'not at 20×'} / "
            f"{('<1/' + format(v['low'], 'g')) if v['low'] else 'not at 1/20'}" for k, v in sv.items()))
    g = r["guarantee_replay"]
    L.append(f"  guarantee replay (detect plan): {g['readings_replayed']} adversarial readings — every corner × 3 rails × meter error "
             f"toward the design — {g['violations']} violations")
    for key, label in (("correct_loose_parts_2x", "parts 2× looser than stated"), ("correct_bad_meter_2x", "meter 2× worse than stated")):
        c = r[key]
        L.append(f"  correct build, {label:28s} n={c['n']:4d}: as designed {pct(c.get('correct', 0), c['n'])}, "
                 f"named a fault {pct(c.get('false_fault', 0), c['n'])}, charged to D1 {pct(c.get('false_unexplained', 0), c['n'])}, "
                 f"part-off {pct(c.get('false_part_off', 0), c['n'])}")
    u = r["unlisted"]
    if u:
        nm = {k: v for k, v in u.items() if k.startswith("near_miss")}
        tf = {k: v for k, v in u.items() if k.startswith("two_faults")}
        if nm:
            n_ = sum(nm.values())
            L.append(f"  unlisted: one part 1.25× or 0.8× off (n={n_}): " + ", ".join(f"{k.split(':')[1]} {pct(v, n_)}" for k, v in sorted(nm.items())))
        if tf:
            n_ = sum(tf.values())
            L.append(f"  unlisted: two faults at once (n={n_}): " + ", ".join(f"{k.split(':')[1]} {pct(v, n_)}" for k, v in sorted(tf.items())))
    return "\n".join(L)


if __name__ == "__main__":
    args = sys.argv[1:]
    n = 20
    if "--trials" in args:
        n = int(args[args.index("--trials") + 1])
    kinds = ("v", "r")
    if "--kinds" in args:
        kinds = tuple(args[args.index("--kinds") + 1].split(","))
    skip = {args[i + 1] for i, x in enumerate(args[:-1]) if x in ("--trials", "--kinds", "--json")}
    want = [x for x in args if not x.startswith("--") and x not in skip]
    models = {**{f"generated:{k}": v for k, v in standard_models().items()},
              **{f"real:{k}": v for k, v in reference_models().items()}}
    if want:
        models = {k: v for k, v in models.items() if any(w in k for w in want)}
    meter = Meter()
    out: Dict[str, Any] = {}
    print(f"# readings: {'+'.join({'v': 'voltage', 'r': 'resistance (power off)'}[k] for k in kinds)}; {n} random builds per fault")
    for name, model in models.items():
        r = run_design(name, model, n, seed=20261008, meter=meter, kinds=kinds)
        out[name] = r
        print(summarise(name, r), flush=True)
    if "--json" in args:
        path = Path(args[args.index("--json") + 1])
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print("\nwrote", path)
