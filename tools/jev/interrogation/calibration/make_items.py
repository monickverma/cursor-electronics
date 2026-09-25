#!/usr/bin/env python3
"""
make_items.py — the pre-registered Circuit OS calibration battery for Jev (TypeSafe AI).

Writes, next to this file:
  items.jsonl    one labelled item per line: its own small state (and, for numeric and rule
                 items, a twin state), its questions, the ground truth of every question and
                 the derivation (formula, inputs, value, limit, source file:line)
  manifest.json  counts, balance, planned requests, the pre-registered analysis plan and the
                 sha256 of items.jsonl

Ground truth comes from Python arithmetic, the project's own generator functions in the
Phase 2 snapshot (origin/phase2-stage0 @ e803a99), or the repository text. Never from Jev.
Deterministic: fixed seed, so a re-run reproduces items.jsonl byte for byte.

Usage:
  python make_items.py [--snapshot <phase2-stage0 checkout at e803a99>]
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace as NS

SEED = 20260925
HERE = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = "/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2"
MODEL = "jev-1.13.0"
NMI = "need_more_information"
NMI_TEXT = "The state does not give enough information to decide."
LEAD = "Using only the model and the values in the state, "
NEAR = (1.01, 1.05)      # |ratio to the limit| for a near-threshold case: 1–5 %
FAR = (1.25, 4.0)        # far case: 25 %–300 %
BAND_FAR = 1.15          # for band questions: at least 15 % from every band edge
rng = random.Random(SEED)


# ── project code ─────────────────────────────────────────────────────────────

def load_project(snapshot):
    for k, v in {"DATABASE_URL": "postgresql+asyncpg://t:t@localhost/t",
                 "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
        os.environ.setdefault(k, v)
    sys.path.insert(0, str(Path(snapshot) / "backend"))
    import generators.common as common
    import generators.rc_lowpass as rc
    import generators.voltage_divider as vd
    import generators.rs485_node as rs
    import generators.dht22_node as dht
    import generators.led_indicator as led
    import generators.netlist.models as models
    import generators.netlist.spice as spice
    import data.mcu_targets as mt
    import data.component_constraints as cc
    return NS(common=common, rc=rc, vd=vd, rs=rs, dht=dht, led=led, models=models, spice=spice,
              mt=mt, cc=cc)


# ── formatting ───────────────────────────────────────────────────────────────

PREFIX = {"M": 1e6, "k": 1e3, "": 1.0, "m": 1e-3, "µ": 1e-6, "n": 1e-9, "p": 1e-12}
ORDER = ("M", "k", "", "m", "µ", "n", "p")


def fmt_num(v, sig=4):
    if v == 0:
        return "0"
    d = sig - int(math.floor(math.log10(abs(v)))) - 1
    r = round(v, d)
    if d <= 0:
        return str(int(round(r)))
    return f"{r:.{d}f}".rstrip("0").rstrip(".")


def si(x, unit, sig=4, prefix=None):
    if unit == "":
        return fmt_num(x, sig)
    if prefix is None:
        prefix = next((p for p in ORDER if abs(x) >= PREFIX[p] * (1 - 1e-9)), "p")
    return f"{fmt_num(x / PREFIX[prefix], sig)} {prefix}{unit}"


def key(text):
    out = text.replace("µ", "u").replace(" ", "_").replace(".", "p").replace("–", "_to_")
    return "".join(ch for ch in out if ch.isalnum() or ch == "_")


def cap(s):
    return s[0].upper() + s[1:]


# ── question builders ────────────────────────────────────────────────────────

def noul(instructions, true, false):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": true, "false": false}}


def choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def score(instructions, levels):
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


def reversed_choice(q):
    return {**q, "criteria": dict(reversed(list(q["criteria"].items())))}


def reversed_score(q):
    return {**q, "criteria": list(reversed(q["criteria"]))}


def compare_pair(qty, L, style):
    """(q_hi, q_lo): 'above L' / 'L or less' (gt) or 'at least L' / 'below L' (ge)."""
    Q = cap(qty)
    if style == "gt":
        hi = noul(f"{LEAD}is {qty} above {L}?", f"{Q} is greater than {L}.", f"{Q} is {L} or less.")
        lo = noul(f"{LEAD}is {qty} {L} or less?", f"{Q} is {L} or less.", f"{Q} is greater than {L}.")
    else:
        hi = noul(f"{LEAD}is {qty} at least {L}?", f"{Q} is {L} or more.", f"{Q} is less than {L}.")
        lo = noul(f"{LEAD}is {qty} below {L}?", f"{Q} is less than {L}.", f"{Q} is {L} or more.")
    return hi, lo


def sufficiency(text):
    return noul(text, "Every quantity or rule the question needs is stated in the state.",
                "At least one quantity or rule the question needs is missing from the state.")


# ── item assembly ────────────────────────────────────────────────────────────

ITEMS = []


def add(item_id, cat, fam, qtype, state, q1, truth1, *, twin=None, twin_form=None, base_form,
        suff=None, suff_truth=True, deriv=None, meta=None):
    qs = {"q1": q1}
    truth = {"q1": truth1}
    if qtype == "noul":
        raise_if(q1["type"] != "noul", item_id)
    if qtype == "choice":
        qs["q2"] = reversed_choice(q1)
        truth["q2"] = truth1
    elif qtype == "score":
        qs["q2"] = reversed_score(q1)
        k = len(q1["criteria"])
        truth["q2"] = truth1 if truth1 == "unanswerable" else k - 1 - truth1
    if suff is not None:
        qs["q3"] = sufficiency(suff)
        truth["q3"] = suff_truth
    ITEMS.append({
        "item_id": item_id, "category": cat, "family": fam, "qtype": qtype,
        "base_form": base_form, "twin_form": twin_form,
        "state": state, "twin_state": twin, "questions": qs, "truth": truth,
        "derivation": deriv or {}, "meta": meta or {},
    })


def add_noul(item_id, cat, fam, state, q_pos, q_neg, truth_pos, **kw):
    """q1 = q_pos (canonical), q2 = its negated-polarity complement."""
    add(item_id, cat, fam, "noul", state, q_pos, truth_pos, **kw)
    it = ITEMS[-1]
    it["questions"] = {"q1": q_pos, "q2": q_neg, **({"q3": it["questions"]["q3"]} if "q3" in it["questions"] else {})}
    t = it["truth"]
    t["q2"] = "unanswerable" if truth_pos == "unanswerable" else (not truth_pos)
    it["truth"] = {"q1": t["q1"], "q2": t["q2"], **({"q3": t["q3"]} if "q3" in t else {})}


def raise_if(cond, msg):
    if cond:
        raise AssertionError(msg)


# ── numeric families (categories a, b, f) ────────────────────────────────────

def plan(n):
    """Balanced (truth, near) combinations, each with a random canonical phrasing."""
    combos = [(True, True), (False, True), (True, False), (False, False)]
    out = [combos[i % 4] for i in range(n)]
    rng.shuffle(out)
    return [(t, nr, rng.random() < 0.5) for t, nr in out]


def ratio(v, L):
    return max(v / L, L / v)


def band_of(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def near_edge(v, edges):
    return any(NEAR[0] <= ratio(v, e) <= NEAR[1] for e in edges)


def far_edges(v, edges):
    return all(ratio(v, e) >= BAND_FAR for e in edges)


def band_texts(qty, edges, unit, eprefix):
    """Ascending band descriptions and ASCII keys for edges e1 < e2 < … ."""
    Q = cap(qty)
    et = [si(e, unit, 4, eprefix[i] if eprefix else None) for i, e in enumerate(edges)]
    descs, keys = [], []
    descs.append(f"{Q} is below {et[0]}")
    keys.append("below_" + key(et[0]))
    for a, b in zip(et, et[1:]):
        descs.append(f"{Q} is from {a} to {b}")
        keys.append(key(a) + "_to_" + key(b))
    descs.append(f"{Q} is above {et[-1]}")
    keys.append("above_" + key(et[-1]))
    return keys, descs


def numeric_family(P, spec):
    """
    spec keys: cat, fam, prefix (id), cands, value(params)->v, state(params)->dict,
    pre(params, v)->dict (twin additions), unit, qty, style, limits [(L, prefix)],
    bands [[edges], [prefixes]|None], score_edges ([edges], prefixes|None), n (noul, choice, score),
    deriv(params, v)->dict, suff (text), steps, twin_form, lim_prefix override
    """
    items_before = len(ITEMS)
    vals = [(c, spec["value"](c)) for c in spec["cands"]]
    vals = [(c, v) for c, v in vals if v is not None and v > 0]
    n_noul, n_choice, n_score = spec["n"]
    idx = 0
    # Nouls
    for truth, near, canon_hi in plan(n_noul):
        idx += 1
        limits = list(spec["limits"])
        rng.shuffle(limits)
        chosen = None
        for L, lp in limits:
            above = truth if canon_hi else (not truth)
            if spec["style"] == "gt":
                pass
            band = NEAR if near else FAR
            pool = [(c, v) for c, v in vals
                    if ((v > L) == above) and band[0] <= ratio(v, L) <= band[1]]
            if pool:
                chosen = (L, lp, rng.choice(pool))
                break
        raise_if(chosen is None, f"{spec['fam']}: no case for truth={truth} near={near}")
        L, lp, (c, v) = chosen
        Ltext = si(L, spec["unit"], 4, lp)
        hi, lo = compare_pair(spec["qty"], Ltext, spec["style"])
        hi_truth = (v > L) if spec["style"] == "gt" else (v >= L)
        q1, q2 = (hi, lo) if canon_hi else (lo, hi)
        t1 = hi_truth if canon_hi else (not hi_truth)
        raise_if(t1 != truth, "truth mismatch")
        state = spec["state"](c)
        twin = {**state, **spec["pre"](c, v, lp)}
        d = {**spec["deriv"](c, v), "limit": L, "limit_text": Ltext,
             "relation_q1": ("value > limit" if canon_hi else "value <= limit") if spec["style"] == "gt"
             else ("value >= limit" if canon_hi else "value < limit"),
             "margin_rel": v / L - 1.0}
        iid = f"{spec['prefix']}-N{idx:02d}"
        add_noul(iid, spec["cat"], spec["fam"], state, q1, q2, t1, twin=twin,
                 twin_form=spec.get("twin_form", "precomputed"), base_form="compute",
                 suff=spec["suff"], deriv=d,
                 meta={"near": near, "steps": spec["steps"], "unit_trap": spec.get("unit_trap", False)})
    # Choices (bands + need_more_information)
    for j in range(n_choice):
        idx += 1
        near = (j % 2 == 0)
        edges, eprefix = spec["bands"][j % len(spec["bands"])]
        keys, descs = band_texts(spec["qty"], edges, spec["unit"], eprefix)
        target = rng.randrange(len(edges) + 1)
        pool = [(c, v) for c, v in vals if band_of(v, edges) == target and
                (near_edge(v, edges) if near else far_edges(v, edges))]
        if not pool:
            for target in rng.sample(range(len(edges) + 1), len(edges) + 1):
                pool = [(c, v) for c, v in vals if band_of(v, edges) == target and
                        (near_edge(v, edges) if near else far_edges(v, edges))]
                if pool:
                    break
        raise_if(not pool, f"{spec['fam']}: no band case")
        c, v = rng.choice(pool)
        crit = list(zip(keys, descs)) + [(NMI, NMI_TEXT)]
        q1 = choice(f"{LEAD}which range contains {spec['qty']}?", crit)
        state = spec["state"](c)
        twin = {**state, **spec["pre"](c, v, eprefix[0] if eprefix else None)}
        d = {**spec["deriv"](c, v), "band_edges": edges, "band_index": target}
        add(f"{spec['prefix']}-C{idx:02d}", spec["cat"], spec["fam"], "choice", state, q1, keys[target],
            twin=twin, twin_form=spec.get("twin_form", "precomputed"), base_form="compute",
            suff=spec["suff"], deriv=d,
            meta={"near": near, "steps": spec["steps"], "unit_trap": spec.get("unit_trap", False),
                  "k": len(crit)})
    # Scores (ordinal bands)
    for j in range(n_score):
        idx += 1
        near = (j % 2 == 0)
        edges, eprefix = spec["score_edges"]
        _, descs = band_texts(spec["qty"], edges, spec["unit"], eprefix)
        target = rng.randrange(len(edges) + 1)
        pool = []
        for target in [target] + rng.sample(range(len(edges) + 1), len(edges) + 1):
            pool = [(c, v) for c, v in vals if band_of(v, edges) == target and
                    (near_edge(v, edges) if near else far_edges(v, edges))]
            if pool:
                break
        raise_if(not pool, f"{spec['fam']}: no score case")
        c, v = rng.choice(pool)
        q1 = score(f"{LEAD}which level describes {spec['qty']}?", descs)
        state = spec["state"](c)
        twin = {**state, **spec["pre"](c, v, eprefix[0] if eprefix else None)}
        d = {**spec["deriv"](c, v), "level_edges": edges, "level": target}
        add(f"{spec['prefix']}-S{idx:02d}", spec["cat"], spec["fam"], "score", state, q1, target,
            twin=twin, twin_form=spec.get("twin_form", "precomputed"), base_form="compute",
            suff=spec["suff"], deriv=d,
            meta={"near": near, "steps": spec["steps"], "unit_trap": spec.get("unit_trap", False),
                  "k": len(descs)})
    return ITEMS[items_before:]


def pre_value(label, source_fn, unit, sig=4, prefix=None):
    def f(c, v, lp):
        return {f"{label} (computed in code by {source_fn})": si(v, unit, sig, prefix if prefix != "limit" else lp)}
    return f


# Values in the state are written from exact numbers: E96 values have three significant figures,
# capacitors and voltages are catalogue values, so the displayed number is the number used.

def R(x, sig=3, prefix=None):
    return si(x, "Ω", sig, prefix)


def C(x, prefix=None):
    return si(x, "F", 3, prefix)


def V(x, prefix=None):
    return si(x, "V", 4, prefix)


def specs(P):
    e96 = P.common.e96_values
    caps = [(row[0]) for row in P.rc._CAPACITORS]  # rc_lowpass.py:128-137
    S = []

    # A1 — RC cutoff, rc_lowpass.cutoff_hz (rc_lowpass.py:139-141)
    def rc_state(c, rp=None, cp=None):
        r, cc_ = c
        return {"circuit": "RC low-pass filter (source → R1 → output node, C1 from output node to ground)",
                "R1": R(r, 3, rp), "C1": C(cc_, cp), "model": "f_c = 1 / (2 × π × R1 × C1)"}

    def rc_value(c):
        v = P.rc.cutoff_hz(*c)
        raise_if(abs(v - 1 / (2 * math.pi * c[0] * c[1])) > 1e-9 * v, "rc cross-check")
        return v

    rc_deriv = lambda c, v: {"formula": "f_c = 1/(2*pi*R1*C1)", "fn": "generators.rc_lowpass.cutoff_hz",
                             "source": "p2/backend/generators/rc_lowpass.py:139-141",
                             "inputs": {"R1_ohm": c[0], "C1_F": c[1]}, "value": v, "units": "Hz"}
    S.append(dict(cat="a_closed_form", fam="rc_cutoff", prefix="A1",
                  cands=[(r, c) for r in e96(1000.0, 100000.0) for c in caps],
                  value=rc_value, state=rc_state, pre=pre_value("f_c", "rc_lowpass.cutoff_hz", "Hz"),
                  unit="Hz", qty="the cutoff frequency f_c", style="gt",
                  limits=[(100.0, ""), (500.0, ""), (1000.0, "k"), (2000.0, "k"), (5000.0, "k"),
                          (10000.0, "k"), (20000.0, "k")],
                  bands=[([500.0, 2000.0], ["", "k"]), ([1000.0, 5000.0], ["k", "k"]),
                         ([200.0, 1000.0], ["", "k"]), ([2000.0, 10000.0], ["k", "k"])],
                  score_edges=([100.0, 1000.0, 10000.0], ["", "k", "k"]), n=(10, 4, 2),
                  deriv=rc_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the cutoff frequency f_c?"))

    # A2 — unloaded divider, voltage_divider.divider_vout (voltage_divider.py:93-95)
    rlist = e96(1000.0, 1e6)[::4]

    def dv_state(c, rp=None):
        vin, r1, r2 = c
        return {"circuit": "Resistive voltage divider, nothing connected to the output",
                "V_in": V(vin), "R1 (from V_in to V_out)": R(r1, 3, rp), "R2 (from V_out to ground)": R(r2, 3, rp),
                "model": "V_out = V_in × R2 / (R1 + R2)"}

    def dv_value(c):
        vin, r1, r2 = c
        v = P.vd.divider_vout(vin, r1, r2, None)
        raise_if(abs(v - vin * r2 / (r1 + r2)) > 1e-9 * v, "divider cross-check")
        return v

    dv_deriv = lambda c, v: {"formula": "V_out = V_in*R2/(R1+R2)", "fn": "generators.voltage_divider.divider_vout",
                             "source": "p2/backend/generators/voltage_divider.py:93-95",
                             "inputs": {"V_in": c[0], "R1_ohm": c[1], "R2_ohm": c[2]}, "value": v, "units": "V"}
    S.append(dict(cat="a_closed_form", fam="divider_vout", prefix="A2",
                  cands=[(vin, r1, r2) for vin in (3.3, 5.0, 9.0, 12.0, 24.0) for r1 in rlist for r2 in rlist],
                  value=dv_value, state=dv_state, pre=pre_value("V_out", "voltage_divider.divider_vout", "V"),
                  unit="V", qty="the output voltage V_out", style="gt",
                  limits=[(3.3, ""), (1.1, ""), (2.5, ""), (5.0, ""), (0.9, "m")],
                  bands=[([1.1, 3.3], None), ([2.5, 5.0], None), ([1.0, 2.5], None)],
                  score_edges=([1.0, 2.5, 3.3], None), n=(10, 4, 2), deriv=dv_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the output voltage V_out?"))

    # A3 — LED current with pin output resistance (models.py:107-113; component_constraints.py:116,157,177)
    boards = [("Arduino Uno (ATmega328P)", 5.0, P.models.pin_resistance("ATmega328P-PU")),
              ("ESP32-DevKitC (ESP32-WROOM-32E)", 3.3, P.models.pin_resistance("ESP32-WROOM-32E")),
              ("WeAct Black Pill (STM32F411CEU6)", 3.3, P.models.pin_resistance("STM32F411CEU6"))]

    def led_state(c, rp=None):
        (bname, vp, ro), vf, r1 = c
        return {"circuit": "LED indicator: GPIO pin driven high → R1 → LED → ground", "board": bname,
                "V_pin (pin voltage with no load)": V(vp), "R_out (pin output resistance)": R(ro, 3),
                "V_f (LED forward voltage, treat as constant)": V(vf), "R1": R(r1, 3, rp),
                "model": "I = (V_pin − V_f) / (R1 + R_out)"}

    def led_value(c):
        (bname, vp, ro), vf, r1 = c
        return (vp - vf) / (r1 + ro) if vp > vf else None

    led_deriv = lambda c, v: {"formula": "I = (V_pin - V_f)/(R1 + R_out)", "fn": "python (stated linear model)",
                              "source": "R_out from p2/backend/data/component_constraints.py:116,157,177 via "
                                        "generators/netlist/models.py:107-113; the project's predict() solves a "
                                        "Shockley diode instead (models.py:70-89, led_indicator.py:182-184) — labels "
                                        "follow the constant-V_f model the state gives",
                              "inputs": {"board": c[0][0], "V_pin": c[0][1], "R_out": c[0][2], "V_f": c[1],
                                         "R1_ohm": c[2]}, "value": v, "units": "A"}
    S.append(dict(cat="a_closed_form", fam="led_current", prefix="A3",
                  cands=[(b, vf, r1) for b in boards for vf in (1.8, 2.0, 2.2, 2.9, 3.0)
                         for r1 in e96(10.0, 10000.0)[::2] if b[1] - vf >= 0.25],
                  value=led_value, state=led_state, pre=pre_value("I", "the stated model", "A"),
                  unit="A", qty="the LED current I", style="gt",
                  limits=[(0.020, "m"), (0.025, "m"), (0.010, "m"), (0.005, "m"), (0.002, "m")],
                  bands=[([0.010, 0.020], None), ([0.005, 0.010], None), ([0.002, 0.010], None)],
                  score_edges=([0.005, 0.010, 0.020, 0.025], None), n=(10, 4, 2), deriv=led_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the LED current I?"))

    # A4 — resistor dissipation vs package rating (common.py:36; rs485_node.py:101)
    ratings = [(0.0625, "0402", "62.5 mW"), (0.1, "0603", "100 mW"), (0.125, "0805", "125 mW"), (0.25, "1206", "250 mW")]

    def pd_state(c, rp=None):
        form, x, r = c
        st = {"component": "R1, a thick-film chip resistor", "R1": R(r, 3, rp)}
        if form == "V":
            st["voltage across R1"] = V(x)
            st["model"] = "P = V² / R1"
        else:
            st["current through R1"] = si(x, "A", 4, "m")
            st["model"] = "P = I² × R1"
        return st

    def pd_value(c):
        form, x, r = c
        return x * x / r if form == "V" else x * x * r

    pd_deriv = lambda c, v: {"formula": "P = V^2/R or I^2*R", "fn": "python",
                             "source": "ratings: p2/backend/generators/common.py:36 (0402 62.5 mW), "
                                       "p2/backend/generators/rs485_node.py:101 (1206 250 mW)",
                             "inputs": {"form": c[0], "x": c[1], "R1_ohm": c[2]}, "value": v, "units": "W"}
    pd_cands = ([("V", vv, r) for vv in (3.3, 5.0, 12.0, 24.0) for r in e96(10.0, 100000.0)[::2]] +
                [("I", ii, r) for ii in (0.005, 0.01, 0.02, 0.05, 0.1) for r in e96(1.0, 10000.0)[::2]])
    S.append(dict(cat="a_closed_form", fam="resistor_dissipation", prefix="A4",
                  cands=pd_cands, value=pd_value, state=pd_state, pre=pre_value("P", "the stated model", "W"),
                  unit="W", qty="the power P dissipated in R1", style="gt",
                  limits=[(0.0625, "m"), (0.1, "m"), (0.125, "m"), (0.25, "m")],
                  bands=[([0.0625, 0.1, 0.125, 0.25], ["m", "m", "m", "m"])],
                  score_edges=([0.0625, 0.1, 0.125, 0.25], ["m", "m", "m", "m"]), n=(10, 4, 2),
                  deriv=pd_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the power dissipated in R1?"))

    # A5a — DHT22 pull-up rise time, dht22_node.rise_time_us (dht22_node.py:95,161-162); limit 5 µs
    # (component_constraints.py:27)
    def rt_state(c):
        r, cpf = c
        return {"circuit": "DHT22 DATA line: open-drain output with a pull-up resistor to VCC",
                "R_pullup": R(r, 3), "C_bus (total line capacitance)": si(cpf * 1e-12, "F", 3, "p"),
                "model": "t_r (10 % to 90 %) = 2.197 × R_pullup × C_bus"}

    def rt_value(c):
        us = P.dht.rise_time_us(c[0], c[1])
        raise_if(abs(us - math.log(9) * c[0] * c[1] * 1e-6) > 1e-9 * us, "rise cross-check")
        return us * 1e-6

    rt_deriv = lambda c, v: {"formula": "t_r = ln(9)*R*C", "fn": "generators.dht22_node.rise_time_us",
                             "source": "p2/backend/generators/dht22_node.py:95,161-162; limit "
                                       "p2/backend/data/component_constraints.py:27",
                             "inputs": {"R_ohm": c[0], "C_pF": c[1]}, "value": v, "units": "s",
                             "note": "state gives 2.197 for ln(9) = 2.19722"}
    S.append(dict(cat="a_closed_form", fam="rise_time_dht22", prefix="A5",
                  cands=[(r, cpf) for r in e96(1000.0, 20000.0) for cpf in
                         (60.0, 120.0, 220.0, 330.0, 470.0, 520.0, 680.0, 1000.0, 1500.0, 2200.0)],
                  value=rt_value, state=rt_state, pre=pre_value("t_r", "dht22_node.rise_time_us", "s"),
                  unit="s", qty="the rise time t_r", style="gt",
                  limits=[(5e-6, "µ"), (2.5e-6, "µ"), (1e-6, "µ")],
                  bands=[([1e-6, 5e-6], ["µ", "µ"]), ([2.5e-6, 5e-6], ["µ", "µ"])],
                  score_edges=([1e-6, 2.5e-6, 5e-6], ["µ", "µ", "µ"]), n=(10, 4, 2), deriv=rt_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the rise time t_r?"))

    # A5b — I2C 30–70 % rise time, t_r = ln(7/3)·R·C = 0.8473·R·C
    def i2c_state(c):
        r, cpf = c
        return {"circuit": "I2C bus line (SDA) with a pull-up resistor to VCC",
                "R_pullup": R(r, 3), "C_bus (total line capacitance)": si(cpf * 1e-12, "F", 3, "p"),
                "model": "t_r (30 % to 70 % of VCC) = 0.8473 × R_pullup × C_bus"}

    def i2c_value(c):
        return math.log(7 / 3) * c[0] * c[1] * 1e-12

    i2c_deriv = lambda c, v: {"formula": "t_r = ln(7/3)*R*C", "fn": "python",
                              "source": "RC charging from 30 % to 70 %: ln(0.7/0.3) = 0.8473",
                              "inputs": {"R_ohm": c[0], "C_pF": c[1]}, "value": v, "units": "s"}
    S.append(dict(cat="a_closed_form", fam="rise_time_i2c", prefix="A6",
                  cands=[(r, cpf) for r in e96(1000.0, 20000.0) for cpf in (50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 400.0)],
                  value=i2c_value, state=i2c_state, pre=pre_value("t_r", "the stated model", "s"),
                  unit="s", qty="the rise time t_r", style="gt",
                  limits=[(1e-6, "n"), (3e-7, "n")],
                  bands=[([3e-7, 1e-6], ["n", "n"])],
                  score_edges=([3e-7, 1e-6], ["n", "n"]), n=(6, 2, 0), deriv=i2c_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the rise time t_r?"))

    # A7 — RS-485 fail-safe bias, rs485_node.v_ab_mv (rs485_node.py:173-176); 200 mV
    # (component_constraints.py:69); 1.25× margin = 250 mV (rs485_node.py:98)
    def fs_state(c):
        vcc, both, rb = c
        req = ("60 Ω (a 120 Ω terminator at each end of the bus, in parallel)" if both
               else "120 Ω (one 120 Ω terminator; the far end is not terminated)")
        return {"bus": "RS-485 pair A/B, idle: every driver is off", "V_CC": V(vcc),
                "R_up (A to V_CC)": R(rb, 3), "R_down (B to ground)": R(rb, 3),
                "R_eq (termination between A and B)": req,
                "model": "V_AB = V_CC × R_eq / (R_up + R_eq + R_down)"}

    def fs_value(c):
        vcc, both, rb = c
        mv = P.rs.v_ab_mv(vcc, 120.0, rb, rb, 120.0 if both else None)
        req = 60.0 if both else 120.0
        raise_if(abs(mv / 1000 - vcc * req / (2 * rb + req)) > 1e-9, "vab cross-check")
        return mv / 1000.0

    fs_deriv = lambda c, v: {"formula": "V_AB = V_CC*R_eq/(R_up+R_eq+R_down)", "fn": "generators.rs485_node.v_ab_mv",
                             "source": "p2/backend/generators/rs485_node.py:173-176; threshold "
                                       "p2/backend/data/component_constraints.py:69; margin rs485_node.py:98",
                             "inputs": {"V_CC": c[0], "both_ends_terminated": c[1], "R_bias_ohm": c[2]},
                             "value": v, "units": "V"}
    S.append(dict(cat="a_closed_form", fam="rs485_failsafe", prefix="A7",
                  cands=[(vcc, both, rb) for vcc in (5.0, 3.3) for both in (True, False) for rb in e96(100.0, 10000.0)],
                  value=fs_value, state=fs_state, pre=pre_value("V_AB", "rs485_node.v_ab_mv", "V", 4, "m"),
                  unit="V", qty="the idle differential voltage V_AB", style="ge",
                  limits=[(0.2, "m"), (0.25, "m")],
                  bands=[([0.2, 0.25], ["m", "m"])],
                  score_edges=([0.2, 0.25, 0.5], ["m", "m", "m"]), n=(10, 4, 2), deriv=fs_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the idle differential voltage V_AB?"))

    # A8 — terminator worst-case dissipation V_CC²/R (rs485_node.py:304; 1206 = 250 mW rs485_node.py:101)
    def tp_state(c):
        vcc, r = c
        return {"bus": "RS-485 terminator R_term between A and B",
                "V_CC": V(vcc), "R_term": R(r, 3),
                "model (worst case: a driver swings the full supply across R_term)": "P = V_CC² / R_term"}

    tp_deriv = lambda c, v: {"formula": "P = V_CC^2/R_term", "fn": "python (as rs485_node.predict term_worst)",
                             "source": "p2/backend/generators/rs485_node.py:304; ratings common.py:36, rs485_node.py:101",
                             "inputs": {"V_CC": c[0], "R_term_ohm": c[1]}, "value": v, "units": "W"}
    S.append(dict(cat="a_closed_form", fam="termination_power", prefix="A8",
                  cands=[(vcc, r) for vcc in (3.3, 3.6, 5.0, 5.25) for r in e96(40.0, 500.0)],
                  value=lambda c: c[0] ** 2 / c[1], state=tp_state, pre=pre_value("P", "the stated model", "W", 4, "m"),
                  unit="W", qty="the terminator's worst-case dissipation P", style="gt",
                  limits=[(0.0625, "m"), (0.1, "m"), (0.125, "m"), (0.25, "m")],
                  bands=[([0.0625, 0.1, 0.125, 0.25], ["m", "m", "m", "m"])],
                  score_edges=([0.0625, 0.125, 0.25], ["m", "m", "m"]), n=(10, 4, 2), deriv=tp_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the terminator's worst-case dissipation?"))

    # ── b: unit/scale traps with mixed prefixes (same maths, awkward units) ──
    S.append(dict(cat="b_units", fam="units_rc", prefix="B2", unit_trap=True,
                  cands=[(r, c) for r in e96(1000.0, 100000.0) for c in caps],
                  value=rc_value, state=lambda c: rc_state(c, "M", "µ"),
                  pre=pre_value("f_c", "rc_lowpass.cutoff_hz", "Hz", 4, "limit"),
                  unit="Hz", qty="the cutoff frequency f_c", style="gt",
                  limits=[(1000.0, ""), (1e6, "M"), (2000.0, ""), (500.0, "k")],
                  bands=[([1000.0, 1e6], ["", "M"])], score_edges=([1000.0, 1e6], ["", "M"]),
                  n=(3, 1, 0), deriv=rc_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the cutoff frequency f_c?"))
    S.append(dict(cat="b_units", fam="units_led", prefix="B3", unit_trap=True,
                  cands=[(b, vf, r1) for b in boards for vf in (1.8, 2.0, 2.2) for r1 in e96(10.0, 10000.0)[::2]
                         if b[1] - vf >= 0.25],
                  value=led_value, state=lambda c: led_state(c, "k"), pre=pre_value("I", "the stated model", "A", 4, "limit"),
                  unit="A", qty="the LED current I", style="gt",
                  limits=[(0.02, ""), (0.01, ""), (0.005, "")],
                  bands=[([0.005, 0.02], ["", ""])], score_edges=([0.001, 0.01], ["", ""]),
                  n=(3, 0, 1), deriv=led_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the LED current I?"))
    S.append(dict(cat="b_units", fam="units_dissipation", prefix="B4", unit_trap=True,
                  cands=[("V", vv, r) for vv in (5.0, 12.0, 24.0) for r in e96(10.0, 100000.0)[::2]],
                  value=pd_value, state=lambda c: pd_state(c, "k"), pre=pre_value("P", "the stated model", "W", 4, "limit"),
                  unit="W", qty="the power P dissipated in R1", style="gt",
                  limits=[(0.125, ""), (0.25, ""), (0.0625, "")],
                  bands=[([0.0625, 0.25], ["", ""])], score_edges=([0.0625, 0.25], ["", ""]),
                  n=(2, 1, 1), deriv=pd_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the power dissipated in R1?"))
    S.append(dict(cat="b_units", fam="units_divider", prefix="B5", unit_trap=True,
                  cands=[(vin, r1, r2) for vin in (5.0, 12.0, 24.0) for r1 in rlist for r2 in rlist],
                  value=dv_value, state=lambda c: dv_state(c, "M"), pre=pre_value("V_out", "voltage_divider.divider_vout", "V", 4, "limit"),
                  unit="V", qty="the output voltage V_out", style="gt",
                  limits=[(3.3, "m"), (1.1, "m"), (2.5, "m")],
                  bands=[([1.1, 3.3], ["m", "m"])], score_edges=([1.1, 3.3], ["m", "m"]),
                  n=(2, 2, 0), deriv=dv_deriv, steps=1,
                  suff="Does the state give a value for every quantity needed to compute the output voltage V_out?"))

    # ── f: multi-step chains ──
    # F1 divider → 10-bit ADC code
    def adc_state(c):
        vin, r1, r2, vref = c
        return {"circuit": "Divider feeding a 10-bit ADC input (the ADC input draws no current)",
                "V_in": V(vin), "R1 (from V_in to V_out)": R(r1, 3), "R2 (from V_out to ground)": R(r2, 3),
                "ADC": f"10-bit, V_ref = {V(vref)}",
                "model": "step 1: V_out = V_in × R2 / (R1 + R2); step 2: code = floor(1024 × V_out / V_ref), at most 1023"}

    def adc_value(c):
        vin, r1, r2, vref = c
        vout = P.vd.divider_vout(vin, r1, r2, None)
        if vout >= vref:
            return None
        return float(min(1023, math.floor(1024 * vout / vref)))

    def adc_pre(c, v, lp):
        vin, r1, r2, vref = c
        vout = P.vd.divider_vout(vin, r1, r2, None)
        return {"V_out (computed in code by voltage_divider.divider_vout)": V(vout),
                "ADC code (computed in code)": str(int(v))}

    adc_deriv = lambda c, v: {"formula": "code = min(1023, floor(1024*V_in*R2/(R1+R2)/V_ref))",
                              "fn": "generators.voltage_divider.divider_vout + python floor",
                              "source": "p2/backend/generators/voltage_divider.py:93-95",
                              "inputs": {"V_in": c[0], "R1_ohm": c[1], "R2_ohm": c[2], "V_ref": c[3]},
                              "value": v, "units": "counts"}
    S.append(dict(cat="f_multistep", fam="divider_to_adc", prefix="F1",
                  cands=[(vin, r1, r2, vref) for vin in (5.0, 12.0, 24.0) for r1 in rlist[::2] for r2 in rlist[::2]
                         for vref in (5.0, 3.3, 1.1)],
                  value=adc_value, state=adc_state, pre=adc_pre, unit="", qty="the ADC code", style="gt",
                  limits=[(300.0, ""), (512.0, ""), (700.0, ""), (900.0, "")],
                  bands=[([256.0, 768.0], ["", ""])], score_edges=([256.0, 512.0, 768.0], ["", "", ""]),
                  n=(4, 1, 1), deriv=adc_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute the ADC code?"))

    # F2 RC attenuation at a signal frequency
    def att_state(c):
        r, cc_, fs = c
        return {"circuit": "RC low-pass filter driven by a sine wave",
                "R1": R(r, 3), "C1": C(cc_), "signal frequency f": si(fs, "Hz", 3),
                "model": "step 1: f_c = 1 / (2 × π × R1 × C1); step 2: |H| = 1 / √(1 + (f / f_c)²), "
                         "the output amplitude as a fraction of the input amplitude"}

    def att_value(c):
        r, cc_, fs = c
        fc = P.rc.cutoff_hz(r, cc_)
        return 1.0 / math.sqrt(1.0 + (fs / fc) ** 2)

    def att_pre(c, v, lp):
        r, cc_, fs = c
        return {"f_c (computed in code by rc_lowpass.cutoff_hz)": si(P.rc.cutoff_hz(r, cc_), "Hz", 4),
                "|H| (computed in code)": fmt_num(v, 4)}

    att_deriv = lambda c, v: {"formula": "|H| = 1/sqrt(1+(f/f_c)^2), f_c = 1/(2*pi*R*C)",
                              "fn": "generators.rc_lowpass.cutoff_hz + python",
                              "source": "p2/backend/generators/rc_lowpass.py:139-141",
                              "inputs": {"R1_ohm": c[0], "C1_F": c[1], "f_Hz": c[2]}, "value": v, "units": "ratio"}
    S.append(dict(cat="f_multistep", fam="rc_attenuation", prefix="F2",
                  cands=[(r, cc_, fs) for r in e96(1000.0, 100000.0)[::3] for cc_ in caps
                         for fs in (50.0, 200.0, 1000.0, 5000.0, 20000.0)],
                  value=att_value, state=att_state, pre=att_pre, unit="", qty="the gain |H| (output amplitude ÷ input amplitude)", style="gt",
                  limits=[(0.5, ""), (0.707, ""), (0.3, ""), (0.1, "")],
                  bands=[([0.1, 0.5], ["", ""])], score_edges=([0.1, 0.5, 0.9], ["", "", ""]),
                  n=(4, 1, 1), deriv=att_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute |H| at the signal frequency?"))

    # F3 LED current → R1 dissipation
    def lp_value(c):
        i = led_value(c)
        return None if i is None else i * i * c[2]

    def lp_pre(c, v, lp):
        return {"I (computed in code)": si(led_value(c), "A", 4, "m"),
                "P_R1 (computed in code)": si(v, "W", 4, "m")}

    lp_deriv = lambda c, v: {"formula": "I = (V_pin-V_f)/(R1+R_out); P = I^2*R1", "fn": "python (stated model)",
                             "source": "R_out: p2/backend/data/component_constraints.py:116,157,177",
                             "inputs": {"board": c[0][0], "V_pin": c[0][1], "R_out": c[0][2], "V_f": c[1], "R1_ohm": c[2]},
                             "value": v, "units": "W"}
    S.append(dict(cat="f_multistep", fam="led_to_r1_power", prefix="F3",
                  cands=[(b, vf, r1) for b in boards[:1] for vf in (1.8, 2.0, 2.2) for r1 in e96(5.0, 2000.0)],
                  value=lp_value,
                  state=lambda c: {**led_state(c), "model": "step 1: I = (V_pin − V_f) / (R1 + R_out); step 2: P_R1 = I² × R1"},
                  pre=lp_pre, unit="W", qty="the power P_R1 dissipated in R1", style="gt",
                  limits=[(0.0625, "m"), (0.05, "m"), (0.025, "m")],
                  bands=[([0.025, 0.0625], ["m", "m"])], score_edges=([0.025, 0.0625], ["m", "m"]),
                  n=(4, 1, 1), deriv=lp_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute the power dissipated in R1?"))

    # F4 RS-485: parallel terminators → V_AB
    def fs2_state(c):
        vcc, rfar, rb = c
        return {"bus": "RS-485 pair A/B, idle: every driver is off", "V_CC": V(vcc),
                "R_term (this end, between A and B)": "120 Ω",
                "R_far (far-end terminator between A and B)": "not fitted" if rfar is None else R(rfar, 3),
                "R_up (A to V_CC)": R(rb, 3), "R_down (B to ground)": R(rb, 3),
                "model": "step 1: R_eq = R_term in parallel with R_far (R_eq = R_term if R_far is not fitted); "
                         "step 2: V_AB = V_CC × R_eq / (R_up + R_eq + R_down)"}

    def fs2_value(c):
        vcc, rfar, rb = c
        return P.rs.v_ab_mv(vcc, 120.0, rb, rb, rfar) / 1000.0

    def fs2_pre(c, v, lp):
        vcc, rfar, rb = c
        req = 120.0 if rfar is None else 120.0 * rfar / (120.0 + rfar)
        return {"R_eq (computed in code)": R(req, 4), "V_AB (computed in code by rs485_node.v_ab_mv)": si(v, "V", 4, "m")}

    fs2_deriv = lambda c, v: {"formula": "R_eq = R_term||R_far; V_AB = V_CC*R_eq/(2*R_bias+R_eq)",
                              "fn": "generators.rs485_node.v_ab_mv", "source": "p2/backend/generators/rs485_node.py:173-176",
                              "inputs": {"V_CC": c[0], "R_far_ohm": c[1], "R_bias_ohm": c[2]}, "value": v, "units": "V"}
    S.append(dict(cat="f_multistep", fam="rs485_parallel_vab", prefix="F4",
                  cands=[(vcc, rfar, rb) for vcc in (5.0, 3.3) for rfar in (None, 120.0, 100.0, 150.0, 1000.0)
                         for rb in e96(100.0, 10000.0)],
                  value=fs2_value, state=fs2_state, pre=fs2_pre, unit="V", qty="the idle differential voltage V_AB", style="ge",
                  limits=[(0.2, "m"), (0.25, "m")],
                  bands=[([0.2, 0.25], ["m", "m"])], score_edges=([0.2, 0.25, 0.5], ["m", "m", "m"]),
                  n=(4, 1, 1), deriv=fs2_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute the idle differential voltage V_AB?"))

    # F5 DHT22: cable length → C_bus → rise time (dht22_node.py:156-158,161-162)
    def cab_state(c):
        r, length, pfm = c
        return {"circuit": "DHT22 DATA line: open-drain output with a pull-up resistor to VCC",
                "R_pullup": R(r, 3), "cable length": si(length, "m", 3, ""),
                "cable capacitance": f"{fmt_num(pfm, 3)} pF per metre",
                "input capacitance": "10 pF at the MCU pin and 10 pF at the sensor",
                "model": "step 1: C_bus = 10 pF + 10 pF + length × (pF per metre); "
                         "step 2: t_r (10 % to 90 %) = 2.197 × R_pullup × C_bus"}

    def cab_value(c):
        r, length, pfm = c
        cpf = 2 * 10.0 + length * pfm
        return P.dht.rise_time_us(r, cpf) * 1e-6

    def cab_pre(c, v, lp):
        r, length, pfm = c
        return {"C_bus (computed in code)": si((20.0 + length * pfm) * 1e-12, "F", 4, "p"),
                "t_r (computed in code by dht22_node.rise_time_us)": si(v, "s", 4, "µ")}

    cab_deriv = lambda c, v: {"formula": "C_bus = 20 pF + L*pF_per_m; t_r = ln(9)*R*C_bus",
                              "fn": "generators.dht22_node.rise_time_us (C_bus as bus_capacitance_pf)",
                              "source": "p2/backend/generators/dht22_node.py:156-158,161-162",
                              "inputs": {"R_ohm": c[0], "length_m": c[1], "pF_per_m": c[2]}, "value": v, "units": "s"}
    S.append(dict(cat="f_multistep", fam="dht22_cable_rise", prefix="F5",
                  cands=[(r, length, pfm) for r in e96(1000.0, 20000.0) for length in (0.3, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0)
                         for pfm in (50.0, 100.0)],
                  value=cab_value, state=cab_state, pre=cab_pre, unit="s", qty="the rise time t_r", style="gt",
                  limits=[(5e-6, "µ"), (2.5e-6, "µ")],
                  bands=[([1e-6, 5e-6], ["µ", "µ"])], score_edges=([1e-6, 2.5e-6, 5e-6], ["µ", "µ", "µ"]),
                  n=(4, 1, 0), deriv=cab_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute the rise time t_r?"))

    # F6 RC with source impedance: loaded cutoff (rc_lowpass.py:185-187 names the shift)
    def src_state(c):
        r, cc_, rs_ = c
        return {"circuit": "RC low-pass filter driven by a source with output impedance R_src in series with R1",
                "R1": R(r, 3), "C1": C(cc_), "R_src": R(rs_, 3),
                "model": "step 1: R_total = R1 + R_src; step 2: f_c = 1 / (2 × π × R_total × C1)"}

    def src_value(c):
        r, cc_, rs_ = c
        return P.rc.cutoff_hz(r + rs_, cc_)

    def src_pre(c, v, lp):
        r, cc_, rs_ = c
        return {"R_total (computed in code)": R(r + rs_, 4),
                "f_c (computed in code by rc_lowpass.cutoff_hz)": si(v, "Hz", 4, lp if lp else None)}

    src_deriv = lambda c, v: {"formula": "f_c = 1/(2*pi*(R1+R_src)*C1)", "fn": "generators.rc_lowpass.cutoff_hz",
                              "source": "p2/backend/generators/rc_lowpass.py:139-141,185-187",
                              "inputs": {"R1_ohm": c[0], "C1_F": c[1], "R_src_ohm": c[2]}, "value": v, "units": "Hz"}
    S.append(dict(cat="f_multistep", fam="rc_source_loaded", prefix="F6",
                  cands=[(r, cc_, rs_) for r in e96(1000.0, 100000.0)[::2] for cc_ in caps
                         for rs_ in (50.0, 600.0, 1000.0, 4700.0, 10000.0)],
                  value=src_value, state=src_state, pre=src_pre, unit="Hz", qty="the loaded cutoff frequency f_c", style="gt",
                  limits=[(1000.0, "k"), (950.0, ""), (500.0, ""), (2000.0, "k")],
                  bands=[([500.0, 2000.0], ["", "k"])], score_edges=([100.0, 1000.0, 10000.0], ["", "k", "k"]),
                  n=(4, 1, 1), deriv=src_deriv, steps=2,
                  suff="Does the state give a value for every quantity needed to compute the loaded cutoff frequency f_c?"))
    return S


# ── b1: unit conversions (hand-written, truth computed) ──────────────────────

def units_b1():
    rows = [  # (name_a, text_a, SI_a, name_b, text_b, SI_b, relation, q_pos, q_neg)
        ("C1", "0.047 µF", 0.047e-6, "C2", "47 nF", 47e-9, "eq", "Is C1 the same capacitance as C2?", "Do C1 and C2 differ in capacitance?"),
        ("R1 (RKM code)", "4k7", 4700.0, "R2", "470 Ω", 470.0, "eq", "Is R1 the same resistance as R2?", "Do R1 and R2 differ in resistance?"),
        ("P1", "208 mW", 0.208, "P2", "0.25 W", 0.25, "gt", "Is P1 more than P2?", "Is P1 at most P2?"),
        ("I1", "0.02 A", 0.02, "I2", "20 mA", 0.02, "eq", "Is I1 the same current as I2?", "Do I1 and I2 differ?"),
        ("f1", "1.59 kHz", 1590.0, "f2", "1.5 MHz", 1.5e6, "gt", "Is f1 higher than f2?", "Is f1 at most f2?"),
        ("C3", "100 nF", 100e-9, "C4", "1 µF", 1e-6, "gt", "Is C3 larger than C4?", "Is C3 at most C4?"),
        ("R3", "10 kΩ", 1e4, "R4", "0.01 MΩ", 1e4, "eq", "Is R3 the same resistance as R4?", "Do R3 and R4 differ in resistance?"),
        ("t1", "5 µs", 5e-6, "t2", "4985 ns", 4985e-9, "gt", "Is t1 longer than t2?", "Is t1 at most t2?"),
        ("V1", "250 mV", 0.25, "V2", "0.2 V", 0.2, "gt", "Is V1 more than V2?", "Is V1 at most V2?"),
        ("P3", "62.5 mW", 0.0625, "P4", "0.0625 W", 0.0625, "eq", "Is P3 the same power as P4?", "Do P3 and P4 differ?"),
        ("C5", "22 pF", 22e-12, "C6", "0.22 nF", 0.22e-9, "eq", "Is C5 the same capacitance as C6?", "Do C5 and C6 differ in capacitance?"),
        ("I3", "1.2 mA", 1.2e-3, "I4", "0.0015 A", 1.5e-3, "gt", "Is I3 more than I4?", "Is I3 at most I4?"),
    ]
    for i, (na, ta, a, nb, tb, b, rel, qp, qn) in enumerate(rows, 1):
        truth = math.isclose(a, b, rel_tol=1e-9) if rel == "eq" else (a > b and not math.isclose(a, b, rel_tol=1e-9))
        state = {na: ta, nb: tb}
        # twin: both written in the same unit
        unit = {"C": "F", "R": "Ω", "P": "W", "I": "A", "f": "Hz", "t": "s", "V": "V"}[na[0]]
        pfx = next(p for p in ORDER if abs(min(a, b)) >= PREFIX[p] * (1 - 1e-9))
        twin = {**state, "both values in the same unit (converted in code)": f"{na} = {si(a, unit, 4, pfx)}; {nb} = {si(b, unit, 4, pfx)}"}
        src = ("p2/backend/generators/netlist/spice.py:20 (_parse_ohms('4k7') = 4700)" if "RKM" in na
               else "SI prefixes (exact conversion in python)")
        add_noul(f"B1-N{i:02d}", "b_units", "unit_conversion", state,
                 noul(f"Using only the values in the state: {qp}", "Yes.", "No."),
                 noul(f"Using only the values in the state: {qn}", "Yes.", "No."), truth,
                 twin=twin, twin_form="precomputed", base_form="compute",
                 suff=f"Does the state give both {na.split()[0]} and {nb} with their units?",
                 deriv={"formula": rel, "source": src, "value_a_SI": a, "value_b_SI": b,
                        "margin_rel": (a / b - 1.0)},
                 meta={"near": rel == "gt" and abs(a / b - 1) <= 0.05, "steps": 1, "unit_trap": True})


def units_b6():
    """Order-of-magnitude choices: options 1000× apart."""
    rows = [
        ("τ = R × C", {"R": "10 kΩ", "C": "100 nF"}, 1e4 * 100e-9, "s", ["µ", "m", ""], "the time constant τ"),
        ("f_c = 1 / (2 × π × R × C)", {"R": "1 kΩ", "C": "1 µF"}, 1 / (2 * math.pi * 1e3 * 1e-6), "Hz", ["m", "", "k"], "the cutoff frequency f_c"),
        ("I = V / R", {"V": "5 V", "R": "2.2 kΩ"}, 5 / 2200, "A", ["µ", "m", ""], "the current I"),
        ("P = V² / R", {"V": "12 V", "R": "4.7 kΩ"}, 144 / 4700, "W", ["µ", "m", ""], "the power P"),
        ("Q = C × V", {"C": "10 µF", "V": "5 V"}, 10e-6 * 5, "C", ["n", "µ", "m"], "the stored charge Q"),
        ("E = ½ × C × V²", {"C": "100 µF", "V": "12 V"}, 0.5 * 100e-6 * 144, "J", ["µ", "m", ""], "the stored energy E"),
        ("t_r = 2.197 × R × C", {"R": "10 kΩ", "C": "200 pF"}, 2.197 * 1e4 * 200e-12, "s", ["n", "µ", "m"], "the rise time t_r"),
        ("V_AB = V_CC × R_eq / (R_up + R_eq + R_down)", {"V_CC": "5 V", "R_eq": "60 Ω", "R_up": "560 Ω", "R_down": "560 Ω"},
         5 * 60 / 1180, "V", ["µ", "m", ""], "the idle differential voltage V_AB"),
    ]
    for i, (formula, vals, value, unit, pfxs, qty) in enumerate(rows, 1):
        right = next(p for p in ORDER if abs(value) >= PREFIX[p] * (1 - 1e-9))
        raise_if(right not in pfxs, f"B6 {i}: prefix {right} not offered")
        mant = value / PREFIX[right]
        opts = []
        for p in pfxs:
            txt = f"about {fmt_num(mant, 2)} {p}{unit}"
            opts.append((key(txt), cap(qty) + f" is {txt}"))
        order = list(range(len(opts)))
        rng.shuffle(order)
        crit = [opts[k] for k in order] + [(NMI, NMI_TEXT)]
        truth = opts[pfxs.index(right)][0]
        state = {**vals, "model": formula}
        twin = {**state, f"{qty.split()[-1]} (computed in code)": si(value, unit, 4, right)}
        add(f"B6-C{i:02d}", "b_units", "order_of_magnitude", "choice", state,
            choice(f"{LEAD}which is {qty}?", crit), truth, twin=twin, twin_form="precomputed", base_form="compute",
            suff=f"Does the state give a value for every quantity needed to compute {qty}?",
            deriv={"formula": formula, "value_SI": value, "units": unit, "source": "python"},
            meta={"near": False, "steps": 1, "unit_trap": True, "k": len(crit)})


# ── c: qualitative electronics rules (recall, with rule-in-state twins) ──────

def qualitative(P):
    uno = P.mt.TARGETS["arduino_uno"]
    esp = P.mt.TARGETS["esp32_devkitc"]
    pwm_rule = {"pin table (Circuit OS data/mcu_targets.py)":
                "Hardware-PWM pins on the Arduino Uno: D3, D5, D6, D9, D10, D11. No other Uno pin has hardware PWM."}
    src_pwm = "p2/backend/data/mcu_targets.py:79; component_constraints.py:104,123; .claude/rules/simulation.md:111"
    # C1 — Uno PWM, nouls
    for i, n in enumerate([2, 3, 4, 5, 6, 7, 8, 9, 11, 12], 1):
        pin = uno.pins[f"D{n}"]
        state = {"board": "Arduino Uno R3 (ATmega328P)",
                 "design": f"The firmware calls analogWrite() on pin D{n} to dim an LED."}
        add_noul(f"C1-N{i:02d}", "c_qualitative", "uno_pwm_pins", state,
                 noul(f"Does pin D{n} on this board support hardware PWM output?",
                      f"D{n} is one of this board's hardware-PWM pins.", f"D{n} has no hardware PWM on this board."),
                 noul(f"Does pin D{n} on this board lack hardware PWM output?",
                      f"D{n} has no hardware PWM on this board.", f"D{n} is one of this board's hardware-PWM pins."),
                 bool(pin.pwm), twin={**state, **pwm_rule}, twin_form="rule_in_state", base_form="recall",
                 deriv={"source": src_pwm, "pin": f"D{n}", "pwm": bool(pin.pwm)}, meta={"steps": 1})
    # C1 — Uno PWM, choices
    for i, opts in enumerate([["D2", "D4", "D10", "D12"], ["D7", "D8", "D13", "D6"],
                              ["D0", "D1", "D11", "D2"], ["D12", "D5", "D4", "D8"]], 1):
        truth = [o for o in opts if uno.pins[o].pwm]
        raise_if(len(truth) != 1, "pwm choice")
        state = {"board": "Arduino Uno R3 (ATmega328P)",
                 "design": "The firmware needs one pin with hardware PWM (analogWrite) to dim an LED; "
                           f"the free pins are {', '.join(opts)}."}
        crit = [(o, f"{o} has hardware PWM on this board") for o in opts] + [(NMI, NMI_TEXT)]
        add(f"C1-C{i:02d}", "c_qualitative", "uno_pwm_pins", "choice", state,
            choice("Which one of the free pins supports hardware PWM output on this board?", crit), truth[0],
            twin={**state, **pwm_rule}, twin_form="rule_in_state", base_form="recall",
            deriv={"source": src_pwm, "options": opts}, meta={"steps": 1, "k": len(crit)})

    # C2 — ESP32 strapping pins (mcu_targets.py:98-104)
    strap_rule = {"strapping pins (Circuit OS data/mcu_targets.py)":
                  "GPIO0 (boot mode: must be high at reset; low enters the download bootloader), "
                  "GPIO2 (boot mode: must be low or floating at reset for serial download), "
                  "GPIO5 (SDIO slave timing at reset), "
                  "GPIO12 (MTDI: sets the flash voltage at reset; pulled high selects 1.8 V and the module will not boot), "
                  "GPIO15 (MTDO: at reset, low silences the boot log and changes SDIO timing). "
                  "No other GPIO is a strapping pin."}
    src_strap = "p2/backend/data/mcu_targets.py:98-104,123"
    for i, n in enumerate([0, 2, 5, 12, 15, 4, 13, 14, 16, 25], 1):
        pin = esp.pins[f"GPIO{n}"]
        state = {"board": "ESP32-DevKitC (ESP32-WROOM-32E module)",
                 "design": f"An external 10 kΩ resistor connects GPIO{n} to 3.3 V."}
        add_noul(f"C2-N{i:02d}", "c_qualitative", "esp32_strapping", state,
                 noul(f"Is GPIO{n} a strapping pin on this module (a pin whose level at reset selects a boot configuration)?",
                      f"GPIO{n} is a strapping pin.", f"GPIO{n} is not a strapping pin."),
                 noul(f"Is GPIO{n} free of any strapping role on this module (its level at reset selects no boot configuration)?",
                      f"GPIO{n} is not a strapping pin.", f"GPIO{n} is a strapping pin."),
                 pin.strapping is not None, twin={**state, **strap_rule}, twin_form="rule_in_state",
                 base_form="recall", deriv={"source": src_strap, "pin": f"GPIO{n}", "strapping": pin.strapping},
                 meta={"steps": 1})
    for i, opts in enumerate([["GPIO4", "GPIO12", "GPIO16", "GPIO25"], ["GPIO13", "GPIO14", "GPIO27", "GPIO15"]], 1):
        truth = [o for o in opts if esp.pins[o].strapping]
        raise_if(len(truth) != 1, "strap choice")
        state = {"board": "ESP32-DevKitC (ESP32-WROOM-32E module)",
                 "design": f"One of {', '.join(opts)} will get an external pull-up; the designer wants to know which "
                           "of them is a strapping pin."}
        crit = [(o, f"{o} is a strapping pin on this module") for o in opts] + [(NMI, NMI_TEXT)]
        add(f"C2-C{i:02d}", "c_qualitative", "esp32_strapping", "choice", state,
            choice("Which one of these pins is a strapping pin on this module?", crit), truth[0],
            twin={**state, **strap_rule}, twin_form="rule_in_state", base_form="recall",
            deriv={"source": src_strap, "options": opts}, meta={"steps": 1, "k": len(crit)})
    sev_levels = ["No effect on booting.",
                  "The module boots normally, but the boot log or SDIO timing changes.",
                  "The module does not boot normally (wrong flash voltage, or it stays in the download bootloader)."]
    for i, (pin, level, truth) in enumerate([(12, "high", 2), (15, "low", 1), (4, "high", 0), (0, "low", 2)], 1):
        state = {"board": "ESP32-DevKitC (ESP32-WROOM-32E module, 3.3 V flash)",
                 "design": f"An external 10 kΩ resistor holds GPIO{pin} {level} while the module comes out of reset."}
        add(f"C2-S{i:02d}", "c_qualitative", "esp32_strapping", "score", state,
            score(f"What happens at reset because GPIO{pin} is held {level}?", sev_levels), truth,
            twin={**state, **strap_rule}, twin_form="rule_in_state", base_form="recall",
            deriv={"source": src_strap + " (0: must be high; 12: high selects 1.8 V; 15: low silences log)"},
            meta={"steps": 2, "k": 3})

    # C3 — ESP32 input-only and flash pins (mcu_targets.py:108-124)
    io_rule = {"pin facts (Circuit OS data/mcu_targets.py)":
               "GPIO34, GPIO35, GPIO36 and GPIO39 are input only, with no internal pull-up or pull-down. "
               "GPIO6 to GPIO11 are wired to the module's SPI flash and must not be used. "
               "Every other exposed GPIO can drive an output."}
    src_io = "p2/backend/data/mcu_targets.py:108-124"
    c3 = [
        ("Can GPIO34 drive an LED as an output?", "Is GPIO34 unable to drive an LED as an output?", False,
         "The firmware wants to drive an LED from GPIO34."),
        ("Can GPIO25 drive an LED as an output?", "Is GPIO25 unable to drive an LED as an output?", True,
         "The firmware wants to drive an LED from GPIO25."),
        ("Is GPIO6 free to use as a general-purpose output on this module?",
         "Is GPIO6 unavailable as a general-purpose output on this module?", False,
         "The designer wants to use GPIO6 as a general-purpose output."),
        ("Is GPIO32 free to use as a general-purpose output on this module?",
         "Is GPIO32 unavailable as a general-purpose output on this module?", True,
         "The designer wants to use GPIO32 as a general-purpose output."),
        ("Does GPIO35 have an internal pull-up resistor that firmware can enable?",
         "Does GPIO35 lack an internal pull-up resistor?", False,
         "A push-button to ground is wired to GPIO35 with no external resistor."),
    ]
    for i, (qp, qn, truth, design) in enumerate(c3, 1):
        state = {"board": "ESP32-DevKitC (ESP32-WROOM-32E module)", "design": design}
        add_noul(f"C3-N{i:02d}", "c_qualitative", "esp32_io_limits", state,
                 noul(qp, "Yes.", "No."), noul(qn, "Yes.", "No."), truth,
                 twin={**state, **io_rule}, twin_form="rule_in_state", base_form="recall",
                 deriv={"source": src_io}, meta={"steps": 1})
    state = {"board": "ESP32-DevKitC (ESP32-WROOM-32E module)",
             "design": "The firmware needs one pin to drive an LED; the free pins are GPIO34, GPIO35, GPIO36 and GPIO26."}
    crit = [(p, f"{p} can drive the LED") for p in ("GPIO34", "GPIO35", "GPIO36", "GPIO26")] + [(NMI, NMI_TEXT)]
    add("C3-C06", "c_qualitative", "esp32_io_limits", "choice", state,
        choice("Which one of the free pins can drive the LED as an output?", crit), "GPIO26",
        twin={**state, **io_rule}, twin_form="rule_in_state", base_form="recall",
        deriv={"source": src_io}, meta={"steps": 1, "k": len(crit)})

    # C4 — SPICE / MNA rules (simulation.md:23-31,86-97; models.py:30-34)
    spice_rule = {"SPICE facts": "A capacitor is an open circuit at DC. A node with no DC path to ground makes the DC "
                                 "operating-point matrix singular. Two voltage sources connected in parallel form a loop "
                                 "of voltage sources, which also makes the matrix singular, even when their voltages "
                                 "agree. A resistor that carries no current has no voltage across it."}
    src_sp = ".claude/rules/simulation.md:23-31,86-97; p2/backend/generators/netlist/models.py:30-34; MNA theory"
    c4 = [
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 10k | C1 OUT NODE_X 100n",
          "note": "NODE_X connects only to C1."},
         "Does NODE_X have a DC path to ground in this netlist?", "Does NODE_X lack any DC path to ground in this netlist?", False),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 10k | C1 OUT NODE_X 100n",
          "note": "NODE_X connects only to C1."},
         "Will the DC operating-point matrix of this netlist be singular because of NODE_X?",
         "Will the DC operating-point matrix of this netlist be non-singular despite NODE_X?", True),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | VMCU VCC 0 DC 5 | R1 VCC OUT 1k | R2 OUT 0 1k",
          "note": "VMCU is meant to represent a microcontroller on the 5 V rail."},
         "Does this netlist contain a loop made only of voltage sources?",
         "Is this netlist free of loops made only of voltage sources?", True),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R_MCU VCC 0 100 | R1 VCC OUT 1k | R2 OUT 0 1k",
          "note": "R_MCU represents a microcontroller on the 5 V rail."},
         "Does this netlist contain a loop made only of voltage sources?",
         "Is this netlist free of loops made only of voltage sources?", False),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 10k | C1 OUT NODE_X 100n | R_TIE NODE_X 0 1G"},
         "Does NODE_X have a DC path to ground in this netlist?", "Does NODE_X lack any DC path to ground in this netlist?", True),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 10k | C1 OUT NODE_X 100n | R_TIE NODE_X 0 1G",
          "question context": "Compare this netlist with the same netlist without R_TIE (where NODE_X would float)."},
         "Does adding R_TIE change the DC voltage at OUT by more than 1 mV?",
         "Does adding R_TIE leave the DC voltage at OUT within 1 mV of its value without R_TIE?", False),
        ({"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC A 1k | R2 A 0 1k | R3 A B 10k",
          "note": "Node B connects only to R3."},
         "Is node B's DC voltage well defined (equal to node A's voltage, because no current flows in R3)?",
         "Is node B's DC voltage undefined (a singular node) because B connects to only one element?", True),
    ]
    for i, (state, qp, qn, truth) in enumerate(c4, 1):
        add_noul(f"C4-N{i:02d}", "c_qualitative", "spice_mna_rules", state, noul(qp, "Yes.", "No."),
                 noul(qn, "Yes.", "No."), truth, twin={**state, **spice_rule}, twin_form="rule_in_state",
                 base_form="recall", deriv={"source": src_sp}, meta={"steps": 2})
    state = {"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 1k | R2 OUT 0 1k",
             "task": "Add one element between VCC and 0 to represent a microcontroller that draws about 50 mA."}
    crit = [("resistor_100_ohm", "A 100 Ω resistor from VCC to 0"),
            ("voltage_source_5v", "A 5 V DC voltage source from VCC to 0"),
            ("current_source_50ma", "A 50 mA DC current source from VCC to 0"), (NMI, NMI_TEXT)]
    add("C4-C08", "c_qualitative", "spice_mna_rules", "choice", state,
        choice("Which of these elements, added as described, would create a loop made only of voltage sources?", crit),
        "voltage_source_5v", twin={**state, **spice_rule}, twin_form="rule_in_state", base_form="recall",
        deriv={"source": src_sp}, meta={"steps": 1, "k": 4})
    state = {"netlist (DC operating point)": "V1 VCC 0 DC 5 | R1 VCC OUT 10k | C1 OUT NODE_X 100n"}
    crit = [("VCC", "VCC has no DC path to ground"), ("OUT", "OUT has no DC path to ground"),
            ("NODE_X", "NODE_X has no DC path to ground"), (NMI, NMI_TEXT)]
    add("C4-C09", "c_qualitative", "spice_mna_rules", "choice", state,
        choice("Which node in this netlist has no DC path to ground?", crit), "NODE_X",
        twin={**state, **spice_rule}, twin_form="rule_in_state", base_form="recall",
        deriv={"source": src_sp}, meta={"steps": 2, "k": 4})

    # C5 — I2C pull-ups (component_constraints.py:124,194-195; simulation.md:109)
    i2c_rule = {"I2C facts": "SDA and SCL are open-drain: devices only pull the lines low. Each of SDA and SCL needs its "
                             "own pull-up resistor to VCC (4.7 kΩ is typical); a line with no pull-up cannot return high."}
    src_i2c = "p2/backend/data/component_constraints.py:124,194-195; .claude/rules/simulation.md:109"
    c5 = [
        ({"design": "An SHT31-D connects to an Arduino Uno's A4 (SDA) and A5 (SCL). No resistor is connected to SDA or "
                    "SCL, the breakout has none, and the firmware disables the MCU's internal pull-ups."},
         "Will SDA and SCL return to a logic-high level when the bus is idle in this design?",
         "Will SDA and SCL stay unable to return to a logic-high level when the bus is idle in this design?", False),
        ({"design": "An I2C bus with a 4.7 kΩ resistor from SDA to 3.3 V and a 4.7 kΩ resistor from SCL to 3.3 V."},
         "Does each I2C line in this design have the pull-up an open-drain bus needs?",
         "Is either I2C line in this design missing the pull-up an open-drain bus needs?", True),
        ({"design": "An I2C bus with a 4.7 kΩ resistor from SDA to 3.3 V. SCL has no resistor, and the firmware "
                    "disables the MCU's internal pull-ups."},
         "Does this design give both I2C lines the pull-ups they need?",
         "Does this design leave at least one I2C line without the pull-up it needs?", False),
        ({"design": "An SHT31-D temperature sensor on an I2C bus with an ESP32."},
         "Are the SDA and SCL outputs of I2C devices open-drain (they can pull a line low but not drive it high)?",
         "Do I2C devices drive SDA and SCL actively high as well as low (push-pull outputs)?", True),
    ]
    for i, (state, qp, qn, truth) in enumerate(c5, 1):
        add_noul(f"C5-N{i:02d}", "c_qualitative", "i2c_pullups", state, noul(qp, "Yes.", "No."), noul(qn, "Yes.", "No."),
                 truth, twin={**state, **i2c_rule}, twin_form="rule_in_state", base_form="recall",
                 deriv={"source": src_i2c}, meta={"steps": 1})

    # C6 — RS-485 termination and bias (component_constraints.py:56-61,74-75)
    rs_rule = {"RS-485 facts": "A 120 Ω terminator goes between A and B at each of the two physical ends of the bus, and "
                               "nowhere else. Fail-safe bias pulls A toward V_CC and B toward ground, so an idle bus reads "
                               "V_A − V_B ≥ +200 mV, which receivers report as logic 1 (the idle state)."}
    src_rs = "p2/backend/data/component_constraints.py:56-61,74-75"
    bus = {"bus": "Five nodes on one 300 m RS-485 cable: N1 at one end, then N2, N3, N4, and N5 at the other end."}
    add("C6-C01", "c_qualitative", "rs485_termination_bias", "choice", bus,
        choice("Where should the 120 Ω terminators go on this bus?",
               [("ends_only", "At N1 and N5 only (the two ends of the cable)"), ("every_node", "At every node"),
                ("n1_only", "At N1 only"), ("middle_only", "At N3 only (the middle)"), (NMI, NMI_TEXT)]),
        "ends_only", twin={**bus, **rs_rule}, twin_form="rule_in_state", base_form="recall",
        deriv={"source": src_rs}, meta={"steps": 1, "k": 5})
    add_noul("C6-N02", "c_qualitative", "rs485_termination_bias", bus,
             noul("Should node N3 carry a 120 Ω terminator between A and B?", "Yes.", "No."),
             noul("Should node N3 be left without a 120 Ω terminator between A and B?", "Yes.", "No."), False,
             twin={**bus, **rs_rule}, twin_form="rule_in_state", base_form="recall", deriv={"source": src_rs},
             meta={"steps": 1})
    xcvr = "MAX485: A is the non-inverting line and B the inverting line; RO is high when V_A − V_B ≥ +200 mV."
    st = {"transceiver": xcvr, "bias network": "560 Ω from A to V_CC and 560 Ω from B to ground; every driver is off."}
    add_noul("C6-N03", "c_qualitative", "rs485_termination_bias", st,
             noul("With the bus idle, does this bias hold line A above line B?", "Yes.", "No."),
             noul("With the bus idle, does this bias hold line A at or below line B?", "Yes.", "No."), True,
             twin={**st, **rs_rule}, twin_form="rule_in_state", base_form="recall", deriv={"source": src_rs},
             meta={"steps": 1})
    st = {"transceiver": xcvr, "bias network": "560 Ω from A to ground and 560 Ω from B to V_CC; every driver is off."}
    add_noul("C6-N04", "c_qualitative", "rs485_termination_bias", st,
             noul("With the bus idle, does this bias make the receivers report logic 1 (the idle state)?", "Yes.", "No."),
             noul("With the bus idle, does this bias make the receivers report logic 0 instead of the idle state?", "Yes.", "No."),
             False, twin={**st, **rs_rule}, twin_form="rule_in_state", base_form="recall", deriv={"source": src_rs},
             meta={"steps": 2})


# ── d: project-rule facts, stated truly and falsely (rule in state) ──────────

H = "scratchpad/HANDOFF_2026-09-25.md"
RULES = {
    "llm_boundary": ("Rule (Circuit OS handoff §2): LLM never writes SPICE, KiCad, firmware, or CircuitIR. Since Stage 1 "
                     "the LLM writes only IntentIR (the requirement). Deterministic generator writes CircuitIR. "
                     "tests/test_llm_cannot_write_circuit_ir.py enforces via transitive AST scan.",
                     f"{H}:11", "which part of the system may write the CircuitIR"),
    "ai_calls": ("Rule (Circuit OS handoff §2): AI calls: tool_use forced tool_choice only; model from AI_MODEL env. "
                 "Explainer free-text must find first text block.", f"{H}:12",
                 "how AI calls pick the tool_choice and the model name"),
    "x5_retries": ("Rule X5 (Circuit OS handoff §2): Retries: API error → no retry (503). Schema failure → no retry, 422 "
                   "with raw tool input. Semantic refusal → retry once, may add values but never change/drop what the "
                   "user asked. Out-of-catalogue refused.", f"{H}:13",
                   "what happens after API errors, schema failures and semantic refusals"),
    "patches": ("Rule X2/X4 (Circuit OS handoff §2): Patches edit the requirement, never the circuit: RFC 6902 ops over "
                "IntentIR.requirements, re-derived through same gate. No retries; every LLM op must cite command words; "
                "no-op is not a version; 409 version_conflict.", f"{H}:14", "how design patches work"),
    "celery": ("Rule (Circuit OS handoff §2): ngspice via Celery only; predict() closed form synchronous.", f"{H}:15",
               "where ngspice and predict() run"),
    "mcu_models": ("Rule (Circuit OS handoff §2): MCU in SPICE = resistor (100Ω Uno, 41Ω ESP32-WROOM-32E, 132Ω STM32F411).",
                   f"{H}:16", "how each microcontroller is modelled in SPICE"),
    "persistence": ("Rule (Circuit OS handoff §2): Postgres persistence, CORS, JWT, slowapi limits. Static pricing; live "
                    "pricing (X7) needs user approval. IR field names locked. Only generators/realize.py stamps "
                    "circuit_id (uuid5(intent_id)), version, generator. Firmware shown only after PlatformIO compile.",
                    f"{H}:17", "pricing, circuit_id stamping and when firmware is shown"),
    "columnar": ("Rule (Circuit OS .claude/rules/simulation.md): ngspice batch mode (-b) produces columnar output, not "
                 "v(x) = y format. Example: 'v(vcc_5v)               5.00000e+00'. The regex v\\(x\\)\\s*=\\s*(\\d+) "
                 "does NOT match this. The parser uses a columnar DC pattern.",
                 ".claude/rules/simulation.md:37-50", "the format of ngspice batch output"),
    "tolerance": ("Rule (Circuit OS .claude/rules/simulation.md): _TOLERANCE = 0.15. Pass condition: "
                  "abs(actual - expected) / abs(expected) <= 0.15.", ".claude/rules/simulation.md:118-124",
                  "the simulation grader's pass condition"),
    "tiedown": ("Rule (Circuit OS .claude/rules/simulation.md): the SPICE generator adds a 1 GΩ resistor from a node to "
                "ground for any node appearing fewer than 2 times in element lines.",
                ".claude/rules/simulation.md:90-97", "which nodes get tie-down resistors"),
    "field_names": ("Rule (Circuit OS .claude/rules/code-style.md): connection.component_id ← correct; "
                    "connection.node_id ← correct; connection.component ← WRONG; connection.node ← WRONG. "
                    "Do not rename fields.", ".claude/rules/code-style.md:6-14", "the IR connection field names"),
    "jev_protocol": ("Protocol (Circuit OS handoff §3): >0.9 act, 0.5–0.9 act with care, <0.5 a person decides or take "
                     "the most reversible option and say so. TypeSafe never overrides tool_use/IR rules.", f"{H}:21",
                     "the probability bands for acting on a Jev answer"),
    "defeaters": ("Defeater register (Circuit OS handoff §5): D1 validated vs maths/ngspice not hardware (open). "
                  "D8 π bracketed (eliminated). D9 generator bug makes predict() confidently wrong (open per generator "
                  "until under M1 matrix).", f"{H}:32", "the status of defeaters D1, D8 and D9"),
    "grade_floor": ("Rule (Circuit OS handoff §5): grade_floor = worst critical claim. Grades run from best to worst: "
                    "G0, G1, G2, G3, G4, G5, G6, G7.", f"{H}:31", "how a design's grade floor is computed"),
    "generators": ("Catalogue (Circuit OS handoff §5): Five generators (entire catalogue; free-form out of scope): "
                   "rc_lowpass 0.2.3 (TPL_004), voltage_divider 0.1.0 (TPL_005), led_indicator 0.2.0 (TPL_003), "
                   "dht22_node 0.2.0 (TPL_001), rs485_node 0.2.0 (TPL_002). Boards: arduino_uno | esp32_devkitc | "
                   "blackpill_f411ce.", f"{H}:29-30", "the generator catalogue, its versions and boards"),
}


def rule_state(name):
    text, src, topic = RULES[name]
    return {"project rule": text}


def project_rules():
    U = "Under the rule in the state, "

    def rn(i, rule, qp, qn, truth, flip=False):
        text, src, topic = RULES[rule]
        if flip:  # canonical polarity chosen to balance true/false q1 labels
            qp, qn, truth = qn, qp, (not truth)
        add_noul(f"D-N{i:02d}", "d_project_rules", rule, rule_state(rule),
                 noul(U + qp, "Yes, the rule says so.", "No, the rule says otherwise."),
                 noul(U + qn, "Yes, the rule says so.", "No, the rule says otherwise."), truth,
                 base_form="given", suff=f"Does the state state the project's rule on {topic}?",
                 deriv={"source": src}, meta={"steps": 1})

    def rc_(i, rule, q, opts, truth, qtype="choice"):
        text, src, topic = RULES[rule]
        if qtype == "choice":
            add(f"D-C{i:02d}", "d_project_rules", rule, "choice", rule_state(rule),
                choice(U + q, list(opts) + [(NMI, NMI_TEXT)]), truth, base_form="given",
                suff=f"Does the state state the project's rule on {topic}?", deriv={"source": src},
                meta={"steps": 1, "k": len(opts) + 1})
        else:
            add(f"D-S{i:02d}", "d_project_rules", rule, "score", rule_state(rule), score(U + q, opts), truth,
                base_form="given", suff=f"Does the state state the project's rule on {topic}?", deriv={"source": src},
                meta={"steps": 1, "k": len(opts)})

    rn(1, "llm_boundary", "may the LLM produce the IntentIR (the requirement)?",
       "is the LLM barred from producing the IntentIR (the requirement)?", True)
    rn(2, "llm_boundary", "may the LLM write a CircuitIR directly if the CircuitIR passes schema validation?",
       "is the LLM barred from writing a CircuitIR directly even when the CircuitIR passes schema validation?", False)
    rc_(3, "llm_boundary", "what writes the CircuitIR?",
        [("the_llm", "The LLM writes it"), ("deterministic_generator", "A deterministic generator writes it"),
         ("the_user", "The user writes it by hand")], "deterministic_generator")
    rn(4, "ai_calls", "may a module hardcode the model name instead of reading AI_MODEL?",
       "must a module read the model name from AI_MODEL rather than hardcode it?", False, flip=True)
    rc_(5, "ai_calls", "where must the model name for AI calls come from?",
        [("ai_model_env", "The AI_MODEL environment variable"), ("hardcoded", "A name hardcoded in each module"),
         ("request_body", "The user's request")], "ai_model_env")
    rc_(6, "x5_retries", "what happens when the model API returns an error?",
        [("retry_once", "The call is retried once"), ("no_retry_503", "No retry; the request fails with HTTP 503"),
         ("no_retry_422", "No retry; the request fails with HTTP 422"), ("retry_up_to_3", "The call is retried up to 3 times")],
        "no_retry_503")
    rc_(7, "x5_retries", "what happens when the model's tool input fails the schema?",
        [("retry_once", "The call is retried once"), ("no_retry_503", "No retry; the request fails with HTTP 503"),
         ("no_retry_422_raw_input", "No retry; HTTP 422 carrying the raw tool input"),
         ("retry_up_to_3", "The call is retried up to 3 times")], "no_retry_422_raw_input")
    rn(8, "x5_retries", "may the retry after a semantic refusal change a value the user asked for?",
       "must the retry after a semantic refusal keep every value the user asked for unchanged?", False)
    rn(9, "x5_retries", "may the retry after a semantic refusal add values the user did not state?",
       "is the retry after a semantic refusal barred from adding values the user did not state?", True)
    rc_(10, "x5_retries", "how many retries follow a semantic refusal?",
        ["No retry.", "One retry.", "Two retries.", "Three or more retries."], 1, qtype="score")
    rn(11, "patches", "may a patch operation set a CircuitIR component's value directly?",
       "is a patch operation barred from setting a CircuitIR component's value directly?", False, flip=True)
    rn(12, "patches", "does a patch that changes nothing create a new version?",
       "does a patch that changes nothing leave the version count unchanged?", False)
    rn(13, "patches", "must every patch operation proposed by the LLM cite words from the user's command?",
       "may a patch operation proposed by the LLM omit any citation of the user's command?", True)
    rc_(14, "patches", "which HTTP status reports a version conflict?",
        [("http_409", "HTTP 409"), ("http_422", "HTTP 422"), ("http_503", "HTTP 503"), ("http_500", "HTTP 500")], "http_409")
    rn(15, "patches", "is a failed LLM patch retried?", "does a failed LLM patch go without a retry?", False)
    rn(16, "celery", "may an HTTP handler run ngspice inline and wait for its result?",
       "must ngspice runs go through Celery rather than run inline in an HTTP handler?", False, flip=True)
    rn(17, "celery", "may predict() run synchronously?", "must predict() run asynchronously?", True)
    rc_(18, "mcu_models", "how is the ESP32-WROOM-32E modelled in SPICE?",
        [("resistor_100_ohm", "As a 100 Ω resistor"), ("resistor_41_ohm", "As a 41 Ω resistor"),
         ("resistor_132_ohm", "As a 132 Ω resistor"), ("voltage_source_3v3", "As a 3.3 V voltage source")], "resistor_41_ohm")
    rn(19, "mcu_models", "is the STM32F411 modelled in SPICE as a 100 Ω resistor?",
       "is the STM32F411 modelled in SPICE as something other than a 100 Ω resistor?", False)
    rn(20, "mcu_models", "may the Arduino Uno be modelled in SPICE as a 5 V voltage source?",
       "must the Arduino Uno be modelled in SPICE as a resistor rather than a voltage source?", False)
    rn(21, "persistence", "may live Digikey pricing be switched on without the user's approval?",
       "does live pricing need the user's approval before it is switched on?", False, flip=True)
    rc_(22, "persistence", "which module stamps circuit_id?",
        [("generators_realize", "generators/realize.py"), ("ai_intent_producer", "ai/intent_producer.py"),
         ("api_routes_design", "api/routes/design.py"), ("db_crud", "db/crud.py")], "generators_realize")
    rn(23, "persistence", "is circuit_id a random UUID (uuid4)?", "is circuit_id derived deterministically from intent_id?", False)
    rn(24, "persistence", "may the UI show firmware that has not yet compiled under PlatformIO?",
       "must firmware compile under PlatformIO before the UI shows it?", False)
    rn(25, "persistence", "is BOM pricing static by default?", "is BOM pricing live by default?", True)
    rn(26, "columnar", "will the regex v\\(x\\)\\s*=\\s*(\\d+) extract DC voltages from ngspice batch output?",
       "will the regex v\\(x\\)\\s*=\\s*(\\d+) fail to extract DC voltages from ngspice batch output?", False)
    rn(27, "columnar", "is ngspice's batch DC output laid out in columns (node name, then value)?",
       "is ngspice's batch DC output written as v(x) = y lines?", True)
    rn(28, "tolerance", "does a simulated cutoff of 1120 Hz pass against an expected 1000 Hz?",
       "does a simulated cutoff of 1120 Hz fail against an expected 1000 Hz?", True)
    rn(29, "tolerance", "does a simulated cutoff of 820 Hz pass against an expected 1000 Hz?",
       "does a simulated cutoff of 820 Hz fail against an expected 1000 Hz?", False)
    rc_(30, "tolerance", "how does a simulated 1140 Hz grade against an expected 1000 Hz?",
        ["Fails: error above 15 %.", "Passes with an error from 10 % to 15 %.", "Passes with an error under 10 %."], 1,
        qtype="score")
    rn(31, "tiedown", "does a node that appears in only one element line get a 1 GΩ tie-down resistor?",
       "is a node that appears in only one element line left without a tie-down resistor?", True)
    rn(32, "tiedown", "does a node that appears in exactly two element lines get a tie-down resistor?",
       "is a node that appears in exactly two element lines left without a tie-down resistor?", False)
    rn(33, "field_names", "is connection.component an acceptable field name?",
       "is connection.component a wrong field name?", False)
    rn(34, "field_names", "is connection.node_id the correct field name?", "is connection.node_id a wrong field name?", True)
    rc_(35, "jev_protocol", "which band does a Jev probability of 0.72 fall in?",
        [("act", "Act"), ("act_with_care", "Act with care"), ("person_decides", "A person decides")], "act_with_care")
    rn(36, "jev_protocol", "may a Jev answer of 0.95 override the IR rules?",
       "is a Jev answer of 0.95 still barred from overriding the IR rules?", False)
    rn(37, "jev_protocol", "does a Jev probability of 0.95 fall in the act band?",
       "does a Jev probability of 0.95 fall outside the act band?", True)
    rn(38, "defeaters", "is defeater D8 eliminated?", "is defeater D8 still open?", True)
    rn(39, "defeaters", "is defeater D1 closed?", "is defeater D1 open?", False)
    rc_(40, "grade_floor", "what is the grade floor of a design whose critical claims are graded G1, G1 and G5?",
        [("G1", "G1"), ("G3", "G3"), ("G5", "G5")], "G5")
    rc_(41, "generators", "what is the rc_lowpass generator's version?",
        [("v0_1_0", "0.1.0"), ("v0_2_0", "0.2.0"), ("v0_2_3", "0.2.3"), ("v1_0_0", "1.0.0")], "v0_2_3")
    rn(42, "generators", "is free-form circuit generation in scope?", "is free-form circuit generation out of scope?", False)


# ── e: unanswerable (the deciding fact is absent) ────────────────────────────

def unanswerable():
    X = "unanswerable"
    E = "e_unanswerable"

    def en(i, sub, state, qp, qn, suff, **kw):
        add_noul(f"E-N{i:02d}", E, sub, state, qp, qn, X, base_form="missing", suff=suff, suff_truth=False,
                 deriv={"construction": kw.get("why", "the deciding fact is absent from the state")},
                 meta={"steps": 1, "subtype": sub})

    def ec(i, sub, state, q, suff, **kw):
        add(f"E-C{i:02d}", E, sub, "choice", state, q, NMI, base_form="missing", suff=suff, suff_truth=False,
            deriv={"construction": kw.get("why", "the deciding fact is absent from the state")},
            meta={"steps": 1, "subtype": sub, "k": len(q["criteria"])})

    # E1 — numeric input missing
    s = {"circuit": "RC low-pass filter", "R1": "1.58 kΩ", "model": "f_c = 1 / (2 × π × R1 × C1)"}
    hi, lo = compare_pair("the cutoff frequency f_c", "1 kHz", "gt")
    en(1, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the cutoff frequency f_c?", why="C1 absent")
    keys, descs = band_texts("the cutoff frequency f_c", [500.0, 2000.0], "Hz", ["", "k"])
    ec(2, "missing_numeric", s, choice(f"{LEAD}which range contains the cutoff frequency f_c?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the cutoff frequency f_c?", why="C1 absent")
    s = {"circuit": "Resistive voltage divider, nothing connected to the output", "V_in": "12 V",
         "R1 (from V_in to V_out)": "10 kΩ", "model": "V_out = V_in × R2 / (R1 + R2)"}
    hi, lo = compare_pair("the output voltage V_out", "3.3 V", "gt")
    en(3, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the output voltage V_out?", why="R2 absent")
    keys, descs = band_texts("the output voltage V_out", [1.1, 3.3], "V", None)
    ec(4, "missing_numeric", s, choice(f"{LEAD}which range contains the output voltage V_out?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the output voltage V_out?", why="R2 absent")
    s = {"circuit": "LED indicator: GPIO pin driven high → R1 → LED → ground", "board": "Arduino Uno (ATmega328P)",
         "V_pin (pin voltage with no load)": "5 V", "R_out (pin output resistance)": "25 Ω",
         "V_f (LED forward voltage, treat as constant)": "2 V", "model": "I = (V_pin − V_f) / (R1 + R_out)"}
    hi, lo = compare_pair("the LED current I", "20 mA", "gt")
    en(5, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the LED current I?", why="R1 absent")
    keys, descs = band_texts("the LED current I", [0.01, 0.02], "A", None)
    ec(6, "missing_numeric", s, choice(f"{LEAD}which range contains the LED current I?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the LED current I?", why="R1 absent")
    s = {"component": "R1, a thick-film chip resistor", "R1": "330 Ω", "model": "P = V² / R1"}
    hi, lo = compare_pair("the power P dissipated in R1", "62.5 mW", "gt")
    en(7, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the power dissipated in R1?", why="voltage absent")
    keys, descs = band_texts("the power P dissipated in R1", [0.0625, 0.25], "W", ["m", "m"])
    ec(8, "missing_numeric", s, choice(f"{LEAD}which range contains the power P dissipated in R1?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the power dissipated in R1?", why="voltage absent")
    s = {"circuit": "DHT22 DATA line: open-drain output with a pull-up resistor to VCC", "R_pullup": "4.7 kΩ",
         "model": "t_r (10 % to 90 %) = 2.197 × R_pullup × C_bus"}
    hi, lo = compare_pair("the rise time t_r", "5 µs", "gt")
    en(9, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the rise time t_r?", why="C_bus absent")
    keys, descs = band_texts("the rise time t_r", [1e-6, 5e-6], "s", ["µ", "µ"])
    ec(10, "missing_numeric", s, choice(f"{LEAD}which range contains the rise time t_r?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the rise time t_r?", why="C_bus absent")
    s = {"bus": "RS-485 pair A/B, idle: every driver is off", "V_CC": "5 V",
         "R_eq (termination between A and B)": "60 Ω (a 120 Ω terminator at each end, in parallel)",
         "model": "V_AB = V_CC × R_eq / (R_up + R_eq + R_down)"}
    hi, lo = compare_pair("the idle differential voltage V_AB", "200 mV", "ge")
    en(11, "missing_numeric", s, hi, lo, "Does the state give a value for every quantity needed to compute the idle differential voltage V_AB?", why="bias resistors absent")
    keys, descs = band_texts("the idle differential voltage V_AB", [0.2, 0.25], "V", ["m", "m"])
    ec(12, "missing_numeric", s, choice(f"{LEAD}which range contains the idle differential voltage V_AB?", list(zip(keys, descs)) + [(NMI, NMI_TEXT)]),
       "Does the state give a value for every quantity needed to compute the idle differential voltage V_AB?", why="bias resistors absent")

    # E2 — project fact absent: a (d) question asked over a state holding a different rule
    U = "Under the rule in the state, "

    def e_rule(i, other_rule, topic_rule, qp, qn):
        topic = RULES[topic_rule][2]
        en(i, "missing_project_fact", rule_state(other_rule),
           noul(U + qp, "Yes, the rule says so.", "No, the rule says otherwise."),
           noul(U + qn, "Yes, the rule says so.", "No, the rule says otherwise."),
           f"Does the state state the project's rule on {topic}?",
           why=f"state holds '{other_rule}', the question needs '{topic_rule}'")

    def e_rule_c(i, other_rule, topic_rule, q, opts):
        topic = RULES[topic_rule][2]
        ec(i, "missing_project_fact", rule_state(other_rule), choice(U + q, list(opts) + [(NMI, NMI_TEXT)]),
           f"Does the state state the project's rule on {topic}?",
           why=f"state holds '{other_rule}', the question needs '{topic_rule}'")

    e_rule(13, "persistence", "mcu_models", "is the ESP32-WROOM-32E modelled in SPICE as a 41 Ω resistor?",
           "is the ESP32-WROOM-32E modelled in SPICE as something other than a 41 Ω resistor?")
    e_rule_c(14, "celery", "mcu_models", "how is the ESP32-WROOM-32E modelled in SPICE?",
             [("resistor_100_ohm", "As a 100 Ω resistor"), ("resistor_41_ohm", "As a 41 Ω resistor"),
              ("resistor_132_ohm", "As a 132 Ω resistor"), ("voltage_source_3v3", "As a 3.3 V voltage source")])
    e_rule(15, "x5_retries", "patches", "is a failed LLM patch retried?", "does a failed LLM patch go without a retry?")
    e_rule_c(16, "x5_retries", "patches", "which HTTP status reports a version conflict?",
             [("http_409", "HTTP 409"), ("http_422", "HTTP 422"), ("http_503", "HTTP 503"), ("http_500", "HTTP 500")])
    e_rule(17, "columnar", "tolerance", "does a simulated cutoff of 1120 Hz pass against an expected 1000 Hz?",
           "does a simulated cutoff of 1120 Hz fail against an expected 1000 Hz?")
    e_rule_c(18, "tiedown", "tolerance", "what relative error does the simulation grader allow?",
             [("pct_5", "5 %"), ("pct_10", "10 %"), ("pct_15", "15 %"), ("pct_20", "20 %")])
    e_rule(19, "llm_boundary", "defeaters", "is defeater D8 eliminated?", "is defeater D8 still open?")
    e_rule_c(20, "celery", "persistence", "which module stamps circuit_id?",
             [("generators_realize", "generators/realize.py"), ("ai_intent_producer", "ai/intent_producer.py"),
              ("api_routes_design", "api/routes/design.py"), ("db_crud", "db/crud.py")])
    e_rule(21, "field_names", "persistence", "may the UI show firmware that has not yet compiled under PlatformIO?",
           "must firmware compile under PlatformIO before the UI shows it?")
    s = {"project rule": "Catalogue (Circuit OS handoff §5): Five generators (entire catalogue; free-form out of scope): "
                         "rc_lowpass, voltage_divider, led_indicator, dht22_node, rs485_node."}
    ec(22, "missing_project_fact", s, choice(U + "what is the rc_lowpass generator's version?",
                                             [("v0_1_0", "0.1.0"), ("v0_2_0", "0.2.0"), ("v0_2_3", "0.2.3"),
                                              ("v1_0_0", "1.0.0"), (NMI, NMI_TEXT)]),
       "Does the state state the rc_lowpass generator's version?", why="versions removed from the catalogue text")
    e_rule(23, "ai_calls", "jev_protocol", "does a Jev probability of 0.72 fall in the act-with-care band?",
           "does a Jev probability of 0.72 fall outside the act-with-care band?")
    e_rule_c(24, "grade_floor", "generators", "which boards can the rs485_node generator target?",
             [("uno_only", "arduino_uno only"), ("three_boards", "arduino_uno, esp32_devkitc and blackpill_f411ce"),
              ("esp32_only", "esp32_devkitc only")])

    # E3 — board or context unspecified
    s = {"design": "The firmware calls analogWrite() on pin 4 to dim an LED.",
         "boards Circuit OS supports": "Arduino Uno, ESP32-DevKitC, WeAct Black Pill (STM32F411)"}
    en(25, "context_unspecified", s, noul("Does pin 4 on this design's board support hardware PWM output?", "Yes.", "No."),
       noul("Does pin 4 on this design's board lack hardware PWM output?", "Yes.", "No."),
       "Does the state say which board the design uses?", why="board absent; pin 4 is PWM on the ESP32, not on the Uno")
    ec(26, "context_unspecified", s, choice("Which statement about pin 4 holds on this design's board?",
                                            [("hardware_pwm", "Pin 4 has hardware PWM on this board"),
                                             ("no_hardware_pwm", "Pin 4 has no hardware PWM on this board"), (NMI, NMI_TEXT)]),
       "Does the state say which board the design uses?", why="board absent")
    s = {"design": "An external 10 kΩ resistor holds pin 12 high while the board comes out of reset.",
         "boards Circuit OS supports": "Arduino Uno, ESP32-DevKitC, WeAct Black Pill (STM32F411)"}
    en(27, "context_unspecified", s, noul("Will this pull-up stop the board from booting normally?", "Yes.", "No."),
       noul("Will the board boot normally despite this pull-up?", "Yes.", "No."),
       "Does the state say which board the design uses?", why="board absent; GPIO12 high breaks an ESP32 boot, D12 on an Uno is harmless")
    ec(28, "context_unspecified", s, choice("What does this pull-up do at reset?",
                                            [("no_effect", "No effect on booting"),
                                             ("boot_fails", "The board does not boot normally"), (NMI, NMI_TEXT)]),
       "Does the state say which board the design uses?", why="board absent")
    s = {"design": "The microcontroller is modelled in SPICE as a resistor from its supply rail to ground, sized from "
                   "the part's own run current."}
    en(29, "context_unspecified", s, noul("Is that resistor 100 Ω?", "Yes.", "No."),
       noul("Is that resistor something other than 100 Ω?", "Yes.", "No."),
       "Does the state say which microcontroller the design uses?", why="MCU absent (100 / 41 / 132 Ω by board)")
    ec(30, "context_unspecified", s, choice("What is that resistor's value?",
                                            [("ohm_41", "41 Ω"), ("ohm_100", "100 Ω"), ("ohm_132", "132 Ω"), (NMI, NMI_TEXT)]),
       "Does the state say which microcontroller the design uses?", why="MCU absent")

    # E4 — result absent
    s = {"design": "RC low-pass filter, expected cutoff 1 kHz; the grader passes a result within 15 % of expected.",
         "simulation": "Submitted to ngspice through Celery. The simulated cutoff is not included in this state."}
    en(31, "result_absent", s, noul("Did the simulation pass the grader?", "Yes.", "No."),
       noul("Did the simulation fail the grader?", "Yes.", "No."), "Does the state include the simulated cutoff?")
    ec(32, "result_absent", s, choice("What was the grader's verdict?",
                                      [("passed", "The simulation passed"), ("failed", "The simulation failed"), (NMI, NMI_TEXT)]),
       "Does the state include the simulated cutoff?")
    s = {"firmware": "dht22_node sketch generated for arduino_uno",
         "compile gate": "PlatformIO 6.2.0 compile gate; its result is not recorded in this state."}
    en(33, "result_absent", s, noul("Did the sketch compile without errors?", "Yes.", "No."),
       noul("Did the sketch fail to compile?", "Yes.", "No."), "Does the state include the compile result?")
    ec(34, "result_absent", s, choice("What was the compile gate's result?",
                                      [("compiled", "The sketch compiled"), ("failed", "The sketch failed to compile"), (NMI, NMI_TEXT)]),
       "Does the state include the compile result?")
    s = {"design": "rs485_node on esp32_devkitc",
         "claims": "rs485.failsafe_bias is listed as a critical claim; its verdict is not included in this state."}
    en(35, "result_absent", s, noul("Does the rs485.failsafe_bias claim hold for this design?", "Yes.", "No."),
       noul("Does the rs485.failsafe_bias claim fail for this design?", "Yes.", "No."),
       "Does the state include the claim's verdict?")
    ec(36, "result_absent", s, choice("What is the claim's verdict?",
                                      [("holds", "The claim holds"), ("fails", "The claim fails"), (NMI, NMI_TEXT)]),
       "Does the state include the claim's verdict?")


# ── g: comparisons / ordering ────────────────────────────────────────────────

def comparisons(P):
    e96 = P.common.e96_values
    caps = [row[0] for row in P.rc._CAPACITORS]
    G = "g_comparison"
    names = ["A", "B", "C"]

    def pick_three(sampler, value, near, want="max", tries=20000):
        for _ in range(tries):
            ds = [sampler() for _ in range(3)]
            vs = [value(d) for d in ds]
            if any(v is None or v <= 0 for v in vs):
                continue
            order = sorted(range(3), key=lambda k: vs[k], reverse=(want == "max"))
            top, second = vs[order[0]], vs[order[1]]
            r = max(top / second, second / top)
            if len({round(v, 12) for v in vs}) < 3:
                continue
            if (near and NEAR[0] <= r <= NEAR[1]) or (not near and 1.3 <= r <= 4.0):
                return ds, vs, order[0], r
        raise AssertionError("pick_three failed")

    def comp_item(i, fam, sampler, value, render, qty, want, near, pre_label, unit, src, suff, pre_prefix=None):
        ds, vs, win, r = pick_three(sampler, value, near, want)
        state = {f"design {n}": render(d) for n, d in zip(names, ds)}
        state["model"] = {"power_max": "P = V² / R", "cutoff_min": "f_c = 1 / (2 × π × R × C)",
                          "led_max": "I = (V_pin − V_f) / (R1 + R_out)",
                          "vab_max": "V_AB = V_CC × R_eq / (R_up + R_eq + R_down)"}[fam]
        twin = {**state, **{f"{pre_label} for design {n} (computed in code)": si(v, unit, 4, pre_prefix)
                            for n, v in zip(names, vs)}}
        word = "most" if want == "max" else "least"
        crit = [(f"design_{n}", f"Design {n} has the {'highest' if want == 'max' else 'lowest'} {qty}") for n in names] + [(NMI, NMI_TEXT)]
        add(f"G-C{i:02d}", G, fam, "choice", state,
            choice(f"{LEAD}which design has the {'highest' if want == 'max' else 'lowest'} {qty}?", crit),
            f"design_{names[win]}", twin=twin, twin_form="precomputed", base_form="compute",
            suff=f"Does the state give every value needed to compute {qty} for each design?",
            deriv={"values": dict(zip(names, vs)), "units": unit, "winner": names[win], "ratio_top_to_second": r,
                   "source": src}, meta={"near": near, "steps": 3, "k": 4})
        return ds, vs

    # G1 — highest dissipation
    samp_p = lambda: (rng.choice([3.3, 5.0, 12.0, 24.0]), rng.choice(e96(10.0, 100000.0)))
    val_p = lambda d: d[0] ** 2 / d[1]
    rend_p = lambda d: f"{V(d[0])} across {R(d[1], 3)}"
    i = 0
    for j in range(8):
        i += 1
        comp_item(i, "power_max", samp_p, val_p, rend_p, "power dissipated in its resistor", "max", j % 2 == 0,
                  "P", "W", "python P = V^2/R", "", pre_prefix="m")
    # G2 — lowest cutoff
    samp_c = lambda: (rng.choice(e96(1000.0, 100000.0)), rng.choice(caps))
    for j in range(6):
        i += 1
        comp_item(i, "cutoff_min", samp_c, lambda d: P.rc.cutoff_hz(*d), lambda d: f"R = {R(d[0], 3)}, C = {C(d[1])}",
                  "cutoff frequency", "min", j % 2 == 0, "f_c", "Hz", "p2/backend/generators/rc_lowpass.py:139-141", "")
    # G3 — highest LED current
    boards = [("Uno", 5.0, 25.0), ("ESP32", 3.3, 20.0), ("Black Pill", 3.3, 35.0)]
    samp_l = lambda: (rng.choice(boards), rng.choice([1.8, 2.0, 2.2]), rng.choice(e96(47.0, 2000.0)))
    val_l = lambda d: (d[0][1] - d[1]) / (d[2] + d[0][2])
    rend_l = lambda d: f"V_pin = {V(d[0][1])}, R_out = {R(d[0][2], 3)}, V_f = {V(d[1])}, R1 = {R(d[2], 3)}"
    for j in range(6):
        i += 1
        comp_item(i, "led_max", samp_l, val_l, rend_l, "LED current", "max", j % 2 == 0, "I", "A",
                  "python (stated model); R_out component_constraints.py:116,157,177", "", pre_prefix="m")
    # G4 — highest V_AB
    samp_v = lambda: (rng.choice([5.0, 3.3]), rng.choice([60.0, 120.0]), rng.choice(e96(200.0, 5000.0)))
    val_v = lambda d: d[0] * d[1] / (2 * d[2] + d[1])
    rend_v = lambda d: f"V_CC = {V(d[0])}, R_eq = {R(d[1], 3)}, R_up = R_down = {R(d[2], 3)}"
    for j in range(4):
        i += 1
        comp_item(i, "vab_max", samp_v, val_v, rend_v, "idle differential voltage V_AB", "max", j % 2 == 0, "V_AB", "V",
                  "p2/backend/generators/rs485_node.py:173-176", "", pre_prefix="m")
    # G5 — count how many of three exceed 62.5 mW (score 0..3)
    levels = ["None of the three exceeds 62.5 mW.", "Exactly one exceeds 62.5 mW.",
              "Exactly two exceed 62.5 mW.", "All three exceed 62.5 mW."]
    targets = [0, 1, 2, 3, 1, 2]
    for j, tgt in enumerate(targets):
        near = j % 2 == 0
        for _ in range(50000):
            ds = [samp_p() for _ in range(3)]
            vs = [val_p(d) for d in ds]
            cnt = sum(v > 0.0625 for v in vs)
            close = any(NEAR[0] <= ratio(v, 0.0625) <= NEAR[1] for v in vs)
            farok = all(ratio(v, 0.0625) >= 1.25 for v in vs)
            if cnt == tgt and ((near and close) or (not near and farok)):
                break
        else:
            raise AssertionError("G5")
        state = {f"design {n}": f"{rend_p(d)}, resistor rated 62.5 mW" for n, d in zip(names, ds)}
        state["model"] = "P = V² / R"
        twin = {**state, **{f"P for design {n} (computed in code)": si(v, "W", 4, "m") for n, v in zip(names, vs)}}
        add(f"G-S{j + 27:02d}", G, "count_over_rating", "score", state,
            score(f"{LEAD}how many of the three resistors dissipate more than their 62.5 mW rating?", levels), tgt,
            twin=twin, twin_form="precomputed", base_form="compute",
            suff="Does the state give every value needed to compute each resistor's dissipation?",
            deriv={"values": dict(zip(names, vs)), "count": tgt, "source": "python P = V^2/R; rating common.py:36"},
            meta={"near": near, "steps": 4, "k": 4})
    # G6 — pairwise nouls
    for j in range(6):
        near = j % 2 == 0
        truth_want = j % 3 != 0
        for _ in range(50000):
            a, b = samp_p(), samp_p()
            pa, pb = val_p(a), val_p(b)
            r = max(pa / pb, pb / pa)
            if ((pa > pb) == truth_want) and ((near and NEAR[0] <= r <= NEAR[1]) or (not near and 1.3 <= r <= 4.0)):
                break
        else:
            raise AssertionError("G6")
        state = {"design A": rend_p(a), "design B": rend_p(b), "model": "P = V² / R"}
        twin = {**state, "P for design A (computed in code)": si(pa, "W", 4, "m"),
                "P for design B (computed in code)": si(pb, "W", 4, "m")}
        add_noul(f"G-N{j + 33:02d}", G, "pairwise_power", state,
                 noul(f"{LEAD}does design A's resistor dissipate more power than design B's?",
                      "Design A's resistor dissipates more power.", "Design A's resistor dissipates the same or less power."),
                 noul(f"{LEAD}does design A's resistor dissipate at most as much power as design B's?",
                      "Design A's resistor dissipates the same or less power.", "Design A's resistor dissipates more power."),
                 pa > pb, twin=twin, twin_form="precomputed", base_form="compute",
                 suff="Does the state give every value needed to compute both resistors' dissipation?",
                 deriv={"P_A": pa, "P_B": pb, "ratio": r, "source": "python P = V^2/R"},
                 meta={"near": near, "steps": 3})


# ── project-native items taken from predict() itself ─────────────────────────

def project_native(P):
    I = lambda req: NS(requirements=req)
    # DHT22 at 5 m of cable: the generator's own worst-case rise time vs its own 5 µs limit.
    req = {"function": "temperature_humidity_sensor", "constraints": {"cable_length_m": 5}}
    g = P.dht.DHT22NodeGenerator()
    q = g.predict(I(req)).quantities
    r1 = P.dht.select_pullup(P.dht._read(I(req)))
    worst = q["rise_time_us"].hi
    state = {"circuit": "DHT22 DATA line: open-drain output with a pull-up resistor to VCC (dht22_node 0.2.0 choice)",
             "R_pullup": f"{R(r1, 3)} ±1 %", "cable length": "5 m", "cable capacitance": "at most 100 pF per metre",
             "input capacitance": "10 pF at the MCU pin and 10 pF at the sensor",
             "model": "step 1: worst-case R = R_pullup × 1.01; step 2: worst-case C_bus = 10 pF + 10 pF + 5 m × 100 pF/m; "
                      "step 3: t_r = 2.197 × R × C_bus"}
    twin = {**state, "worst-case t_r (computed in code by dht22_node.predict)": si(worst * 1e-6, "s", 4, "µ")}
    hi, lo = compare_pair("the worst-case rise time t_r", "5 µs", "gt")
    add_noul("F7-N01", "f_multistep", "project_native_dht22", state, lo, hi, worst <= 5.0, twin=twin,
             twin_form="precomputed", base_form="compute",
             suff="Does the state give a value for every quantity needed to compute the worst-case rise time t_r?",
             deriv={"fn": "generators.dht22_node.DHT22NodeGenerator.predict (rise_time_us.hi)",
                    "source": "p2/backend/generators/dht22_node.py:254-290", "value_us": worst, "limit_us": 5.0,
                    "margin_rel": worst / 5.0 - 1.0},
             meta={"near": True, "steps": 3})
    # RS-485 on the Uno with the far end terminated: the generator's bias choice vs the 1.25× margin.
    req = {"function": "modbus_rtu_master", "constraints": {"mcu": "arduino_uno", "far_end_terminated": True}}
    g = P.rs.RS485NodeGenerator()
    q = g.predict(I(req)).quantities
    r1, r2, r3 = P.rs.select(P.rs._read(I(req)))
    lo_mv = q["v_ab_idle_mv"].lo
    state = {"bus": "RS-485 pair A/B, idle (rs485_node 0.2.0 choice on arduino_uno)", "V_CC": "5 V",
             "R_term (this end)": "120 Ω ±1 %", "R_far (far-end terminator)": "120 Ω ±1 %",
             "R_up (A to V_CC)": f"{R(r2, 3)} ±1 %", "R_down (B to ground)": f"{R(r3, 3)} ±1 %",
             "model": "worst case: R_term and R_far at −1 %, R_up and R_down at +1 %; R_eq = R_term ∥ R_far; "
                      "V_AB = V_CC × R_eq / (R_up + R_eq + R_down)"}
    twin = {**state, "worst-case V_AB (computed in code by rs485_node.predict)": si(lo_mv / 1000, "V", 4, "m")}
    hi, lo = compare_pair("the worst-case idle differential voltage V_AB", "250 mV", "ge")
    add_noul("F7-N02", "f_multistep", "project_native_rs485", state, hi, lo, lo_mv >= 250.0, twin=twin,
             twin_form="precomputed", base_form="compute",
             suff="Does the state give a value for every quantity needed to compute the worst-case V_AB?",
             deriv={"fn": "generators.rs485_node.RS485NodeGenerator.predict (v_ab_idle_mv.lo)",
                    "source": "p2/backend/generators/rs485_node.py:292-315", "value_mV": lo_mv, "limit_mV": 250.0,
                    "margin_rel": lo_mv / 250.0 - 1.0},
             meta={"near": True, "steps": 3})
    # LED on the ESP32 at 15 mA: the envelope refuses because the worst case exceeds 20 mA.
    req = {"function": "led_indicator", "targets": {"led_current_ma": 15}, "constraints": {"mcu": "esp32_devkitc"}}
    decision = P.led.LedIndicatorGenerator().envelope(I(req))
    state = {"request": "LED indicator at 15 mA on esp32_devkitc (led_indicator 0.2.0)",
             "generator finding": decision.reason if not decision.accepted else "accepted",
             "limit": "20 mA recommended per pin"}
    add_noul("F7-N03", "f_multistep", "project_native_led", state,
             noul("Using only the state, can the pin source more than the recommended 20 mA at some corner of the part tolerances?",
                  "Yes, the worst case exceeds 20 mA.", "No, it stays at or under 20 mA."),
             noul("Using only the state, does the pin stay at or under the recommended 20 mA at every corner of the part tolerances?",
                  "Yes, it stays at or under 20 mA.", "No, the worst case exceeds 20 mA."),
             not decision.accepted, twin=None, base_form="given",
             suff="Does the state give the worst-case pin current or the generator's finding about it?",
             deriv={"fn": "generators.led_indicator.LedIndicatorGenerator.envelope", "reason": decision.reason,
                    "source": "p2/backend/generators/led_indicator.py:249-312"},
             meta={"near": True, "steps": 1})


# ── flags, manifest ──────────────────────────────────────────────────────────

ANSWERABLE = ("a_closed_form", "b_units", "c_qualitative", "d_project_rules", "f_multistep", "g_comparison")


def set_flags():
    by_cat = {}
    for it in ITEMS:
        by_cat.setdefault(it["category"], []).append(it)
    for cat, its in sorted(by_cat.items()):
        k = round(0.2 * len(its))
        for it in rng.sample(its, k):
            it["meta"]["repeat"] = True
        if cat in ANSWERABLE:
            cand = [it for it in its if it["qtype"] in ("noul", "choice")]
            for it in rng.sample(cand, 4):
                it["meta"]["solo"] = True
    for it in ITEMS:
        it["meta"].setdefault("repeat", False)
        it["meta"].setdefault("solo", False)


def request_plan(items):
    reqs = []
    for it in items:
        reqs.append((it["item_id"], "base", it["state"], it["questions"]))
        if it["twin_state"] is not None:
            reqs.append((it["item_id"], "twin", it["twin_state"], it["questions"]))
        if it["meta"].get("repeat"):
            reqs.append((it["item_id"], "repeat", it["state"], it["questions"]))
        if it["meta"].get("solo"):
            reqs.append((it["item_id"], "solo", it["state"], {"q1": it["questions"]["q1"]}))
    return reqs


ANALYSIS_PLAN = {
    "model": MODEL,
    "primary_pool": "answerable categories a,b,c,d,f,g; question q1 (canonical polarity / label order); base form; first run",
    "correctness": {"noul": "correct iff (p>0.5 and truth) or (p<0.5 and not truth); p==0.5 counts as wrong",
                    "choice": "correct iff the returned choice (argmax) equals the true label",
                    "score": "correct iff argmax level of probabilities equals the true level; also MAE of expected score"},
    "calibration": {"brier": "noul (p-y)^2; choice/score multi-class sum_k (p_k - y_k)^2",
                    "log_loss": "-ln p(true outcome), p clipped to [0.005, 0.995] because answers carry 2-decimal resolution",
                    "ece": "10 equal-width bins on top-label confidence (noul max(p,1-p), choice/score p_top); "
                           "also P(yes) reliability for nouls",
                    "p_top_bins": [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001]},
    "selective": "coverage and accuracy among answers with p_top >= t for t in {0.6,0.7,0.8,0.9,0.95,0.99}",
    "variants": {"polarity": "noul q2 is the negated complement; coherence s = p(q1)+p(q2); incoherent if |s-1|>0.15; "
                             "contradiction if both >0.5 or both <0.5",
                 "order": "choice/score q2 has reversed labels/levels; flip = argmax label differs from q1; also total "
                          "variation distance between label-aligned distributions",
                 "repeat": "identical request re-sent; max |delta p|",
                 "solo": "q1 sent alone; |delta p| vs batched q1",
                 "twin": "precomputed (numbers computed in code and written into the state) or rule_in_state; paired vs base"},
    "abstention": {"choice": "argmax == need_more_information",
                   "noul": "0.35 <= p <= 0.65 on unanswerable items (mid-band); also distribution of p",
                   "sufficiency_q3": "p(q3) < 0.5 means 'information missing'; truth true on answerable, false on unanswerable"},
    "ci": "percentile bootstrap, 2000 resamples, resampling items (clusters), seed 12345",
    "hypotheses": {
        "H1": "Accuracy on compute forms is lower than on the same items with numbers precomputed (paired).",
        "H2": "Near-threshold (1-5%) numeric items are less accurate than far (25-300%) items.",
        "H3": "Among answers with p_top >= 0.9, accuracy on compute items is below 0.9; on rule-in-state items it is at least 0.9.",
        "H4": "Nouls on unanswerable items do not sit in the 0.35-0.65 band (they lean to 'no').",
        "H5": "Choices with need_more_information abstain on at least 80 % of unanswerable items.",
        "H6": "Polarity sums deviate from 1 more on compute items than on rule items."},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=os.environ.get("CIRCUITOS_P2", DEFAULT_SNAPSHOT))
    a = ap.parse_args()
    P = load_project(a.snapshot)
    for spec in specs(P):
        numeric_family(P, spec)
    units_b1()
    units_b6()
    qualitative(P)
    project_rules()
    unanswerable()
    comparisons(P)
    project_native(P)
    set_flags()

    ids = [it["item_id"] for it in ITEMS]
    raise_if(len(ids) != len(set(ids)), "duplicate item ids")
    from typesafe_sdk._schemas.models import SystemOneRequest
    reqs = request_plan(ITEMS)
    chars = 0
    for iid, variant, state, qs in reqs:
        SystemOneRequest.model_validate({"state": state, "model": MODEL, "questions": qs})
        chars += len(json.dumps(state, ensure_ascii=False)) + len(json.dumps(qs, ensure_ascii=False))

    out = HERE / "items.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for it in ITEMS:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=False) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()

    counts = {}
    for it in ITEMS:
        c = counts.setdefault(it["category"], {"items": 0, "noul": 0, "choice": 0, "score": 0, "twin": 0,
                                               "repeat": 0, "solo": 0, "near": 0, "q1_true": 0})
        c["items"] += 1
        c[it["qtype"]] += 1
        c["twin"] += it["twin_state"] is not None
        c["repeat"] += it["meta"]["repeat"]
        c["solo"] += it["meta"]["solo"]
        c["near"] += bool(it["meta"].get("near"))
        c["q1_true"] += it["truth"]["q1"] is True
    variants = {}
    for _, v, _, _ in reqs:
        variants[v] = variants.get(v, 0) + 1
    manifest = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "items_file": "items.jsonl", "items_sha256": digest, "n_items": len(ITEMS),
        "generator": "make_items.py", "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "seed": SEED, "snapshot": "origin/phase2-stage0 @ e803a99 (p2/)", "counts_by_category": counts,
        "planned_requests": len(reqs), "planned_by_variant": variants,
        "approx_input_tokens_planned": int(chars / 3.5),
        "analysis_plan": ANALYSIS_PLAN,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("n_items", "items_sha256", "planned_requests", "planned_by_variant",
                                               "approx_input_tokens_planned")}, indent=2))
    for cat, c in sorted(counts.items()):
        print(cat, c)


if __name__ == "__main__":
    main()
