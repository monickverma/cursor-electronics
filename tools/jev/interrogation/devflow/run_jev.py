"""Run the pre-registered devflow plan against Jev (TypeSafe) and log every call to results.jsonl.

  python run_jev.py --dry-run                 # validate every request offline (no network), print plan size
  python run_jev.py --tasks T2 T4             # run those tasks (resumes: skips calls already logged OK)

Budget: at most 1,500 requests and 15,000,000 input tokens across ALL runs (read back from results.jsonl);
a call is reserved before it is sent, so concurrency cannot overshoot. At most 8 requests in flight.
The API key is read by the SDK from TYPESAFE_API_KEY and is never printed or logged.
"""
import argparse
import asyncio
import datetime
import json
import os
import sys
import time

from common import HERE, PINNED_MODEL, SETS, read_jsonl, secret_findings, sha_obj
from questions import questions_for

RESULTS = HERE / "results.jsonl"
MAX_REQUESTS = 1500
MAX_INPUT_TOKENS = 15_000_000
CONCURRENCY = 8

SET_FILES = {"T1": "t1_entry_covers.jsonl", "T2": "t2_failure_class.jsonl", "T3": "t3_doc_drift.jsonl",
             "Q": "q_entry_quality.jsonl", "T4": "t4_owner_attention.jsonl", "CONV": "conv_commit_subjects.jsonl"}
BLIND_STATE = "No artifact is given."


def plan():
    """Every request of the pre-registered design, in a fixed order."""
    reqs = []
    for task, fname in SET_FILES.items():
        items = read_jsonl(SETS / fname)
        for it in items:
            for v in ("orig", "rev", "rep"):
                reqs.append({"task": task, "item_id": it["item_id"], "variant": v, "state": it["state"],
                             "questions": questions_for(task, v)})
        if task == "T1":
            for it in [i for i in items if i["stratum"] == "match"]:
                st = {"commit": it["state"]["commit"], "decision_entry": "(no entry was provided)"}
                reqs.append({"task": task, "item_id": it["item_id"], "variant": "blind_partial", "state": st,
                             "questions": questions_for(task, "blind_partial")})
                reqs.append({"task": task, "item_id": it["item_id"], "variant": "unpacked_template",
                             "state": it["state"], "questions": questions_for(task, "unpacked_template")})
        if task == "T3":
            chosen = [i for i in items if i["type"] == "real"] + [i for i in items if i["type"] == "dated"][:3]
            for it in chosen:
                st = {**it["state"], "derived_facts": {}}
                reqs.append({"task": task, "item_id": it["item_id"], "variant": "blind_partial", "state": st,
                             "questions": questions_for(task, "blind_partial")})
        reqs.append({"task": task, "item_id": f"{task}-BLIND", "variant": "blind", "state": BLIND_STATE,
                     "questions": questions_for(task, "blind")})
    for r in reqs:
        r["key"] = f"{r['task']}|{r['item_id']}|{r['variant']}"
        r["state_sha256"] = sha_obj(r["state"])
        r["questions_sha256"] = sha_obj(r["questions"])
    return reqs


def plan_digest(reqs):
    return sha_obj([[r["key"], r["state_sha256"], r["questions_sha256"]] for r in reqs])


def validate(reqs):
    from typesafe_sdk._schemas.models import SystemOneRequest
    for r in reqs:
        SystemOneRequest.model_validate({"state": r["state"], "model": PINNED_MODEL, "questions": r["questions"]})
        hits = secret_findings(r["state"]) + secret_findings(r["questions"])
        assert not hits, (r["key"], hits)
    return True


def logged():
    if not RESULTS.exists():
        return [], 0, 0
    rows = read_jsonl(RESULTS)
    n_req = len(rows)
    tokens = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in rows)
    return rows, n_req, tokens


def dump_answer(a):
    d = a.model_dump() if hasattr(a, "model_dump") else dict(a)
    return json.loads(json.dumps(d, default=str))


async def run(tasks, limit):
    from typesafe_sdk import AsyncTypeSafeClient
    reqs = [r for r in plan() if r["task"] in tasks]
    rows, n_req, tokens = logged()
    done_ok = {r["key"] for r in rows if not r.get("error")}
    todo = [r for r in reqs if r["key"] not in done_ok]
    if limit:
        todo = todo[:limit]
    print(f"plan {len(reqs)} for {tasks}; already OK {len(reqs) - len([r for r in reqs if r['key'] not in done_ok])}; "
          f"to send {len(todo)}; budget used {n_req} req / {tokens} tok", flush=True)
    state = {"reserved": n_req, "tokens": tokens, "sent": 0, "errors": 0}
    sem = asyncio.Semaphore(CONCURRENCY)
    lock = asyncio.Lock()

    async def one(client, r):
        async with sem:
            async with lock:
                est = len(json.dumps(r["state"])) // 3 + len(json.dumps(r["questions"])) // 3
                if state["reserved"] + 1 > MAX_REQUESTS or state["tokens"] + est > MAX_INPUT_TOKENS:
                    return "budget"
                state["reserved"] += 1
            t0 = time.perf_counter()
            row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "task": r["task"],
                   "item_id": r["item_id"], "variant": r["variant"], "key": r["key"],
                   "model_requested": PINNED_MODEL, "state_sha256": r["state_sha256"],
                   "questions_sha256": r["questions_sha256"]}
            try:
                resp = await client.system_one(r["state"], r["questions"], model=PINNED_MODEL, timeout=60)
                row.update({"model_resolved": resp.model, "request_id": getattr(resp, "request_id", None),
                            "usage": resp.usage.model_dump(),
                            "answers": {k: dump_answer(v) for k, v in resp.answers.items()}})
            except Exception as e:  # logged, never retried here beyond the SDK's own policy
                msg = str(e)
                key = os.environ.get("TYPESAFE_API_KEY", "")
                if key:
                    msg = msg.replace(key, "<redacted>")
                row.update({"error": type(e).__name__, "error_message": msg[:500],
                            "request_id": getattr(e, "request_id", None)})
            row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            async with lock:
                state["tokens"] += (row.get("usage") or {}).get("input_tokens") or 0
                state["sent"] += 1
                state["errors"] += bool(row.get("error"))
                with RESULTS.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if state["sent"] % 50 == 0:
                    print(f"  sent {state['sent']}/{len(todo)} errors {state['errors']} "
                          f"budget {state['reserved']} req {state['tokens']} tok", flush=True)
            return "error" if row.get("error") else "ok"

    async with AsyncTypeSafeClient() as client:
        results = await asyncio.gather(*(one(client, r) for r in todo))
    print(f"done: ok {results.count('ok')} error {results.count('error')} skipped_for_budget "
          f"{results.count('budget')}; totals {state['reserved']} requests, {state['tokens']} input tokens", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=list(SET_FILES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    reqs = plan()
    if a.dry_run:
        validate(reqs)
        from collections import Counter
        est = sum(len(json.dumps(r["state"])) // 3 + len(json.dumps(r["questions"])) // 3 for r in reqs)
        print(json.dumps({"requests": len(reqs), "by_task": Counter(r["task"] for r in reqs),
                          "by_variant": Counter(r["variant"] for r in reqs), "est_input_tokens_upper": est,
                          "plan_sha256": plan_digest(reqs)}, indent=1))
        return
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        sys.exit("TYPESAFE_API_KEY is not set.")
    asyncio.run(run(a.tasks, a.limit))


if __name__ == "__main__":
    main()
