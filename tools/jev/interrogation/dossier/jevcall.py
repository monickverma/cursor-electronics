"""jevcall.py — the one path every Jev call in this study goes through.

Every call (probe, battery, variant, control) is appended to results.jsonl with:
ts, phase, variant, model_requested, model_resolved, request_id, usage, state_sha256,
questions_sha256, full answers (raw model_dump) and derived signals (argmax, p_top, margin,
p_abstain). Failed/rejected calls are logged too (status, message), and counted against the
budget with an estimated token count.

Budget (hard stop, checked before every call): <= 1,500 requests and <= 15,000,000 input tokens
for this track. Concurrency <= 8 (semaphore). SDK retries are disabled so every attempt is counted.

The API key is read by the SDK from TYPESAFE_API_KEY. It is never printed, logged or written.
"""
import asyncio
import datetime
import hashlib
import json
import pathlib
import re
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results.jsonl"
LEDGER = HERE / "budget_ledger.json"
PINNED_MODEL = "jev-1.13.0"
ABSTAIN = "need_more_information"
MAX_REQUESTS = 1500
MAX_INPUT_TOKENS = 15_000_000
MAX_CONCURRENCY = 8

# Anything that looks like a credential or contact detail must never reach Jev.
SECRET_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),   # email addresses
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),                               # API-key shaped strings
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)TYPESAFE_API_KEY\s*="),
    re.compile(r"(?i)postgres(ql)?(\+asyncpg)?://[^\s:]+:[^\s@]+@"),   # DSN with inline password
    re.compile(r"TestPass\w*"),                                        # the project's test-account password
    re.compile(r"(?i)c:[\\/]+users[\\/]+[A-Za-z0-9_.-]+"),              # Windows user-profile paths
]


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def secret_hits(obj):
    blob = json.dumps(obj, ensure_ascii=False)
    hits = []
    for p in SECRET_PATTERNS:
        for m in p.finditer(blob):
            hits.append(m.group(0)[:40])
    return hits


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"requests": 0, "input_tokens": 0, "failed_requests": 0, "estimated_tokens_failed": 0}


def save_ledger(led):
    LEDGER.write_text(json.dumps(led, indent=2))


def signals(ans):
    t = ans.type
    if t == "choice":
        probs = {str(k): float(v) for k, v in ans.probabilities.items()}
        p = sorted(probs.values(), reverse=True)
        return {"type": "choice", "argmax": ans.choice, "k": len(p), "p_top": p[0],
                "margin": p[0] - (p[1] if len(p) > 1 else 0.0),
                "p_abstain": probs.get(ABSTAIN, 0.0),
                "live_options": sum(v >= 0.05 for v in p), "probabilities": probs,
                "confidence_raw_do_not_threshold": float(ans.confidence)}
    if t == "noul":
        return {"type": "noul", "p_yes": float(ans.noul)}
    return {"type": "score", "score": float(ans.score),
            "probabilities": {str(k): float(v) for k, v in ans.probabilities.items()},
            "confidence_raw_do_not_threshold": float(ans.confidence)}


class Budget:
    def __init__(self, chars_per_token=3.0):
        self.lock = asyncio.Lock()
        self.cpt = chars_per_token

    async def reserve(self, est_tokens):
        async with self.lock:
            led = load_ledger()
            if led["requests"] + 1 > MAX_REQUESTS:
                raise SystemExit(f"BUDGET STOP: requests {led['requests']} >= {MAX_REQUESTS}")
            if led["input_tokens"] + led["estimated_tokens_failed"] + est_tokens > MAX_INPUT_TOKENS:
                raise SystemExit(f"BUDGET STOP: tokens would exceed {MAX_INPUT_TOKENS}")
            led["requests"] += 1
            save_ledger(led)

    async def settle(self, tokens, failed=False):
        async with self.lock:
            led = load_ledger()
            if failed:
                led["failed_requests"] += 1
                led["estimated_tokens_failed"] += int(tokens)
            else:
                led["input_tokens"] += int(tokens)
            save_ledger(led)


async def call(client, sem, budget, state, questions, *, phase, variant, meta=None, timeout=240.0,
               log_path=RESULTS):
    """Send one request; log it; return the logged row (answers keyed by question name)."""
    hits = secret_hits({"state": state, "questions": questions})
    if hits:
        raise SystemExit(f"REFUSING TO SEND: secret-like strings found: {hits[:5]}")
    from typesafe_sdk import RetryPolicy, TypeSafeAPIError
    blob_chars = len(json.dumps(state, ensure_ascii=False)) + len(json.dumps(questions, ensure_ascii=False))
    est = int(blob_chars / budget.cpt)
    await budget.reserve(est)
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "phase": phase,
           "variant": variant, "meta": meta or {}, "model_requested": PINNED_MODEL,
           "state_sha256": sha(state), "questions_sha256": sha(questions),
           "n_questions": len(questions), "state_chars": len(state) if isinstance(state, str)
           else len(json.dumps(state, ensure_ascii=False)), "est_tokens": est}
    t0 = time.time()
    async with sem:
        try:
            r = await client.system_one(state, questions, model=PINNED_MODEL,
                                        retry=RetryPolicy(max_retries=0), timeout=timeout)
        except TypeSafeAPIError as e:
            row.update({"ok": False, "status": getattr(e, "status", None),
                        "error": str(getattr(e, "message", "") or e)[:2000],
                        "body": e.body if isinstance(getattr(e, "body", None), (dict, list, str)) else None,
                        "seconds": round(time.time() - t0, 2)})
            await budget.settle(est, failed=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            return row
        except Exception as e:  # connection/timeouts
            row.update({"ok": False, "status": None, "error": f"{type(e).__name__}: {e}"[:2000],
                        "seconds": round(time.time() - t0, 2)})
            await budget.settle(est, failed=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            return row
    usage = r.usage.model_dump()
    row.update({"ok": True, "model_resolved": r.model, "request_id": getattr(r, "request_id", None),
                "usage": usage, "seconds": round(time.time() - t0, 2),
                "answers_raw": {k: v.model_dump(mode="json") for k, v in r.answers.items()},
                "answers": {k: signals(v) for k, v in r.answers.items()}})
    await budget.settle(usage.get("input_tokens") or est)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def make_client():
    from typesafe_sdk import AsyncTypeSafeClient
    return AsyncTypeSafeClient(timeout=240.0)
