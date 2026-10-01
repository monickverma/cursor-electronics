"""
Check a part figure against its document and record that you did — D7.

`brain/decisions.md` [2026-09-24] D1, D2, D7. Every figure a claim reads has a
provenance record in `backend/data/figures.py`, written by the agent from its
reading of the document and never verified. This is how a person verifies
one: open the document the record names, find the figure where it says, and
confirm the record's statement and the table's value agree with it.

    python scripts/verify_figures.py                     # what is unverified, by part
    python scripts/verify_figures.py --show RC0402FR/power_w
    python scripts/verify_figures.py --verify RC0402FR/power_w --by "<your name>"

Since [2026-09-25] the agent has checked the records against the documents it
could obtain and cited each page (`backend/data/figure_evidence.json`). That is
evidence, not verification. To confirm it:

    python scripts/verify_figures.py --review            # every record beside the agent's evidence
    python scripts/verify_figures.py --confirm-agreeing --by "<your name>"

`--confirm-agreeing` records your verification of every figure whose evidence
agrees and whose record has not changed since it was checked, and says in each
entry that you confirmed the agent's cited evidence rather than read the page
yourself. Everything else is listed for you to check with `--verify`.

A verification is bound to the record's hash, which covers the record and the
table's current value: edit either and the verification no longer counts, and
`--review` lists it as one to confirm again. `--by` must be a person's name: a
placeholder ("Your Name", "<your name>") is refused ([2026-09-30] — the first
confirmation in this repository was recorded under the documentation's
placeholder).
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

from data.figures import (  # noqa: E402
    FIGURES, PLACEHOLDERS, TRUSTABLE, VERIFICATIONS_PATH, evidence, record_hash, trusted, value, verified,
)

#: What a verification says about how it was made.
METHOD_DOCUMENT = "read the document"
METHOD_AGENT_EVIDENCE = "confirmed the agent's cited evidence (backend/data/figure_evidence.json)"


def _store() -> Path:
    return Path(os.environ.get("CIRCUITOS_FIGURE_VERIFICATIONS") or VERIFICATIONS_PATH)


def _person(by: str, what: str) -> str:
    name = by.strip()
    if not name:
        raise SystemExit(f"--by is required: {what} names the person who did it")
    if name.lower() in PLACEHOLDERS:
        raise SystemExit(f"--by {by!r} is the documentation's placeholder, not a name: {what} must name "
                         f"the person who did it")
    return name


def stale() -> list:
    """(figure, by, at) for verifications whose record or value has changed since."""
    path = _store()
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8")).get("verifications", [])
    return [(v["figure"], v.get("by", "?"), v.get("at", "?")) for v in rows
            if v.get("figure") in FIGURES and v.get("record_hash") != record_hash(v["figure"])]


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


def _record(entries: list) -> None:
    path = _store()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"verifications": []}
    replaced = {e["figure"] for e in entries}
    data["verifications"] = [v for v in data.get("verifications", []) if v.get("figure") not in replaced] + entries
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _entry(figure_id: str, by: str, note: str, method: str) -> dict:
    return {"figure": figure_id, "record_hash": record_hash(figure_id), "by": by.strip(),
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "method": method, "note": note}


def verify(figure_id: str, by: str, note: str = "") -> dict:
    if figure_id not in FIGURES:
        raise SystemExit(f"no record {figure_id!r} in backend/data/figures.py")
    by = _person(by, "a verification")
    entry = _entry(figure_id, by, note, METHOD_DOCUMENT)
    _record([entry])
    return entry


def confirmable(ev: dict) -> tuple:
    """(figures the agent's evidence lets a person confirm, {figure: why not} for the rest)."""
    ok, not_ok = [], {}
    for fid in FIGURES:
        item = (ev.get("figures") or {}).get(fid)
        if item is None:
            not_ok[fid] = "no evidence"
        elif item["verdict"] != "agrees":
            not_ok[fid] = item["verdict"].replace("_", " ") + (f" — {item['note']}" if item.get("note") else "")
        elif item["record_hash"] != record_hash(fid):
            not_ok[fid] = "stale: the record or its value changed after the agent checked it"
        elif verified(fid):
            not_ok[fid] = "already verified"
        else:
            ok.append(fid)
    return ok, not_ok


def confirm_agreeing(by: str) -> list:
    by = _person(by, "a confirmation")
    ok, _ = confirmable(evidence())
    entries = [_entry(fid, by, "", METHOD_AGENT_EVIDENCE) for fid in ok]
    if entries:
        _record(entries)
    return entries


def review(show_all: bool = False) -> str:
    ev = evidence()
    if not ev:
        return "No agent evidence (backend/data/figure_evidence.json)."
    docs = ev.get("documents", {})
    ok, not_ok = confirmable(ev)
    lines = [f"Agent evidence, {ev.get('checked_by', '')}. Not a verification until you confirm it.", ""]
    for fid in ok if not show_all else list(FIGURES):
        item = ev["figures"].get(fid) or {}
        record = FIGURES[fid]
        cited = "; ".join(f"{docs[d]['maker']} {docs[d]['title']} {docs[d]['revision']}"
                          for d in item.get("documents", []) if d in docs)
        lines += [f"{fid}   [{item.get('verdict', 'no evidence')}]",
                  f"  value      {value(fid)!r}",
                  f"  record     {record.statement}",
                  f"  document   {cited or '—'}",
                  f"  page       {item.get('pages') or '—'}   {item.get('location') or ''}",
                  f"  it reads   {item.get('reads') or '—'}"]
        if item.get("note"):
            lines.append(f"  note       {item['note']}")
        lines.append("")
    outgrown = stale()
    if outgrown:
        lines.append(f"{len(outgrown)} earlier confirmations no longer count — the record or its value changed "
                     f"since; review them again:")
        for fid, by, at in outgrown:
            lines.append(f"  {fid}: changed since {by} confirmed it ({at})")
        lines.append("")
    lines.append(f"{len(ok)} figures would be confirmed by --confirm-agreeing.")
    if not_ok:
        lines.append(f"{len(not_ok)} would not, and need --verify after you check them yourself:")
        for fid, why in not_ok.items():
            lines.append(f"  {fid}: {why}")
    return "\n".join(lines)


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
    parser.add_argument("--review", action="store_true", help="the agent's evidence beside each record")
    parser.add_argument("--all", action="store_true", help="with --review: every record, not only the agreeing")
    parser.add_argument("--confirm-agreeing", action="store_true",
                        help="record your verification of every figure whose evidence agrees and is current")
    parser.add_argument("--by", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)
    if args.confirm_agreeing:
        entries = confirm_agreeing(args.by)
        print(f"recorded {len(entries)} verifications by {args.by.strip()}, method: {METHOD_AGENT_EVIDENCE}")
        for e in entries:
            print(f"  {e['figure']}")
        print(unverified_summary())
    elif args.review:
        print(review(args.all))
    elif args.verify:
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
