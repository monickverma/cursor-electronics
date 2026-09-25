"""Decision-entry quality: every decisions.md entry in the phase2-stage0 snapshot (40) plus degraded copies.

The project's entry shape (decisions.md header: "Format: decision → reason → alternatives rejected → date", plus a
revisit trigger, which the criterion-12 and D1 entries use) is parsed deterministically into five elements.
Degraded copies are built by removing one labelled block, so each has a known, lower-quality original (paired):
  no_alternatives  the '**Alternatives rejected:**' / '**Rejected alternatives:**' block removed
  no_reason        the '**Reason:**' block removed
  no_date          the date removed from the heading
"""
import re

from common import P2, SETS, secret_findings, write_jsonl

DEC = P2 / ".claude/shared-memory/brain/decisions.md"

CHECKS = {
    "date": re.compile(r"\A## \[\d{4}-\d{2}-\d{2}\]"),
    "decision": re.compile(r"(?m)^\*\*Decision\b|^Decision:"),
    "reason": re.compile(r"(?m)^\*\*(Reasons?|Why)\b|^Reason:"),
    "alternatives": re.compile(r"(?im)alternatives rejected|rejected alternatives|\*rejected:\*|^rejected:"),
    "trigger": re.compile(r"(?i)\btrigger|\brevisit|\bre-?open|when (lab|hardware|bench) access|upgrade it"),
}


def checklist(entry):
    found = {k: bool(rx.search(entry)) for k, rx in CHECKS.items()}
    return {"elements": found, "score": sum(found.values())}


def entries():
    text = DEC.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## \[)", text)
    return [re.sub(r"\n-{3,}\s*$", "", p.rstrip()).rstrip() for p in parts if p.startswith("## [")]


def remove_block(entry, label_rx):
    lines = entry.splitlines()
    for i, line in enumerate(lines):
        if re.match(label_rx, line):
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if nxt.startswith("**") or nxt.startswith("---") or nxt.startswith("## "):
                    if j > i + 1 and not lines[j - 1].strip():
                        break
                j += 1
            out = lines[:i] + lines[j:]
            return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return None


def build():
    es = entries()
    items = []
    for n, e in enumerate(es, 1):
        items.append({"task": "Q", "item_id": f"Q-{n:02d}", "kind": "real", "entry_index": n,
                      "title": e.splitlines()[0], "state": {"entry": e}, "checklist": checklist(e)})
    alt_rx = r"^\*\*(Alternatives rejected|Rejected alternatives):\*\*"
    alts = [(n, e) for n, e in enumerate(es, 1) if re.search("(?m)" + alt_rx, e)]
    reas = [(n, e) for n, e in enumerate(es, 1) if re.search(r"(?m)^\*\*Reason:\*\*", e)][:10]
    for group, kind, rx in ((alts, "no_alternatives", alt_rx), (reas, "no_reason", r"^\*\*Reason:\*\*")):
        for n, e in group:
            txt = remove_block(e, rx)
            assert txt and txt != e, (n, kind)
            items.append({"task": "Q", "item_id": f"Q-{n:02d}-{kind}", "kind": kind, "entry_index": n,
                          "pair_of": f"Q-{n:02d}", "title": e.splitlines()[0], "state": {"entry": txt},
                          "checklist": checklist(txt)})
    used = {n for n, _ in alts} | {n for n, _ in reas}
    for n, e in [(n, e) for n, e in enumerate(es, 1) if n not in used][:8]:
        txt = re.sub(r"\A## \[\d{4}-\d{2}-\d{2}\] ", "## ", e)
        items.append({"task": "Q", "item_id": f"Q-{n:02d}-no_date", "kind": "no_date", "entry_index": n,
                      "pair_of": f"Q-{n:02d}", "title": e.splitlines()[0], "state": {"entry": txt},
                      "checklist": checklist(txt)})
    for it in items:
        it["label_rule"] = ("real: checklist parse is the deterministic reference; degraded: the original "
                            "(pair_of) has one more element by construction, so its score must be lower")
        assert not secret_findings(it["state"]), it["item_id"]
    return items


if __name__ == "__main__":
    items = build()
    from collections import Counter
    h = write_jsonl(SETS / "q_entry_quality.jsonl", items)
    print(len(items), Counter(i["kind"] for i in items), h)
    print(Counter(i["checklist"]["score"] for i in items if i["kind"] == "real"))
    for it in items:
        if it["kind"] != "real":
            orig = next(x for x in items if x["item_id"] == it["pair_of"])
            print(it["item_id"], orig["checklist"]["score"], "->", it["checklist"]["score"], len(it["state"]["entry"]))
