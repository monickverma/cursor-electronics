#!/usr/bin/env python3
"""
run_calibration.py — send the pre-registered battery (items.jsonl) to Jev and log every call.

    python run_calibration.py --limit 6          # pilot
    python run_calibration.py                    # everything not yet logged (resumable)

Refuses to run unless items.jsonl hashes to the pre-registered sha256. Each request is one item's
own state with its questions; variants: base, twin (precomputed or rule-in-state), repeat
(identical re-send), solo (q1 alone). Every HTTP attempt counts against the budget (SDK retries
disabled; this script retries 429/5xx/timeouts itself). Stops before exceeding 1,500 requests or
15M input tokens. A request rejected for size is split by question and the limit recorded.

Logs (append-only, next to this file):
  results.jsonl  one row per answered request: ts, request_key, item_id, variant, form,
                 model_requested, model_resolved, request_id, usage, state_sha256,
                 questions_sha256 (order-preserving), answers (full), latency_s, attempt
  errors.jsonl   one row per failed attempt (status, error class, short message; no secrets)
  budget.json    running totals
Needs TYPESAFE_API_KEY in the environment; the key is never printed or logged.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREGISTERED_SHA256 = "69a52ee5c689d37eb65cf6f59f6063937379eb446d5c862d2efc9b7cb67a86c9"
MODEL = "jev-1.13.0"
MAX_REQUESTS = 1500
MAX_INPUT_TOKENS = 15_000_000
CONCURRENCY = 8
RESULTS = HERE / "results.jsonl"
ERRORS = HERE / "errors.jsonl"
BUDGET = HERE / "budget.json"


def sha(obj):
    """Order-preserving hash: label order is part of the request (sort_keys would hide reversal)."""
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_items():
    raw = (HERE / "items.jsonl").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PREREGISTERED_SHA256:
        sys.exit(f"items.jsonl sha256 {digest} != pre-registered {PREREGISTERED_SHA256}; refusing to run")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def plan(items):
    reqs = []
    for it in items:
        base_form, twin_form = it["base_form"], it["twin_form"]
        reqs.append(dict(key=f"{it['item_id']}|base", item_id=it["item_id"], variant="base", form=base_form,
                         state=it["state"], questions=it["questions"]))
        if it["twin_state"] is not None:
            reqs.append(dict(key=f"{it['item_id']}|twin", item_id=it["item_id"], variant="twin", form=twin_form,
                             state=it["twin_state"], questions=it["questions"]))
        if it["meta"].get("repeat"):
            reqs.append(dict(key=f"{it['item_id']}|repeat", item_id=it["item_id"], variant="repeat", form=base_form,
                             state=it["state"], questions=it["questions"]))
        if it["meta"].get("solo"):
            reqs.append(dict(key=f"{it['item_id']}|solo", item_id=it["item_id"], variant="solo", form=base_form,
                             state=it["state"], questions={"q1": it["questions"]["q1"]}))
    return reqs


def done_keys():
    keys = set()
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if not row.get("split_part"):
                    keys.add(row["request_key"])
                else:
                    keys.add(row["request_key"] + f"#{row['split_part']}")
    return keys


class Ledger:
    def __init__(self):
        b = json.loads(BUDGET.read_text()) if BUDGET.exists() else {}
        self.attempts = b.get("requests_attempted", 0)
        self.ok = b.get("requests_ok", 0)
        self.inp = b.get("input_tokens", 0)
        self.out = b.get("output_tokens", 0)
        self.errors = b.get("errors", 0)
        self.size_limit_notes = b.get("size_limit_notes", [])
        self.lock = asyncio.Lock()

    def can_send(self):
        return self.attempts < MAX_REQUESTS and self.inp < MAX_INPUT_TOKENS

    def save(self):
        BUDGET.write_text(json.dumps({
            "updated": now(), "requests_attempted": self.attempts, "requests_ok": self.ok, "errors": self.errors,
            "input_tokens": self.inp, "output_tokens": self.out, "limit_requests": MAX_REQUESTS,
            "limit_input_tokens": MAX_INPUT_TOKENS, "size_limit_notes": self.size_limit_notes}, indent=2) + "\n")


def append(path, row):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def dump_answer(ans):
    d = ans.model_dump()
    return json.loads(json.dumps(d, default=str))


async def send(client, req, ledger, questions=None, split_part=None):
    from typesafe_sdk._core.errors import (TypeSafeAPIConnectionError, TypeSafeAPIError, TypeSafeRateLimitError)
    qs = questions if questions is not None else req["questions"]
    for attempt in range(1, 4):
        async with ledger.lock:
            if not ledger.can_send():
                return "budget"
            ledger.attempts += 1
            ledger.save()
        t0 = time.monotonic()
        try:
            r = await client.system_one(req["state"], qs, model=MODEL)
        except TypeSafeAPIError as e:
            status = getattr(e, "status", None)
            msg = str(e)[:300]
            async with ledger.lock:
                ledger.errors += 1
                ledger.save()
            append(ERRORS, {"ts": now(), "request_key": req["key"], "split_part": split_part, "attempt": attempt,
                            "status": status, "error": type(e).__name__, "message": msg})
            if status in (413,) or (status in (400, 422) and any(w in msg.lower() for w in ("token", "context", "too large", "length"))):
                if len(qs) > 1 and split_part is None:
                    async with ledger.lock:
                        ledger.size_limit_notes.append({"request_key": req["key"], "status": status, "message": msg})
                        ledger.save()
                    names = list(qs)
                    res = []
                    for i, n in enumerate(names, 1):
                        res.append(await send(client, req, ledger, {n: qs[n]}, split_part=f"{i}/{len(names)}"))
                    return "split"
                return "size_error"
            if isinstance(e, TypeSafeRateLimitError) or (status is not None and (status >= 500 or status == 408)):
                await asyncio.sleep([2, 5, 10][attempt - 1])
                continue
            return "error"
        except TypeSafeAPIConnectionError as e:
            async with ledger.lock:
                ledger.errors += 1
                ledger.save()
            append(ERRORS, {"ts": now(), "request_key": req["key"], "split_part": split_part, "attempt": attempt,
                            "status": None, "error": type(e).__name__, "message": str(e)[:300]})
            await asyncio.sleep([2, 5, 10][attempt - 1])
            continue
        latency = time.monotonic() - t0
        usage = r.usage.model_dump()
        row = {"ts": now(), "request_key": req["key"], "item_id": req["item_id"], "variant": req["variant"],
               "form": req["form"], "split_part": split_part, "model_requested": MODEL, "model_resolved": r.model,
               "request_id": r.request_id, "usage": usage, "state_sha256": sha(req["state"]),
               "questions_sha256": sha(qs), "question_names": list(qs),
               "answers": {k: dump_answer(v) for k, v in r.answers.items()},
               "latency_s": round(latency, 3), "attempt": attempt}
        async with ledger.lock:
            ledger.ok += 1
            ledger.inp += usage.get("input_tokens") or 0
            ledger.out += usage.get("output_tokens") or 0
            ledger.save()
        append(RESULTS, row)
        return "ok"
    return "gave_up"


async def main_async(a):
    from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy
    items = load_items()
    reqs = plan(items)
    if a.variants:
        keep = set(a.variants.split(","))
        reqs = [r for r in reqs if r["variant"] in keep]
    done = done_keys()
    todo = [r for r in reqs if r["key"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    ledger = Ledger()
    print(f"planned {len(reqs)}, already logged {len(reqs) - len([r for r in reqs if r['key'] not in done])}, "
          f"sending {len(todo)}; budget used so far {ledger.attempts} requests / {ledger.inp} input tokens")
    sem = asyncio.Semaphore(CONCURRENCY)
    outcomes = {}

    async with AsyncTypeSafeClient(retry=RetryPolicy(max_retries=0), timeout=120.0) as client:
        async def worker(req):
            async with sem:
                res = await send(client, req, ledger)
                outcomes[res] = outcomes.get(res, 0) + 1
                n = sum(outcomes.values())
                if n % 50 == 0:
                    print(f"  {n}/{len(todo)} done; attempts {ledger.attempts}, input tokens {ledger.inp}", flush=True)
        await asyncio.gather(*(worker(r) for r in todo))
    print("outcomes:", outcomes)
    print(f"budget: {ledger.attempts} requests attempted, {ledger.ok} ok, {ledger.errors} errors, "
          f"{ledger.inp} input tokens, {ledger.out} output tokens")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--variants", default="", help="comma list: base,twin,repeat,solo")
    a = ap.parse_args()
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set")
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
