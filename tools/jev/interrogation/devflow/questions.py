"""Question sets for the devflow interrogation. Written and hashed before any Jev call.

Template wordings are copied verbatim from tools/jev/templates/ci_triage.questions.json (B15).
"Explicit" wordings are this study's pre-registered rewrites (criteria that name the evidence).
Variants:
  orig   - the question set as written
  rev    - Choice: criteria order reversed; Noul: the negated-polarity question; Score: levels reversed
  rep    - identical to orig (determinism check)
  blind  - orig questions on a state with the artifact removed
"""
import copy
import json
import pathlib

TEMPLATE_FILE = pathlib.Path(__file__).resolve().parents[2] / "templates" / "ci_triage.questions.json"
_TEMPLATE = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))

# ------------------------------------------------------------------ T1 entry_covers_diff
T1_TEMPLATE = {"entry_covers_diff": _TEMPLATE["entry_covers_diff"]}
T1_EXPLICIT = {"entry_covers_diff_explicit": {
    "type": "choice",
    "instructions": ("`decision_entry` was submitted as the decisions.md record for the commit described in "
                     "`commit` (its subject, diffstat and diff_summary). Judge whether the entry covers what "
                     "this commit changed."),
    "criteria": {
        "covers": ("The entry is about this commit's change, and every substantive change listed in the commit "
                   "(each changed source module, new class or function group, and any VERSION change) is named "
                   "or plainly described in the entry. Test files do not need to be named."),
        "partially_covers_missing_named_item": (
            "The entry is about this commit's change, but at least one substantive changed source module, "
            "class or function group, or VERSION change listed in the commit is not mentioned or described "
            "anywhere in the entry."),
        "unrelated": ("The entry describes a different change: its subject does not match the commit subject, "
                      "and the modules it discusses are mostly not the ones this commit changed."),
        "need_more_information": "The commit data or the entry is missing or empty, so coverage cannot be judged.",
    }}}

# ------------------------------------------------------------------ T2 failure_class
T2_TEMPLATE = {"failure_class": _TEMPLATE["failure_class"]}
T2_EXPLICIT = {"failure_class_explicit": {
    "type": "choice",
    "instructions": "`failure` is the output of one failing pytest test. What kind of failure is it?",
    "criteria": {
        "infra_hiccup": (
            "The failure comes from the test environment, not from the code's results: the traceback shows an "
            "environment exception such as FileNotFoundError for an executable (ngspice, pio), connection "
            "refused or cannot connect (PostgreSQL, Redis, network), subprocess.TimeoutExpired or a test "
            "timeout, or PermissionError / no space left on a temporary file."),
        "accuracy_disagreement": (
            "The code ran and produced a numeric result, and an assertion compares it with an expected value, "
            "bound or tolerance and finds it outside (for example 'x% off', 'exceeds the 2% gate', 'outside "
            "proven band', 'assert a <= tol', a pytest.approx mismatch). No environment exception appears."),
        "test_nondeterminism_bug": (
            "The traceback shows that the result depends on test order, on state leaked from another test, on "
            "an unseeded random draw, or on hash or set iteration order."),
        "unknown": (
            "The traceback does not show which of the above caused the failure (a bare assert, a missing key or "
            "an empty result with no cause shown, a crash with no detail), or it is an ordinary code bug that "
            "fits none of the above."),
    }}}

# ------------------------------------------------------------------ T3 doc drift
T3_NOUL = {"contradicts_derived_fact": {
    "type": "noul",
    "instructions": ("Does `paragraph` (from the document named in `document`) state something about the "
                     "project's current state that contradicts `derived_facts`?"),
    "criteria": {
        "true": ("Yes: the paragraph presents as currently true a count, version, status, phase, capability or "
                 "file that conflicts with a value in `derived_facts`."),
        "false": ("No: everything the paragraph states is consistent with `derived_facts`, or `derived_facts` "
                  "does not address it, or the differing statement is explicitly dated in the past (for example "
                  "'as of 2026-08-07') or belongs to a document described as a frozen snapshot."),
    }}}
T3_NOUL_NEG = {"consistent_with_derived_facts": {
    "type": "noul",
    "instructions": ("Is everything `paragraph` (from the document named in `document`) states about the "
                     "project's current state consistent with `derived_facts`?"),
    "criteria": {
        "true": ("Yes: consistent with `derived_facts`, or not addressed by it, or the differing statement is "
                 "explicitly dated in the past or belongs to a document described as a frozen snapshot."),
        "false": ("No: the paragraph presents as currently true a count, version, status, phase, capability or "
                  "file that conflicts with a value in `derived_facts`."),
    }}}
T3_CHOICE = {"drift_status": {
    "type": "choice",
    "instructions": "How does `paragraph` relate to `derived_facts`?",
    "criteria": {
        "contradicts_current_fact": ("The paragraph presents as currently true something that conflicts with a "
                                     "value in `derived_facts`."),
        "consistent_or_historical": ("What the paragraph says matches `derived_facts`, or any differing number is "
                                     "explicitly dated in the past or in a frozen snapshot document."),
        "facts_do_not_address": "`derived_facts` says nothing about what the paragraph describes.",
        "need_more_information": "The paragraph or the facts are missing, so no comparison is possible.",
    }}}

# ------------------------------------------------------------------ Decision-entry quality
_SHAPE = ("The decisions.md entry shape in this project has five elements: (1) a dated heading "
          "'## [YYYY-MM-DD] title'; (2) an explicit statement of what was decided; (3) the reasons for it; "
          "(4) alternatives that were considered and rejected; (5) a trigger or condition for revisiting the "
          "decision, or a deferred follow-up tied to a condition.")
_LEVELS = ["None of the five elements is present.",
           "Exactly one of the five elements is present.",
           "Two of the five elements are present.",
           "Three of the five elements are present.",
           "Four of the five elements are present.",
           "All five elements are present."]
Q_SCORE = {"entry_shape": {"type": "score",
                           "instructions": _SHAPE + " Rate `entry` by how many of the five it contains.",
                           "criteria": list(_LEVELS)}}
Q_SCORE_REV = {"entry_shape_rev": {"type": "score",
                                   "instructions": _SHAPE + " Rate `entry` by how many of the five it contains.",
                                   "criteria": list(reversed(_LEVELS))}}
_ELEMENTS = {
    "el_date": ("Does `entry` begin with a dated heading of the form '## [YYYY-MM-DD] title'?",
                "Is the date missing from the heading of `entry` (no '## [YYYY-MM-DD] title' form)?"),
    "el_decision": ("Does `entry` state explicitly what was decided (a 'Decision:' line or an equivalent plain "
                    "statement of the choice made)?",
                    "Is an explicit statement of what was decided missing from `entry`?"),
    "el_reason": ("Does `entry` give the reasons for the decision?",
                  "Are the reasons for the decision missing from `entry`?"),
    "el_alternatives": ("Does `entry` name at least one alternative that was considered and rejected?",
                        "Is `entry` missing any alternative that was considered and rejected?"),
    "el_trigger": ("Does `entry` state a trigger or condition under which the decision should be revisited, "
                   "or a deferred follow-up tied to a condition?",
                   "Is `entry` missing any trigger or condition for revisiting the decision?"),
}
Q_ELEMENTS = {k: {"type": "noul", "instructions": v[0]} for k, v in _ELEMENTS.items()}
Q_ELEMENTS_NEG = {k + "_missing": {"type": "noul", "instructions": v[1]} for k, v in _ELEMENTS.items()}

# ------------------------------------------------------------------ T4 needs_owner_attention
T4 = {"needs_owner_attention": {
    "type": "choice",
    "instructions": ("`pull_request` is a proposed change to Circuit OS (title, description, diffstat and a diff "
                     "excerpt). Decide whether the project owner must review it because it touches an "
                     "owner-reserved area, listed in `owner_reserved_areas`."),
    "criteria": {
        "owner_reserved": ("The change touches at least one owner-reserved area: live or vendor pricing (X7), the "
                           "sign-off hash or the signed property sentences, a generator VERSION, IR field names, "
                           "RS-485 default parts or DE/RE biasing, the project licence, or the explainer's "
                           "token/cost budget. Judge by what the diff does, not by the tone of the description."),
        "engineering_only": ("Code, test, CI or tooling change that touches none of the owner-reserved areas."),
        "docs_only": "Only documentation or prose files change; no code, tests or configuration.",
        "need_more_information": "The pull request gives too little to tell what it changes.",
    }}}
OWNER_RESERVED_AREAS = [
    "Live or vendor pricing (X7): any runtime price lookup from Digikey, LCSC, Mouser or similar needs explicit owner approval; Phase 2 pricing is static.",
    "The sign-off hash: how signed property sentences are canonicalised and hashed, and the sentences themselves.",
    "Any generator VERSION constant (rc_lowpass, voltage_divider, led_indicator, dht22_node, rs485_node).",
    "IR field names (CircuitIR, IntentIR): field names are locked.",
    "RS-485 default parts and biasing, including a DE/RE pull-down (an open owner decision).",
    "The project licence (AGPL-3.0).",
    "The explainer's token budget or model cost (raising max_tokens is an owner decision).",
]

# ------------------------------------------------------------------ Commit convention
CONV = {"commit_convention": {
    "type": "choice",
    "instructions": "Which commit-message convention does the commit subject in `subject` follow?",
    "criteria": {
        "conventional": ("Conventional Commits: starts with one of the lowercase types feat, fix, test, docs, "
                         "chore, refactor, perf, build, ci, style or revert, optionally followed by a scope in "
                         "parentheses and '!', then a colon and a space, e.g. 'fix(ai): ...' or 'docs: ...'."),
        "brain": "Starts with the lowercase prefix 'brain:' followed by a space.",
        "session": "Starts with the lowercase prefix 'session:' followed by a space.",
        "other": ("Anything else, including other prefixes such as 'memory:', combined types such as 'test+fix:', "
                  "capitalised types, a missing space after the colon, or plain sentences."),
    }}}


# ------------------------------------------------------------------ variant transforms
def reverse_choices(qs):
    out = {}
    for name, q in qs.items():
        q = copy.deepcopy(q)
        if q["type"] == "choice":
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
        out[name] = q
    return out


TASK_QUESTIONS = {
    # task: {variant: questions}
    "T1": {"orig": {**T1_TEMPLATE, **T1_EXPLICIT},
           "rev": reverse_choices({**T1_TEMPLATE, **T1_EXPLICIT}),
           "unpacked_template": T1_TEMPLATE},
    "T2": {"orig": {**T2_TEMPLATE, **T2_EXPLICIT},
           "rev": reverse_choices({**T2_TEMPLATE, **T2_EXPLICIT})},
    "T3": {"orig": {**T3_NOUL, **T3_CHOICE},
           "rev": {**T3_NOUL_NEG, **reverse_choices(T3_CHOICE)}},
    "Q": {"orig": {**Q_SCORE, **Q_ELEMENTS},
          "rev": {**Q_SCORE_REV, **Q_ELEMENTS_NEG}},
    "T4": {"orig": T4, "rev": reverse_choices(T4)},
    "CONV": {"orig": CONV, "rev": reverse_choices(CONV)},
}


def questions_for(task, variant):
    base = "orig" if variant in ("orig", "rep", "blind", "blind_partial") else variant
    return copy.deepcopy(TASK_QUESTIONS[task][base])
