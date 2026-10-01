"""
The LED part decision, re-run under the stability-gated protocol the engineer's own research proposes
("Jev decisions for Circuit OS Phase 3", §"A stability-gated protocol replaces the 0.5/0.9 confidence
bands"): three variants (original, options reversed, neutral state), signals computed from probabilities —
never from `confidence` — and the agent's independent analysis written before the calls.

Usage:  python tools/jev/2026-10-02_led_part.py        (needs TYPESAFE_API_KEY; writes the .results.jsonl beside it)

Tools compute, Jev weighs: every number in the state was computed or read from a document first
(brain/decisions.md [2026-10-02] "The LED part").
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUEST = HERE / "2026-10-02_led_part.json"
RESULTS = HERE / "2026-10-02_led_part.results.jsonl"
MODEL = "jev-1.13.0"   # pinned: the build the first two attempts returned

#: Written before any variant was sent (2026-10-02), as the protocol asks.
AGENT_PRIOR = {
    "led_part": ("wurth_150080rs75000 — stocked at Mouser, same typical and maximum V_F as the catalogue, so no "
                 "R1 choice changes; the documented-minimum part cannot be bought or priced"),
    "vf_minimum": ("1_6_symmetric — computed to cost no reach versus 1.7 V, and more conservative; nothing in "
                   "any document read supports a value under 1.6 V for a red AlGaInP LED at 20 mA"),
}


def load_request() -> dict:
    return json.loads(REQUEST.read_text(encoding="utf-8"))


def reversed_options(request: dict) -> dict:
    out = copy.deepcopy(request)
    for q in out["questions"].values():
        if q["type"] == "choice":
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
    return out


def neutral_state(request: dict) -> dict:
    """The state without the agent's framing: no earlier answers, no 'tension' — facts only."""
    out = copy.deepcopy(request)
    follow = out["state"].get("follow_up", {})
    follow.pop("your_first_answers", None)
    follow.pop("the_tension", None)
    return out


def call(request: dict, key: str) -> tuple[dict, str]:
    body = json.dumps(request, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode()), resp.headers.get("x-typesafe-request-id", "")


def signals(answers_by_variant: dict) -> dict:
    out = {}
    names = next(iter(answers_by_variant.values())).keys()
    for name in names:
        rows = [a[name] for a in answers_by_variant.values()]
        if rows[0]["type"] == "choice":
            tops, margins, argmaxes, nmi = [], [], [], []
            for r in rows:
                p = sorted(r["probabilities"].values(), reverse=True)
                tops.append(p[0])
                margins.append(p[0] - (p[1] if len(p) > 1 else 0.0))
                argmaxes.append(max(r["probabilities"], key=r["probabilities"].get))
                nmi.append(r["probabilities"].get("none_of_these", 0.0))
            out[name] = {"k": len(rows[0]["probabilities"]), "argmax": argmaxes,
                         "argmax_stable": len(set(argmaxes)) == 1, "min_p_top": round(min(tops), 3),
                         "min_margin": round(min(margins), 3), "max_need_more_information": round(max(nmi), 3)}
        else:
            vals = [r["noul"] for r in rows]
            out[name] = {"noul": vals, "reading": "decisive" if all(v >= 0.9 for v in vals) or
                         all(v <= 0.1 for v in vals) else "unsettled"}
    return out


def band(s: dict) -> str:
    if not s.get("argmax_stable"):
        return "owner_decides"
    if s["min_p_top"] >= 0.90 and s["min_margin"] >= 0.60 and s["max_need_more_information"] < 0.05:
        return "act"
    if (s["min_p_top"] >= 0.60 and s["min_margin"] >= 0.25 and s["max_need_more_information"] < 0.20
            and s["argmax"][0] != "none_of_these"):
        return "act_with_care"
    return "owner_decides"


def main() -> None:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
                key = str(winreg.QueryValueEx(reg, "TYPESAFE_API_KEY")[0]).strip()
        except OSError:
            pass
    if not key:
        sys.exit("TYPESAFE_API_KEY is not set")
    base = load_request()
    base["model"] = MODEL
    variants = {"original": base, "options_reversed": reversed_options(base), "neutral_state": neutral_state(base)}
    answers = {}
    with RESULTS.open("a", encoding="utf-8") as log:
        for name, request in variants.items():
            response, request_id = call(request, key)
            answers[name] = response["answers"]
            log.write(json.dumps({
                "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "variant": name, "requested_model": MODEL, "returned_model": response.get("model"),
                "request_id": request_id,
                "state_sha256": hashlib.sha256(json.dumps(request["state"], sort_keys=True,
                                                          ensure_ascii=False).encode()).hexdigest(),
                "answers": response["answers"], "usage": response.get("usage")}, ensure_ascii=False) + "\n")
        s = signals(answers)
        summary = {"summary": True, "agent_prior": AGENT_PRIOR, "signals": s,
                   "bands": {n: band(v) for n, v in s.items() if "argmax" in v}}
        log.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
