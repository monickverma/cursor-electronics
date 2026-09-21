"""
Stage 2 — patching the requirement, not the design. `core/intent_patch.py`.

PHASE_2_PLAN_v2.md §4.1 and the X2 + X4 entry in `brain/decisions.md`
[2026-09-21]. This file owns three of the Stage 2 gates and criterion 7:

- **Idempotence** — an empty patch, or one that leaves the requirement equal,
  is not a version, and realises a byte-identical design.
- **Validation by construction** — a patched intent passes `envelope()` or is
  refused with a reason, exactly like a fresh one.
- **Readable history** — the chain reads `targets.cutoff_hz: 1000 → 2000`,
  not `R1: 1590Ω → 795Ω`.
- **Criterion 7, re-earned** — five sequential patches, no corruption. Its
  Phase 1 automation patched CircuitIR directly and went with that module;
  `TestCriterion7` is its replacement and `CRITERIA_TEST_MAP` points here.
"""

import pytest
from pydantic import ValidationError

from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import (
    PatchError,
    PatchOp,
    apply_patch,
    flatten,
    parse_pointer,
)
from core.ir_validator import validate_ir
from generators.rc_lowpass import RCLowPassGenerator
from generators.realize import canonical_json, realize

GEN = RCLowPassGenerator()


def make(**requirements):
    base = {
        "function": "low_pass_filter",
        "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
        "constraints": {"supply_v": 5, "source_impedance_ohm": 50},
    }
    base.update(requirements)
    return IntentIR(requirements=base, provenance=Provenance(producer=Producer.FORM))


def op(kind, path, *value):
    return PatchOp(op=kind, path=path, **({"value": value[0]} if value else {}))


# ── The operation language ───────────────────────────────────────────────────

class TestOperations:
    def test_replace_changes_one_requirement(self):
        out = apply_patch(make(), [op("replace", "/targets/cutoff_hz", 2000)])
        assert out.intent.requirements["targets"]["cutoff_hz"] == 2000
        assert out.intent.requirements["constraints"] == make().requirements["constraints"]

    def test_add_creates_a_member_and_a_missing_section(self):
        base = IntentIR(
            requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}},
            provenance=Provenance(producer=Producer.FORM),
        )
        out = apply_patch(base, [op("add", "/constraints/supply_v", 12)])
        assert out.intent.requirements["constraints"] == {"supply_v": 12}

    def test_add_can_pin_a_part(self):
        out = apply_patch(make(), [op("add", "/constraints/pinned", {"R1": "4.7k"})])
        assert out.intent.requirements["constraints"]["pinned"] == {"R1": "4.7k"}

    def test_remove_deletes_a_member(self):
        out = apply_patch(make(), [op("remove", "/constraints/source_impedance_ohm")])
        assert "source_impedance_ohm" not in out.intent.requirements["constraints"]

    def test_test_op_guards_the_rest_of_the_patch(self):
        with pytest.raises(PatchError, match="test failed"):
            apply_patch(make(), [
                op("test", "/targets/cutoff_hz", 5000),
                op("replace", "/targets/cutoff_hz", 2000),
            ])

    def test_pointer_escapes_are_decoded(self):
        assert parse_pointer("/preferences/a~1b~0c") == ["preferences", "a/b~c"]

    def test_replace_of_a_missing_member_is_refused_per_rfc(self):
        with pytest.raises(PatchError, match="does not exist"):
            apply_patch(make(), [op("replace", "/targets/q_factor", 0.7)])

    def test_remove_of_a_missing_member_is_refused_per_rfc(self):
        with pytest.raises(PatchError, match="does not exist"):
            apply_patch(make(), [op("remove", "/preferences/package")])

    def test_move_and_copy_are_not_approximated(self):
        with pytest.raises(ValidationError):
            PatchOp(op="move", path="/targets/cutoff_hz")

    def test_value_is_required_where_rfc_requires_it(self):
        with pytest.raises(ValidationError):
            PatchOp.model_validate({"op": "replace", "path": "/targets/cutoff_hz"})


class TestScope:
    """A patch cannot reach anything but the requirement."""

    @pytest.mark.parametrize("path", [
        "", "targets/cutoff_hz", "/intent_id", "/provenance/model",
        "/signed_off", "/revision", "/targts/cutoff_hz",
    ])
    def test_paths_outside_requirements_are_refused(self, path):
        with pytest.raises(PatchError):
            apply_patch(make(), [op("replace", path, "x")])

    def test_function_cannot_be_removed(self):
        with pytest.raises(PatchError, match="function cannot be removed"):
            apply_patch(make(), [op("remove", "/function")])

    def test_function_is_not_an_object(self):
        with pytest.raises(PatchError, match="function"):
            apply_patch(make(), [op("add", "/function/x", 1)])

    def test_a_result_that_is_not_a_valid_requirement_is_refused(self):
        with pytest.raises(PatchError, match="not valid"):
            apply_patch(make(), [op("replace", "/function", "   ")])

    def test_a_non_serialisable_value_is_refused(self):
        with pytest.raises(PatchError):
            apply_patch(make(), [op("add", "/preferences/when", {1, 2})])


class TestAtomicity:
    def test_a_failing_operation_applies_none_of_them(self):
        intent = make()
        before = intent.model_dump_json()
        with pytest.raises(PatchError) as exc:
            apply_patch(intent, [
                op("replace", "/targets/cutoff_hz", 2000),
                op("remove", "/targets/does_not_exist"),
            ])
        assert exc.value.op_index == 1
        assert intent.model_dump_json() == before

    def test_the_input_intent_is_never_mutated(self):
        intent = make(constraints={"supply_v": 5, "pinned": {"R1": "4.7k"}})
        before = intent.model_dump_json()
        apply_patch(intent, [op("replace", "/constraints/pinned/R1", "10k")])
        assert intent.model_dump_json() == before


# ── Idempotence (Stage 2 gate) ───────────────────────────────────────────────

class TestIdempotence:
    def test_empty_patch_is_not_a_version(self):
        intent = make()
        out = apply_patch(intent, [])
        assert not out.changed
        assert out.intent is intent
        assert out.intent.revision == 1

    def test_a_value_preserving_patch_is_not_a_version(self):
        out = apply_patch(make(), [op("replace", "/targets/cutoff_hz", 1000)])
        assert not out.changed
        assert out.readable == ()

    def test_adding_an_empty_default_section_is_not_a_change(self):
        out = apply_patch(make(), [op("add", "/preferences", {})])
        assert not out.changed

    def test_empty_patch_realises_a_byte_identical_design(self):
        intent = make()
        assert canonical_json(realize(GEN, apply_patch(intent, []).intent)) == \
            canonical_json(realize(GEN, intent))


# ── Validation by construction (Stage 2 gate) ────────────────────────────────

class TestValidationByConstruction:
    def test_a_patched_intent_goes_through_the_same_envelope(self):
        out = apply_patch(make(), [op("replace", "/targets/cutoff_hz", 2_000_000)])
        decision = GEN.envelope(out.intent)
        assert not decision.accepted
        assert "2e+06" in decision.reason   # the offending value is named

    def test_a_patch_drops_the_signature(self):
        # Changed requirements are not the ones agreed to — D-B.
        signed = make().sign_off(by="user-1")
        out = apply_patch(signed, [op("replace", "/targets/cutoff_hz", 2000)])
        assert not out.intent.is_signed


# ── Readable history (Stage 2 gate) ──────────────────────────────────────────

class TestReadableHistory:
    def test_history_reads_as_requirements(self):
        out = apply_patch(make(), [op("replace", "/targets/cutoff_hz", 2000)])
        assert out.readable == ("targets.cutoff_hz: 1000 → 2000",)
        assert out.changed_paths == ("targets.cutoff_hz",)

    def test_additions_and_removals_say_so(self):
        out = apply_patch(make(), [
            op("add", "/constraints/pinned", {"R1": "4.7k"}),
            op("remove", "/constraints/source_impedance_ohm"),
        ])
        assert out.readable == (
            'constraints.pinned.R1: (unset) → "4.7k"',
            "constraints.source_impedance_ohm: 50 → (unset)",
        )

    def test_nothing_in_history_names_a_component(self):
        # The whole point: R1/C1 values are consequences, not the edit.
        out = apply_patch(make(), [op("replace", "/targets/cutoff_hz", 2000)])
        assert not any("R1" in line or "C1" in line for line in out.readable)

    def test_flatten_keeps_nested_paths_and_drops_empty_sections(self):
        flat = flatten({"function": "f", "targets": {}, "constraints": {"pinned": {"R1": "1k"}}})
        assert flat == {"function": "f", "constraints.pinned.R1": "1k"}


# ── Criterion 7, re-earned at the IntentIR layer ─────────────────────────────

class TestCriterion7:
    """
    Phase 1 criterion 7: *5 sequential patches to the same design — no data
    corruption.* Automated on 2026-08-07 against the CircuitIR patcher, which
    Stage 2 removes. Re-earned here on requirement patches, each realised
    through the generator, asserting the same four things the original did.
    """

    SEQUENCE = [
        [op("replace", "/targets/cutoff_hz", 2000)],
        [op("replace", "/targets/tolerance_pct", 3)],
        [op("replace", "/constraints/source_impedance_ohm", 600)],
        [op("replace", "/constraints/supply_v", 12)],
        [op("add", "/constraints/pinned", {"C1": "10nF"})],
    ]

    def _run(self):
        intent = make()
        designs = [realize(GEN, intent)]
        history = []
        for ops in self.SEQUENCE:
            out = apply_patch(intent, ops)
            assert out.changed
            assert GEN.envelope(out.intent).accepted, GEN.envelope(out.intent).reason
            intent = out.intent
            designs.append(realize(GEN, intent))
            history.extend(out.readable)
        return intent, designs, history

    def test_five_sequential_patches_keep_every_design_valid(self):
        _, designs, _ = self._run()
        for design in designs:
            result = validate_ir(design)
            assert result.is_valid, result.errors

    def test_versions_advance_one_per_patch_on_one_design(self):
        intent, designs, _ = self._run()
        assert [d.version for d in designs] == [1, 2, 3, 4, 5, 6]
        assert intent.revision == 6
        assert len({d.circuit_id for d in designs}) == 1, "a patch changed the design's identity"

    def test_later_patches_do_not_erase_earlier_ones(self):
        # The regression the original class existed to catch, at the layer
        # where edits now live.
        intent, _, _ = self._run()
        req = intent.requirements
        assert req["targets"] == {"cutoff_hz": 2000, "tolerance_pct": 3}
        assert req["constraints"] == {
            "supply_v": 12, "source_impedance_ohm": 600, "pinned": {"C1": "10nF"},
        }

    def test_the_final_design_honours_every_accumulated_edit(self):
        _, designs, _ = self._run()
        final = designs[-1]
        parts = {c.id: c for c in final.components}
        assert parts["C1"].value == "10nF"                   # patch 5
        assert final.constraints["supply_voltage"] == 12     # patch 4
        assert "600Ω source impedance" in parts["R1"].justification  # patch 3
        assert final.constraints["cutoff_hz"] == 2000        # patch 1

    def test_connection_refs_still_resolve_after_patching(self):
        _, designs, _ = self._run()
        for design in designs:
            ids = {c.id for c in design.components}
            nodes = {n.id for n in design.nodes}
            for conn in design.connections:
                assert conn.component_id in ids and conn.node_id in nodes

    def test_the_history_reads_as_five_requirement_edits(self):
        _, _, history = self._run()
        assert history == [
            "targets.cutoff_hz: 1000 → 2000",
            "targets.tolerance_pct: 5 → 3",
            "constraints.source_impedance_ohm: 50 → 600",
            "constraints.supply_v: 5 → 12",
            'constraints.pinned.C1: (unset) → "10nF"',
        ]
