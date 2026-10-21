"""
repair_findings.py — make findings.jsonl parseable, and update the statuses.

One line had an unescaped backslash in a Windows path (Temp\\router_check\\),
which made the whole file unparseable. JSONL that does not parse is a ledger
nobody can read, so this repairs it and then applies the status changes the
master session decided.

    python .claude/shared-memory/alpha/repair_findings.py
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
FINDINGS = HERE / "findings.jsonl"

#: A backslash that is not a valid JSON escape character.
_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _repair(line: str) -> str:
    """Escape the lone backslashes a hand-written JSONL line can carry."""
    return _BAD_ESCAPE.sub(r"\\\\", line)


def load(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append(json.loads(_repair(line)))
    return rows


def main() -> int:
    rows = load(FINDINGS)
    by_id = {r["id"]: r for r in rows}

    def set_status(fid: str, status: str, fixed_by=None, verified_by=None) -> None:
        r = by_id.get(fid)
        if r is None:
            print(f"  ! no finding {fid}")
            return
        r["status"] = status
        if fixed_by is not None:
            r["fixed_by"] = fixed_by
        if verified_by is not None:
            r["verified_by"] = verified_by

    set_status(
        "F-0001", "fixed", "323b4ef",
        "tests/test_rate_limit_config.py (35 tests); the defaults are unchanged "
        "(10/20/100/60 per hour) and the values now come from the environment")
    set_status(
        "F-0002", "fixed", "799475b",
        "S3 diagnosed it as not reproducing at 323b4ef: IR_005 routes 12/12 with "
        "0 DRC errors and III.2 passing. S4 added the pad-to-pad DRC rule on top "
        "(branch claude/alpha-s4-build-router-e19024, commit ef6f1fc)")
    set_status(
        "F-0003", "in_progress",
        "S4 (branch claude/alpha-s4-build-router-e19024); not yet merged")
    set_status(
        "F-0006", "fixed", "45c27c8",
        "tests/test_explanation_queue.py (18 tests) and tests/test_migrations.py "
        "(6 tests). 2748 passed, 13 skipped.")

    FINDINGS.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for r in rows:
        print(f"  {r['id']:<8} {r['status']:<12} {r.get('fixed_by') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
