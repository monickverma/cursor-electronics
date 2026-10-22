"""
stage_master_rows.py — stage only the master session's NEW rows in a shared JSONL.

WHY THIS EXISTS
---------------
`alpha/ledger.jsonl` and `alpha/findings.jsonl` are shared files: the master
session and the peer program (S1-S8) both append to them, in the same
working tree. The handoff says the master session must not commit the
peer's in-flight work. But a JSONL file cannot be half-committed with
`git add` — the whole file goes, peer rows and all.

So the staged content is built as: everything already committed, plus the
master session's new rows. The peer's new rows stay in the working tree,
uncommitted. Nothing already in history is removed — a commit never
rewrites what came before it — and nothing of the peer's is claimed.

    python .claude/shared-memory/alpha/stage_master_rows.py           # stage
    python .claude/shared-memory/alpha/stage_master_rows.py --check   # report only

THE SPLIT RULE
--------------
ledger.jsonl     a row is the master's when it says so: `"by": "master"`.
                 The peer writes `"by": "S2"`, `"by": "S7"` and so on.

findings.jsonl   a row is the master's when it is not the peer's. The
                 master's findings carry an id in F-00NN and a prompt of
                 "" or "A1 overlooker run, ...", and F-S0-0001 — the
                 master's own filing of the wrong-pinout false pass — is
                 kept by id, because its prompt field names a peer session
                 but the finding is the master's.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ALPHA = REPO / ".claude" / "shared-memory" / "alpha"

#: (path relative to alpha/, kind)
SHARED = [
    ("ledger.jsonl", "ledger"),
    ("findings.jsonl", "findings"),
]

#: The master's own finding that happens to name a peer session.
MASTER_IDS = {"F-S0-0001"}


def is_master(row: dict, kind: str) -> bool:
    if kind == "ledger":
        return row.get("by") == "master"
    prompt = str(row.get("prompt") or "")
    if str(row.get("id")) in MASTER_IDS:
        return True
    return not prompt.startswith("peer ")


def row_key(row: dict, kind: str) -> str:
    """What makes a row the same row. Used to tell new rows from old ones."""
    if kind == "ledger":
        return f"milestone:{row.get('milestone')}"
    return f"id:{row.get('id')}"


def head_lines(path: Path) -> list[str]:
    rel = path.relative_to(REPO).as_posix()
    proc = subprocess.run(["git", "show", f"HEAD:{rel}"],
                          cwd=REPO, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def build(path: Path, kind: str) -> tuple[list[str], int, int]:
    old = head_lines(path)
    old_keys = set()
    for line in old:
        try:
            old_keys.add(row_key(json.loads(line), kind))
        except json.JSONDecodeError:
            pass

    work = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    keep = list(old)
    new_master = 0
    skipped_peer = 0
    for line in work:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row_key(row, kind)
        if key in old_keys:
            continue                       # already committed, in either file
        if is_master(row, kind):
            keep.append(line)
            old_keys.add(key)
            new_master += 1
        else:
            skipped_peer += 1
    return keep, new_master, skipped_peer


def stage(path: Path, kind: str, check_only: bool) -> None:
    keep, new_master, skipped_peer = build(path, kind)
    committed = len(head_lines(path))
    print(f"{path.name}: {committed} committed + {new_master} new master rows"
          f" -> {len(keep)} staged; {skipped_peer} peer rows left uncommitted")
    if check_only:
        return

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8", newline="\n") as tmp:
        tmp.write("".join(ln + "\n" for ln in keep))
        tmp_path = tmp.name
    try:
        blob = subprocess.run(["git", "hash-object", "-w", tmp_path],
                              cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
        rel = path.relative_to(REPO).as_posix()
        subprocess.run(["git", "update-index", "--cacheinfo", f"100644,{blob},{rel}"],
                       cwd=REPO, check=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    for name, kind in SHARED:
        path = ALPHA / name
        if not path.exists():
            print(f"missing: {path}")
            return 1
        stage(path, kind, check_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
