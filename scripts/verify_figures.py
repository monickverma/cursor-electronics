"""
Check a part figure against its document and record that you did — D7.

`brain/decisions.md` [2026-09-24] D1, D2, D7. Every figure a claim reads has a
provenance record in `backend/data/figures.py`, written by the agent from its
reading of the document and never verified. This is how a person verifies
one: open the document the record names, find the figure where it says, and
confirm the record's statement and the table's value agree with it.

    python scripts/verify_figures.py                     # what is unverified, by part
    python scripts/verify_figures.py --show RC0402FR/power_w
    python scripts/verify_figures.py --verify RC0402FR/power_w --by "Your Name"

A verification is bound to the record's hash, which covers the record and the
table's current value: edit either and the verification no longer counts.
Verifying a typical or a stated assumption is allowed — it confirms the record
says what the figure is — but only a guaranteed limit, a standard's figure or
a policy becomes trusted, so only those let a claim drop D7.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from data.figures import FIGURES, TRUSTABLE, VERIFICATIONS_PATH, record_hash, trusted, value, verified  # noqa: E402


def _store() -> Path:
    return Path(os.environ.get("CIRCUITOS_FIGURE_VERIFICATIONS") or VERIFICATIONS_PATH)


def show(figure_id: str) -> str:
    record = FIGURES[figure_id]
    src = record.source
    lines = [
        f"figure     {record.id}",
        f"value      {value(figure_id)!r}   (from the table that owns it)",
        f"kind       {record.kind.value}" + ("" if record.kind in TRUSTABLE else "  — never trusted, even verified"),
        f"statement  {record.statement}",
        f"document   {src.maker}, {src.document}" if src else "document   none — the project's own figure",
        f"where      {src.location}" if src else "",
        f"inputs     {', '.join(record.inputs)}" if record.inputs else "",
        f"recorded   {record.recorded_by}",
        f"verified   {'yes' if verified(figure_id) else 'no'}; trusted {'yes' if trusted(figure_id) else 'no'}",
        f"hash       {record_hash(figure_id)}",
    ]
    return "\n".join(line for line in lines if line)


def verify(figure_id: str, by: str, note: str = "") -> dict:
    if figure_id not in FIGURES:
        raise SystemExit(f"no record {figure_id!r} in backend/data/figures.py")
    if not by.strip():
        raise SystemExit("--by is required: a verification names the person who checked the document")
    path = _store()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"verifications": []}
    entry = {"figure": figure_id, "record_hash": record_hash(figure_id), "by": by.strip(),
             "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "note": note}
    data["verifications"] = [v for v in data.get("verifications", []) if v.get("figure") != figure_id] + [entry]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry


def unverified_summary() -> str:
    by_owner = defaultdict(list)
    for fid in FIGURES:
        if not verified(fid):
            by_owner[fid.rpartition("/")[0]].append(fid.rpartition("/")[2])
    done = len(FIGURES) - sum(len(v) for v in by_owner.values())
    lines = [f"{done} of {len(FIGURES)} figures verified."]
    for owner in sorted(by_owner):
        keys = by_owner[owner]
        lines.append(f"  {owner}: {', '.join(keys) if len(keys) <= 6 else f'{len(keys)} figures'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--show", metavar="FIGURE")
    parser.add_argument("--verify", metavar="FIGURE")
    parser.add_argument("--by", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)
    if args.verify:
        entry = verify(args.verify, args.by, args.note)
        print(f"recorded: {entry['figure']} checked by {entry['by']} at {entry['at']}")
        print(show(args.verify))
    elif args.show:
        print(show(args.show))
    else:
        print(unverified_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
