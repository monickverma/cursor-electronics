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

WHAT WAS FIXED ON 2026-10-22, AND WHY
-------------------------------------
Two defects in this scorer were found by reading the runs it had already
scored. Both of them moved the number, and neither moved it honestly.

  1. A MISSED DETECTION. The key's phrases were matched against a text that
     had been normalised (underscores turned into spaces) while the phrases
     themselves were not. So a net name written `relay_ctrl` in the key could
     never match `RELAY_CTRL` in a finding, and a detection that named the
     fault was scored as a miss. Fixed: both sides are normalised the same
     way now.

  2. A FALSE CLEAN BILL. The clean-bill test was a substring search for
     "is correct" and "passed". It fired on "the flyback diode IS CORRECT
     under a 'pad 1 = cathode' convention" and on "the 2N2222A is BYPASSED",
     and turned a board the overlooker had refused to send to a fab into a
     false pass. Fixed: a clean bill now has to be a claim ABOUT THE BOARD,
     said without a hedge and without a negation. A remark about one part is
     not a verdict on the board.

Two things were also added, both of which make the instrument sharper rather
than kinder:

  3. NEAR-MISS KEYWORDS. The key can now list words that name the PART
     involved ("2n2222a", "dht22_data") separately from words that name the
     FAULT. A finding that only names the part is a near miss, not a
     detection. Before this, a finding that merely mentioned the transistor
     scored as finding a transposed transistor.

  4. A VALUE CHECK. One seeded defect is a wrong value: the fitted
     capacitance is not the one the request names. A phrase list cannot
     catch that in every wording — "a factor of ten below the value the
     request named" is as much a detection as "wrong capacitor value" is. So
     a case can now declare the value the design specifies, and a finding
     that states BOTH that value and a different one has named the fault,
     whatever words it used. The rule comes from the defect, not from any one
     run's phrasing.

    python .claude/shared-memory/alpha/score_overlooker.py --findings <path> [--key <path>]
    python .claude/shared-memory/alpha/score_overlooker.py --findings <path> --json
    python .claude/shared-memory/alpha/score_overlooker.py --findings <path> --explain
"""
from __future__ import annotations

import argparse
import json
import re
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


# ─────────────────────────────────────────────────────────────────────────────
# A clean bill: the claim that the board is fault-free.
#
# A false pass is the outcome that blocks the stage, so the test for it has
# to be exact. Five things must all hold before a piece of text counts as
# the overlooker saying the board is fine:
#
#   1. it says a fault is absent (the phrase list),
#   2. it says so about the BOARD — a remark about one part is not a verdict
#      on the board ("the diode is correct" is not "the board is correct"),
#   3. it is not negated ("the board is NOT passed as clean" is the opposite
#      of a clean bill),
#   4. it is not hedged ("under a 'pad 1 = cathode' convention the diode is
#      correct" is a conditional remark about a part, not a verdict),
#   5. the finding it sits in reports no defect of its own. A finding that
#      complains about something and says the board is correct is a
#      complaint, not a clean bill.
# ─────────────────────────────────────────────────────────────────────────────

#: Claims that a fault is absent.
_CLEAN_PHRASES = (
    "no faults", "no defects", "no problems", "no issues", "no error",
    "no errors", "no findings", "no violations", "no discrepancy",
    "no mismatch", "nothing wrong", "everything is correct",
    "every check passes", "all checks pass", "is correct", "are correct",
    "looks correct", "appears correct", "is clean", "are clean",
    "passed", "passes the check", "no short", "no open",
)

#: What a clean claim has to be about. The thing under test is the board.
_CLEAN_SUBJECTS = (
    "board", "design", "layout", "netlist", "pcb", "schematic", "artifact",
    "everything", "all checks", "all the checks", "whole board",
)

#: Words that make a sentence conditional. A conditional remark is not a
#: verdict, whatever else it says.
_CLEAN_HEDGES = re.compile(
    r"\b(under|assuming|unless|otherwise|either|perhaps|possibly|"
    r"presumably|convention|if|would be|could be|could have been|"
    r"might be|were to be|it seems|appears to be)\b"
)

#: Words that turn a sentence into a negation. "The board is not clean" is
#: the opposite of a clean bill.
_CLEAN_NEGATIONS = re.compile(
    r"\b(not|never|nor|neither|no way|cannot|isn t|wasn t|doesn t|don t|"
    r"didn t|won t|couldn t|shouldn t)\b"
)

#: Words that mean the finding is reporting a defect. A finding that reports
#: a defect is not a clean bill, however politely it is worded.
_DEFECT_WORDS = re.compile(
    r"\b(missing|absent|wrong|incorrect|instead|broken|breaks?|fails?|failed|"
    r"failure|cannot|never|mismatch|disagree|understate|omitted|omission|"
    r"dropped|drops?|unconnect|dangling|lacks?|reversed|reversed|"
    r"transposed|backwards|faulty|defective)\b"
)

#: A clause boundary: a sentence end, or a contrast that starts a new claim.
#: A full stop BETWEEN DIGITS is a decimal point, not a sentence end. A
#: splitter that treats "0.35 mm" as two clauses cannot read the measurement
#: at all, and a measurement is exactly what the gap rule is about.
_CLAUSE_SPLIT = re.compile(
    r"(?:[!?;:]|\n)|(?:(?<!\d)\.|\.(?!\d))|"
    r"(?:\bbut\b|\bhowever\b|\balthough\b|\bthough\b|"
    r"\bexcept\b|\baside from\b|\bnevertheless\b)"
)


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text or "") if c and c.strip()]


def _clean_phrase_in(clause: str) -> str | None:
    """The clean phrase this clause claims, if it claims one."""
    for phrase in _CLEAN_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", clause):
            return phrase
    return None


def _says_clean(text: str) -> bool:
    """Does this text say the board is fine?

    The text is one finding's `observed` field. It has to carry a clean
    claim ABOUT THE BOARD, said flatly, in a finding that reports no defect
    of its own. A finding that merely fails to name a fault is a near miss,
    not a false pass — the difference matters, because a false pass is the
    one outcome that blocks the stage.
    """
    if not text:
        return False
    # The defect check runs on the text with the clean phrases taken out, so
    # that "nothing wrong" is not read as the word "wrong".
    residual = text
    for phrase in _CLEAN_PHRASES:
        residual = re.sub(rf"\b{re.escape(phrase)}\b", " ", residual)
    if _DEFECT_WORDS.search(residual):
        # This finding reports a defect. It cannot also be a clean bill,
        # however correct it says some other part of the board is.
        return False
    for clause in _clauses(text):
        phrase = _clean_phrase_in(clause)
        if not phrase:
            continue
        if _CLEAN_NEGATIONS.search(clause):
            continue
        if _CLEAN_HEDGES.search(clause):
            continue
        if not any(re.search(rf"\b{re.escape(s)}\b", clause) for s in _CLEAN_SUBJECTS):
            # A remark about one part is not a verdict on the board.
            continue
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# The value check: a finding that states the specified value AND a different
# one has named a wrong-value defect, whatever words it used.
# ─────────────────────────────────────────────────────────────────────────────

#: A capacitance with a unit prefix. The prefix is required: "7 F" out of a
#: part number ("1N4148W-7-F") is not seven farads, and reading it as one
#: would invent a fault that is not there.
_CAPACITANCE = re.compile(r"(\d+(?:\.\d+)?)\s*(p|n|u|µ|μ|m)\s*f\b")
_CAP_SCALE = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3}

#: A length on a board. "mm" is what a board measurement uses. Bare "m" is
#: left out on purpose: "2 m" in a finding is usually a cable length, and
#: reading it as a board measurement would invent a fault.
_LENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mm|cm|mil|inch|in)\b")
_LENGTH_SCALE = {"mm": 1e-3, "cm": 1e-2, "mil": 25.4e-6, "inch": 25.4e-3, "in": 25.4e-3}

#: Words that make a number a measurement of a SPACE between two things. A
#: number only counts as a gap when the sentence it sits in is talking about
#: a space: "the 0.25 mm track" is a track width, not a clearance, and reading
#: it as one would invent a fault that is not there.
_GAP_WORDS = (
    "gap", "clearance", "creepage", "spacing", "separation",
    "insulation", "isolation",
)

#: Words that are only a gap word in company. "0.35 mm from the data net" is
#: a separation; "0.35 mm from the pad centre" is a placement. A case that
#: wants these has to say what the finding has to be about.
_WEAK_GAP_WORDS = ("apart", "between", "distance", "from", "nearest", "closest")

#: Words that make a number a FEATURE, not a space, when they sit right next
#: to it. A hole size, a track width and a drill diameter are all
#: measurements, and none of them is a clearance. The window is short on
#: purpose: in "the 0.35 mm gap between the track and the edge", the word
#: "track" is part of what is being measured apart, not a feature size.
_FEATURE_AFTER = (
    "track", "width", "hole", "drill", "diameter", "radius", "annular",
    "pitch", "thick", "thickness", "pad",
)
_FEATURE_BEFORE = (
    "width", "hole", "drill", "diameter", "radius", "annular", "pitch",
    "thick", "thickness",
)

#: A gap word followed by a word about CONFIGURATION. "the 0.2 mm clearance
#: rules in the project file are set to zero" is a statement about a rule
#: the product has configured, not a measurement of the board. The number
#: beside it is the rule's value, and reading it as a clearance would
#: invent a fault that is not there.
_CONFIGURED_CLEARANCE = re.compile(
    r"\b(?:gap|clearance|creepage|spacing|separation|insulation|isolation)"
    r"\s+(?:rules?|limits?|settings?|configured|constraints?)\b"
)


def _strip_thousands(text: str) -> str:
    """'10,000 pF' is ten thousand picofarads, not ten and 000.

    Only a thousands separator is removed. A comma that is not a thousands
    group ('0,350') is a decimal comma in some languages, and dropping it
    would turn 0.35 into 350.
    """
    return re.sub(r"(?<!\d)([1-9]\d{0,2}),(\d{3})(?!\d)", r"\1\2", text)


def _capacitances(text: str) -> list[float]:
    """Every capacitance in farads that this text states."""
    found = []
    cleaned = _strip_thousands(text or "").lower()
    for number, prefix in _CAPACITANCE.findall(cleaned):
        try:
            value = float(number)
        except ValueError:
            continue
        found.append(value * _CAP_SCALE[prefix])
    return found


def _length_matches(text: str) -> list[tuple[float, int, int]]:
    """Every length in metres that this text states, and where it is."""
    out: list[tuple[float, int, int]] = []
    cleaned = _strip_thousands(text or "").lower()
    for match in _LENGTH.finditer(cleaned):
        try:
            value = float(match.group(1)) * _LENGTH_SCALE[match.group(2)]
        except ValueError:
            continue
        out.append((value, match.start(), match.end()))
    return out


def _lengths(text: str) -> list[float]:
    """Every length in metres that this text states."""
    return [value for value, _, _ in _length_matches(text)]


def _gap_measurements(text: str, value_check: dict | None = None) -> list[float]:
    """Lengths this text states as a measurement of a space between things.

    The number alone is not enough. "the 0.25 mm track" is a track width and
    "the 0.35 mm gap between the mains net and the SELV net" is a clearance
    fault, and only the second one is a defect. So a number counts only when
    the sentence it sits in is talking about a space, and only when the words
    around it are not about a feature.

    A case can say what counts for it: `gap_words` replaces the strong list,
    `weak_gap_words` adds words that only count when the finding as a whole
    is about the thing the case names (`context_words`).
    """
    value_check = value_check or {}
    strong = tuple(value_check.get("gap_words") or _GAP_WORDS)
    weak = tuple(value_check.get("weak_gap_words") or _WEAK_GAP_WORDS)
    context = tuple(value_check.get("context_words") or ())
    context_ok = any(word in text for word in context)
    out: list[float] = []
    for clause in _clauses(text):
        has_strong = any(word in clause for word in strong)
        # The weak words only count when the case has said what the finding
        # has to be about, and the finding is about it.
        has_weak = bool(context) and context_ok and any(word in clause for word in weak)
        if not (has_strong or has_weak):
            continue
        configured = [m.span() for m in _CONFIGURED_CLEARANCE.finditer(clause)]
        for value, start, end in _length_matches(clause):
            after = clause[end:end + 12]
            before = clause[max(0, start - 20):start]
            if any(word in after for word in _FEATURE_AFTER):
                continue
            if any(word in before for word in _FEATURE_BEFORE):
                continue
            if any(lo - 30 <= end and start <= hi + 30 for lo, hi in configured):
                # The number belongs to a configured rule, not to the board.
                continue
            out.append(value)
    return out


def _values_of(text: str, quantity: str) -> list[float]:
    if quantity == "length":
        return _lengths(text)
    if quantity == "capacitance":
        return _capacitances(text)
    return []


def _names_a_wrong_value(text: str, value_check: dict) -> bool:
    """Does this finding state the specified value AND a different one?

    The rule is the definition of the defect, not a phrase: a wrong value is
    a fitted value that is not the specified one, so a finding that says
    both has named it. A finding that states only the fitted value ("C1
    10nF" in a parts list) has not — it might be listing parts.

    TWO RULES, and either one is enough.

    1. THE WRONG VALUE. The finding states the value the design specifies
       and a different one.

    2. THE GAP TOO SMALL. A length case can also say how small a space is
       too small: a finding that MEASURES a gap and finds it a fraction of
       a millimetre has named the fault, whatever words it used and whatever
       requirement it compared against. The measurement has to be a gap —
       a track width is not a gap — so the number is read out of the
       sentences that talk about a space.
    """
    if not value_check:
        return False
    quantity = str(value_check.get("quantity") or "capacitance")
    specified = value_check.get("specified")
    if isinstance(specified, str):
        specified = [specified]
    tolerance = float(value_check.get("tolerance_pct", 5.0)) / 100.0
    direction = str(value_check.get("direction")
                    or ("below" if quantity == "length" else "any"))

    # Rule 2 — the gap too small.
    below = value_check.get("below")
    if below is not None and quantity == "length":
        if isinstance(below, str):
            limits = _lengths(below)
            limit = limits[0] if limits else None
        else:
            limit = float(below) * 1e-3      # a bare number is millimetres
        if limit is not None and any(
            v < limit for v in _gap_measurements(text, value_check)
        ):
            return True

    # Rule 1 — the wrong value.
    spec_values: list[float] = []
    for s in specified or []:
        spec_values.extend(_values_of(str(s), quantity))
    if not spec_values:
        return False
    values = _values_of(text, quantity)
    if not values:
        return False
    if quantity == "length":
        # The fault is a measured space, so the wrong value has to be a
        # measured space too. A track width is not a fault, and a finding
        # that says "the required clearance is 5 mm and the tracks are
        # 0.25 mm wide" has not found one.
        fault_values = _gap_measurements(text, value_check)
        if not fault_values:
            return False
    else:
        fault_values = values

    def _matches(value: float) -> bool:
        return any(abs(value - s) <= abs(s) * tolerance for s in spec_values)

    has_spec = any(_matches(v) for v in values)
    if direction == "below":
        limit = min(spec_values)
        has_other = any(v < limit * (1 - tolerance) for v in fault_values)
    else:
        has_other = any(not _matches(v) for v in fault_values)
    return has_spec and has_other


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


def _classify_detail(key_entry: dict, findings: list[dict]) -> tuple[str, list[dict], str]:
    """How the overlooker did on one seeded case, and why.

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

    The key can also list NEAR-MISS words — the name of the part involved
    ("2n2222a", "dht22_data"). A finding that only says those noticed the
    right part; it did not find the fault. That scores FLAGGED, not
    DETECTED, and the difference is the difference between "the overlooker
    found it" and "the overlooker was looking in the right place".

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
    # Both sides of the comparison are normalised the same way. A net name
    # written `relay_ctrl` in the key has to be able to match `RELAY_CTRL`
    # in a finding, and it could not before 2026-10-22.
    keywords = [_norm(k) for k in (key_entry.get("detection_keywords") or [])]
    near_words = [_norm(k) for k in (key_entry.get("near_miss_keywords") or [])]
    value_check = key_entry.get("value_check") or {}
    artifact_hint = (key_entry.get("artifact_hint") or "").lower()
    #: The name of the staged board the overlooker was handed. The staging is
    #: opaque — `artifacts/board_03` — and the number is assigned once and
    #: never reused, so a finding that names the board it was given is
    #: matched to the case it was given for.
    artifact_folder = (key_entry.get("artifact_folder") or "").lower()
    #: The file names that also identify this case's board. The early
    #: staging named each board after its case; those names are kept so an
    #: older findings file still scores.
    artifact_names = [str(a).lower() for a in (key_entry.get("artifact_names") or [])]
    case_norm = _norm(case_id)
    check_norms = [_norm(str(c)) for c in check_ids]

    def _text(f: dict) -> str:
        return _norm(" ".join(
            str(f.get(k, ""))
            for k in ("id", "observed", "expected", "evidence", "detail")
        ))

    def _observed(f: dict) -> str:
        return _norm(" ".join(
            str(f.get(k, ""))
            for k in ("observed", "detail")
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
            # carries the case's name, the staged board's name, one of the
            # case's own board file names, or a phrase the key says means
            # this board.
            if artifact_folder and artifact_folder in artifact:
                return True
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
        if any(k in blob for k in keywords + near_words):
            return True
        return False

    def _names_the_fault(text: str) -> str | None:
        """The phrase that names the fault, or None."""
        if case_norm and case_norm in text:
            return case_id
        for c in check_norms:
            if c in text:
                return c
        for k in keywords:
            if k and k in text:
                return k
        return None

    def _names_the_part(text: str) -> str | None:
        for k in near_words:
            if k and k in text:
                return k
        return None

    relevant = [f for f in findings if _about_this_board(f)]
    if not relevant:
        return MISSED, [], "no finding is about this board"

    for f in relevant:
        text = _text(f)
        if _names_a_wrong_value(text, value_check):
            # A stated value and a different stated value is the fault, in
            # any wording. A gap report never states both.
            return DETECTED, relevant, (
                f"{f.get('id')}: states the specified value and a different one"
            )
        if _is_gap_report(text):
            # A gap report never names a fault. Keep looking at the others.
            continue
        phrase = _names_the_fault(text)
        if phrase:
            return DETECTED, relevant, f"{f.get('id')}: names the fault ({phrase!r})"

    # Nothing named the fault. Did the overlooker pass the board?
    for f in relevant:
        if _is_gap_report(_text(f)):
            continue
        if _says_clean(_observed(f)):
            return PASSED_CLEAN, relevant, f"{f.get('id')}: says the board is clean"

    # The board was looked at and the part was named, but the fault was not.
    for f in relevant:
        if _is_gap_report(_text(f)):
            continue
        part = _names_the_part(_text(f))
        if part:
            return FLAGGED, relevant, f"{f.get('id')}: names the part ({part!r}), not the fault"

    return FLAGGED, relevant, "the board was looked at; the fault was not named"


def _classify(key_entry: dict, findings: list[dict]) -> tuple[str, list[dict]]:
    """The two-value form, for the tests and for callers that do not care
    why."""
    outcome, relevant, _why = _classify_detail(key_entry, findings)
    return outcome, relevant


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", required=True, type=Path, help="the overlooker's findings.jsonl")
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY, help="the answer key")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--explain", action="store_true",
                    help="say which finding decided each case, and why")
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
        outcome, relevant, why = _classify_detail(entry, findings)
        rows.append(
            {
                "id": entry.get("id"),
                "defect_class": entry.get("defect_class"),
                "critical": bool(entry.get("critical")),
                "outcome": outcome,
                "findings": [f.get("id") for f in relevant],
                "why": why,
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
            if args.explain:
                print(f"                 {r['why']}")
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
