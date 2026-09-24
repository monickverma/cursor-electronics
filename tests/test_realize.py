"""
Stage 2 — `generators/realize.py`: determinism, locality, and the predict() delta.

PHASE_2_PLAN_v2.md §4.1. Gates owned here:

- **Determinism** — same IntentIR + same generator version → byte-identical
  CircuitIR (analytic, G1). Blocked since Task 0.3 on `circuit_id` being a
  fresh uuid4; `realize()` derives it from the intent's lineage.
- **Locality** — the CircuitIR diff ⊆ the declared dependency closure of the
  changed requirement paths. Swept here across every declared path. Graded
  *projected* until a generator with more than two parts exists: with R1 and
  C1 a closure is nearly the whole circuit (decisions.md, X2 + X4, item 11).
  It still found a real bug on its first run — see
  `test_supply_crossing_the_capacitor_rating_reaches_r1`.
- **Acceptance** — *"make the cutoff 2 kHz"* end to end, justified by the
  predict() delta. The replacement for the DS18B20 gate, which cannot pass
  anywhere in Phase 2 (item 15).
"""

import uuid

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp, apply_patch
from core.ir_schema import CircuitIR
from generators.rc_lowpass import RCLowPassGenerator
from generators.realize import (
    CIRCUIT_ID_NAMESPACE,
    RefusedIntent,
    canonical_json,
    check_locality,
    component_diff,
    design_circuit_id,
    predict_delta,
    realize,
)

GEN = RCLowPassGenerator()


def make(intent_id=None, **requirements):
    base = {
        "function": "low_pass_filter",
        "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
        "constraints": {"supply_v": 5, "source_impedance_ohm": 50},
    }
    base.update(requirements)
    extra = {"intent_id": intent_id} if intent_id else {}
    return IntentIR(requirements=base, provenance=Provenance(producer=Producer.FORM), **extra)


def patched(intent, path, value, op="replace"):
    return apply_patch(intent, [PatchOp(op=op, path=path, value=value)])


# ── Determinism (Stage 2 gate) ───────────────────────────────────────────────

class TestDeterminism:
    def test_same_intent_same_version_is_byte_identical(self):
        intent = make()
        assert canonical_json(realize(GEN, intent)) == canonical_json(realize(GEN, intent))

    def test_byte_identical_across_a_serialisation_round_trip(self):
        # The stored intent is what a patch starts from, so the property has to
        # survive the database, not only the process.
        intent = make()
        reloaded = IntentIR.model_validate_json(intent.model_dump_json())
        assert canonical_json(realize(GEN, reloaded)) == canonical_json(realize(GEN, intent))

    def test_raw_generate_is_not_byte_identical_which_is_why_realize_exists(self):
        # Negative control. If generate() became deterministic on its own this
        # would fail and realize()'s stamping could be revisited — until then
        # the gate is only honest because this is true.
        a, b = GEN.generate(make()), GEN.generate(make())
        assert a.circuit_id != b.circuit_id

    def test_stamps_what_a_generator_cannot_know(self):
        intent = make()
        design = realize(GEN, intent)
        assert design.circuit_id == design_circuit_id(intent)
        assert design.version == intent.revision
        assert design.generator == f"{GEN.name}@{GEN.version}"

    def test_a_refused_intent_is_never_realised(self):
        with pytest.raises(RefusedIntent) as exc:
            realize(GEN, make(targets={"cutoff_hz": 2_000_000}))
        assert exc.value.generator == "rc_lowpass"
        assert "outside declared envelope" in exc.value.reason


class TestCircuitIdentity:
    def test_derived_from_the_lineage_not_the_content(self):
        intent = make(intent_id="11111111-1111-1111-1111-111111111111")
        assert design_circuit_id(intent) == str(uuid.uuid5(CIRCUIT_ID_NAMESPACE, intent.intent_id))

    def test_survives_every_patch(self):
        intent = make()
        later = patched(patched(intent, "/targets/cutoff_hz", 2000).intent, "/constraints/supply_v", 12).intent
        assert realize(GEN, later).circuit_id == realize(GEN, intent).circuit_id

    def test_two_users_asking_the_same_thing_do_not_collide(self):
        # circuit_designs.circuit_id is UNIQUE. A content hash would collide.
        assert realize(GEN, make()).circuit_id != realize(GEN, make()).circuit_id

    def test_a_generator_upgrade_does_not_change_identity(self):
        class Upgraded(RCLowPassGenerator):
            version = "9.9.9"

        intent = make()
        assert realize(Upgraded(), intent).circuit_id == realize(GEN, intent).circuit_id
        assert realize(Upgraded(), intent).generator == "rc_lowpass@9.9.9"

    def test_the_namespace_is_pinned(self):
        # Changing it would re-key every stored design. This test is the tripwire.
        assert str(CIRCUIT_ID_NAMESPACE) == "5b3f9e2a-6c1d-4f0e-9a7b-2d8c4e6f1a30"


# ── Locality (Stage 2 gate) ──────────────────────────────────────────────────

#: Every declared path, with values that exercise it — including the supply
#: values either side of the 16 V rating of the first-choice capacitor.
LOCALITY_SWEEP = [
    ("/targets/cutoff_hz", v) for v in (47, 330, 2000, 12_345, 90_000)
] + [
    ("/targets/tolerance_pct", v) for v in (2, 10)
] + [
    ("/constraints/supply_v", v) for v in (3.3, 12, 16, 20, 45)
] + [
    # 60 Ω, not 600: against R1 ≈ 1.6 kΩ, 600 Ω moves f_c 27% and rc_lowpass
    # 0.2.2 refuses it — the sweep would silently skip the path.
    # 600 Ω at 1 kHz is swamped (0.2.3): the capacitor changes, so C1 is in scope.
    ("/constraints/source_impedance_ohm", v) for v in (0, 60, 600)
]


class TestLocality:
    @pytest.mark.parametrize("path, value", LOCALITY_SWEEP)
    def test_diff_is_inside_the_declared_closure(self, path, value):
        base = make()
        out = patched(base, path, value)
        if not GEN.envelope(out.intent).accepted:
            pytest.skip("refused — nothing realised, nothing to localise")
        report = check_locality(GEN, out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert report.ok, (
            f"{path}={value} changed {report.diff} but {GEN.name} declares only "
            f"{report.closure} for {report.changed_paths}"
        )

    def test_pinning_is_inside_its_closure(self):
        base = make()
        out = patched(base, "/constraints/pinned", {"C1": "10nF"}, op="add")
        report = check_locality(GEN, out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert report.ok and set(report.diff) == {"R1", "C1"}

    def test_supply_crossing_the_capacitor_rating_reaches_r1(self):
        # The bug this gate found on its first sweep. Stage 0's closure for
        # supply_v was {C1}. Above 16 V the 100 nF part is out, another
        # capacitor is chosen, and R1 is re-snapped — so R1 changes too.
        base = make()
        out = patched(base, "/constraints/supply_v", 20)
        report = check_locality(GEN, out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert set(report.diff) == {"R1", "C1"}
        assert report.ok

    def test_the_check_catches_a_closure_that_is_too_narrow(self):
        # Negative control: the Stage 0 closure, reinstated, must fail.
        class Stage0Closure(RCLowPassGenerator):
            def dependency_closure(self, requirement_path):
                if requirement_path == "constraints.supply_v":
                    return frozenset({"C1"})
                return super().dependency_closure(requirement_path)

        base = make()
        out = patched(base, "/constraints/supply_v", 20)
        report = check_locality(Stage0Closure(), out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert report.violations == ("R1",)

    def test_a_small_source_touches_only_r1(self):
        # Inside tolerance nothing is re-chosen: only R1's loading note moves.
        base = make()
        out = patched(base, "/constraints/source_impedance_ohm", 60)
        report = check_locality(GEN, out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert report.diff == ("R1",) and report.ok

    def test_a_swamped_source_reaches_c1_and_its_closure_says_so(self):
        base = make()
        out = patched(base, "/constraints/source_impedance_ohm", 600)
        report = check_locality(GEN, out.changed_paths, realize(GEN, base), realize(GEN, out.intent))
        assert set(report.diff) == {"R1", "C1"} and report.ok

    def test_component_diff_sees_additions_and_removals(self):
        design = realize(GEN, make())
        fewer = design.model_copy(update={"components": design.components[:1]})
        assert component_diff(design, fewer) == frozenset({"C1"})
        assert component_diff(fewer, design) == frozenset({"C1"})

    def test_a_change_of_generator_is_reported_not_localised(self):
        design = realize(GEN, make())
        other = design.model_copy(update={"generator": "divider@0.1.0"})
        report = check_locality(GEN, ["function"], design, other)
        assert not report.applicable


# ── The predict() delta, and the acceptance test ─────────────────────────────

class TestPredictDelta:
    def test_only_quantities_that_moved_are_reported(self):
        base = make()
        out = patched(base, "/constraints/source_impedance_ohm", 60)
        # Source impedance changes R1's note, not a predicted quantity.
        assert predict_delta(GEN, base, GEN, out.intent) == []

    def test_an_unpredictable_before_side_is_absent_not_fatal(self):
        refused = make(targets={"cutoff_hz": 2_000_000})
        deltas = predict_delta(GEN, refused, GEN, make())
        assert deltas and all(d.before is None for d in deltas)

    def test_a_missing_before_generator_is_absent_not_fatal(self):
        deltas = predict_delta(None, make(), GEN, make())
        assert deltas and all(d.before is None for d in deltas)


class TestAcceptanceMakeTheCutoff2kHz:
    """
    The Stage 2 acceptance test that can pass today (decisions.md, item 15):
    a requirement patch, realised, justified by the predict() delta.
    """

    def _run(self):
        base = make()
        out = patched(base, "/targets/cutoff_hz", 2000)
        before, after = realize(GEN, base), realize(GEN, out.intent)
        return base, out, before, after, predict_delta(GEN, base, GEN, out.intent)

    def test_the_new_design_meets_the_new_requirement(self):
        _, out, _, after, _ = self._run()
        band = GEN.predict(out.intent).quantities["cutoff_hz"]
        assert abs(band.nominal - 2000) / 2000 <= 0.05
        assert after.version == 2

    def test_the_justification_is_the_predict_delta(self):
        _, _, _, _, deltas = self._run()
        by_name = {d.name: d for d in deltas}
        cutoff = by_name["cutoff_hz"]
        assert cutoff.before.nominal == pytest.approx(996.0, rel=0.01)
        assert cutoff.after.nominal == pytest.approx(2000, rel=0.05)
        line = cutoff.describe()
        assert line.startswith("cutoff_hz: ") and "→" in line and "Hz" in line

    def test_the_history_names_the_requirement_and_the_delta_names_the_physics(self):
        _, out, before, after, deltas = self._run()
        assert out.readable == ("targets.cutoff_hz: 1000 → 2000",)
        assert {d.name for d in deltas} >= {"cutoff_hz"}
        assert before.circuit_id == after.circuit_id

    def test_the_patched_design_is_a_valid_circuit(self):
        _, _, _, after, _ = self._run()
        CircuitIR.model_validate(after.model_dump())
