"""tools/jev/run.py — run one Jev decision request in counterbalanced variants and band it.

Usage (from the repo root):
    python tools/jev/run.py tools/jev/requests/rs485_de_re_pulldown.json [--repeats 2] [--blind]
    python tools/jev/run.py tools/jev/requests/*.json --dry-run      # validate only, no network

Needs `pip install typesafe-sdk==0.7.1` and TYPESAFE_API_KEY in the environment.
Appends every variant to <request>.results.jsonl next to the request file. Never edits code
or decisions.md: the decision entry links the request and results files instead.

Protocol (see reports/Jev decisions for Circuit OS Phase 3.md, "A stability-gated protocol"):
bands are computed from top probability, margin to the runner-up and stability across variants.
`confidence` is logged but never thresholded: it is (k*p_top - 1)/(k - 1) and moves with the
number of options.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import sys

PINNED_MODEL = "jev-1.13.0"  # pinned; the model string the server returns is logged too
ABSTAIN = "need_more_information"
PLACEHOLDERS = ("<PASTE", "<VERIFY", "<CONFIRM")


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def reversed_labels(questions):
    out = {}
    for name, q in questions.items():
        q = dict(q)
        if q["type"] == "choice":
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
        out[name] = q
    return out


def signals(ans):
    if ans.type == "choice":
        probs = {str(k): v for k, v in ans.probabilities.items()}
        p = sorted(probs.values(), reverse=True)
        return {"type": "choice", "argmax": ans.choice, "k": len(p), "p_top": p[0],
                "margin": p[0] - (p[1] if len(p) > 1 else 0.0),
                "p_abstain": probs.get(ABSTAIN, 0.0),
                "live_options": sum(v >= 0.05 for v in p), "probabilities": probs,
                "confidence_raw_do_not_threshold": ans.confidence}
    if ans.type == "noul":
        return {"type": "noul", "p_yes": ans.noul}
    return {"type": "score", "score": ans.score,
            "probabilities": {str(k): v for k, v in ans.probabilities.items()},
            "confidence_raw_do_not_threshold": ans.confidence}


def band(rows, agent_agrees):
    stable = len({r["argmax"] for r in rows}) == 1
    p_min = min(r["p_top"] for r in rows)
    m_min = min(r["margin"] for r in rows)
    abst = max(r["p_abstain"] for r in rows)
    top = rows[0]["argmax"]
    if stable and p_min >= .90 and m_min >= .60 and abst < .05 and agent_agrees:
        return "act"
    if stable and p_min >= .60 and m_min >= .25 and abst < .20 and top != ABSTAIN and agent_agrees:
        return "care"
    return "owner"


def variants_for(req, path, repeats, blind):
    para = path.with_name(path.stem + ".paraphrase.json")  # state rewritten by a second author
    out = [("original", req["state"], req["questions"]),
           ("reversed", req["state"], reversed_labels(req["questions"]))]
    if para.exists():
        out.append(("paraphrase", json.loads(para.read_text(encoding="utf-8")), req["questions"]))
    out += [(f"repeat{i}", req["state"], req["questions"]) for i in range(repeats)]
    if blind:
        out.append(("blind", "No context is given. Judge from the options alone.", req["questions"]))
    return out


def check_request(req, path, allow_placeholders):
    from typesafe_sdk._schemas.models import SystemOneRequest
    SystemOneRequest.model_validate({"state": req["state"], "model": PINNED_MODEL,
                                     "questions": req["questions"]})
    governing = req["governing"] if isinstance(req["governing"], list) else [req["governing"]]
    for g in governing:
        assert req["questions"][g]["type"] == "choice", f"{path.name}: governing {g} must be a choice"
    for yes, no in req.get("polarity_pairs", []):
        assert yes in req["questions"] and no in req["questions"], f"{path.name}: bad polarity pair"
    blob = json.dumps(req["state"])
    holes = [p for p in PLACEHOLDERS if p in blob]
    if holes and not allow_placeholders:
        raise SystemExit(f"{path.name}: state still has {holes} slots. Fill them in (or pass "
                         "--allow-placeholders to run anyway and say so in the decision entry).")
    return governing


def run_one(path, a):
    req = json.loads(path.read_text(encoding="utf-8"))
    governing = check_request(req, path, a.allow_placeholders or a.dry_run)
    variants = variants_for(req, path, a.repeats, a.blind)
    if a.dry_run:
        print(f"OK  {path.name}: {len(req['questions'])} questions, governing {governing}, "
              f"{len(variants)} variants, state {len(json.dumps(req['state']))} chars")
        return
    from typesafe_sdk import TypeSafeClient
    log = path.with_name(path.stem + ".results.jsonl")
    per_variant = []
    with TypeSafeClient() as client:
        for name, state, qs in variants:
            r = client.system_one(state, qs, model=PINNED_MODEL)
            row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "decision_id": req["decision_id"], "attempt_n": req.get("attempt_n", 1),
                   "variant": name, "model_requested": PINNED_MODEL, "model_resolved": r.model,
                   "request_id": r.request_id, "usage": r.usage.model_dump(),
                   "state_sha256": sha(state), "questions_sha256": sha(qs),
                   "answers": {k: signals(v) for k, v in r.answers.items()}}
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            if name != "blind":
                per_variant.append(row["answers"])
    print(f"\n=== {req['decision_id']} (attempt {req.get('attempt_n', 1)}) -> {log.name}")
    for yes, no in req.get("polarity_pairs", []):
        sums = [v[yes]["p_yes"] + v[no]["p_yes"] for v in per_variant]
        print(f"polarity {yes}/{no}: sums {['%.2f' % s for s in sums]}",
              "INCOHERENT" if any(abs(s - 1) > .15 for s in sums) else "ok")
    for name in req["questions"]:
        vals = [v[name] for v in per_variant]
        if vals[0]["type"] == "noul":
            ps = [x["p_yes"] for x in vals]
            verdict = "decisive" if all(p >= .9 for p in ps) or all(p <= .1 for p in ps) else "unsettled"
            print(f"noul  {name}: {['%.2f' % p for p in ps]} {verdict}")
        elif vals[0]["type"] == "score":
            print(f"score {name}: {['%.2f' % x['score'] for x in vals]}")
    prior = req.get("agent_prior_agrees_with") or {}
    for g in governing:
        rows = [v[g] for v in per_variant]
        want = prior.get(g) if isinstance(prior, dict) else prior
        b = band(rows, want is not None and want in {r["argmax"] for r in rows})
        if req.get("owner_owned") or req.get("door") == "one_way":
            b = f"{b} -> owner decides (recommendation only)"
        print(json.dumps({"governing": g, "argmax_per_variant": [r["argmax"] for r in rows],
                          "p_top_min": min(r["p_top"] for r in rows),
                          "margin_min": min(r["margin"] for r in rows),
                          "p_abstain_max": max(r["p_abstain"] for r in rows),
                          "prior": want, "band": b}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("requests", nargs="+")
    ap.add_argument("--repeats", type=int, default=0)
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="validate against the SDK schema; no network")
    ap.add_argument("--allow-placeholders", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set in this shell.")
    for p in a.requests:
        run_one(pathlib.Path(p), a)


if __name__ == "__main__":
    main()
