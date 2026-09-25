"""run_battery.py — send battery.json against the dossier in token-bounded chunks; log to battery_results.jsonl.

Variants: full (original option order), full_rev (reversed option order), core (25 KB core dossier).
Request limit measured at ~32.9k input tokens, so each request packs questions up to LIMIT tokens.
"""
import asyncio, json, pathlib, sys
from jevcall import call, make_client, Budget
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "battery_results.jsonl"
LIMIT = 31000
CPT = 3.4
B = json.loads((HERE / "battery.json").read_text(encoding="utf-8"))
QS = B if isinstance(B, list) else B["questions"]
DOC = {"full": (HERE / "circuit_os_dossier.md").read_text(encoding="utf-8"),
       "core": (HERE / "circuit_os_dossier_core.md").read_text(encoding="utf-8")}

def rev(q):
    q = dict(q)
    if q["type"] == "choice":
        q["criteria"] = dict(reversed(list(q["criteria"].items())))
    return q

def chunks(state, rows, transform):
    room = LIMIT - len(state) / CPT - 300
    cur, used = {}, 0
    for r in rows:
        q = transform(r["q"]); t = len(json.dumps(q)) / CPT + 40
        if cur and used + t > room:
            yield cur; cur, used = {}, 0
        cur[r["key"]] = q; used += t
    if cur:
        yield cur

async def main():
    done = set()
    if OUT.exists():
        for l in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if r.get("ok"):
                done |= {(r["variant"], k) for k in r["answers"]}
    plan = [("full", DOC["full"], QS, lambda q: q), ("full_rev", DOC["full"], QS, rev),
            ("core", DOC["core"], QS, lambda q: q)]
    client = make_client(); sem = asyncio.Semaphore(6); budget = Budget(chars_per_token=CPT)
    jobs = []
    for name, state, rows, tf in plan:
        todo = [r for r in rows if (name, r["key"]) not in done]
        for qs in chunks(state, todo, tf):
            jobs.append(call(client, sem, budget, state, qs, phase="battery", variant=name, log_path=OUT))
    print(len(jobs), "requests")
    rows = await asyncio.gather(*jobs)
    print("errors", sum(not r["ok"] for r in rows), [r.get("error", "")[:120] for r in rows if not r["ok"]][:3])

asyncio.run(main())
