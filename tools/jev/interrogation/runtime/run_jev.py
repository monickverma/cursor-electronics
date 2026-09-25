"""Send the planned requests to Jev and log every call. Never prints or writes the API key.

    python run_jev.py --dry-run                       # build and validate the plan, no network
    python run_jev.py --corpus T --variants O R       # concurrency 8 (default)
    python run_jev.py --corpus T --variants P --concurrency 1   # sequential, for latency

Appends one JSON line per call to results.jsonl: ts, corpus, item_id, variant, model_requested,
model_resolved, request_id, usage, state_sha256, questions_sha256, answers (full wire answers),
latency_ms, concurrency, error. Resumable: a (corpus, item, variant) with a successful row is
skipped. Budget guard: stops before exceeding MAX_REQUESTS requests or MAX_INPUT_TOKENS input
tokens counted over every row already in results.jsonl.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import os
import pathlib
import sys
import time

from questions import build_all

HERE = pathlib.Path(__file__).resolve().parent
LOG = HERE / "results.jsonl"
MODEL = "jev-1.13.0"
MAX_REQUESTS = 1500
MAX_INPUT_TOKENS = 15_000_000
TIMEOUT_S = 60.0


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_log():
    rows = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def totals(rows):
    n = len(rows)
    tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in rows)
    return n, tok


def load_corpora():
    tc = json.loads((HERE / "corpus_transcription.json").read_text(encoding="utf-8"))
    pc = json.loads((HERE / "corpus_patch.json").read_text(encoding="utf-8"))
    ic = json.loads((HERE / "corpus_injection.json").read_text(encoding="utf-8"))
    return tc, pc, ic


def validate(plan):
    from typesafe_sdk._schemas.models import SystemOneRequest
    for p in plan:
        SystemOneRequest.model_validate({"state": p["state"], "model": MODEL, "questions": p["questions"]})
        assert "TYPESAFE" not in json.dumps(p["state"]) and "sk-" not in json.dumps(p["state"])


class Budget:
    def __init__(self, rows):
        self.n, self.tok = totals(rows)
        self.lock = asyncio.Lock()
        self.stopped = False

    async def reserve(self):
        async with self.lock:
            if self.stopped or self.n + 1 > MAX_REQUESTS or self.tok > MAX_INPUT_TOKENS:
                self.stopped = True
                return False
            self.n += 1
            return True

    async def add_tokens(self, t):
        async with self.lock:
            self.tok += t or 0
            if self.tok > MAX_INPUT_TOKENS:
                self.stopped = True


async def run(plan, concurrency):
    from typesafe_sdk import AsyncTypeSafeClient
    rows = load_log()
    budget = Budget(rows)
    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    done = {"ok": 0, "err": 0, "skipped_budget": 0}

    async with AsyncTypeSafeClient(timeout=TIMEOUT_S) as client:
        async def one(p):
            async with sem:
                if not await budget.reserve():
                    done["skipped_budget"] += 1
                    return
                row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "corpus": p["corpus"],
                       "item_id": p["item_id"], "variant": p["variant"], "model_requested": MODEL,
                       "state_sha256": sha(p["state"]), "questions_sha256": sha(p["questions"]),
                       "meta": p["meta"], "concurrency": concurrency}
                t0 = time.perf_counter()
                try:
                    r = await client.system_one(p["state"], p["questions"], model=MODEL)
                    row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    row["model_resolved"] = r.model
                    row["request_id"] = r.request_id
                    row["usage"] = r.usage.model_dump()
                    row["answers"] = {k: v.model_dump(mode="json") for k, v in r.answers.items()}
                    row["error"] = None
                    await budget.add_tokens(row["usage"].get("input_tokens"))
                    done["ok"] += 1
                except Exception as exc:  # noqa: BLE001 - logged, counted, never fatal
                    row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    row["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                    row["answers"] = None
                    done["err"] += 1
                async with write_lock:
                    with LOG.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")

        await asyncio.gather(*(one(p) for p in plan))
    n, tok = budget.n, budget.tok
    print(json.dumps({**done, "running_total_requests": n, "running_total_input_tokens": tok,
                      "budget_stopped": budget.stopped}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", nargs="*", default=["T", "P", "I"])
    ap.add_argument("--variants", nargs="*", default=None)
    ap.add_argument("--items", nargs="*", default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    assert 1 <= a.concurrency <= 8, "concurrency must be 1..8"
    tc, pc, ic = load_corpora()
    plan = build_all(tc, pc, ic)
    validate(plan)
    sel = [p for p in plan if p["corpus"] in a.corpus and (a.variants is None or p["variant"] in a.variants)
           and (a.items is None or p["item_id"] in a.items)]
    have = {(r["corpus"], r["item_id"], r["variant"]) for r in load_log() if not r.get("error")}
    todo = [p for p in sel if (p["corpus"], p["item_id"], p["variant"]) not in have]
    if a.limit:
        todo = todo[: a.limit]
    n, tok = totals(load_log())
    print(f"plan {len(plan)} total; selected {len(sel)}; to run {len(todo)}; "
          f"logged so far {n} requests / {tok} input tokens")
    if a.dry_run:
        from collections import Counter
        print(Counter((p["corpus"], p["variant"]) for p in plan))
        return
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY is not set")
    asyncio.run(run(todo, a.concurrency))


if __name__ == "__main__":
    main()
