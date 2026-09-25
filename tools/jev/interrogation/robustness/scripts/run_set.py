"""run_set.py - send every request of a pre-registered item set to Jev and log each call.

Usage: python run_set.py ../items/E3_order.json [--concurrency 8] [--model jev-1.13.0]
                         [--tag later] [--only ITEM,ITEM] [--skip-done]
The file's sha256 must match items/PREREGISTRATION.tsv. Each call is logged by jevlog (one row
per HTTP request) with experiment = the file's `experiment` field and variant = request variant
(+ ':' + tag when --tag is given).
"""
import argparse
import asyncio
import json
import pathlib
import sys

import jevlog


async def main(a):
    path = pathlib.Path(a.items).resolve()
    jevlog.verify_prereg(path)
    d = json.loads(path.read_text(encoding="utf-8"))
    exp = d["experiment"]
    reqs = d["requests"]
    if a.only:
        keep = set(a.only.split(","))
        reqs = [r for r in reqs if r["item_id"] in keep]
    done = set()
    if a.skip_done:
        for r in jevlog.load_rows(exp):
            if not r.get("error"):
                done.add((r["item_id"], r["variant"], r["payload_sha256"]))
    todo = []
    for r in reqs:
        variant = r["variant"] + (f":{a.tag}" if a.tag else "")
        payload = {"state": r["state"], "model": a.model, "questions": r["questions"]}
        if (r["item_id"], variant, jevlog.sha(payload)) in done:
            continue
        todo.append((r, variant))
    print(f"{exp}: {len(todo)} requests to send (of {len(reqs)})", flush=True)
    errors = 0
    async with jevlog.Jev(concurrency=a.concurrency) as j:
        async def one(r, variant):
            nonlocal errors
            row = await j.ask(exp, variant, r["item_id"], r["state"], r["questions"], model=a.model,
                              extra={"items_file": path.name})
            if row["error"]:
                errors += 1
                print("ERROR", r["item_id"], variant, row["error"]["type"], row["error"]["status"],
                      str(row["error"]["body"])[:200], flush=True)
            return row
        try:
            await asyncio.gather(*(one(r, v) for r, v in todo))
        except jevlog.BudgetExceeded as e:
            print("BUDGET STOP:", e)
            sys.exit(2)
        print(f"{exp}: sent {len(todo)}, errors {errors}; budget now {j.budget.requests} requests, "
              f"{j.budget.input_tokens} input tokens", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("items")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--model", default=jevlog.PINNED)
    ap.add_argument("--tag", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-done", action="store_true")
    asyncio.run(main(ap.parse_args()))
