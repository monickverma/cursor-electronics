#!/usr/bin/env python3
"""Capture one full /design/generate response to a JSON file.

Why this exists: criterion 12 and the explanation ablation both need the real
output of the running app, not a mock. This grabs it reproducibly so the same
prompt can be re-captured whenever `explainer.py` changes and the two runs
compared.

    start.bat                       # backend must be up on :8000
    python scripts/capture_explanation.py
    python scripts/capture_explanation.py --prompt "..." --out foo.json

Writes captures/<slug>__<model>__<timestamp>.json containing the whole
response plus the model that produced it. The model matters: "the explainer
passed review" is not a reproducible claim without naming the model that wrote
the words the reviewer read.

Stdlib only — no requests, no httpx.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PROMPT = "Arduino reads DHT22 and alerts above 30°C"
DEFAULT_BASE = "http://localhost:8000"
DEFAULT_EMAIL = "test@circuitos.dev"
DEFAULT_PASSWORD = "TestPass123!"

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "captures"


def _post(url: str, data: bytes, content_type: str, token: str | None = None,
          timeout: int = 180) -> dict:
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", content_type)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"HTTP {e.code} from {url}\n{body}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {url} — is the backend running? ({e.reason})")


def login(base: str, email: str, password: str) -> str:
    form = urllib.parse.urlencode({"username": email, "password": password}).encode()
    out = _post(f"{base}/auth/login", form,
                "application/x-www-form-urlencoded", timeout=30)
    return out["access_token"]


def generate(base: str, token: str, prompt: str) -> dict:
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    return _post(f"{base}/design/generate", body, "application/json", token=token)


def model_in_use() -> str:
    """Read AI_MODEL from .env, falling back to the config default.

    Deliberately does not import backend.core.config — this script must run
    without the backend's dependencies installed.
    """
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("AI_MODEL="):
                return line.split("=", 1)[1].strip() or "unset"
    return os.environ.get("AI_MODEL", "unknown")


def slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n] or "capture"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--email", default=os.environ.get("CIRCUITOS_EMAIL", DEFAULT_EMAIL))
    ap.add_argument("--password", default=os.environ.get("CIRCUITOS_PASSWORD", DEFAULT_PASSWORD))
    ap.add_argument("--out", default=None, help="output path (default: captures/...)")
    args = ap.parse_args()

    print(f"  prompt : {args.prompt}")
    print(f"  base   : {args.base}")
    print("  logging in...", flush=True)
    token = login(args.base, args.email, args.password)

    print("  generating (this takes ~15s)...", flush=True)
    resp = generate(args.base, token, args.prompt)

    model = model_in_use()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "captured_at": stamp,
        "prompt": args.prompt,
        "model": model,
        "response": resp,
    }

    if args.out:
        path = Path(args.out)
    else:
        CAPTURES.mkdir(exist_ok=True)
        path = CAPTURES / f"{slug(args.prompt)}__{slug(model, 30)}__{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    expl = resp.get("explanation") or ""
    print()
    print(f"  model       : {model}")
    print(f"  circuit_id  : {resp.get('circuit_id')}")
    print(f"  components  : {len(resp.get('ir', {}).get('components', []))}")
    print(f"  bom rows    : {len(resp.get('bom') or [])}")
    print(f"  explanation : {len(expl)} chars, {len(expl.split())} words")
    if not expl.strip():
        print("  WARNING: explanation is empty — check ANTHROPIC_API_KEY and the logs.")
    print(f"\n  -> {path}")


if __name__ == "__main__":
    main()
