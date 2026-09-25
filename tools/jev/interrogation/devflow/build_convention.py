"""Commit convention: every commit subject on origin/phase2-stage0 (79) labelled by regex, plus 8 synthetic
edge cases (flagged). No real commit on any branch uses 'session:' (0 of 90 distinct subjects), so the only
'session:' items are synthetic. Subjects are read with --format=%s (no author, no e-mail).
"""
import re

from common import BRANCH, SETS, git, secret_findings, write_jsonl

CONVENTIONAL = re.compile(r"^(feat|fix|test|docs|chore|refactor|perf|build|ci|style|revert)(\([^)]+\))?!?: \S")


def regex_label(subject):
    if CONVENTIONAL.match(subject):
        return "conventional"
    if subject.startswith("brain: "):
        return "brain"
    if subject.startswith("session: "):
        return "session"
    return "other"


SYNTHETIC = [
    "session: Stage 6 BOM substitution work in progress",
    "session: close the D7 provenance records",
    "session: regen state after the grid gate",
    "session: figure audit and verify_figures",
    "feat:add pin rules for the Black Pill",          # no space after the colon -> other
    "Fix(ai): capitalised type",                       # capitalised type -> other
    "brain /update-memory — no colon",                 # missing colon -> other
    "chore(memory)!: breaking memory layout",          # bang -> conventional
]


def build():
    lines = git("log", BRANCH, "--format=%h\t%s").splitlines()
    items = []
    for line in lines:
        sha, subject = line.split("\t", 1)
        items.append({"task": "CONV", "item_id": f"CONV-{sha}", "synthetic": False, "label": regex_label(subject),
                      "state": {"subject": subject}, "label_rule": "regex (see build_convention.py)"})
    for k, s in enumerate(SYNTHETIC, 1):
        items.append({"task": "CONV", "item_id": f"CONV-syn{k}", "synthetic": True, "label": regex_label(s),
                      "state": {"subject": s}, "label_rule": "regex (see build_convention.py)"})
    for it in items:
        assert not secret_findings(it["state"]), it["item_id"]
    return items


if __name__ == "__main__":
    items = build()
    from collections import Counter
    h = write_jsonl(SETS / "conv_commit_subjects.jsonl", items)
    print(len(items), Counter((i["synthetic"], i["label"]) for i in items), h)
