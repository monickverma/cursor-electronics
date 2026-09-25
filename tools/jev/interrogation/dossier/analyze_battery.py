"""analyze_battery.py — score battery_results.jsonl against battery.json labels. Writes BATTERY_RESULTS.md.
Needles: present (answer in the dossier), absent (by construction → need_more_information), polarity pairs.
Judgment items (no ground truth): stability full vs full_rev vs core, agreement with the agent prior / reference."""
import collections, json, pathlib, statistics as st
H = pathlib.Path(__file__).resolve().parent
NMI = "need_more_information"
B = json.loads((H / "battery.json").read_text()); B = B if isinstance(B, list) else B["questions"]
Q = {q["key"]: q for q in B}
A = collections.defaultdict(dict); rows = []
for l in (H / "battery_results.jsonl").read_text().splitlines():
    r = json.loads(l); rows.append(r)
    if r.get("ok"):
        for k, a in r["answers"].items(): A[r["variant"]][k] = a
def pct(k, n): return f"{k}/{n} = {100*k/n:.0f} %" if n else "—"
out = ["# Dossier battery — results\n",
       f"The full Circuit OS dossier (`circuit_os_dossier.md`, {len((H/'circuit_os_dossier.md').read_text()):,} chars ≈ 27k tokens) or the core "
       f"dossier ({len((H/'circuit_os_dossier_core.md').read_text()):,} chars) is the state; the {len(Q)} battery questions are packed into requests "
       "up to ~31k input tokens (measured hard limit ≈ 32.9k, see results.jsonl probes). Variants: `full`, `full_rev` (option order reversed), `core`.\n"]
W = out.append
ok = [r for r in rows if r.get("ok")]
W(f"{len(rows)} requests, {len(rows)-len(ok)} errors, {sum(r['usage']['input_tokens'] for r in ok):,} input tokens, "
  f"median {st.median(r['seconds'] for r in ok):.1f} s per request.\n")
W("## A. Reading the dossier (ground truth from the text or by construction)\n")
W("| Needle kind | full | full_rev | core |\n|---|---|---|---|")
def needle_ok(q, a):
    if q["type"] == "choice": return a["argmax"] == q["gt"]
    if q["sub"] == "absent_noul": return .25 <= a["p_yes"] <= .75
    return (a["p_yes"] > .5) == q["gt"]
for sub, label in (("present", "present answer (choice)"), ("absent", "absent answer → need_more_information"),
                   ("absent_noul", "absent answer, yes/no → 0.25–0.75"), ("polarity", "polarity yes/no")):
    cells = []
    for v in ("full", "full_rev", "core"):
        qs = [q for q in B if q.get("sub") == sub and q["key"] in A[v]]
        if v == "core" and sub == "present":
            inc = [q for q in qs if q.get("in_core")]; outc = [q for q in qs if not q.get("in_core")]
            cells.append(f"in core {pct(sum(needle_ok(q, A[v][q['key']]) for q in inc), len(inc))}; "
                         f"not in core → NMI {pct(sum(A[v][q['key']]['argmax'] == NMI for q in outc), len(outc))}, still right {sum(needle_ok(q, A[v][q['key']]) for q in outc)}")
        else:
            cells.append(pct(sum(needle_ok(q, A[v][q["key"]]) for q in qs), len(qs)))
    W(f"| {label} | " + " | ".join(cells) + " |")
wrong = [(q["key"], q["gt"], A["full"][q["key"]].get("argmax", A["full"][q["key"]].get("p_yes")), q.get("section"))
         for q in B if q["category"] == "needle" and q["key"] in A["full"] and not needle_ok(q, A["full"][q["key"]])]
W(f"\nWrong on the full dossier ({len(wrong)}): " + "; ".join(f"`{k}` truth {g} → {j} ({s})" for k, g, j, s in wrong))
pairs = collections.defaultdict(dict)
for q in B:
    if q.get("sub") == "polarity" and q["key"] in A["full"]: pairs[q["pair"]][q["key"][-3:]] = A["full"][q["key"]]["p_yes"]
sums = [p["pos"] + p["neg"] for p in pairs.values() if len(p) == 2]
W(f"\nPolarity pairs (full): P(yes)+P(not) median {st.median(sums):.2f}, off by >0.15: {sum(abs(s-1)>.15 for s in sums)}/{len(sums)}.")
by_rel = collections.defaultdict(lambda: [0, 0])
for q in B:
    if q.get("sub") == "present" and q["key"] in A["full"]:
        b = min(int(q["anchor_hits"][0]["rel"] * 4), 3); by_rel[b][0] += needle_ok(q, A["full"][q["key"]]); by_rel[b][1] += 1
W("Present-answer accuracy by position of the answer in the 94 KB file: " + ", ".join(f"{25*b}–{25*b+25} %: {pct(*by_rel[b])}" for b in sorted(by_rel)))

W("\n## B/C. Judgment questions (no ground truth; stability and agreement)\n")
W("| Category | n | same answer full/full_rev/core | full = full_rev | agrees with reference (where one exists) | agrees with agent prior | median p_top (full) | picks need_more_information (full) |\n|---|---|---|---|---|---|---|---|")
cats = collections.defaultdict(list)
for q in B:
    if q["category"] != "needle": cats[q["category"]].append(q)
unstable = []
for c, qs in cats.items():
    s3 = s2 = rf = rn = pr = pn = nmi = 0; pts = []
    for q in qs:
        vals = [A[v].get(q["key"]) for v in ("full", "full_rev", "core")]
        if any(x is None for x in vals): continue
        key = (lambda a: a["argmax"]) if q["type"] == "choice" else ((lambda a: a["p_yes"] > .5) if q["type"] == "noul" else (lambda a: round(a["score"])))
        ks = [key(x) for x in vals]
        s3 += len(set(ks)) == 1; s2 += ks[0] == ks[1]
        if len(set(ks[:2])) > 1: unstable.append((q["key"], ks))
        if q.get("ref") is not None: rn += 1; rf += str(ks[0]) == str(q["ref"])
        if q.get("prior") is not None: pn += 1; pr += str(ks[0]) == str(q["prior"])
        if q["type"] == "choice": pts.append(vals[0]["p_top"]); nmi += ks[0] == NMI
    W(f"| {c} | {len(qs)} | {pct(s3, len(qs))} | {pct(s2, len(qs))} | {pct(rf, rn)} | {pct(pr, pn)} | {st.median(pts) if pts else float('nan'):.2f} | {nmi} |")
W(f"\nJudgment questions whose answer flipped just from reversing option order ({len(unstable)}): " + "; ".join(f"`{k}` {v[0]}→{v[1]}" for k, v in unstable))
(H / "BATTERY_RESULTS.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
