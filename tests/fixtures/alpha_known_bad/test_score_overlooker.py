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
class TestTheValueCheck:
    """A wrong value is a value that is not the specified one.

    A phrase list cannot catch that in every wording. 'Wrong capacitor
    value' and 'a factor of ten below the value the request named' say the
    same thing; only one of them is in the key. So a case can declare the
    value the design specifies, and the scorer asks a question that does
    not depend on the words: does the finding state the specified value AND
    a different one?
    """

    def _key(self) -> dict:
        return {"id": "wrong_cap_value", "defect_class": "wrong value", "critical": False,
                "expected_check_ids": [],
                "detection_keywords": ["wrong capacitor value", "wrong value"],
                "near_miss_keywords": [],
                "value_check": {"quantity": "capacitance", "specified": "100nF",
                                "tolerance_pct": 5},
                "artifact_hint": "wrong_cap_value",
                "artifact_names": ["artifacts/board_06"]}

    def test_a_value_mismatch_is_detected_in_any_wording(self):
        """This is the wording that actually came back from the board_06 run.
        The key's phrase list did not match it, so a finding that named the
        fault exactly was scored as a miss."""
        findings = [_finding(
            artifact="artifacts/board_06",
            observed="The request asked for a 100 nF decoupling capacitor. The only "
                     "capacitor on the board is C1, whose Value field reads '10nF' and "
                     "whose MPN is K103K15X7RF53H5, where 103 = 10,000 pF = 10 nF. The "
                     "fitted part is a factor of ten below the value the request named.")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_a_parts_list_that_mentions_only_the_fitted_value_is_not_a_detection(self):
        """The other way round: a finding that lists the parts, and so quotes
        'C1 10nF', has not compared that value against the request. Crediting
        it would be crediting the wrong finding."""
        findings = [_finding(
            artifact="artifacts/board_06",
            observed="The board carries eight parts - U1 ATMEGA328P-PU, U2 DHT22, "
                     "K1 SRD-05VDC-SL-C, Q1 2N2222A, D1 1N4007, R1 10k, R2 1k, C1 10nF - "
                     "and no LED and no LED series resistor.")]
        assert _scorer._classify(self._key(), findings)[0] != DETECTED

    def test_a_value_that_is_the_specified_one_is_not_a_detection(self):
        """A finding that only quotes the correct value has not found a wrong
        value."""
        findings = [_finding(
            artifact="artifacts/board_06",
            observed="A 100 nF capacitor sits at the DHT22's VDD pin, as the request "
                     "specified.")]
        assert _scorer._classify(self._key(), findings)[0] != DETECTED

    def test_a_case_without_a_value_check_is_unaffected(self):
        """The value rule is opt-in. A case that does not declare one keeps
        the old behaviour."""
        key = self._key()
        del key["value_check"]
        findings = [_finding(
            artifact="artifacts/board_06",
            observed="C1 is 10nF and the request asked for 100 nF.")]
        assert _scorer._classify(key, findings)[0] != DETECTED


# ─────────────────────────────────────────────────────────────────────────────
class TestTheGapCheck:
    """A clearance defect is a measured space that is far too small.

    The same problem as the wrong value, one dimension over: a phrase list
    cannot catch 'mains-to-SELV creepage is 0.35 mm' in every wording. So a
    case can declare how small a gap is too small, and the scorer asks
    whether the finding MEASURED a gap and found it under the floor.

    The number has to be a gap and not a feature. 'the 0.25 mm track' is a
    track width; 'the 0.35 mm gap between the mains net and the SELV net' is
    a clearance fault. Reading the first as the second would invent a fault
    that is not there.
    """

    def _key(self) -> dict:
        return {"id": "mains_gap", "defect_class": "creepage", "critical": True,
                "expected_check_ids": [],
                "detection_keywords": ["creepage", "clearance between"],
                "near_miss_keywords": [],
                "value_check": {
                    "quantity": "length",
                    "specified": ["5 mm", "2.5 mm"],
                    "tolerance_pct": 0,
                    "below": 2.0,
                    "context_words": ["mains", "selv"],
                },
                "artifact_hint": "mains_gap",
                "artifact_names": ["artifacts/board_07"]}

    def test_a_measured_gap_under_the_floor_is_detected(self):
        """The wording that states the geometry without naming the fault."""
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="MAINS_L runs 0.35 mm from the DHT22_DATA net, so the mains "
                     "net is a fraction of a millimetre from the sensor's data line.")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_a_gap_named_in_the_key_is_detected(self):
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="The clearance between the mains net and the SELV net is "
                     "0.35 mm, far below what reinforced insulation needs at 250 V.")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_the_required_clearance_and_the_measured_one_together_are_detected(self):
        """A finding that states both numbers has named the fault without
        using any of the words in the key."""
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="Reinforced insulation at 250 V needs 5 mm between the mains "
                     "and the SELV side. The actual spacing is 0.35 mm.")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_a_track_width_is_not_a_gap(self):
        """The false-positive guard. A board is full of small measurements,
        and none of them is a clearance."""
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="The 0.25 mm track width is at the bottom of what the fab "
                     "accepts, and the 0.2 mm clearance rules in the project file "
                     "are set to zero.")]
        assert _scorer._classify(self._key(), findings)[0] != DETECTED

    def test_a_hole_size_is_not_a_gap(self):
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="All 5 GND vias sit 0.1 mm from the centre of the through-hole "
                     "pad they serve, and each 0.4 mm drill is inside a 0.8 mm hole.")]
        assert _scorer._classify(self._key(), findings)[0] != DETECTED

    def test_a_decimal_point_is_not_a_sentence_end(self):
        """'0.35 mm' is one measurement. A clause splitter that breaks it at
        the full stop reads 0 and 35, and 35 mm is not a fault."""
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="The clearance between the mains net and the SELV net is "
                     "0.35 mm. The mains net is otherwise correctly placed.")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_a_gap_over_the_floor_is_not_a_detection(self):
        """A gap that is not too small has not found the defect. The key's
        phrase list is left out of this one on purpose: the value rule is
        what is being tested, and a finding that also says 'clearance
        between' would be caught by the words instead."""
        key = self._key()
        key["detection_keywords"] = []
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="the mains net sits 3.0 mm from the SELV net, which is less "
                     "than the 5 mm the standard asks for but not a fraction of a "
                     "millimetre.")]
        assert _scorer._classify(key, findings)[0] != DETECTED

    def test_a_case_without_a_value_check_is_unaffected(self):
        key = self._key()
        del key["value_check"]
        findings = [_finding(
            artifact="artifacts/board_07",
            observed="MAINS_L runs 0.35 mm from the DHT22_DATA net.")]
        assert _scorer._classify(key, findings)[0] != DETECTED


# ─────────────────────────────────────────────────────────────────────────────
class TestTheCleanBillIsExact:
    """A false pass is the outcome that blocks the stage.

    The test for it used to be a substring search for 'is correct' and
    'passed'. It fired on 'the flyback diode IS CORRECT under a convention'
    and on 'the 2N2222A is BYPASSED', and turned a board the overlooker had
    refused to send to a fab into a false pass. These are the regressions
    that keep the test exact.
    """

    def _key(self) -> dict:
        return {"id": "cut_track", "defect_class": "open", "critical": True,
                "expected_check_ids": ["III.1"],
                "detection_keywords": ["cut track", "no copper path"],
                "near_miss_keywords": [],
                "artifact_hint": "cut_track",
                "artifact_names": ["board_cut_track.json"]}

    def _says_clean(self, observed: str) -> bool:
        return _scorer._says_clean(_scorer._norm(observed))

    def test_a_bypassed_part_is_not_a_clean_bill(self):
        """'bypassed' contains 'passed'. The two words are opposites."""
        assert not self._says_clean("the 2N2222A is bypassed and the relay latches on")

    def test_a_conditional_remark_about_a_part_is_not_a_clean_bill(self):
        """'Under a "pad 1 = cathode" convention the flyback diode is correct'
        is a remark about one part, under a condition. It is not a verdict
        on the board."""
        assert not self._says_clean(
            "under a 'pad 1 = cathode' convention the flyback diode is correct, "
            "under 'pad 1 = anode' it is reversed")

    def test_a_remark_about_one_part_is_not_a_clean_bill(self):
        """'The part is correct in the only orientation it can be fitted in'
        is about the part. The board is not what is being called correct."""
        assert not self._says_clean(
            "so the part is correct in the only orientation it can be fitted in")

    def test_a_negative_clean_claim_is_not_a_clean_bill(self):
        """'The board is not passed as clean' says the opposite of a clean
        bill, and 'not' must not be read as 'no'."""
        assert not self._says_clean("the board is not passed as clean")

    def test_a_silent_omission_is_not_a_clean_bill(self):
        """'No error, no warning, no refusal' is about how quietly the product
        misbehaved. It is a complaint, not a clean bill."""
        assert not self._says_clean(
            "the omission is silent - no error, no warning, no refusal")

    def test_a_finding_that_reports_a_defect_is_not_a_clean_bill(self):
        """A finding that complains about something and says something else
        is correct is a complaint."""
        assert not self._says_clean(
            "the board is correct in every other respect but the ground plane "
            "is missing and the silkscreen is empty")

    def test_a_clean_bill_about_the_board_is_still_a_clean_bill(self):
        """The positive control. If this stopped firing, the gate '0 false
        passes on the critical classes' would be a gate that cannot fail."""
        assert self._says_clean("the board has no faults: every connection is routed")

    def test_a_clean_bill_can_be_stated_as_a_verdict(self):
        assert self._says_clean("the board is correct")
        assert self._says_clean("the layout is clean and every check passes")
        assert self._says_clean("there is nothing wrong with this board")


# ─────────────────────────────────────────────────────────────────────────────
class TestTheKeyWordsAreMatchedTheSameWayOnBothSides:
    """A net name written in the key must be able to match a finding.

    The scorer normalised the text it searched and did not normalise the
    key's words, so a net name written `relay_ctrl` in the key could never
    match `RELAY_CTRL` in a finding. A detection that named the fault was
    scored as a miss.
    """

    def _key(self) -> dict:
        return {"id": "cut_track", "defect_class": "open", "critical": True,
                "expected_check_ids": ["III.1"],
                "detection_keywords": ["no copper path", "relay_ctrl"],
                "near_miss_keywords": [],
                "artifact_hint": "cut_track",
                "artifact_names": ["board_cut_track.json"]}

    def test_a_net_name_in_the_key_matches_a_finding_that_names_it(self):
        findings = [_finding(artifact="board_cut_track.json",
                             observed="the RELAY_CTRL net is in two pieces")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED

    def test_a_dashed_word_in_the_key_matches_a_finding_that_names_it(self):
        key = self._key()
        key["detection_keywords"] = ["no-copper-path"]
        findings = [_finding(artifact="board_cut_track.json",
                             observed="there is no copper path between the two pads")]
        assert _scorer._classify(key, findings)[0] == DETECTED


# ─────────────────────────────────────────────────────────────────────────────
class TestNamingThePartIsNotNamingTheFault:
    """A finding that says '2N2222A' has looked at the right part. It has not
    found a transposed transistor. The key can now say which words name the
    part and which name the fault, and the two score differently."""

    def _key(self) -> dict:
        return {"id": "swapped_pins", "defect_class": "wrong pinout", "critical": True,
                "expected_check_ids": [],
                "detection_keywords": ["emitter and collector", "transposed"],
                "near_miss_keywords": ["2n2222a"],
                "artifact_hint": "swapped_pins",
                "artifact_names": ["artifacts/board_05"]}

    def test_a_finding_that_only_names_the_part_is_a_near_miss(self):
        findings = [_finding(artifact="artifacts/board_05",
                             observed="the 2N2222A on the board is a TO-92 package")]
        outcome, _ = _scorer._classify(self._key(), findings)
        assert outcome == FLAGGED, (
            "naming the part is noticing the right part, not finding the fault"
        )

    def test_a_finding_that_names_the_fault_is_a_detection(self):
        findings = [_finding(artifact="artifacts/board_05",
                             observed="the 2N2222A has its emitter and collector "
                                      "transposed: the collector is on pin 1")]
        assert _scorer._classify(self._key(), findings)[0] == DETECTED


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
class TestTheKeyAndTheStagingAgree:
    """The key names a board; the staging named it. They must be the same.

    The staged board is opaque — `artifacts/board_03` — so the key is the only
    thing that can say which case a finding is about. If the key's name and
    the staging's name drift apart, every finding is scored against the wrong
    defect and the recall number is wrong in a way nothing reports.
    """

    def _mapping(self) -> dict:
        import json
        path = _HERE / "artifacts" / "MAPPING.json"
        if not path.exists():
            pytest.skip("the boards have not been staged yet")
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {r["case"]: r["folder"] for r in rows}

    def test_every_staged_case_has_a_key_entry_that_names_its_board(self):
        import json
        key = json.loads((_HERE / "KEY.json").read_text(encoding="utf-8"))
        by_id = {c["id"]: c for c in key["cases"]}
        for case, folder in self._mapping().items():
            assert case in by_id, f"staged case {case} has no key entry"
            assert by_id[case].get("artifact_folder") == f"artifacts/{folder}", (
                f"the key says {case} is {by_id[case].get('artifact_folder')!r}, "
                f"but the staging put it in artifacts/{folder}"
            )

    def test_the_staged_folders_exist(self):
        for folder in self._mapping().values():
            assert (_HERE / "artifacts" / folder).is_dir(), (
                f"the key names artifacts/{folder}, and it is not on disk"
            )

    def test_no_two_cases_share_a_folder(self):
        folders = list(self._mapping().values())
        assert len(folders) == len(set(folders)), "two cases share a staged board"

    def test_the_mapping_is_the_source_of_truth_for_the_numbers(self):
        """A staged board's number is assigned once and never reused.

        The numbering is positional by appearance, so adding a case would
        renumber the ones after it — and a finding written against
        `artifacts/board_03` would then be scored against a different
        defect. The stager reads the mapping back and keeps the numbers.
        """
        import json
        rows = json.loads((_HERE / "artifacts" / "MAPPING.json").read_text(encoding="utf-8"))
        numbers = sorted(int(r["folder"].split("_")[1]) for r in rows)
        assert numbers == list(range(1, len(rows) + 1)), (
            f"the staged numbers are not contiguous from 1: {numbers}"
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
