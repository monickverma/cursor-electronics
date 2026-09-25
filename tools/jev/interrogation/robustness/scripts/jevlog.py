"""jevlog.py - one logged, budgeted way to call Jev for the robustness interrogation.

Every HTTP attempt is one row in ../results.jsonl:
  ts, experiment, variant, item_id, model_requested, model_resolved, request_id, usage,
  latency_ms, state_sha256, questions_sha256 (order-preserving), questions_sha256_sorted
  (the tools/jev/run.py convention, blind to label order), full raw answers, selected
  response headers, error type/status/body.
The exact payload of every request is stored once, content-addressed, in ../payloads/<sha>.json.gz,
so every row is re-runnable.

Retries are disabled in the SDK (RetryPolicy(max_retries=0)) so one row == one HTTP request and
429/5xx are observed, not hidden. Budget: <= 1,500 requests and <= 15M input tokens, enforced
before each send (hard stop). The API key is read by the SDK from TYPESAFE_API_KEY and is never
printed, logged or written; request headers are never logged.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import gzip
import hashlib
import json
import os
import pathlib
import time
from typing import Any

import httpx2
from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy
from typesafe_sdk._core.errors import (TypeSafeAPIConnectionError, TypeSafeAPIError,
                                       TypeSafeAPITimeoutError, TypeSafeError)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results.jsonl"
PAYLOADS = ROOT / "payloads"
BUDGET_FILE = ROOT / "budget.json"
MAX_REQUESTS = 1500
MAX_INPUT_TOKENS = 15_000_000
PINNED = "jev-1.13.0"
# Response headers worth keeping (never request headers; never cookies).
KEEP_HEADER_PREFIXES = ("x-ratelimit", "ratelimit", "retry-after", "x-typesafe", "server-timing",
                        "x-request-id", "content-length", "date", "x-processing", "via", "cf-cache",
                        "x-envoy", "openai-processing")
SECRET_HEADERS = {"authorization", "proxy-authorization", "x-api-key", "api-key", "cookie", "set-cookie"}


def canon(obj: Any) -> str:
    """Order-preserving canonical JSON (label order matters, so no sort_keys)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def sha(obj: Any) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def sha_sorted(obj: Any) -> str:
    """The tools/jev/run.py hash convention (sort_keys=True) - cannot see label order."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def store_payload(payload: dict) -> str:
    h = sha(payload)
    PAYLOADS.mkdir(parents=True, exist_ok=True)
    p = PAYLOADS / f"{h}.json.gz"
    if not p.exists():
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(canon(payload))
    return h


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Running totals, persisted after every call; reconstructed from results.jsonl at start."""

    def __init__(self) -> None:
        self.requests = 0
        self.input_tokens = 0
        if RESULTS.exists():
            for line in RESULTS.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("counted_request", True):
                    self.requests += 1
                u = row.get("usage") or {}
                self.input_tokens += int(u.get("input_tokens") or 0)
        self.lock = asyncio.Lock()

    def check(self, est_tokens: int) -> None:
        if self.requests + 1 > MAX_REQUESTS:
            raise BudgetExceeded(f"request budget exhausted ({self.requests}/{MAX_REQUESTS})")
        if self.input_tokens + est_tokens > MAX_INPUT_TOKENS:
            raise BudgetExceeded(f"token budget would be exceeded ({self.input_tokens}+{est_tokens})")

    def persist(self) -> None:
        BUDGET_FILE.write_text(json.dumps({"requests": self.requests, "input_tokens": self.input_tokens,
                                           "max_requests": MAX_REQUESTS,
                                           "max_input_tokens": MAX_INPUT_TOKENS,
                                           "updated": _dt.datetime.now(_dt.timezone.utc).isoformat()},
                                          indent=1))


def _answers_raw(r) -> dict:
    out = {}
    for name, a in r.answers.items():
        d = a.model_dump(mode="json")
        out[name] = d
    return out


def _keep_headers(h) -> dict:
    out = {}
    for k, v in h.items():
        kl = k.lower()
        if kl in SECRET_HEADERS:
            continue
        if kl.startswith(KEEP_HEADER_PREFIXES):
            out[kl] = v
    return out


class Jev:
    """Async, budgeted, logged caller. Use: async with Jev(concurrency=8) as j: await j.ask(...)."""

    def __init__(self, concurrency: int = 8, timeout: float = 90.0) -> None:
        assert 1 <= concurrency <= 8, "concurrency must stay <= 8"
        self.sem = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.budget = Budget()
        self.client: AsyncTypeSafeClient | None = None
        self._write_lock = asyncio.Lock()

    async def __aenter__(self):
        self.client = AsyncTypeSafeClient(retry=RetryPolicy(max_retries=0), timeout=self.timeout)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)
        self.budget.persist()

    async def _log(self, row: dict) -> None:
        async with self._write_lock:
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def ask(self, experiment: str, variant: str, item_id: str, state: Any, questions: dict,
                  model: str = PINNED, extra: dict | None = None, raise_on_error: bool = False) -> dict:
        payload = {"state": state, "model": model, "questions": questions}
        est = max(1, len(canon(payload)) // 3)
        async with self.sem:
            async with self.budget.lock:
                self.budget.check(est)
                self.budget.requests += 1  # reserve before sending
            payload_sha = store_payload(payload)
            row: dict[str, Any] = {
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(), "experiment": experiment,
                "variant": variant, "item_id": item_id, "model_requested": model,
                "state_sha256": sha(state), "questions_sha256": sha(questions),
                "questions_sha256_sorted": sha_sorted(questions), "payload_sha256": payload_sha,
                "n_questions": len(questions), "payload_chars": len(canon(payload)),
                "state_chars": len(canon(state)) if not isinstance(state, str) else len(state),
                "counted_request": True,
            }
            if extra:
                row["extra"] = extra
            t0 = time.perf_counter()
            try:
                r = await self.client.system_one(state, questions, model=model)
                row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                row["model_resolved"] = r.model
                row["request_id"] = r.request_id
                row["usage"] = r.usage.model_dump()
                row["answers"] = _answers_raw(r)
                try:
                    raw = r.raw_http_response
                    row["headers"] = _keep_headers(raw.headers)
                    row["http_status"] = raw.status_code
                except Exception:  # noqa: BLE001
                    pass
                row["error"] = None
            except TypeSafeAPIError as e:
                row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                body = e.body
                try:
                    body_txt = canon(body)
                except Exception:  # noqa: BLE001
                    body_txt = str(body)
                row["error"] = {"type": type(e).__name__, "status": e.status,
                                "body": body_txt[:2000],
                                "request_id": e.request_id,
                                "headers": _keep_headers(e.headers) if e.headers is not None else {}}
                row["usage"] = None
                row["answers"] = None
            except (TypeSafeAPITimeoutError, TypeSafeAPIConnectionError, TypeSafeError) as e:
                row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                row["error"] = {"type": type(e).__name__, "status": None, "body": str(e)[:500]}
                row["usage"] = None
                row["answers"] = None
            except Exception as e:  # noqa: BLE001 - log anything else, including httpx2 errors
                row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                row["error"] = {"type": type(e).__name__, "status": None, "body": str(e)[:500]}
                row["usage"] = None
                row["answers"] = None
            async with self.budget.lock:
                if row.get("usage"):
                    self.budget.input_tokens += int(row["usage"].get("input_tokens") or 0)
                self.budget.persist()
            await self._log(row)
            if raise_on_error and row["error"]:
                raise RuntimeError(row["error"])
            return row


async def list_models() -> dict:
    """GET /v1/models, logged as a counted request (it is one HTTP call)."""
    budget = Budget()
    budget.check(0)
    t0 = time.perf_counter()
    row = {"ts": _dt.datetime.now(_dt.timezone.utc).isoformat(), "experiment": "E0_models",
           "variant": "models.list", "item_id": "-", "counted_request": True}
    async with AsyncTypeSafeClient(retry=RetryPolicy(max_retries=0), timeout=30) as c:
        try:
            m = await c.models.list()
            row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            row["models"] = [x.model_dump(mode="json") for x in m.models]
            row["error"] = None
        except Exception as e:  # noqa: BLE001
            row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            row["error"] = {"type": type(e).__name__, "status": getattr(e, "status", None),
                            "body": str(e)[:500]}
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    budget.requests += 1
    budget.persist()
    return row


def load_rows(experiment: str | None = None) -> list[dict]:
    rows = []
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if experiment is None or r.get("experiment") == experiment:
                    rows.append(r)
    return rows


def verify_prereg(item_file: pathlib.Path) -> str:
    """Refuse to run an item set whose bytes differ from the pre-registered hash."""
    reg = ROOT / "items" / "PREREGISTRATION.tsv"
    want = None
    for line in reg.read_text(encoding="utf-8").splitlines()[1:]:
        cols = line.split("\t")
        if cols[1] == item_file.name:
            want = cols[2]
    got = file_sha(item_file)
    if want != got:
        raise SystemExit(f"{item_file.name}: sha256 {got} != pre-registered {want}; refusing to run")
    return got
