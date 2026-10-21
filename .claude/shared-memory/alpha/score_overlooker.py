"""
score_overlooker.py — score an overlooker run against the answer key.

WHAT THIS IS
------------
Alpha stage A1 exits on two numbers:

  1. RECALL — of the defects we seeded, how many did the overlooker find?
  2. FALSE PASSES — of the defects we seeded, how many did the overlooker miss
     while reporting the board as clean? On the CRITICAL classes (short, open,
     wrong pinout, reversed diode, creepage) a single false pass blocks the
     stage. A missed defect that the overlooker flagged as "suspicious" is a
     near miss, and it is recorded separately: it is a much better outcome
     than a clean pass, and lumping it in with a false pass would hide the
     difference.

The key file is `tests/fixtures/alpha_known_bad/KEY.json` — the answer key.
The overlooker NEVER sees it. This script sees both the key and the
overlooker's findings file, and it is the only thing that reads the key.

THE HONEST PART
---------------
This script measures ONE thing: whether an overlooker run, reading only the
product, found the defects we had already planted. It says nothing about
whether the product is correct, and nothing about whether the defects matter
in the real world. A recall of 100% on a set of eight planted defects is a
calibration result, not a product guarantee.

    python .claude/shared-memory/alpha/score_overlooker.py --findings <path> [--key <path>]
    python .claude/shared-memory/alpha/score_overlooker.py --findings <path> --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "fixtures" / "alpha_known_bad"
DEFAULT_KEY = FIXTURES / "KEY.json"

# How an overlooker's report on a seeded board is read, worst to best.
PASSED_CLEAN = "passed_clean"          # said the board was fine — a false pass
MISSED = "missed"                      # said nothing about the defect
FLAGGED = "flagged"                    # noticed something, but did not name the defect
DETECTED = "detected"                  # named the defect, or its check


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("_", " ").replace("-", " ").split())


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _classify(key_entry: dict, findings: list[dict]) -> tuple[str, list[dict]]:
    """How the overlooker did on one seeded case.

    THE OUTCOMES, worst to best:

      passed_clean  the overlooker looked at this board and said it was fine.
                   This is the false pass, and on a critical class it blocks
                   the stage.
      missed        the overlooker said nothing about this board.
      flagged       the overlooker noticed something was wrong but did not
                   name the fault. A near miss — much better than a false
                   pass, and scored separately so the difference is visible.
      detected      the overlooker named the fault, or the check that found
                   it.

    HOW A FINDING IS MATCHED TO A CASE
    ----------------------------------
    Two steps, and the order matters.

    STEP 1 — is this finding about this board? A finding that names an
    artifact is about that artifact: if the artifact is not this case's,
    the finding is not evidence about this case, whatever else it says. A
    finding with no artifact falls back to what it says.

    STEP 2 — did it name the fault? The KEY lists the phrases that name
    each fault. The bare class word is deliberately NOT among them: "short"
    and "open" are ordinary English, and a sentence that says "the product
    has no check for shorts" has not found a short. Matching on the class
    word alone made a gap report score as a detection, which is exactly
    backwards and would turn the recall number into a fiction.

    A GAP REPORT is a finding that says a check is missing. It is not a
    detection (nothing was found) and it is not a false pass (the board was
    not passed — the tool was found wanting). It is a near miss, and a
    valuable one, because it says the same thing about the product that this
    program has been saying.
    """
    case_id = key_entry.get("id", "")
    check_ids = key_entry.get("expected_check_ids") or []
    if isinstance(check_ids, str):
        check_ids = [check_ids]
    keywords = [k.lower() for k in (key_entry.get("detection_keywords") or [])]
    artifact_hint = (key_entry.get("artifact_hint") or "").lower()
    #: The file names that identify this case's board. The master session
    #: hands each seeded board over under its own name
    #: (`boards/board_<case>.json`), so a finding that names the file it was
    #: given can be matched to the case it was given for.
    artifact_names = [str(a).lower() for a in (key_entry.get("artifact_names") or [])]
    case_norm = _norm(case_id)
    check_norms = [_norm(str(c)) for c in check_ids]

    def _text(f: dict) -> str:
        return _norm(" ".join(
            str(f.get(k, ""))
            for k in ("id", "observed", "expected", "evidence", "detail")
        ))

    def _all(f: dict) -> str:
        return _norm(" ".join(
            str(f.get(k, ""))
            for k in ("id", "observed", "expected", "evidence", "artifact", "detail")
        ))

    def _is_gap_report(text: str) -> bool:
        return any(g in text for g in (
            "no check", "not implemented", "does not check", "does not detect",
            "cannot detect", "no rule", "no test", "not checked", "never checks",
            "no test for", "would not catch", "would not detect", "no support for",
        ))

    def _about_this_board(f: dict) -> bool:
        artifact = str(f.get("artifact", "")).lower()
        if artifact:
            # The artifact is authoritative: a finding that names a file is
            # about that file. It counts for this case when the artifact
            # carries the case's name, one of the case's own board file
            # names, or a phrase the key says means this board.
            if artifact_hint and artifact_hint in artifact:
                return True
            if case_norm and case_norm in _norm(artifact):
                return True
            if any(_norm(a) in _norm(artifact) for a in artifact_names):
                return True
            return False
        blob = _all(f)
        if case_norm and case_norm in blob:
            return True
        if any(c in blob for c in check_norms):
            return True
        return any(k in blob for k in keywords)

    def _names_the_fault(text: str) -> bool:
        if case_norm and case_norm in text:
            return True
        if any(c in text for c in check_norms):
            return True
        if keywords and any(k in text for k in keywords):
            return True
        return False

    relevant = [f for f in findings if _about_this_board(f)]
    if not relevant:
        return MISSED, []

    for f in relevant:
        text = _text(f)
        if _is_gap_report(text):
            # A gap report never names a fault. Keep looking at the others.
            continue
        if _names_the_fault(text):
            return DETECTED, relevant

    # Nothing named the fault. Did the overlooker pass the board?
    for f in relevant:
        text = _text(f)
        if _is_gap_report(text):
            continue
        if _says_clean(text):
            return PASSED_CLEAN, relevant

    return FLAGGED, relevant


def _says_clean(text: str) -> bool:
    """Does this text say the board is fine?

    The signs are explicit: the board passed, is correct, has no faults, is
    clean. A finding that merely fails to name a fault is a near miss, not a
    false pass — the difference matters, because a false pass is the one
    outcome that blocks the stage.
    """
    clean_phrases = (
        "no faults", "no defects", "no problems", "no issues", "no errors",
        "is correct", "are correct", "looks correct", "appears correct",
        "is clean", "are clean", "passed", "passes the check", "no short",
        "no open", "nothing wrong", "no discrepancy", "no mismatch",
        "no violations", "no findings", "everything is correct",
        "every check passes", "all checks pass",
    )
    return any(p in text for p in clean_phrases)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", required=True, type=Path, help="the overlooker's findings.jsonl")
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY, help="the answer key")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.findings.exists():
        print(f"no findings file at {args.findings}")
        return 1
    if not args.key.exists():
        print(f"no answer key at {args.key}")
        print("The key is built by the calibration workflow. Until it exists, recall cannot be scored.")
        return 1

    key = json.loads(args.key.read_text(encoding="utf-8"))
    cases = key.get("cases", [])
    findings = _load_jsonl(args.findings)

    rows = []
    for entry in cases:
        outcome, relevant = _classify(entry, findings)
        rows.append(
            {
                "id": entry.get("id"),
                "defect_class": entry.get("defect_class"),
                "critical": bool(entry.get("critical")),
                "outcome": outcome,
                "findings": [f.get("id") for f in relevant],
            }
        )

    detected = [r for r in rows if r["outcome"] == DETECTED]
    flagged = [r for r in rows if r["outcome"] == FLAGGED]
    missed = [r for r in rows if r["outcome"] == MISSED]
    critical = [r for r in rows if r["critical"]]
    critical_missed = [r for r in critical if r["outcome"] in (MISSED, PASSED_CLEAN)]

    total = len(rows)
    recall = len(detected) / total if total else 0.0
    critical_recall = (
        len([r for r in critical if r["outcome"] == DETECTED]) / len(critical) if critical else 1.0
    )
    false_passes = [r for r in rows if r["outcome"] == PASSED_CLEAN]

    if args.json:
        print(json.dumps({
            "total": total,
            "detected": len(detected),
            "flagged": len(flagged),
            "missed": len(missed),
            "recall": round(recall, 4),
            "critical_total": len(critical),
            "critical_recall": round(critical_recall, 4),
            "false_passes": len(false_passes),
            "rows": rows,
        }, indent=2))
    else:
        print("=" * 72)
        print("Alpha overlooker — scored against the answer key")
        print("=" * 72)
        for r in rows:
            mark = {
                DETECTED: "DETECTED",
                FLAGGED: "FLAGGED",
                MISSED: "MISSED  ",
                PASSED_CLEAN: "FALSELY PASSED",
            }.get(r["outcome"], r["outcome"])
            crit = " (critical)" if r["critical"] else ""
            print(f"  {mark:<14} {r['id']:<20} {r['defect_class'] or '':<14}{crit}")
        print("-" * 72)
        print(f"cases              {total}")
        print(f"detected           {len(detected)}")
        print(f"flagged (near miss){len(flagged)}")
        print(f"missed             {len(missed)}")
        print(f"recall             {recall:.0%}   (A1 target: >= 90%)")
        print(f"critical recall    {critical_recall:.0%}   over {len(critical)} cases")
        print(f"false passes       {len(false_passes)}   (A1 target: 0 on critical classes)")
        print()
        if critical_missed:
            print("GATE: BLOCKED — a critical defect was not detected.")
        else:
            print("GATE: every critical defect was detected.")
        if recall < 0.9:
            print("GATE: below the 90% recall target.")
        print()
        print("This measures the OVERLOOKER on a set of planted defects.")
        print("It does not measure whether the product is correct, and it is not")
        print("a product guarantee. A board can pass this and still be wrong.")

    return 0 if recall >= 0.9 and not critical_missed else 1


if __name__ == "__main__":
    raise SystemExit(main())
