#!/usr/bin/env python3
"""
analyze.py — pre-registered analysis of the Circuit OS calibration battery (items.jsonl + results.jsonl).

Writes results_tables.md and metrics.json next to this file. Definitions follow manifest.json
"analysis_plan": q1/base/first-run is the primary pool; nouls are correct when p is on the
truth's side of 0.5 (p == 0.5 is wrong); choices by the returned argmax; scores by the argmax
level. Log loss clips p to [0.005, 0.995] (answers carry 2-decimal resolution). 95 % CIs are
percentile bootstraps over items (clusters), 2,000 resamples, seed 12345.

If label_corrections.jsonl exists, every headline is reported under the original labels (primary)
and again under the corrected labels.
"""
import collections
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
NMI = "need_more_information"
EPS = 0.005
B = 2000
SEED = 12345
ANSWERABLE = ["a_closed_form", "b_units", "c_qualitative", "d_project_rules", "f_multistep", "g_comparison"]
NUMERIC = ["a_closed_form", "b_units", "f_multistep", "g_comparison"]
CAT_SHORT = {"a_closed_form": "a closed-form", "b_units": "b units", "c_qualitative": "c qualitative",
             "d_project_rules": "d project rules", "e_unanswerable": "e unanswerable", "f_multistep": "f multi-step",
             "g_comparison": "g comparison"}
PTOP_BINS = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001]
THRESHOLDS = [0.6, 0.7, 0.8, 0.9, 0.95, 0.99]


def load():
    items = {}
    for line in (HERE / "items.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            it = json.loads(line)
            items[it["item_id"]] = it
    res = {}
    for line in (HERE / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            res.setdefault((r["item_id"], r["variant"]), r)
    corr = {}
    cp = HERE / "label_corrections.jsonl"
    if cp.exists():
        for line in cp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                corr[(c["item_id"], c["question"])] = c["corrected_truth"]
    return items, res, corr


def clip(p):
    return min(max(p, EPS), 1 - EPS)


def record(item, variant, qname, ans, truth):
    q = item["questions"][qname]
    qt = q["type"]
    rec = {"item_id": item["item_id"], "category": item["category"], "family": item["family"], "qtype": qt,
           "variant": variant, "qname": qname, "truth": truth, "near": item["meta"].get("near"),
           "steps": item["meta"].get("steps", 1),
           "form": item["base_form"] if variant in ("base", "repeat", "solo") else item["twin_form"]}
    answerable = truth not in ("unanswerable", None)
    if qt == "noul":
        p = float(ans["noul"])
        rec["p"] = p
        rec["conf"] = max(p, 1 - p)
        if answerable:
            y = 1.0 if truth else 0.0
            rec["correct"] = (p > 0.5) if truth else (p < 0.5)
            rec["brier"] = (p - y) ** 2
            rec["logloss"] = -math.log(clip(p if truth else 1 - p))
    elif qt == "choice":
        probs = {k: float(v) for k, v in ans["probabilities"].items()}
        labels = list(q["criteria"])
        srt = sorted(probs.values(), reverse=True)
        rec.update(choice=ans["choice"], probs=probs, p_top=srt[0], margin=srt[0] - (srt[1] if len(srt) > 1 else 0),
                   p_nmi=probs.get(NMI, 0.0), conf=srt[0], k=len(labels))
        if answerable:
            rec["correct"] = ans["choice"] == truth
            rec["brier"] = sum((probs.get(l, 0.0) - (1.0 if l == truth else 0.0)) ** 2 for l in labels)
            rec["logloss"] = -math.log(clip(probs.get(truth, 0.0)))
    else:
        probs = {int(k): float(v) for k, v in ans["probabilities"].items()}
        levels = list(range(len(q["criteria"])))
        am = max(levels, key=lambda l: (probs.get(l, 0.0), -l))
        rec.update(argmax=am, probs=probs, p_top=probs.get(am, 0.0), conf=probs.get(am, 0.0),
                   expected=float(ans["score"]), k=len(levels))
        if answerable:
            rec["correct"] = am == truth
            rec["brier"] = sum((probs.get(l, 0.0) - (1.0 if l == truth else 0.0)) ** 2 for l in levels)
            rec["logloss"] = -math.log(clip(probs.get(truth, 0.0)))
            rec["abs_err"] = abs(float(ans["score"]) - truth)
    return rec


def build(items, res, corr=None):
    recs = []
    for (iid, variant), row in res.items():
        it = items[iid]
        for qname, ans in row["answers"].items():
            truth = it["truth"][qname]
            if corr and (iid, qname) in corr:
                truth = corr[(iid, qname)]
            recs.append(record(it, variant, qname, ans, truth))
    return recs


# ── bootstrap helpers (cluster = item) ───────────────────────────────────────

def clusters(recs, fn):
    """Per-item tuples of sums from fn(rec) -> tuple."""
    agg = collections.OrderedDict()
    for r in recs:
        t = fn(r)
        if t is None:
            continue
        a = agg.get(r["item_id"])
        agg[r["item_id"]] = t if a is None else tuple(x + y for x, y in zip(a, t))
    return list(agg.values())


def boot(groups, stat):
    """stat(summed tuple) -> float. Returns (estimate, lo, hi)."""
    if not groups:
        return (float("nan"),) * 3
    tot = tuple(map(sum, zip(*groups)))
    est = stat(tot)
    rng = random.Random(SEED)
    n = len(groups)
    vals = []
    width = len(groups[0])
    for _ in range(B):
        acc = [0.0] * width
        for _ in range(n):
            g = groups[rng.randrange(n)]
            for i in range(width):
                acc[i] += g[i]
        v = stat(acc)
        if v == v:
            vals.append(v)
    if not vals:
        return est, float("nan"), float("nan")
    vals.sort()
    return est, vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


def ratio(t):
    return t[0] / t[1] if t[1] else float("nan")


def mean_metric(recs, key):
    g = clusters(recs, lambda r: (float(r[key]), 1.0) if key in r else None)
    return boot(g, ratio), len([r for r in recs if key in r])


def ece_groups(recs, nb=10):
    def fn(r):
        if "correct" not in r:
            return None
        b = min(int(r["conf"] * nb), nb - 1)
        t = [0.0] * (3 * nb)
        t[3 * b] = 1.0
        t[3 * b + 1] = r["conf"]
        t[3 * b + 2] = 1.0 if r["correct"] else 0.0
        return tuple(t)
    return clusters(recs, fn)


def ece_stat(t, nb=10):
    n = sum(t[3 * b] for b in range(nb))
    if not n:
        return float("nan")
    return sum(abs(t[3 * b + 1] - t[3 * b + 2]) for b in range(nb) if t[3 * b]) / n


def fmt(x, d=3):
    return "—" if x is None or x != x else f"{x:.{d}f}"


def ci(e, d=3):
    return f"{fmt(e[0], d)} [{fmt(e[1], d)}, {fmt(e[2], d)}]"


def pct(e):
    return f"{100 * e[0]:.1f} % [{100 * e[1]:.1f}, {100 * e[2]:.1f}]" if e[0] == e[0] else "—"


def summary(recs):
    ans = [r for r in recs if "correct" in r]
    acc, n = mean_metric(ans, "correct")
    return {"n": n, "items": len({r["item_id"] for r in ans}), "acc": acc,
            "brier": mean_metric(ans, "brier")[0], "logloss": mean_metric(ans, "logloss")[0],
            "ece": boot(ece_groups(ans), ece_stat),
            "mean_conf": (sum(r["conf"] for r in ans) / len(ans)) if ans else float("nan")}


def sel(recs, t):
    ans = [r for r in recs if "correct" in r]
    g = clusters(ans, lambda r: (1.0 if (r["conf"] >= t and r["correct"]) else 0.0, 1.0 if r["conf"] >= t else 0.0, 1.0))
    acc = boot(g, ratio)
    cov = sum(x[1] for x in g) / max(1.0, sum(x[2] for x in g))
    return acc, int(sum(x[1] for x in g)), cov


# ── tables ───────────────────────────────────────────────────────────────────

def main():
    items, res, corr = load()
    recs = build(items, res)
    out = []
    M = {}
    W = out.append

    rows = list(res.values())
    models = collections.Counter(r["model_resolved"] for r in rows)
    usage_in = sum(r["usage"]["input_tokens"] or 0 for r in rows)
    usage_out = sum(r["usage"]["output_tokens"] or 0 for r in rows)
    variants = collections.Counter(r["variant"] for r in rows)
    ts = sorted(r["ts"] for r in rows)
    W("# Jev calibration on Circuit OS — results tables\n")
    W("Generated by `analyze.py` from `items.jsonl` (pre-registered, sha256 in `manifest.json`) and `results.jsonl`. "
      "All CIs are 95 % item-clustered percentile bootstraps (2,000 resamples). Primary pool = canonical question q1, "
      "base form, first run, answerable categories a–d, f, g.\n")
    W("## 0. Run\n")
    W(f"| Requests answered | Variants | Input tokens | Output tokens | Model(s) resolved | First call | Last call |\n|---|---|---|---|---|---|---|\n"
      f"| {len(rows)} | {dict(variants)} | {usage_in:,} | {usage_out:,} | {dict(models)} | {ts[0]} | {ts[-1]} |\n")
    M["run"] = {"requests": len(rows), "variants": dict(variants), "input_tokens": usage_in,
                "output_tokens": usage_out, "models": dict(models), "first": ts[0], "last": ts[-1]}

    prim = [r for r in recs if r["variant"] == "base" and r["qname"] == "q1" and r["category"] in ANSWERABLE]

    def srow(label, rr):
        s = summary(rr)
        return (f"| {label} | {s['n']} | {pct(s['acc'])} | {ci(s['brier'])} | {ci(s['logloss'])} | "
                f"{ci(s['ece'])} | {fmt(s['mean_conf'])} |"), s

    hdr = "| Group | n | Accuracy [95 % CI] | Brier | Log loss | ECE [95 % CI] | Mean top-label conf |\n|---|---|---|---|---|---|---|"
    W("## 1. Headline (primary pool: q1, base form)\n")
    W(hdr)
    line, s = srow("All answerable", prim)
    W(line)
    M["headline"] = s
    for qt in ("noul", "choice", "score"):
        line, s = srow(f"type = {qt}", [r for r in prim if r["qtype"] == qt])
        W(line)
        M[f"type_{qt}"] = s
    W("")
    W("### 1a. By category (q1, base)\n")
    W(hdr)
    for c in ANSWERABLE:
        line, s = srow(CAT_SHORT[c], [r for r in prim if r["category"] == c])
        W(line)
        M[f"cat_{c}"] = s
    W("")
    W("### 1b. By category × question type (q1, base): accuracy (n)\n")
    W("| Category | noul | choice | score |\n|---|---|---|---|")
    for c in ANSWERABLE:
        cells = []
        for qt in ("noul", "choice", "score"):
            rr = [r for r in prim if r["category"] == c and r["qtype"] == qt]
            if rr:
                a, n = mean_metric(rr, "correct")
                cells.append(f"{pct(a)} ({n})")
            else:
                cells.append("—")
        W(f"| {CAT_SHORT[c]} | " + " | ".join(cells) + " |")
    W("")

    # Pooled over polarity/order variants (q1+q2) for robustness
    pooled = [r for r in recs if r["variant"] == "base" and r["qname"] in ("q1", "q2") and r["category"] in ANSWERABLE]
    W("### 1c. Pooled q1 + q2 (negated polarity / reversed labels), base form\n")
    W(hdr)
    line, s = srow("All answerable, q1+q2", pooled)
    W(line)
    M["pooled_q1q2"] = s
    for c in ANSWERABLE:
        line, _ = srow(CAT_SHORT[c], [r for r in pooled if r["category"] == c])
        W(line)
    W("")

    # Families
    W("## 2. By family (q1, base): where Jev can and cannot be used\n")
    W("| Category | Family | n | Accuracy | Mean conf | Answers with conf ≥ 0.9 | Accuracy when conf ≥ 0.9 | Confidently wrong (conf ≥ 0.9) |\n|---|---|---|---|---|---|---|---|")
    fams = collections.OrderedDict()
    for r in prim:
        fams.setdefault((r["category"], r["family"]), []).append(r)
    M["families"] = {}
    for (c, f), rr in fams.items():
        a, n = mean_metric(rr, "correct")
        hi = [r for r in rr if r["conf"] >= 0.9]
        acc_hi = sum(r["correct"] for r in hi) / len(hi) if hi else float("nan")
        wrong_hi = sum(1 for r in hi if not r["correct"])
        mc = sum(r["conf"] for r in rr) / len(rr)
        W(f"| {CAT_SHORT[c]} | {f} | {n} | {pct(a)} | {fmt(mc, 2)} | {len(hi)} | {fmt(acc_hi, 2)} | {wrong_hi} |")
        M["families"][f] = {"category": c, "n": n, "acc": a, "mean_conf": mc, "n_conf_ge_0.9": len(hi),
                            "acc_conf_ge_0.9": acc_hi, "wrong_conf_ge_0.9": wrong_hi}
    W("")

    # Reliability
    W("## 3. Reliability\n")
    W("### 3a. Top-label reliability, 10 equal-width bins (q1, base, answerable)\n")
    W("| Bin | n | Mean confidence | Accuracy | Gap (acc − conf) |\n|---|---|---|---|---|")
    ans = [r for r in prim if "correct" in r]
    M["reliability_top"] = []
    for b in range(10):
        lo, hi_ = b / 10, (b + 1) / 10
        rr = [r for r in ans if lo <= r["conf"] < hi_ or (b == 9 and r["conf"] == 1.0)]
        if not rr:
            continue
        mc = sum(r["conf"] for r in rr) / len(rr)
        ac = sum(r["correct"] for r in rr) / len(rr)
        W(f"| [{lo:.1f}, {hi_:.1f}{']' if b == 9 else ')'} | {len(rr)} | {mc:.3f} | {ac:.3f} | {ac - mc:+.3f} |")
        M["reliability_top"].append({"bin": [lo, hi_], "n": len(rr), "conf": mc, "acc": ac})
    W("")
    W("### 3b. Noul P(yes) reliability (q1 and q2, base, answerable nouls)\n")
    W("| P(yes) bin | n | Mean P(yes) | Observed frequency of 'yes' |\n|---|---|---|---|")
    nouls = [r for r in pooled if r["qtype"] == "noul" and "correct" in r]
    M["reliability_pyes"] = []
    for b in range(10):
        lo, hi_ = b / 10, (b + 1) / 10
        rr = [r for r in nouls if lo <= r["p"] < hi_ or (b == 9 and r["p"] == 1.0)]
        if not rr:
            continue
        mp = sum(r["p"] for r in rr) / len(rr)
        fy = sum(1 for r in rr if r["truth"] is True) / len(rr)
        W(f"| [{lo:.1f}, {hi_:.1f}{']' if b == 9 else ')'} | {len(rr)} | {mp:.3f} | {fy:.3f} |")
        M["reliability_pyes"].append({"bin": [lo, hi_], "n": len(rr), "p": mp, "freq_yes": fy})
    W("")
    W("### 3c. Accuracy by p_top bin (pre-registered bins; q1, base)\n")
    W("| p_top bin | All answerable: n, accuracy | Numeric (a, b, f, g): n, accuracy | Rules and facts (c, d): n, accuracy |\n|---|---|---|---|")
    M["ptop_bins"] = []
    for lo, hi_ in zip(PTOP_BINS, PTOP_BINS[1:]):
        cells = []
        entry = {"bin": [lo, min(hi_, 1.0)]}
        for name, pool in (("all", ans), ("numeric", [r for r in ans if r["category"] in NUMERIC]),
                           ("rules", [r for r in ans if r["category"] in ("c_qualitative", "d_project_rules")])):
            rr = [r for r in pool if lo <= r["conf"] < hi_]
            if rr:
                a = boot(clusters(rr, lambda r: (1.0 if r["correct"] else 0.0, 1.0)), ratio)
                cells.append(f"{len(rr)}, {pct(a)}")
                entry[name] = {"n": len(rr), "acc": a}
            else:
                cells.append("—")
        W(f"| [{lo:.2f}, {min(hi_, 1.0):.2f}{']' if hi_ > 1 else ')'} | " + " | ".join(cells) + " |")
        M["ptop_bins"].append(entry)
    W("")
    W("### 3d. Selective accuracy: answer only when top-label confidence ≥ t (q1, base)\n")
    W("| t | All: coverage, accuracy | Numeric a,b,f,g | c qualitative | d project rules |\n|---|---|---|---|---|")
    M["selective"] = {}
    for t in THRESHOLDS:
        cells = []
        for name, pool in (("all", ans), ("numeric", [r for r in ans if r["category"] in NUMERIC]),
                           ("c", [r for r in ans if r["category"] == "c_qualitative"]),
                           ("d", [r for r in ans if r["category"] == "d_project_rules"])):
            a, n, cov = sel(pool, t)
            cells.append(f"{100 * cov:.0f} % (n={n}), {pct(a)}")
            M["selective"].setdefault(str(t), {})[name] = {"coverage": cov, "n": n, "acc": a}
        W(f"| {t} | " + " | ".join(cells) + " |")
    W("")

    # Compute vs precomputed (paired)
    W("## 4. Tools compute, Jev weighs: same items, numbers computed by Jev vs precomputed in the state\n")
    W("Paired on q1. Base = Jev must compute from component values; twin = the value computed in code and written "
      "into the state (Jev only compares it with the limit or picks the band). Difference = twin − base.\n")
    W("| Category | Subset | Pairs | Accuracy, compute | Accuracy, precomputed | Difference [95 % CI] | Brier compute → precomputed | base wrong→twin right / base right→twin wrong |\n|---|---|---|---|---|---|---|---|")
    M["precompute"] = {}

    def paired(cat_list, sub=lambda it: True, forms=("compute",)):
        pairs = []
        for iid, it in items.items():
            if it["category"] not in cat_list or it["base_form"] not in forms or not sub(it):
                continue
            b, t = res.get((iid, "base")), res.get((iid, "twin"))
            if not b or not t:
                continue
            rb = record(it, "base", "q1", b["answers"]["q1"], it["truth"]["q1"])
            rt = record(it, "twin", "q1", t["answers"]["q1"], it["truth"]["q1"])
            if "correct" in rb:
                pairs.append((iid, rb, rt))
        return pairs

    def paired_row(label, sublabel, pairs, key):
        if not pairs:
            return
        g = [(1.0 if rt["correct"] else 0.0, 1.0 if rb["correct"] else 0.0, rt["brier"], rb["brier"], 1.0)
             for _, rb, rt in pairs]
        diff = boot(g, lambda t: (t[0] - t[1]) / t[4])
        ab = sum(x[1] for x in g) / len(g)
        at = sum(x[0] for x in g) / len(g)
        bb = sum(x[3] for x in g) / len(g)
        bt = sum(x[2] for x in g) / len(g)
        up = sum(1 for _, rb, rt in pairs if not rb["correct"] and rt["correct"])
        down = sum(1 for _, rb, rt in pairs if rb["correct"] and not rt["correct"])
        W(f"| {label} | {sublabel} | {len(pairs)} | {100 * ab:.1f} % | {100 * at:.1f} % | "
          f"{100 * diff[0]:+.1f} pp [{100 * diff[1]:+.1f}, {100 * diff[2]:+.1f}] | {bb:.3f} → {bt:.3f} | {up} / {down} |")
        M["precompute"][key] = {"pairs": len(pairs), "acc_compute": ab, "acc_precomputed": at, "diff": diff,
                                "brier_compute": bb, "brier_precomputed": bt, "improved": up, "worsened": down}

    paired_row("All numeric", "all", paired(NUMERIC), "numeric_all")
    paired_row("All numeric", "near threshold (1–5 %)", paired(NUMERIC, lambda it: it["meta"].get("near") is True), "numeric_near")
    paired_row("All numeric", "far (≥ 25 % / ≥ 15 % from band edges)", paired(NUMERIC, lambda it: it["meta"].get("near") is False), "numeric_far")
    for c in NUMERIC:
        paired_row(CAT_SHORT[c], "all", paired([c]), f"{c}_all")
        paired_row(CAT_SHORT[c], "near", paired([c], lambda it: it["meta"].get("near") is True), f"{c}_near")
        paired_row(CAT_SHORT[c], "far", paired([c], lambda it: it["meta"].get("near") is False), f"{c}_far")
    for qt in ("noul", "choice", "score"):
        paired_row("All numeric", f"type = {qt}", paired(NUMERIC, lambda it, qt=qt: it["qtype"] == qt), f"numeric_{qt}")
    paired_row("c qualitative", "recall → rule written in state", paired(["c_qualitative"], forms=("recall",)), "c_rule_in_state")
    W("")

    # Near vs far and steps (base and twin)
    W("## 5. Failure zones: nearness to the threshold, number of steps, unit traps (q1)\n")
    W("| Pool | Subset | n (base) | Accuracy, compute (base) | Accuracy, precomputed (twin) | Mean conf (base) | Confidently wrong, base (conf ≥ 0.9) |\n|---|---|---|---|---|---|---|")
    M["zones"] = {}

    def zone(label, sub, pool_cats):
        rb = [r for r in recs if r["variant"] == "base" and r["qname"] == "q1" and r["category"] in pool_cats
              and "correct" in r and sub(items[r["item_id"]])]
        rt = [r for r in recs if r["variant"] == "twin" and r["qname"] == "q1" and r["category"] in pool_cats
              and "correct" in r and sub(items[r["item_id"]])]
        if not rb:
            return
        a, n = mean_metric(rb, "correct")
        at, _ = mean_metric(rt, "correct")
        mc = sum(r["conf"] for r in rb) / len(rb)
        cw = sum(1 for r in rb if r["conf"] >= 0.9 and not r["correct"])
        W(f"| {label} | | {n} | {pct(a)} | {pct(at)} | {mc:.2f} | {cw} |")
        M["zones"][label] = {"n": n, "acc_base": a, "acc_twin": at, "mean_conf": mc, "confidently_wrong": cw}

    zone("Numeric, near (1–5 %)", lambda it: it["meta"].get("near") is True, NUMERIC)
    zone("Numeric, far", lambda it: it["meta"].get("near") is False, NUMERIC)
    zone("Numeric, 1 step", lambda it: it["meta"].get("steps", 1) == 1, NUMERIC)
    zone("Numeric, 2 steps", lambda it: it["meta"].get("steps", 1) == 2, NUMERIC)
    zone("Numeric, 3+ steps", lambda it: it["meta"].get("steps", 1) >= 3, NUMERIC)
    zone("Unit trap (b)", lambda it: True, ["b_units"])
    zone("Same maths, plain units (a)", lambda it: True, ["a_closed_form"])
    zone("Comparisons (g)", lambda it: True, ["g_comparison"])
    zone("Multi-step (f)", lambda it: True, ["f_multistep"])
    zone("Project-native predict() items", lambda it: it["family"].startswith("project_native"), ["f_multistep"])
    W("")
    # score-specific
    sc = [r for r in prim if r["qtype"] == "score" and "abs_err" in r]
    if sc:
        mae = sum(r["abs_err"] for r in sc) / len(sc)
        within1 = sum(1 for r in sc if abs(r["argmax"] - r["truth"]) <= 1) / len(sc)
        W(f"Score questions (q1, base, n = {len(sc)}): mean |expected score − true level| = {mae:.2f} levels; "
          f"argmax within one level of the truth: {100 * within1:.0f} %.\n")
        M["score_mae"] = mae
        M["score_within1"] = within1

    # Polarity coherence
    W("## 6. Consistency\n")
    W("### 6a. Polarity coherence of Nouls: s = P(q1) + P(q2) where q2 is the negated statement (same request)\n")
    W("| Category | Form | Pairs | Mean abs(s − 1) | Incoherent (abs(s − 1) > 0.15) | Contradictory (both > 0.5 or both < 0.5) |\n|---|---|---|---|---|---|")
    M["polarity"] = {}
    for c in ANSWERABLE + ["e_unanswerable"]:
        for variant in ("base", "twin"):
            prs = []
            for iid, it in items.items():
                if it["category"] != c or it["qtype"] != "noul":
                    continue
                row = res.get((iid, variant))
                if not row or "q2" not in row["answers"]:
                    continue
                p1, p2 = row["answers"]["q1"]["noul"], row["answers"]["q2"]["noul"]
                prs.append((iid, p1, p2))
            if not prs:
                continue
            g = [(abs(p1 + p2 - 1), 1.0 if abs(p1 + p2 - 1) > 0.15 else 0.0,
                  1.0 if (p1 > 0.5 and p2 > 0.5) or (p1 < 0.5 and p2 < 0.5) else 0.0, 1.0) for _, p1, p2 in prs]
            m = boot(g, lambda t: t[0] / t[3])
            inc = boot(g, lambda t: t[1] / t[3])
            con = boot(g, lambda t: t[2] / t[3])
            form = items[prs[0][0]]["base_form"] if variant == "base" else items[prs[0][0]]["twin_form"]
            W(f"| {CAT_SHORT[c]} | {variant} ({form}) | {len(prs)} | {ci(m)} | {pct(inc)} | {pct(con)} |")
            M["polarity"][f"{c}|{variant}"] = {"pairs": len(prs), "mean_abs_dev": m, "incoherent": inc, "contradictory": con}
    W("")
    W("### 6b. Label-order effects: q2 = same Choice with labels reversed (Score: levels reversed), same request\n")
    W("| Category | Type | Pairs | Argmax flips | Mean total-variation distance |\n|---|---|---|---|---|")
    M["order"] = {}
    for c in ANSWERABLE + ["e_unanswerable"]:
        for qt in ("choice", "score"):
            prs = []
            for iid, it in items.items():
                if it["category"] != c or it["qtype"] != qt:
                    continue
                row = res.get((iid, "base"))
                if not row:
                    continue
                a1, a2 = row["answers"]["q1"], row["answers"]["q2"]
                if qt == "choice":
                    labels = list(it["questions"]["q1"]["criteria"])
                    d1 = {l: float(a1["probabilities"].get(l, 0.0)) for l in labels}
                    d2 = {l: float(a2["probabilities"].get(l, 0.0)) for l in labels}
                    flip = a1["choice"] != a2["choice"]
                else:
                    k = len(it["questions"]["q1"]["criteria"])
                    d1 = {l: float(a1["probabilities"].get(str(l), a1["probabilities"].get(l, 0.0))) for l in range(k)}
                    d2 = {l: float(a2["probabilities"].get(str(k - 1 - l), a2["probabilities"].get(k - 1 - l, 0.0))) for l in range(k)}
                    flip = max(d1, key=lambda l: (d1[l], -l)) != max(d2, key=lambda l: (d2[l], -l))
                tvd = 0.5 * sum(abs(d1[l] - d2[l]) for l in d1)
                prs.append((1.0 if flip else 0.0, tvd, 1.0))
            if not prs:
                continue
            fl = boot(prs, lambda t: t[0] / t[2])
            tv = boot(prs, lambda t: t[1] / t[2])
            W(f"| {CAT_SHORT[c]} | {qt} | {len(prs)} | {pct(fl)} | {ci(tv)} |")
            M["order"][f"{c}|{qt}"] = {"pairs": len(prs), "flip": fl, "tvd": tv}
    W("")

    def delta_rows(variant_b):
        out_ = []
        for iid, it in items.items():
            b, o = res.get((iid, "base")), res.get((iid, variant_b))
            if not b or not o:
                continue
            for qn, ao in o["answers"].items():
                ab = b["answers"][qn]
                if ab["type"] == "noul":
                    d = abs(ab["noul"] - ao["noul"])
                    am = (ab["noul"] > 0.5) != (ao["noul"] > 0.5)
                elif ab["type"] == "choice":
                    ks = set(ab["probabilities"]) | set(ao["probabilities"])
                    d = max(abs(ab["probabilities"].get(k, 0) - ao["probabilities"].get(k, 0)) for k in ks)
                    am = ab["choice"] != ao["choice"]
                else:
                    ks = set(ab["probabilities"]) | set(ao["probabilities"])
                    d = max(abs(ab["probabilities"].get(k, 0) - ao["probabilities"].get(k, 0)) for k in ks)
                    pb = {int(k): v for k, v in ab["probabilities"].items()}
                    po = {int(k): v for k, v in ao["probabilities"].items()}
                    am = max(pb, key=lambda l: (pb[l], -l)) != max(po, key=lambda l: (po[l], -l))
                out_.append((iid, qn, d, am))
        return out_

    W("### 6c. Identical repeats and batching\n")
    W("| Comparison | Answers compared | Mean abs Δp | Median abs Δp | Max abs Δp | Share with abs Δp ≥ 0.05 | Argmax / side of 0.5 changed |\n|---|---|---|---|---|---|---|")
    M["repeat_solo"] = {}
    for variant_b, label in (("repeat", "Identical request re-sent (repeat vs base)"),
                             ("solo", "q1 alone vs q1 batched with q2/q3 (solo vs base)")):
        dr = delta_rows(variant_b)
        if not dr:
            continue
        ds = sorted(x[2] for x in dr)
        W(f"| {label} | {len(dr)} | {sum(ds) / len(ds):.3f} | {ds[len(ds) // 2]:.3f} | {ds[-1]:.3f} | "
          f"{100 * sum(1 for x in ds if x >= 0.05) / len(ds):.1f} % | {sum(1 for x in dr if x[3])} of {len(dr)} |")
        M["repeat_solo"][variant_b] = {"n": len(dr), "mean": sum(ds) / len(ds), "median": ds[len(ds) // 2], "max": ds[-1],
                                       "share_ge_0.05": sum(1 for x in ds if x >= 0.05) / len(ds),
                                       "argmax_changed": sum(1 for x in dr if x[3])}
    W("")

    # Abstention
    W("## 7. Unanswerable items and false abstention\n")
    W("### 7a. Category e (the deciding fact is absent), base form\n")
    W("| Subtype | Choice items | Choice abstains (argmax = need_more_information), q1 / q2 | Mean P(nmi) q1 | Noul items | Mean P(yes) q1 / q2 | Noul in 0.35–0.65, q1 | Mean polarity sum | Sufficiency Noul says 'missing' (p < 0.5) |\n|---|---|---|---|---|---|---|---|---|")
    M["unanswerable"] = {}
    subs = collections.OrderedDict()
    for iid, it in items.items():
        if it["category"] == "e_unanswerable":
            subs.setdefault(it["meta"]["subtype"], []).append(it)
    subs["ALL"] = [it for it in items.values() if it["category"] == "e_unanswerable"]
    for sub, its in subs.items():
        ch = [it for it in its if it["qtype"] == "choice"]
        nl = [it for it in its if it["qtype"] == "noul"]
        a1 = [res[(it["item_id"], "base")]["answers"]["q1"] for it in ch]
        a2 = [res[(it["item_id"], "base")]["answers"]["q2"] for it in ch]
        abst1 = sum(a["choice"] == NMI for a in a1)
        abst2 = sum(a["choice"] == NMI for a in a2)
        pn = sum(a["probabilities"].get(NMI, 0) for a in a1) / max(1, len(a1))
        n1 = [res[(it["item_id"], "base")]["answers"]["q1"]["noul"] for it in nl]
        n2 = [res[(it["item_id"], "base")]["answers"]["q2"]["noul"] for it in nl]
        mid = sum(1 for p in n1 if 0.35 <= p <= 0.65)
        psum = sum(a + b for a, b in zip(n1, n2)) / max(1, len(n1))
        q3 = [res[(it["item_id"], "base")]["answers"]["q3"]["noul"] for it in its]
        miss = sum(1 for p in q3 if p < 0.5)
        W(f"| {sub} | {len(ch)} | {abst1}/{len(ch)} / {abst2}/{len(ch)} | {pn:.2f} | {len(nl)} | "
          f"{(sum(n1) / max(1, len(n1))):.2f} / {(sum(n2) / max(1, len(n2))):.2f} | {mid}/{len(nl)} | {psum:.2f} | {miss}/{len(q3)} |")
        M["unanswerable"][sub] = {"choice_n": len(ch), "abstain_q1": abst1, "abstain_q2": abst2, "mean_p_nmi": pn,
                                  "noul_n": len(nl), "noul_mean_q1": sum(n1) / max(1, len(n1)),
                                  "noul_mean_q2": sum(n2) / max(1, len(n2)), "noul_midband": mid,
                                  "polarity_sum": psum, "sufficiency_missing": miss, "sufficiency_n": len(q3),
                                  "noul_p_q1": n1, "noul_p_q2": n2}
    # CI for pooled choice abstention
    ch_all = [it for it in items.values() if it["category"] == "e_unanswerable" and it["qtype"] == "choice"]
    g = [(1.0 if res[(it["item_id"], "base")]["answers"]["q1"]["choice"] == NMI else 0.0, 1.0) for it in ch_all]
    M["unanswerable_choice_abstain_ci"] = boot(g, ratio)
    nl_all = [it for it in items.values() if it["category"] == "e_unanswerable" and it["qtype"] == "noul"]
    g = [(1.0 if 0.35 <= res[(it["item_id"], "base")]["answers"]["q1"]["noul"] <= 0.65 else 0.0, 1.0) for it in nl_all]
    M["unanswerable_noul_midband_ci"] = boot(g, ratio)
    g = [(1.0 if res[(it["item_id"], "base")]["answers"]["q1"]["noul"] < 0.5 else 0.0, 1.0) for it in nl_all]
    M["unanswerable_noul_below_half_ci"] = boot(g, ratio)
    W(f"\nPooled: Choice abstention on unanswerable q1 {pct(M['unanswerable_choice_abstain_ci'])} (n = {len(ch_all)}); "
      f"unanswerable Nouls inside 0.35–0.65 {pct(M['unanswerable_noul_midband_ci'])}, below 0.5 "
      f"{pct(M['unanswerable_noul_below_half_ci'])} (n = {len(nl_all)}).\n")
    W("### 7b. False abstention on answerable items\n")
    W("| Category | Answerable choices (q1, base) | argmax = need_more_information | Mean P(nmi) | Items with sufficiency Noul | Sufficiency says 'missing' (p < 0.5), base | same, twin |\n|---|---|---|---|---|---|---|")
    M["false_abstention"] = {}
    for c in ANSWERABLE:
        ch = [r for r in prim if r["category"] == c and r["qtype"] == "choice"]
        fa = sum(1 for r in ch if r["choice"] == NMI)
        mp = sum(r["p_nmi"] for r in ch) / max(1, len(ch))
        q3b = [res[(iid, "base")]["answers"]["q3"]["noul"] for iid, it in items.items()
               if it["category"] == c and (iid, "base") in res and "q3" in res[(iid, "base")]["answers"]]
        q3t = [res[(iid, "twin")]["answers"]["q3"]["noul"] for iid, it in items.items()
               if it["category"] == c and (iid, "twin") in res and "q3" in res[(iid, "twin")]["answers"]]
        mb = sum(1 for p in q3b if p < 0.5)
        mt = sum(1 for p in q3t if p < 0.5)
        W(f"| {CAT_SHORT[c]} | {len(ch)} | {fa} | {mp:.3f} | {len(q3b)} | {mb} | {mt if q3t else '—'} |")
        M["false_abstention"][c] = {"choices": len(ch), "nmi_argmax": fa, "mean_p_nmi": mp, "q3_n": len(q3b),
                                    "q3_missing_base": mb, "q3_missing_twin": mt}
    W("")

    # Confidently wrong list
    W("## 8. Every confidently wrong answer (q1, base, top-label confidence ≥ 0.9)\n")
    W("| Item | Family | Truth | Jev | Confidence | Value / limit (derivation) |\n|---|---|---|---|---|---|")
    cw = sorted([r for r in prim if "correct" in r and not r["correct"] and r["conf"] >= 0.9], key=lambda r: -r["conf"])
    M["confidently_wrong"] = []
    for r in cw:
        it = items[r["item_id"]]
        d = it["derivation"]
        val = d.get("value", d.get("value_us", d.get("value_mV", d.get("values", ""))))
        lim = d.get("limit", d.get("band_edges", d.get("level_edges", "")))
        jev = r.get("p", r.get("choice", r.get("argmax")))
        vtxt = f"{val:.4g} vs {lim}" if isinstance(val, float) else f"{val} {lim}"
        W(f"| {r['item_id']} | {r['family']} | {r['truth']} | {jev} | {r['conf']:.2f} | {vtxt} |")
        M["confidently_wrong"].append({"item": r["item_id"], "family": r["family"], "truth": r["truth"],
                                       "jev": jev, "conf": r["conf"]})
    W("")

    # Hypotheses
    W("## 9. Pre-registered hypotheses\n")
    hyp = {}
    pc = M["precompute"].get("numeric_all")
    hyp["H1"] = ("compute less accurate than precomputed",
                 pc and pc["diff"][1] > 0, f"difference {100 * pc['diff'][0]:+.1f} pp [{100 * pc['diff'][1]:+.1f}, {100 * pc['diff'][2]:+.1f}]" if pc else "—")
    zn, zf = M["zones"].get("Numeric, near (1–5 %)"), M["zones"].get("Numeric, far")
    hyp["H2"] = ("near less accurate than far", zn and zf and zn["acc_base"][2] < zf["acc_base"][1] or
                 (zn and zf and zn["acc_base"][0] < zf["acc_base"][0]),
                 f"near {pct(zn['acc_base'])} vs far {pct(zf['acc_base'])}" if zn and zf else "—")
    num_hi = sel([r for r in ans if r["category"] in NUMERIC], 0.9)
    c_twin = [r for r in recs if r["variant"] == "twin" and r["qname"] == "q1" and r["category"] == "c_qualitative" and "correct" in r]
    d_base = [r for r in ans if r["category"] == "d_project_rules"]
    rule_hi = sel(c_twin + d_base, 0.9)
    hyp["H3"] = ("conf ≥ 0.9: compute < 0.9 accurate; rule-in-state ≥ 0.9", None,
                 f"numeric compute at conf ≥ 0.9: {pct(num_hi[0])} (n={num_hi[1]}); rule-in-state (c twin + d) at conf ≥ 0.9: {pct(rule_hi[0])} (n={rule_hi[1]})")
    hyp["H3"] = (hyp["H3"][0], num_hi[0][0] < 0.9 and rule_hi[0][0] >= 0.9, hyp["H3"][2])
    u = M["unanswerable"]["ALL"]
    hyp["H4"] = ("unanswerable Nouls lean 'no' rather than 0.35–0.65", u["noul_midband"] < u["noul_n"] / 2,
                 f"{u['noul_midband']}/{u['noul_n']} inside 0.35–0.65; mean P(yes) q1 {u['noul_mean_q1']:.2f}")
    hyp["H5"] = ("Choices abstain on ≥ 80 % of unanswerable", u["abstain_q1"] / max(1, u["choice_n"]) >= 0.8,
                 f"{u['abstain_q1']}/{u['choice_n']} (q1)")
    pol_num = [M["polarity"][k]["mean_abs_dev"][0] for k in M["polarity"] if k.split("|")[0] in NUMERIC and k.endswith("|base")]
    pol_rule = [M["polarity"][k]["mean_abs_dev"][0] for k in M["polarity"] if k.split("|")[0] in ("c_qualitative", "d_project_rules") and k.endswith("|base")]
    hyp["H6"] = ("polarity deviates more on compute than on rules", (sum(pol_num) / len(pol_num)) > (sum(pol_rule) / len(pol_rule)),
                 f"mean abs(s − 1): numeric categories {sum(pol_num) / len(pol_num):.3f} vs c, d {sum(pol_rule) / len(pol_rule):.3f}")
    W("| Hypothesis | Supported? | Evidence |\n|---|---|---|")
    for k, (desc, ok, ev) in hyp.items():
        W(f"| {k}: {desc} | {'yes' if ok else 'no'} | {ev} |")
    M["hypotheses"] = {k: {"desc": v[0], "supported": bool(v[1]), "evidence": v[2]} for k, v in hyp.items()}
    W("")

    # Corrections
    if corr:
        rc = build(items, res, corr)
        prim_c = [r for r in rc if r["variant"] == "base" and r["qname"] == "q1" and r["category"] in ANSWERABLE]
        W("## 10. Headline under corrected labels (see label_corrections.jsonl)\n")
        W(hdr)
        line, s = srow("All answerable (corrected labels)", prim_c)
        W(line)
        for c in ANSWERABLE:
            line, _ = srow(CAT_SHORT[c], [r for r in prim_c if r["category"] == c])
            W(line)
        M["headline_corrected"] = s
        W("")

    (HERE / "results_tables.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (HERE / "metrics.json").write_text(json.dumps(M, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o)) + "\n",
                                       encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
