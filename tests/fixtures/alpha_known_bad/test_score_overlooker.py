"""
test_score_overlooker.py — does the scorer measure what it claims to measure?

WHY THIS FILE EXISTS
--------------------
`score_overlooker.py` is the instrument that decides whether Alpha stage A1
exits. It reads a planted-defect set and an overlooker's report and returns a
recall number. An instrument that cannot be wrong is not an instrument: if the
scorer has a bug that makes every case look detected, or makes a false pass
unreachable, then the number it prints is a decoration.

So the scorer gets its own tests, and they are tests of the SCORER, not of
the product. The product's behaviour is measured elsewhere
(`verify_calibration.py` measures the verifier; the overlooker run measures
the overlooker).

THE FIVE THINGS THAT HAD TO BE PROVEN
--------------------------------------
1. A finding that names the fault scores DETECTED.
2. A finding that notices the board but not the fault scores FLAGGED.
3. A finding that says the board is FINE scores PASSED_CLEAN — the false
   pass. This outcome was unreachable before 2026-10-21, which meant the
   A1 gate "0 false passes on the critical classes" could not fail. A gate
   that cannot fail is not a gate.
4. A finding about a DIFFERENT board does not count against this case.
5. A finding that merely names a CHECK ("the product has no check for
   shorts") is NOT a detection of a short. Without this rule a single
   sentence about a missing rule would score as finding the fault, which is
   exactly backwards.

    python -m pytest tests/fixtures/alpha_known_bad/test_score_overlooker.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Load the scorer. It lives in .claude/shared-memory/alpha/, not in the
# package tree, so it is loaded by path.
# ─────────────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
# alpha_known_bad -> fixtures -> tests -> repo root
_SCORER = _HERE.parents[2] / ".claude" / "shared-memory" / "alpha" / "score_overlooker.py"

#: The marker that says the calibration set is FINISHED: every case the handoff
#: names is on disk, with a manifest, and the key covers all of them. Until
#: it exists, the set is still being built and the completeness test waits.
_COMPLETE_MARKER = _HERE / "CALIBRATION_COMPLETE"
_CALIBRATION_COMPLETE = _COMPLETE_MARKER

_spec = importlib.util.spec_from_file_location("score_overlooker", _SCORER)
assert _spec and _spec.loader, f"cannot load the scorer at {_SCORER}"
_scorer = importlib.util.module_from_spec(_spec)
sys.modules["score_overlooker"] = _scorer
_spec.loader.exec_module(_scorer)

DETECTED = _scorer.DETECTED
FLAGGED = _scorer.FLAGGED
MISSED = _scorer.MISSED
PASSED_CLEAN = _scorer.PASSED_CLEAN


def _finding(**kw) -> dict:
    """One finding, in the shape the scorer reads."""
    base = {"id": "X-0001", "severity": "critical", "observed": "",
            "expected": "", "evidence": "", "artifact": "", "detail": ""}
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────────────────────
class TestTheFourOutcomesAreReachable:
    """Each outcome must be reachable, or the score has a hole in it."""

    def test_a_named_fault_is_detected(self):
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_cut_track.json",
                             observed="a track is cut: no copper path joins the two pads")]
        outcome, relevant = _scorer._classify(key, findings)
        assert outcome == DETECTED
        assert len(relevant) == 1

    def test_a_named_check_is_detected(self):
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"], "detection_keywords": [],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_cut_track.json",
                             observed="III.1 fails: 1 of 12 required connections has no copper path")]
        assert _scorer._classify(key, findings)[0] == DETECTED

    def test_noticing_the_board_without_naming_the_fault_is_flagged(self):
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_cut_track.json",
                             observed="something is off about the routing on this board")]
        assert _scorer._classify(key, findings)[0] == FLAGGED

    def test_saying_the_board_is_fine_is_a_false_pass(self):
        """THE ONE THAT MATTERS MOST.

        Before 2026-10-21 the scorer could never return PASSED_CLEAN, so the
        A1 gate '0 false passes on the critical classes' was a gate that
        could not fail. This test is the regression that keeps it real.
        """
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_cut_track.json",
                             observed="the board has no faults: every connection is routed")]
        assert _scorer._classify(key, findings)[0] == PASSED_CLEAN

    def test_a_clean_bill_that_names_a_missing_check_is_not_a_false_pass(self):
        """Reporting that a check does not exist is reporting a GAP, not
        passing the board. Those are different findings and must score
        differently."""
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_cut_track.json",
                             observed="the product has no check for cut tracks, "
                                      "so it cannot detect them")]
        outcome, _ = _scorer._classify(key, findings)
        assert outcome == FLAGGED, (
            "a gap report is a near miss, not a clean bill and not a detection"
        )

    def test_saying_nothing_about_the_board_is_missed(self):
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_something_else.json",
                             observed="the voltage divider's resistor is mislabelled")]
        assert _scorer._classify(key, findings)[0] == MISSED


# ─────────────────────────────────────────────────────────────────────────────
class TestTheRulesThatStopFalseDetections:
    """A finding about a different board, or about a CHECK, is not a finding."""

    def test_a_finding_about_another_board_does_not_count(self):
        key = {"id": "cut_track", "defect_class": "open", "critical": True,
               "expected_check_ids": ["III.1"],
               "detection_keywords": ["cut track", "no copper path"],
               "artifact_hint": "cut_track",
               "artifact_names": ["board_cut_track.json"]}
        findings = [_finding(artifact="board_something_else.json",
                             observed="no copper path on the other board")]
        assert _scorer._classify(key, findings)[0] == MISSED

    def test_naming_a_missing_check_is_not_finding_the_fault(self):
        """The backwards case: 'the product has no check for shorts' must not
        score as 'found a short'."""
        key = {"id": "bridged_nets", "defect_class": "short", "critical": True,
               "expected_check_ids": ["III.2"],
               "detection_keywords": ["short circuit", "is short", "shorted"],
               "artifact_hint": "bridged_nets",
               "artifact_names": ["board_bridged_nets.json"]}
        findings = [_finding(artifact="board_bridged_nets.json",
                             observed="the product has no check for shorts, "
                                      "so a short would not be caught")]
        outcome, _ = _scorer._classify(key, findings)
        assert outcome != DETECTED, (
            "a report that a CHECK IS MISSING is not a report that the fault EXISTS"
        )
        assert outcome == FLAGGED

    def test_a_class_word_beside_a_fault_word_counts(self):
        """The KEY's own phrases are what count. 'shorted together' is one of
        the phrases the key lists for a short, so it detects."""
        key = {"id": "bridged_nets", "defect_class": "short", "critical": True,
               "expected_check_ids": ["III.2"],
               "detection_keywords": ["short circuit", "is short", "shorted"],
               "artifact_hint": "bridged_nets",
               "artifact_names": ["board_bridged_nets.json"]}
        findings = [_finding(artifact="board_bridged_nets.json",
                             observed="two nets are shorted together by a solder bridge")]
        assert _scorer._classify(key, findings)[0] == DETECTED

    def test_a_class_word_alone_does_not_count(self):
        """A finding that mentions the class as a TOPIC, not as a fault seen,
        is not a detection. 'short-detection rule' is about a rule; it is not
        a short."""
        key = {"id": "bridged_nets", "defect_class": "short", "critical": True,
               "expected_check_ids": ["III.2"],
               "detection_keywords": ["short circuit", "is short", "shorted"],
               "artifact_hint": "bridged_nets",
               "artifact_names": ["board_bridged_nets.json"]}
        findings = [_finding(artifact="board_bridged_nets.json",
                             observed="the short-detection rule in the product is undocumented")]
        assert _scorer._classify(key, findings)[0] != DETECTED


# ─────────────────────────────────────────────────────────────────────────────
class TestTheKeyIsWellFormed:
    """The key is the answer. A malformed key is a wrong answer."""

    def _key(self) -> dict:
        import json
        return json.loads((_HERE / "KEY.json").read_text(encoding="utf-8"))

    def test_every_case_has_the_fields_the_scorer_reads(self):
        for case in self._key()["cases"]:
            for field in ("id", "defect_class", "critical", "expected_check_ids",
                          "detection_keywords", "artifact_hint"):
                assert field in case, f"case {case.get('id')} has no {field}"

    def test_the_case_ids_are_unique(self):
        ids = [c["id"] for c in self._key()["cases"]]
        assert len(ids) == len(set(ids))

    def test_the_key_covers_every_seeded_case_on_disk(self):
        """A seeded case with no key entry is a defect that cannot be scored,
        and a defect that cannot be scored is a defect nobody is measuring."""
        on_disk = {p.name for p in _HERE.iterdir()
                   if p.is_dir() and (p / "manifest.json").exists()}
        in_key = {c["id"] for c in self._key()["cases"]}
        missing = on_disk - in_key
        assert not missing, f"seeded cases with no key entry: {sorted(missing)}"

    def test_every_key_entry_has_a_case_on_disk(self):
        """The key may name a case that is still being built, but it may not
        name one that does not exist and is not on the way.

        A case under construction is a directory with a `mutate.py` and no
        `manifest.json` yet. A key entry for it is fine — the key is written
        before the case is finished. A key entry for a directory that does
        not exist at all is a mistake.
        """
        dirs = {p.name for p in _HERE.iterdir() if p.is_dir()}
        on_disk = {p.name for p in _HERE.iterdir()
                   if p.is_dir() and (p / "manifest.json").exists()}
        in_key = {c["id"] for c in self._key()["cases"]}
        # A key entry with no directory at all is only a mistake once the
        # calibration set is declared complete. Until then, the master
        # session writes the key before the builders finish, and this test
        # would fail for a legitimate reason.
        if not _CALIBRATION_COMPLETE.exists():
            pytest.skip("the calibration set is still being built")
        extra = in_key - dirs
        assert not extra, (
            f"key entries with no case directory at all: {sorted(extra)}"
        )
        # A key entry for a case that is neither finished nor under
        # construction is a mistake; a directory with neither manifest.json
        # nor mutate.py is an empty leftover.
        unfinished = in_key - on_disk
        for case_id in unfinished:
            assert (_HERE / case_id / "mutate.py").exists(), (
                f"key names {case_id}, but it is neither a finished case nor "
                f"one under construction (no mutate.py)"
            )

    def test_the_critical_classes_match_the_handoff(self):
        """The handoff names five: short, open, wrong pinout, reversed diode,
        creepage. A critical case outside that set is a judgement call that
        belongs to the owner, not to the scorer."""
        handoff = {"short", "open", "wrong pinout", "reversed diode", "creepage"}
        for case in self._key()["cases"]:
            if case["critical"]:
                assert case["defect_class"] in handoff, (
                    f"{case['id']} is critical but its class "
                    f"'{case['defect_class']}' is not one of the handoff's five"
                )


# ─────────────────────────────────────────────────────────────────────────────
class TestTheGateCanFail:
    """The gate is the whole point of the stage. Prove it can fail."""

    def _key(self) -> dict:
        import json
        return json.loads((_HERE / "KEY.json").read_text(encoding="utf-8"))

    def test_a_missed_critical_defect_blocks_the_gate(self, tmp_path, monkeypatch):
        import json
        key = self._key()
        # A findings file that says nothing about any case.
        findings = tmp_path / "empty.jsonl"
        findings.write_text("", encoding="utf-8")
        monkeypatch.setattr(sys, "argv",
                            ["score_overlooker.py", "--findings", str(findings),
                             "--key", str(_HERE / "KEY.json")])
        assert _scorer.main() == 1, "the gate passed with nothing detected"

    def test_a_false_pass_on_a_critical_class_blocks_the_gate(self, tmp_path, monkeypatch):
        import json
        key = self._key()
        critical = [c for c in key["cases"] if c["critical"]]
        assert critical, "the key has no critical cases to test with"
        # A findings file that passes every critical board as clean.
        lines = []
        for case in critical:
            lines.append(json.dumps({
                "id": f"F-{case['id']}",
                "severity": "minor",
                "artifact": f"{case['artifact_hint']}/board_defective.json",
                "observed": "the board has no faults; every check passes",
            }))
        findings = tmp_path / "clean.jsonl"
        findings.write_text("\n".join(lines) + "\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv",
                            ["score_overlooker.py", "--findings", str(findings),
                             "--key", str(_HERE / "KEY.json")])
        assert _scorer.main() == 1, "the gate passed with a false pass on a critical class"

    def test_a_full_detection_passes_the_gate(self, tmp_path, monkeypatch):
        import json
        key = self._key()
        lines = []
        for case in key["cases"]:
            kw = (case["detection_keywords"] or [""])[0]
            lines.append(json.dumps({
                "id": f"F-{case['id']}",
                "severity": "critical",
                "artifact": f"{case['artifact_hint']}/board_defective.json",
                "observed": f"found {kw}",
            }))
        findings = tmp_path / "all.jsonl"
        findings.write_text("\n".join(lines) + "\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv",
                            ["score_overlooker.py", "--findings", str(findings),
                             "--key", str(_HERE / "KEY.json")])
        assert _scorer.main() == 0, "the gate failed on a perfect detection run"
