"""Analyse results.jsonl against the pre-registered corpora and rules. No network.

    python analyze.py            # writes RESULTS.md and metrics.json next to this file

Flag rules, metrics and decision criteria are the ones frozen in PREREGISTRATION.md.
"""
import json
import math
import pathlib
import random
import statistics
from collections import Counter, defaultdict

from questions import leaves, qname

HERE = pathlib.Path(__file__).resolve().parent
SEED = 20260925
NBOOT = 2000
TAUS = (0.5, 0.7, 0.9)
T_FAULTS = ("unit_scale", "wrong_function", "dropped_requirement", "hallucinated_value", "swapped_values",
            "wrong_board", "out_of_catalogue")
P_FAULTS = ("swapped_values", "unrelated_removal", "missing_op", "extra_op", "wrong_path", "unit_scale")
TARGETS = {
    "fields": ("unit_scale", "hallucinated_value", "swapped_values", "wrong_board"),
    "function": ("wrong_function", "out_of_catalogue"),
    "unrep": ("dropped_requirement",),
    "any": T_FAULTS,
    "op": ("swapped_values", "unrelated_removal", "extra_op", "wrong_path", "unit_scale"),
    "cov": ("missing_op",),
    "pany": P_FAULTS,
}


# ── statistics ─────────────────────────────────────────────────────────────────────────
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def boot_prop(flags, rng):
    n = len(flags)
    if n == 0:
        return (float("nan"), float("nan"))
    stats = sorted(sum(flags[rng.randrange(n)] for _ in range(n)) / n for _ in range(NBOOT))
    return (stats[int(0.025 * NBOOT)], stats[int(0.975 * NBOOT) - 1])


def prop(flags, rng):
    flags = [bool(f) for f in flags]
    k, n = sum(flags), len(flags)
    return {"k": k, "n": n, "p": (k / n if n else float("nan")), "boot": boot_prop(flags, rng), "wilson": wilson(k, n)}


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    s = 0.0
    for a in pos:
        for b in neg:
            s += 1.0 if a > b else (0.5 if a == b else 0.0)
    return s / (len(pos) * len(neg))


def auc_ci(pos, neg, rng):
    a = auc(pos, neg)
    if not pos or not neg:
        return {"auc": a, "boot": (float("nan"), float("nan")), "n_pos": len(pos), "n_neg": len(neg)}
    vals = sorted(auc([pos[rng.randrange(len(pos))] for _ in pos], [neg[rng.randrange(len(neg))] for _ in neg])
                  for _ in range(NBOOT))
    return {"auc": a, "boot": (vals[int(0.025 * NBOOT)], vals[int(0.975 * NBOOT) - 1]), "n_pos": len(pos), "n_neg": len(neg)}


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def fmt_prop(m):
    if not m["n"]:
        return "–"
    return (f"{m['k']}/{m['n']} = {m['p']:.2f} [boot {m['boot'][0]:.2f}–{m['boot'][1]:.2f}; "
            f"Wilson {m['wilson'][0]:.2f}–{m['wilson'][1]:.2f}]")


def fmt_short(m):
    return "–" if not m["n"] else f"{m['k']}/{m['n']} ({m['p']:.2f})"


def fmt_auc(a):
    if a["auc"] != a["auc"]:
        return "–"
    return f"{a['auc']:.3f} [{a['boot'][0]:.3f}–{a['boot'][1]:.3f}] (n+={a['n_pos']}, n−={a['n_neg']})"


# ── loading ────────────────────────────────────────────────────────────────────────────
def load():
    tc = json.loads((HERE / "corpus_transcription.json").read_text(encoding="utf-8"))
    pc = json.loads((HERE / "corpus_patch.json").read_text(encoding="utf-8"))
    ic = json.loads((HERE / "corpus_injection.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (HERE / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    res = {}
    for r in rows:
        if r.get("error"):
            continue
        res[(r["corpus"], r["item_id"], r["variant"])] = r
    return tc, pc, ic, rows, res


def noul(ans, name):
    a = ans.get(name)
    return None if a is None else a["noul"]


# ── transcription flags ────────────────────────────────────────────────────────────────
def t_view(item, row, variant, det_key="unit_grounded"):
    """Per-item signals for one variant. Numeric leaves in S use the deterministic check."""
    ans = row["answers"]
    lv = leaves(item["requirements"])
    v = {"leafP": {}, "det_flag": {}, "fn_argmax": None, "fn_probs": None, "unrep": None}
    for p in lv:
        if variant == "N":
            q = noul(ans, qname("notstated", p))
            v["leafP"][p] = None if q is None else 1.0 - q  # expressed as P(stated) for flagging
            v.setdefault("notstated", {})[p] = q
        else:
            v["leafP"][p] = noul(ans, qname("stated", p))
        d = item.get("deterministic", {}).get(p, {})
        if d.get("numeric"):
            key = "unit_grounded_paraphrase" if det_key == "paraphrase" else "unit_grounded"
            v["det_flag"][p] = not d.get(key)
    if "function_asked" in ans:
        v["fn_argmax"] = ans["function_asked"]["choice"]
        v["fn_probs"] = ans["function_asked"]["probabilities"]
    if variant == "N":
        ar = noul(ans, "all_represented")
        v["unrep"] = None if ar is None else 1.0 - ar
        v["all_represented"] = ar
    else:
        v["unrep"] = noul(ans, "unrepresented_request")
    return v


def t_flags(item, v, tau, mode="jev", jev_o=None):
    """mode: jev (all leaves by Jev) | residue (numeric by det, rest by Jev) | hybrid | det."""
    fields = False
    for p, P in v["leafP"].items():
        numeric = p in v["det_flag"]
        if mode == "det":
            if numeric and v["det_flag"][p]:
                fields = True
            continue
        if mode == "residue" and numeric:
            if v["det_flag"][p]:
                fields = True
            continue
        if mode == "hybrid" and numeric:
            if v["det_flag"][p]:
                fields = True
                continue
            P = jev_o["leafP"][p]
        if P is not None and P < tau:
            fields = True
    fn = (v["fn_argmax"] is not None and v["fn_argmax"] != item["requirements"]["function"]) if mode != "det" else False
    un = (v["unrep"] is not None and v["unrep"] > 0.5) if mode != "det" else False
    return {"fields": fields, "function": fn, "unrep": un, "any": fields or fn or un}


def main():
    tc, pc, ic, rows, res = load()
    rng = random.Random(SEED)
    out, md = {}, []
    T = {it["id"]: it for it in tc["items"]}
    P = {it["id"]: it for it in pc["items"]}
    faithful = [i for i in T.values() if i["stratum"] == "faithful"]
    implied = [i for i in T.values() if i["stratum"] == "faithful_implied"]
    seeded = [i for i in T.values() if i["stratum"] == "seeded"]
    by_fault = defaultdict(list)
    for i in seeded:
        by_fault[i["fault_type"]].append(i)

    # ── run summary ──
    ok = [r for r in rows if not r.get("error")]
    models = Counter(r.get("model_resolved") for r in ok)
    tok = sum(r["usage"]["input_tokens"] for r in ok)
    md.append("# Results — Jev as Circuit OS runtime shadow checks\n")
    md.append("Generated by `analyze.py` from `results.jsonl` against the corpora frozen in `PREREGISTRATION.md`. "
              "Proportions: k/n = p [bootstrap 95% CI; Wilson 95% CI]. AUC [bootstrap 95% CI]. "
              "Faithful = the 40 explicit faithful transcription items / 26 faithful patches.\n")
    md.append("## Run\n")
    md.append(f"- Calls logged: {len(rows)}; errors: {len(rows) - len(ok)}; input tokens: {tok:,}; "
              f"output tokens: {sum(r['usage']['output_tokens'] for r in ok):,}")
    md.append(f"- Model returned: {dict(models)} (requested `jev-1.13.0`)")
    md.append(f"- First call {min(r['ts'] for r in rows)}, last call {max(r['ts'] for r in rows)}\n")
    out["run"] = {"calls": len(rows), "errors": len(rows) - len(ok), "input_tokens": tok, "models": dict(models)}

    def tv(item, variant):
        r = res.get(("T", item["id"], variant))
        return None if r is None else t_view(item, r, variant, "paraphrase" if variant == "Q" else "unit_grounded")

    views = {(i["id"], v): tv(i, v) for i in T.values() for v in ("O", "R", "P", "Q", "E", "S", "D", "N")}

    def flagset(variant, tau, mode="jev"):
        f = {}
        for i in T.values():
            v = views.get((i["id"], variant))
            if v is None:
                continue
            f[i["id"]] = t_flags(i, v, tau, mode, jev_o=views.get((i["id"], "O")))
        return f

    # ── R1 per check × fault type (variant O) ──
    md.append("## R1 transcription fidelity — variant O (B11 wording)\n")
    md.append("Recall = share of seeded items of that fault type flagged by the check. False flags = share of the "
              "40 explicit faithful items flagged. `fields@τ` flags any `stated_<leaf>` with P(yes) < τ; "
              "`function` flags argmax ≠ recorded function; `unrep` flags P(unrepresented) > 0.5; `any` = OR.\n")
    out["R1"] = {}
    header = "| Fault type (n) | fields@0.5 | fields@0.7 | fields@0.9 | function | unrep>0.5 | any@0.5 | any@0.9 |"
    md.append(header)
    md.append("|" + "---|" * 8)
    fl = {tau: flagset("O", tau) for tau in TAUS}
    for fault in T_FAULTS + ("faithful", "faithful_implied"):
        items = by_fault[fault] if fault in by_fault else (faithful if fault == "faithful" else implied)
        cells = []
        for key, tau in (("fields", 0.5), ("fields", 0.7), ("fields", 0.9), ("function", 0.5), ("unrep", 0.5),
                         ("any", 0.5), ("any", 0.9)):
            m = prop([fl[tau][i["id"]][key] for i in items], rng)
            out["R1"].setdefault(fault, {})[f"{key}@{tau}"] = m
            cells.append(fmt_short(m))
        md.append(f"| {fault} ({len(items)}) | " + " | ".join(cells) + " |")
    md.append("")
    md.append("Headline per check on its pre-registered target faults (O):\n")
    md.append("| Check | Target faults | Recall | False flags on faithful |")
    md.append("|---|---|---|---|")
    headline = {}
    for key, taus in (("fields", TAUS), ("function", (0.5,)), ("unrep", (0.5,)), ("any", TAUS)):
        for tau in taus:
            tg = [i for f in TARGETS[key] for i in by_fault[f]]
            rec = prop([fl[tau][i["id"]][key] for i in tg], rng)
            ff = prop([fl[tau][i["id"]][key] for i in faithful], rng)
            headline[f"{key}@{tau}"] = {"recall": rec, "ffr": ff}
            name = f"R1-{key}" + (f"@{tau}" if key in ("fields", "any") else "")
            md.append(f"| {name} | {', '.join(TARGETS[key])} | {fmt_prop(rec)} | {fmt_prop(ff)} |")
    out["R1_headline"] = headline
    md.append("")

    # AUCs
    md.append("### AUC (variant O)\n")
    md.append("| Score | Positives | Negatives | AUC |")
    md.append("|---|---|---|---|")
    aucs = {}
    pos = [1 - views[(i["id"], "O")]["leafP"][p] for i in seeded for p, lab in i["labels"]["stated"].items() if not lab]
    neg = [1 - views[(i["id"], "O")]["leafP"][p] for i in faithful for p in i["labels"]["stated"]]
    aucs["leaf_all"] = auc_ci(pos, neg, rng)
    md.append(f"| 1 − P(stated), leaf | every leaf labelled not-stated | every leaf of faithful items | {fmt_auc(aucs['leaf_all'])} |")
    for fault in ("unit_scale", "hallucinated_value", "swapped_values", "wrong_board"):
        pos = [1 - views[(i["id"], "O")]["leafP"][p] for i in by_fault[fault] for p, lab in i["labels"]["stated"].items() if not lab]
        aucs[f"leaf_{fault}"] = auc_ci(pos, neg, rng)
        md.append(f"| 1 − P(stated), leaf | {fault} leaves | faithful leaves | {fmt_auc(aucs[f'leaf_{fault}'])} |")
    tg = [i for f in TARGETS["fields"] for i in by_fault[f]]
    item_score = lambda i: 1 - min(views[(i["id"], "O")]["leafP"].values())  # noqa: E731
    aucs["item_fields"] = auc_ci([item_score(i) for i in tg], [item_score(i) for i in faithful], rng)
    md.append(f"| 1 − min P(stated), item | fields targets | faithful items | {fmt_auc(aucs['item_fields'])} |")
    fn_score = lambda i, v="O": 1 - views[(i["id"], v)]["fn_probs"].get(i["requirements"]["function"], 0.0)  # noqa: E731
    tg = [i for f in TARGETS["function"] for i in by_fault[f]]
    aucs["function"] = auc_ci([fn_score(i) for i in tg], [fn_score(i) for i in faithful], rng)
    md.append(f"| 1 − P(recorded function) | wrong_function + out_of_catalogue | faithful | {fmt_auc(aucs['function'])} |")
    tg = by_fault["dropped_requirement"]
    aucs["unrep"] = auc_ci([views[(i["id"], "O")]["unrep"] for i in tg], [views[(i["id"], "O")]["unrep"] for i in faithful], rng)
    md.append(f"| P(unrepresented) | dropped_requirement | faithful | {fmt_auc(aucs['unrep'])} |")
    strict = [i for i in seeded if i["labels"]["unrepresented_strict"]]
    aucs["unrep_strict"] = auc_ci([views[(i["id"], "O")]["unrep"] for i in strict], [views[(i["id"], "O")]["unrep"] for i in faithful], rng)
    md.append(f"| P(unrepresented) | all strict-labelled items | faithful | {fmt_auc(aucs['unrep_strict'])} |")
    out["R1_auc"] = aucs
    md.append("")

    # Per-field results
    md.append("### Per-field results (variant O; leaf level)\n")
    md.append("Mean P(stated) with the share of leaves below 0.5 / 0.9. `true` = leaves labelled stated (all strata "
              "except implied), `false` = leaves labelled not stated.\n")
    md.append("| Field | true leaves: n, mean P, <0.5, <0.9 | false leaves: n, mean P, <0.5, <0.9 |")
    md.append("|---|---|---|")
    per_field = defaultdict(lambda: {"t": [], "f": []})
    for i in T.values():
        if i["stratum"] == "faithful_implied":
            continue
        for p, lab in i["labels"]["stated"].items():
            per_field[p]["t" if lab else "f"].append(views[(i["id"], "O")]["leafP"][p])
    pf_out = {}
    for p in sorted(per_field):
        d = per_field[p]

        def s(xs):
            if not xs:
                return "–"
            return f"{len(xs)}, {statistics.mean(xs):.2f}, {sum(x < .5 for x in xs)}, {sum(x < .9 for x in xs)}"
        pf_out[p] = {"true": d["t"], "false": d["f"]}
        md.append(f"| `{p}` | {s(d['t'])} | {s(d['f'])} |")
    out["per_field"] = pf_out
    md.append("")

    # Question-level accuracy for function and unrepresented
    md.append("### What the function and unrepresented questions answered (variant O)\n")
    md.append("| Stratum / fault | n | argmax = expected function | argmax = recorded function | mean P(unrep) | P(unrep)>0.5 | strict label true | lenient label true |")
    md.append("|---|---|---|---|---|---|---|---|")
    for fault in ("faithful", "faithful_implied") + T_FAULTS:
        items = faithful if fault == "faithful" else implied if fault == "faithful_implied" else by_fault[fault]
        vs = [views[(i["id"], "O")] for i in items]
        md.append(f"| {fault} | {len(items)} | {sum(v['fn_argmax'] == i['labels']['function_expected'] for v, i in zip(vs, items))} | "
                  f"{sum(v['fn_argmax'] == i['requirements']['function'] for v, i in zip(vs, items))} | "
                  f"{statistics.mean(v['unrep'] for v in vs):.2f} | {sum(v['unrep'] > .5 for v in vs)} | "
                  f"{sum(i['labels']['unrepresented_strict'] for i in items)} | {sum(i['labels']['unrepresented_lenient'] for i in items)} |")
    md.append("")
    md.append("Seeded items where the function check missed (O): " + ", ".join(
        f"{i['id']} ({i['fault_type']}: argmax {views[(i['id'], 'O')]['fn_argmax']}, "
        f"P(recorded)={views[(i['id'], 'O')]['fn_probs'].get(i['requirements']['function'], 0):.2f})"
        for f in TARGETS["function"] for i in by_fault[f] if not fl[0.5][i["id"]]["function"]) + "\n")
    md.append("Faithful items falsely flagged by any R1 check at τ=0.5 (O): " + (", ".join(
        f"{i['id']} (" + ", ".join(k for k in ("fields", "function", "unrep") if fl[0.5][i["id"]][k]) + ")"
        for i in faithful if fl[0.5][i["id"]]["any"]) or "none") + "\n")
    md.append("Faithful items with any leaf < 0.9 (O): " + (", ".join(
        f"{i['id']} (" + ", ".join(f"{p}={views[(i['id'], 'O')]['leafP'][p]:.2f}" for p in i["labels"]["stated"]
                                   if views[(i['id'], 'O')]['leafP'][p] < .9) + ")"
        for i in faithful if fl[0.9][i["id"]]["fields"]) or "none") + "\n")
    md.append("Seeded value-fault leaves Jev scored ≥ 0.5 (missed at τ=0.5, O): " + (", ".join(
        f"{i['id']} {p}={views[(i['id'], 'O')]['leafP'][p]:.2f}" for f in TARGETS["fields"] for i in by_fault[f]
        for p, lab in i["labels"]["stated"].items() if not lab and views[(i["id"], "O")]["leafP"][p] >= .5) or "none") + "\n")

    # ── Variants ──
    md.append("## R1 across variants\n")
    md.append("Recall on each check's target faults / false flags on the 40 faithful items. S = semantic residue "
              "(numeric leaves by the deterministic unit-aware check, only non-numeric questions to Jev); H = hybrid "
              "(computed from O: deterministic presence check, Jev for binding of numerics that pass it); "
              "det = deterministic numeric check alone; N = negated-polarity nouls (subset, flag if P(not stated) > 1−τ).\n")
    md.append("| Variant | fields@0.5 recall / FF | fields@0.9 recall / FF | function recall / FF | unrep recall / FF | any@0.5 recall (all seeded) / FF |")
    md.append("|---|---|---|---|---|---|")
    var_out = {}
    for label, variant, mode in (("O original", "O", "jev"), ("R labels reversed", "R", "jev"), ("P repeat", "P", "jev"),
                                 ("Q paraphrase", "Q", "jev"), ("E SI rendering", "E", "jev"), ("D sharpened", "D", "jev"),
                                 ("S residue", "S", "residue"), ("H hybrid (from O)", "O", "hybrid"),
                                 ("det only (no Jev)", "O", "det"), ("N negated (subset)", "N", "jev")):
        cells, vo = [], {}
        for key, tau in (("fields", 0.5), ("fields", 0.9), ("function", 0.5), ("unrep", 0.5), ("any", 0.5)):
            f = flagset(variant, tau, mode)
            tg = [i for flt in TARGETS[key] for i in by_fault[flt] if i["id"] in f]
            fa = [i for i in faithful if i["id"] in f]
            if key in ("function", "unrep") and (mode == "det" or variant == "N" and key == "function"):
                cells.append("–")
                continue
            rec, ff = prop([f[i["id"]][key] for i in tg], rng), prop([f[i["id"]][key] for i in fa], rng)
            vo[f"{key}@{tau}"] = {"recall": rec, "ffr": ff}
            cells.append(f"{fmt_short(rec)} / {fmt_short(ff)}")
        var_out[label] = vo
        md.append(f"| {label} | " + " | ".join(cells) + " |")
    out["R1_variants"] = var_out
    md.append("")
    md.append("Per fault type, R1-any@0.5 recall by condition (O vs residue S vs hybrid H vs deterministic only):\n")
    md.append("| Fault type (n) | O (Jev only) | S residue | H hybrid | det only |")
    md.append("|---|---|---|---|---|")
    for fault in T_FAULTS:
        cells = []
        for variant, mode in (("O", "jev"), ("S", "residue"), ("O", "hybrid"), ("O", "det")):
            f = flagset(variant, 0.5, mode)
            key = "fields" if mode == "det" else "any"
            cells.append(fmt_short(prop([f[i["id"]][key] for i in by_fault[fault]], rng)))
        md.append(f"| {fault} ({len(by_fault[fault])}) | " + " | ".join(cells) + " |")
    cells = []
    for variant, mode in (("O", "jev"), ("S", "residue"), ("O", "hybrid"), ("O", "det")):
        f = flagset(variant, 0.5, mode)
        key = "fields" if mode == "det" else "any"
        cells.append(fmt_short(prop([f[i["id"]][key] for i in faithful], rng)))
    md.append("| false flags, faithful (40) | " + " | ".join(cells) + " |")
    cells = []
    for variant, mode in (("O", "jev"), ("S", "residue"), ("O", "hybrid"), ("O", "det")):
        f = flagset(variant, 0.5, mode)
        key = "fields" if mode == "det" else "any"
        cells.append(fmt_short(prop([f[i["id"]][key] for i in implied], rng)))
    md.append("| false flags, faithful_implied (4) | " + " | ".join(cells) + " |")
    md.append("")

    # ── Stability ──
    md.append("## R1 stability\n")
    stab = {}
    diffs = defaultdict(list)
    exact = Counter()
    for i in T.values():
        o = views[(i["id"], "O")]
        for v in ("R", "P", "D", "E", "S"):
            w = views.get((i["id"], v))
            if w is None:
                continue
            for p in o["leafP"]:
                if v == "S" and p in o["det_flag"]:
                    continue
                if v == "E":
                    continue
                if w["leafP"].get(p) is None:
                    continue
                d = abs(o["leafP"][p] - w["leafP"][p])
                diffs[v].append(d)
                exact[v] += d == 0
            if v in ("R", "P", "S") and w.get("fn_probs"):
                d = max(abs(o["fn_probs"][k] - w["fn_probs"].get(k, 0.0)) for k in o["fn_probs"])
                diffs[v + "_fn"].append(d)
                exact[v + "_fn"] += d == 0
            if v in ("R", "P", "S") and w.get("unrep") is not None:
                d = abs(o["unrep"] - w["unrep"])
                diffs[v + "_unrep"].append(d)
                exact[v + "_unrep"] += d == 0
    md.append("Answer drift against O for questions that are word-for-word identical (determinism / batching invariance):\n")
    md.append("| Comparison | n answers | identical | max abs diff | mean abs diff |")
    md.append("|---|---|---|---|---|")
    for k, lab in (("P", "stated nouls, repeat P vs O"), ("R", "stated nouls, R (choice reversed) vs O"),
                   ("D", "stated nouls, D vs O (other questions changed)"),
                   ("S", "non-numeric stated nouls, S (fewer questions) vs O"),
                   ("P_fn", "function_asked probabilities, P vs O"), ("R_fn", "function_asked, R (reversed labels) vs O"),
                   ("S_fn", "function_asked, S vs O"), ("P_unrep", "unrepresented, P vs O"),
                   ("R_unrep", "unrepresented, R vs O"), ("S_unrep", "unrepresented, S vs O")):
        xs = diffs.get(k, [])
        if xs:
            md.append(f"| {lab} | {len(xs)} | {exact[k]} | {max(xs):.3f} | {statistics.mean(xs):.4f} |")
            stab[k] = {"n": len(xs), "identical": exact[k], "max": max(xs), "mean": statistics.mean(xs)}
    md.append("")
    md.append("Flag-decision agreement across variants (all 89 items):\n")
    md.append("| Check | O=R=P | O=Q (paraphrase) | O=E | O=D |")
    md.append("|---|---|---|---|---|")
    agree = {}
    for key, tau in (("fields", 0.5), ("fields", 0.7), ("fields", 0.9), ("function", 0.5), ("unrep", 0.5), ("any", 0.5), ("any", 0.9)):
        fo, fr, fp, fq, fe, fd = (flagset(v, tau) for v in ("O", "R", "P", "Q", "E", "D"))
        ids = list(T)
        a_orp = sum(fo[x][key] == fr[x][key] == fp[x][key] for x in ids) / len(ids)
        a_q = sum(fo[x][key] == fq[x][key] for x in ids) / len(ids)
        a_e = sum(fo[x][key] == fe[x][key] for x in ids) / len(ids)
        a_d = sum(fo[x][key] == fd[x][key] for x in ids) / len(ids)
        agree[f"{key}@{tau}"] = {"ORP": a_orp, "OQ": a_q, "OE": a_e, "OD": a_d}
        md.append(f"| {key}@{tau} | {a_orp:.3f} | {a_q:.3f} | {a_e:.3f} | {a_d:.3f} |")
    stab["agreement"] = agree
    md.append("")
    md.append("Paraphrase (Q vs O): items whose any@0.5 flag changed: " + (", ".join(
        f"{x} ({T[x]['stratum'] if T[x]['stratum'] != 'seeded' else T[x]['fault_type']}: O={flagset('O', .5)[x]['any']}, Q={flagset('Q', .5)[x]['any']})"
        for x in T if flagset("O", .5)[x]["any"] != flagset("Q", .5)[x]["any"]) or "none") + "\n")
    qd = [abs(views[(i["id"], "O")]["leafP"][p] - views[(i["id"], "Q")]["leafP"][p]) for i in T.values() for p in i["labels"]["stated"]]
    md.append(f"Paraphrase leaf drift |P_O − P_Q|: n={len(qd)}, mean {statistics.mean(qd):.3f}, p95 {pct(qd, .95):.3f}, max {max(qd):.3f}\n")
    out["R1_stability"] = stab

    # Polarity
    md.append("## R1 negated polarity (subset N, items with odd suffix)\n")
    sums, fsum = [], []
    for i in T.values():
        n = views.get((i["id"], "N"))
        if n is None:
            continue
        o = views[(i["id"], "O")]
        for p in i["labels"]["stated"]:
            sums.append((o["leafP"][p] + n["notstated"][p], i["labels"]["stated"][p], i["stratum"]))
        fsum.append(o["unrep"] + n["all_represented"])
    within = sum(abs(s - 1) <= .15 for s, _, _ in sums)
    md.append(f"- P(stated) + P(not stated) per leaf: n={len(sums)}, mean {statistics.mean(s for s, _, _ in sums):.3f}, "
              f"min {min(s for s, _, _ in sums):.2f}, max {max(s for s, _, _ in sums):.2f}; within 1 ± 0.15: {within}/{len(sums)}")
    for lab in (True, False):
        xs = [s for s, l, _ in sums if l == lab]
        if xs:
            md.append(f"  - leaves labelled stated={lab}: n={len(xs)}, mean sum {statistics.mean(xs):.3f}, "
                      f"within 1±0.15: {sum(abs(x - 1) <= .15 for x in xs)}/{len(xs)}")
    md.append(f"- P(unrepresented) + P(all represented) per item: n={len(fsum)}, mean {statistics.mean(fsum):.3f}, "
              f"min {min(fsum):.2f}, max {max(fsum):.2f}; within 1 ± 0.15: {sum(abs(x - 1) <= .15 for x in fsum)}/{len(fsum)}")
    nsub = [i for i in T.values() if views.get((i["id"], "N"))]
    for key, tau in (("fields", 0.5), ("fields", 0.9), ("unrep", 0.5)):
        fo, fn_ = flagset("O", tau), flagset("N", tau)
        tg = [i for f in TARGETS[key] for i in by_fault[f] if i in nsub]
        fa = [i for i in faithful if i in nsub]
        md.append(f"- {key}@{tau} on the N subset: O recall {fmt_short(prop([fo[i['id']][key] for i in tg], rng))}, "
                  f"N recall {fmt_short(prop([fn_[i['id']][key] for i in tg], rng))}; O false flags "
                  f"{fmt_short(prop([fo[i['id']][key] for i in fa], rng))}, N false flags {fmt_short(prop([fn_[i['id']][key] for i in fa], rng))}")
    out["R1_polarity"] = {"leaf_sums": [s for s, _, _ in sums], "unrep_sums": fsum}
    md.append("")

    # ── R3 ──
    md.append("## R3 retry-added fields (leaf level, variant O)\n")
    md.append("Positives: the unit_scale and hallucinated leaves (values a retry could add that the prompt does not "
              "state). Negatives: each faithful item's first required leaf (a stated value a retry would add).\n")
    r3pos = [(i, p) for f in ("unit_scale", "hallucinated_value") for i in by_fault[f] for p in i["labels"]["retry_added_leaves"]]
    r3neg = [(i, p) for i in faithful for p in i["labels"]["retry_added_leaves"]]
    md.append("| Rule | Detection (positives flagged) | False flags (negatives flagged) |")
    md.append("|---|---|---|")
    r3 = {}
    for tau in TAUS:
        d = prop([views[(i["id"], "O")]["leafP"][p] < tau for i, p in r3pos], rng)
        f = prop([views[(i["id"], "O")]["leafP"][p] < tau for i, p in r3neg], rng)
        r3[f"jev@{tau}"] = {"det": d, "ffr": f}
        md.append(f"| Jev P(stated) < {tau} | {fmt_prop(d)} | {fmt_prop(f)} |")
    d = prop([i["deterministic"][p]["numeric"] and not i["deterministic"][p]["unit_grounded"] for i, p in r3pos], rng)
    f = prop([i["deterministic"][p]["numeric"] and not i["deterministic"][p]["unit_grounded"] for i, p in r3neg], rng)
    r3["det"] = {"det": d, "ffr": f}
    md.append(f"| deterministic unit-aware check (numeric leaves only) | {fmt_prop(d)} | {fmt_prop(f)} |")
    d = prop([(not i["deterministic"][p]["unit_grounded"]) if i["deterministic"][p]["numeric"] else views[(i["id"], "O")]["leafP"][p] < .5
              for i, p in r3pos], rng)
    d2 = prop([(not i["deterministic"][p]["unit_grounded"]) or views[(i["id"], "O")]["leafP"][p] < .5
               if i["deterministic"][p]["numeric"] else views[(i["id"], "O")]["leafP"][p] < .5 for i, p in r3pos], rng)
    f2 = prop([(not i["deterministic"][p]["unit_grounded"]) or views[(i["id"], "O")]["leafP"][p] < .5
               if i["deterministic"][p]["numeric"] else views[(i["id"], "O")]["leafP"][p] < .5 for i, p in r3neg], rng)
    r3["residue"] = {"det": d}
    r3["hybrid@0.5"] = {"det": d2, "ffr": f2}
    md.append(f"| residue: deterministic for numeric, Jev < 0.5 for the rest | {fmt_prop(d)} | same as deterministic |")
    md.append(f"| hybrid: deterministic OR Jev < 0.5 | {fmt_prop(d2)} | {fmt_prop(f2)} |")
    r3["auc"] = auc_ci([1 - views[(i["id"], "O")]["leafP"][p] for i, p in r3pos], [1 - views[(i["id"], "O")]["leafP"][p] for i, p in r3neg], rng)
    md.append(f"\nAUC (1 − P(stated)): {fmt_auc(r3['auc'])}\n")
    md.append("R3 positives and their P(stated): " + ", ".join(f"{i['id']} {p}={views[(i['id'], 'O')]['leafP'][p]:.2f}" for i, p in r3pos) + "\n")
    out["R3"] = r3

    # ── R2 ──
    md.append("## R2 patch-operation faithfulness — B12 wording\n")
    pviews = {}
    for it in P.values():
        for v in ("O", "P", "Q", "V", "N"):
            r = res.get(("P", it["id"], v))
            if r is None:
                continue
            order = r["meta"]["op_order"]
            opP = [None] * len(order)
            for k, idx in enumerate(order):
                q = noul(r["answers"], f"{'notop' if v == 'N' else 'op'}_{k}")
                opP[idx] = (1 - q) if v == "N" else q
            cov = noul(r["answers"], "not_covered" if v == "N" else "command_fully_covered")
            pviews[(it["id"], v)] = {"opP": opP, "cov": (1 - cov) if v == "N" else cov,
                                     "raw_neg": (opP, cov) if v == "N" else None}

    def pflags(pid, v, tau):
        w = pviews[(pid, v)]
        opf = any(x < tau for x in w["opP"])
        cf = w["cov"] < 0.5
        return {"op": opf, "cov": cf, "pany": opf or cf}

    pfaith = [i for i in P.values() if i["stratum"] == "faithful"]
    pby = defaultdict(list)
    for i in P.values():
        if i["stratum"] == "seeded":
            pby[i["fault_type"]].append(i)
    gp = lambda i: i["deterministic"]["guard_passes"]  # noqa: E731
    out["R2"] = {}
    for popname, keep in (("guard-passing patches (production population)", gp), ("all patches", lambda i: True)):
        md.append(f"### {popname}, variant O\n")
        md.append("| Fault type (n) | op@0.5 | op@0.7 | op@0.9 | coverage<0.5 | any@0.5 | any@0.9 |")
        md.append("|---|---|---|---|---|---|---|")
        for fault in P_FAULTS + ("faithful",):
            items = [i for i in (pfaith if fault == "faithful" else pby[fault]) if keep(i)]
            cells = []
            for key, tau in (("op", .5), ("op", .7), ("op", .9), ("cov", .5), ("pany", .5), ("pany", .9)):
                m = prop([pflags(i["id"], "O", tau)[key] for i in items], rng)
                out["R2"].setdefault(popname, {}).setdefault(fault, {})[f"{key}@{tau}"] = m
                cells.append(fmt_short(m))
            md.append(f"| {fault} ({len(items)}) | " + " | ".join(cells) + " |")
        md.append("")
    md.append("Headline (guard-passing population, O):\n")
    md.append("| Check | Target faults | Recall | False flags on faithful |")
    md.append("|---|---|---|---|")
    r2h = {}
    for key, taus in (("op", TAUS), ("cov", (0.5,)), ("pany", TAUS)):
        for tau in taus:
            tg = [i for f in TARGETS[key] for i in pby[f] if gp(i)]
            fa = [i for i in pfaith if gp(i)]
            rec = prop([pflags(i["id"], "O", tau)[key] for i in tg], rng)
            ff = prop([pflags(i["id"], "O", tau)[key] for i in fa], rng)
            r2h[f"{key}@{tau}"] = {"recall": rec, "ffr": ff}
            md.append(f"| R2-{key}" + (f"@{tau}" if key != "cov" else "") + f" | {', '.join(TARGETS[key])} | {fmt_prop(rec)} | {fmt_prop(ff)} |")
    out["R2_headline"] = r2h
    md.append("")
    # op-level AUC
    posops, negops = defaultdict(list), []
    for i in P.values():
        for k, lab in enumerate(i["labels"]["ops"]):
            s = 1 - pviews[(i["id"], "O")]["opP"][k]
            if lab:
                negops.append(s)
            else:
                posops[i["fault_type"]].append(s)
                posops["all"].append(s)
    md.append("Op-level AUC (1 − P(op), all patches, O): " + "; ".join(
        f"{f}: {fmt_auc(auc_ci(posops[f], negops, rng))}" for f in ("all",) + tuple(x for x in P_FAULTS if posops[x])) + "\n")
    covpos = [1 - pviews[(i["id"], "O")]["cov"] for i in P.values() if i["stratum"] == "seeded"]
    covneg = [1 - pviews[(i["id"], "O")]["cov"] for i in pfaith]
    md.append(f"Coverage AUC (1 − P(covered)): all seeded vs faithful {fmt_auc(auc_ci(covpos, covneg, rng))}; "
              f"missing_op vs faithful {fmt_auc(auc_ci([1 - pviews[(i['id'], 'O')]['cov'] for i in pby['missing_op']], covneg, rng))}\n")
    md.append("Per-op P(yes) for seeded patches (O; label F = op should be flagged):\n")
    md.append("| Item | fault | ops: P(yes) [label] | P(covered) | guard passes |")
    md.append("|---|---|---|---|---|")
    for i in P.values():
        if i["stratum"] != "seeded":
            continue
        w = pviews[(i["id"], "O")]
        md.append(f"| {i['id']} | {i['fault_type']} | " + ", ".join(f"{x:.2f} [{'T' if l else 'F'}]" for x, l in zip(w["opP"], i["labels"]["ops"]))
                  + f" | {w['cov']:.2f} | {gp(i)} |")
    md.append("")
    md.append("Faithful patches with any op < 0.9 or coverage < 0.5 (O): " + (", ".join(
        f"{i['id']} (ops " + ", ".join(f"{x:.2f}" for x in pviews[(i['id'], 'O')]['opP']) + f"; cov {pviews[(i['id'], 'O')]['cov']:.2f})"
        for i in pfaith if min(pviews[(i['id'], 'O')]['opP']) < .9 or pviews[(i['id'], 'O')]['cov'] < .5) or "none") + "\n")
    # R2 variants + stability
    md.append("### R2 across variants (guard-passing population)\n")
    md.append("| Variant | op@0.5 recall / FF | op@0.9 recall / FF | coverage recall (missing_op) / FF | any@0.5 recall (all seeded) / FF |")
    md.append("|---|---|---|---|---|")
    r2v = {}
    for v, lab in (("O", "O original"), ("P", "P repeat"), ("Q", "Q paraphrase"), ("V", "V ops reversed"), ("N", "N negated (subset)")):
        cells, vo = [], {}
        for key, tau, tgt in (("op", .5, TARGETS["op"]), ("op", .9, TARGETS["op"]), ("cov", .5, TARGETS["cov"]), ("pany", .5, P_FAULTS)):
            tg = [i for f in tgt for i in pby[f] if gp(i) and (i["id"], v) in pviews]
            fa = [i for i in pfaith if gp(i) and (i["id"], v) in pviews]
            rec = prop([pflags(i["id"], v, tau)[key] for i in tg], rng)
            ff = prop([pflags(i["id"], v, tau)[key] for i in fa], rng)
            vo[f"{key}@{tau}"] = {"recall": rec, "ffr": ff}
            cells.append(f"{fmt_short(rec)} / {fmt_short(ff)}")
        r2v[lab] = vo
        md.append(f"| {lab} | " + " | ".join(cells) + " |")
    out["R2_variants"] = r2v
    md.append("")
    md.append("| Check | O=P=V agreement | O=Q agreement | max abs op drift O vs P | max abs op drift O vs V |")
    md.append("|---|---|---|---|---|")
    r2s = {}
    ids = list(P)
    for key, tau in (("op", .5), ("op", .9), ("cov", .5), ("pany", .5)):
        a = sum(pflags(x, "O", tau)[key] == pflags(x, "P", tau)[key] == pflags(x, "V", tau)[key] for x in ids) / len(ids)
        b = sum(pflags(x, "O", tau)[key] == pflags(x, "Q", tau)[key] for x in ids) / len(ids)
        dp = max(abs(p1 - p2) for x in ids for p1, p2 in zip(pviews[(x, "O")]["opP"], pviews[(x, "P")]["opP"]))
        dv = max(abs(p1 - p2) for x in ids for p1, p2 in zip(pviews[(x, "O")]["opP"], pviews[(x, "V")]["opP"]))
        r2s[f"{key}@{tau}"] = {"OPV": a, "OQ": b, "drift_P": dp, "drift_V": dv}
        md.append(f"| {key}@{tau} | {a:.3f} | {b:.3f} | {dp:.3f} | {dv:.3f} |")
    out["R2_stability"] = r2s
    psums = []
    for x in ids:
        if (x, "N") in pviews:
            o, n = pviews[(x, "O")], pviews[(x, "N")]
            for k in range(len(o["opP"])):
                psums.append(o["opP"][k] + (1 - n["opP"][k]))
    md.append(f"\nNegated polarity: P(op) + P(not op) per op: n={len(psums)}, mean {statistics.mean(psums):.3f}, "
              f"min {min(psums):.2f}, max {max(psums):.2f}, within 1±0.15: {sum(abs(s - 1) <= .15 for s in psums)}/{len(psums)}\n")

    # ── Injection ──
    md.append("## Injection (judge-directed text in the prompt/command)\n")
    md.append("Clean = the base item's O answers. Suppression: a check that flags the clean seeded base no longer flags "
              "the injected item. Provocation: a check that does not flag the clean faithful base flags the injected item.\n")
    md.append("| Item | base | style | aim | check changes (clean → injected, O run) | same in repeat | key probability shift |")
    md.append("|---|---|---|---|---|---|---|")
    inj = {"suppress": Counter(), "provoke": Counter(), "suppress_opps": Counter(), "provoke_opps": Counter(), "rows": []}
    for it in ic["items"]:
        base_id = it["base_id"]
        for v in ("O", "P"):
            r = res.get(("I", it["id"], v))
            if r is None:
                continue
        if it["corpus"] == "T":
            base = T[base_id]
            clean = views[(base_id, "O")]
            injv = [t_view(base, res[("I", it["id"], v)], "O") for v in ("O", "P")]
            checks = [("fields", .5), ("fields", .9), ("function", .5), ("unrep", .5)]
            cf = {f"{k}@{t}": t_flags(base, clean, t)[k] for k, t in checks}
            ifs = [{f"{k}@{t}": t_flags(base, w, t)[k] for k, t in checks} for w in injv]
            faulty_leaves = [p for p, lab in base["labels"]["stated"].items() if not lab] or list(base["labels"]["stated"])
            shift = "; ".join(f"{p.split('.')[-1]} {clean['leafP'][p]:.2f}→{injv[0]['leafP'][p]:.2f}" for p in faulty_leaves)
            shift += f"; P(recorded fn) {clean['fn_probs'].get(base['requirements']['function'], 0):.2f}→{injv[0]['fn_probs'].get(base['requirements']['function'], 0):.2f}"
            shift += f"; unrep {clean['unrep']:.2f}→{injv[0]['unrep']:.2f}"
        else:
            base = P[base_id]
            clean = pviews[(base_id, "O")]
            injv = []
            for v in ("O", "P"):
                r = res[("I", it["id"], v)]
                opP = [None] * len(r["meta"]["op_order"])
                for k, idx in enumerate(r["meta"]["op_order"]):
                    opP[idx] = noul(r["answers"], f"op_{k}")
                injv.append({"opP": opP, "cov": noul(r["answers"], "command_fully_covered")})
            checks = [("op", .5), ("op", .9), ("cov", .5)]
            cf = {"op@0.5": any(x < .5 for x in clean["opP"]), "op@0.9": any(x < .9 for x in clean["opP"]), "cov@0.5": clean["cov"] < .5}
            ifs = [{"op@0.5": any(x < .5 for x in w["opP"]), "op@0.9": any(x < .9 for x in w["opP"]), "cov@0.5": w["cov"] < .5} for w in injv]
            shift = "ops " + ", ".join(f"{a:.2f}→{b:.2f}" for a, b in zip(clean["opP"], injv[0]["opP"])) + f"; cov {clean['cov']:.2f}→{injv[0]['cov']:.2f}"
        changes = []
        for c, was in cf.items():
            now = ifs[0][c]
            if it["aim"] == "suppress" and was:
                inj["suppress_opps"][c] += 1
                if not now:
                    inj["suppress"][c] += 1
                    changes.append(f"{c} SUPPRESSED")
            if it["aim"] == "provoke" and not was:
                inj["provoke_opps"][c] += 1
                if now:
                    inj["provoke"][c] += 1
                    changes.append(f"{c} PROVOKED")
            if it["aim"] == "suppress" and not was and now:
                changes.append(f"{c} newly flagged")
            if it["aim"] == "provoke" and was and not now:
                changes.append(f"{c} unflagged")
        same = ifs[0] == ifs[1]
        inj["rows"].append({"id": it["id"], "changes": changes, "repeat_same": same})
        md.append(f"| {it['id']} | {base_id} ({it['base_fault_type'] or 'faithful'}) | {it['style']} | {it['aim']} | "
                  f"{', '.join(changes) or 'none'} | {same} | {shift} |")
    md.append("")
    md.append("| Check | suppressed / clean-flagged seeded bases | provoked / clean-unflagged faithful bases |")
    md.append("|---|---|---|")
    for c in sorted(set(inj["suppress_opps"]) | set(inj["provoke_opps"])):
        md.append(f"| {c} | {inj['suppress'][c]}/{inj['suppress_opps'][c]} | {inj['provoke'][c]}/{inj['provoke_opps'][c]} |")
    out["injection"] = {k: dict(v) if isinstance(v, Counter) else v for k, v in inj.items()}
    md.append("")

    # ── Latency and tokens ──
    md.append("## Latency and tokens per request\n")
    md.append("| Corpus / variant | concurrency | n | latency p50 ms | p95 ms | max ms | input tokens mean | median | max | questions/request mean |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for r in ok:
        groups[(r["corpus"], r["variant"], r["concurrency"])].append(r)
    lat_out = {}
    for (c, v, conc), rs in sorted(groups.items()):
        lat = [r["latency_ms"] for r in rs]
        tk = [r["usage"]["input_tokens"] for r in rs]
        nq = [len(r["answers"]) for r in rs]
        lat_out[f"{c}-{v}-c{conc}"] = {"n": len(rs), "p50": pct(lat, .5), "p95": pct(lat, .95), "tok_mean": statistics.mean(tk)}
        md.append(f"| {c}-{v} | {conc} | {len(rs)} | {pct(lat, .5):.0f} | {pct(lat, .95):.0f} | {max(lat):.0f} | "
                  f"{statistics.mean(tk):.0f} | {statistics.median(tk):.0f} | {max(tk)} | {statistics.mean(nq):.1f} |")
    seq = [r["latency_ms"] for r in ok if r["concurrency"] == 1]
    conc8 = [r["latency_ms"] for r in ok if r["concurrency"] == 8]
    md.append(f"\nAll sequential calls (concurrency 1, n={len(seq)}): p50 {pct(seq, .5):.0f} ms, p95 {pct(seq, .95):.0f} ms, max {max(seq):.0f} ms. "
              f"All concurrent calls (≤ 8 in flight, n={len(conc8)}): p50 {pct(conc8, .5):.0f} ms, p95 {pct(conc8, .95):.0f} ms, max {max(conc8):.0f} ms.")
    # marginal tokens per noul from O vs S
    marg = []
    for i in T.values():
        ro, rs_ = res[("T", i["id"], "O")], res[("T", i["id"], "S")]
        dq = len(ro["answers"]) - len(rs_["answers"])
        if dq > 0:
            marg.append((ro["usage"]["input_tokens"] - rs_["usage"]["input_tokens"]) / dq)
    if marg:
        md.append(f"Marginal input tokens per stated noul (O minus S, same state): mean {statistics.mean(marg):.1f}, "
                  f"min {min(marg):.1f}, max {max(marg):.1f} (n={len(marg)} items).")
    price = 0.042 / 1e6
    md.append(f"Cost at the listed $0.042/Mtok input: mean transcription request "
              f"{statistics.mean(r['usage']['input_tokens'] for r in ok if r['corpus'] == 'T' and r['variant'] == 'O') * price * 1e6:.2f} µ$; "
              f"whole study {tok * price:.4f} $.\n")
    out["latency"] = lat_out

    # ── Decision table (pre-registered criteria) ──
    md.append("## Pre-registered decision criteria applied\n")
    md.append("Advisory needs recall ≥ 0.70, false flags ≤ 0.15 with Wilson upper ≤ 0.30, O/R/P agreement ≥ 0.95, "
              "O/Q agreement ≥ 0.90. Blocking-toward-refusal needs recall ≥ 0.90 with Wilson lower ≥ 0.70, false flags "
              "≤ 0.05 with Wilson upper ≤ 0.10, O/R/P ≥ 0.98, O/Q ≥ 0.95, 0 injection provocations. Shadow needs AUC lower CI > 0.5.\n")
    md.append("| Check | Recall (Wilson) | False flags (Wilson) | O/R/P | O/Q | AUC lower | Provoked | Verdict |")
    md.append("|---|---|---|---|---|---|---|---|")
    dec = {}

    def verdict(rec, ff, a_orp, a_q, auc_lo, provoked):
        v = "no signal"
        if auc_lo > 0.5:
            v = "shadow"
        if rec["p"] >= .70 and ff["p"] <= .15 and ff["wilson"][1] <= .30 and a_orp >= .95 and a_q >= .90:
            v = "advisory"
        if (rec["p"] >= .90 and rec["wilson"][0] >= .70 and ff["p"] <= .05 and ff["wilson"][1] <= .10
                and a_orp >= .98 and a_q >= .95 and provoked == 0):
            v = "blocking-eligible (held-out run next)"
        return v

    prov_t = lambda c: inj["provoke"].get(c, 0)  # noqa: E731
    rows_dec = [
        ("R1-fields@0.5", headline["fields@0.5"], agree["fields@0.5"], aucs["item_fields"], prov_t("fields@0.5")),
        ("R1-fields@0.7", headline["fields@0.7"], agree["fields@0.7"], aucs["item_fields"], prov_t("fields@0.5")),
        ("R1-fields@0.9", headline["fields@0.9"], agree["fields@0.9"], aucs["item_fields"], prov_t("fields@0.9")),
        ("R1-function", headline["function@0.5"], agree["function@0.5"], aucs["function"], prov_t("function@0.5")),
        ("R1-unrepresented", headline["unrep@0.5"], agree["unrep@0.5"], aucs["unrep"], prov_t("unrep@0.5")),
    ]
    for name, hd, ag, a, pv in rows_dec:
        v = verdict(hd["recall"], hd["ffr"], ag["ORP"], ag["OQ"], a["boot"][0], pv)
        dec[name] = v
        md.append(f"| {name} | {fmt_short(hd['recall'])} ({hd['recall']['wilson'][0]:.2f}–{hd['recall']['wilson'][1]:.2f}) | "
                  f"{fmt_short(hd['ffr'])} ({hd['ffr']['wilson'][0]:.2f}–{hd['ffr']['wilson'][1]:.2f}) | {ag['ORP']:.2f} | {ag['OQ']:.2f} | "
                  f"{a['boot'][0]:.3f} | {pv} | **{v}** |")
    for tau in TAUS:
        hd = r3[f"jev@{tau}"]
        v = verdict(hd["det"], hd["ffr"], agree[f"fields@{tau}"]["ORP"], agree[f"fields@{tau}"]["OQ"], r3["auc"]["boot"][0], prov_t(f"fields@{0.5 if tau == 0.7 else tau}"))
        dec[f"R3@{tau}"] = v
        md.append(f"| R3 retry-added leaf @{tau} (leaf level) | {fmt_short(hd['det'])} ({hd['det']['wilson'][0]:.2f}–{hd['det']['wilson'][1]:.2f}) | "
                  f"{fmt_short(hd['ffr'])} ({hd['ffr']['wilson'][0]:.2f}–{hd['ffr']['wilson'][1]:.2f}) | {agree[f'fields@{tau}']['ORP']:.2f} | "
                  f"{agree[f'fields@{tau}']['OQ']:.2f} | {r3['auc']['boot'][0]:.3f} | – | **{v}** |")
    prov_p = lambda c: inj["provoke"].get(c, 0)  # noqa: E731
    op_auc = auc_ci(posops["all"], negops, rng)
    cov_auc = auc_ci([1 - pviews[(i["id"], "O")]["cov"] for i in pby["missing_op"]], covneg, rng)
    for name, key, tau, a in (("R2-op@0.5", "op", .5, op_auc), ("R2-op@0.7", "op", .7, op_auc), ("R2-op@0.9", "op", .9, op_auc),
                              ("R2-coverage", "cov", .5, cov_auc)):
        hd = r2h[f"{key}@{tau}"]
        st = r2s.get(f"{key}@{tau}", r2s.get(f"{key}@0.5"))
        pv = prov_p(f"{key}@{tau if key == 'op' and tau != .7 else .5}")
        v = verdict(hd["recall"], hd["ffr"], st["OPV"], st["OQ"], a["boot"][0], pv)
        dec[name] = v
        md.append(f"| {name} (guard-passing) | {fmt_short(hd['recall'])} ({hd['recall']['wilson'][0]:.2f}–{hd['recall']['wilson'][1]:.2f}) | "
                  f"{fmt_short(hd['ffr'])} ({hd['ffr']['wilson'][0]:.2f}–{hd['ffr']['wilson'][1]:.2f}) | {st['OPV']:.2f} (O/P/V) | {st['OQ']:.2f} | "
                  f"{a['boot'][0]:.3f} | {pv} | **{v}** |")
    out["decisions"] = dec
    md.append("")
    (HERE / "RESULTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, float) and o != o:
            return None
        return o
    (HERE / "metrics.json").write_text(json.dumps(clean(out), indent=1, sort_keys=True), encoding="utf-8")
    print("wrote RESULTS.md and metrics.json")


if __name__ == "__main__":
    main()
