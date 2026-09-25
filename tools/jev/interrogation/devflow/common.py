"""Shared helpers for the devflow interrogation of Jev (T1-T4, convention, entry quality).

Read-only with respect to the repository: git is only ever called with show / log / tag.
Every set is written as JSONL (one item per line, sorted keys) and hashed before any Jev call.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path(os.environ.get("CIRCUITOS_REPO", "/home/user/cursor-electronics"))
# origin/phase2-stage0 at e803a99, exported to the session scratchpad (see HANDOFF_2026-09-25.md)
P2 = pathlib.Path(os.environ.get(
    "CIRCUITOS_P2",
    "/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2"))
BRANCH = "origin/phase2-stage0"
SETS = HERE / "sets"
PINNED_MODEL = "jev-1.13.0"
PRICE_PER_MTOK_USD = 0.042  # docs.typesafe.ai/models, input tokens only, 2026-09-24

_READ_ONLY_GIT = {"show", "log", "tag", "rev-parse"}


def git(*args):
    if args[0] not in _READ_ONLY_GIT:
        raise RuntimeError(f"git {args[0]} is not allowed here (read-only harness)")
    out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr[:300]}")
    return out.stdout


def sha_obj(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def sha_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_jsonl(path, items):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, sort_keys=True, ensure_ascii=False) + "\n")
    return sha_file(path)


def read_jsonl(path):
    with pathlib.Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------- secret hygiene
_EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PATTERNS = {
    "email": _EMAIL,
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{6,}"),
    "generic_sk_key": re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}"),
    "url_with_credentials": re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
    "password_assignment": re.compile(r"(?i)password\s*[=:]\s*\S+"),
    "secret_key_value": re.compile(r"(?i)secret_key\s*[=:]\s*['\"]?[A-Za-z0-9_-]{8,}"),
    "windows_user_path": re.compile(r"(?i)C:\\\\?Users\\\\?[A-Za-z0-9_.-]+"),
}


def redact(text):
    text = _EMAIL.sub("<email>", text)
    text = _PATTERNS["windows_user_path"].sub(r"C:\\Users\\<user>", text)
    return text


def secret_findings(obj):
    """Return a list of (pattern, excerpt-free description). Never returns the matched text."""
    blob = json.dumps(obj, ensure_ascii=False)
    hits = [name for name, rx in _PATTERNS.items() if rx.search(blob)]
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key and key in blob:
        hits.append("typesafe_api_key")
    return hits
