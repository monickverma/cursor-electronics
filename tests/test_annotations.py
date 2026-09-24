"""
Stage 2 — the annotation layer. `core/annotations.py`.

Gate: *"Orphaned annotations surfaced, never dropped"* — analytic, G1. And the
council's condition on X2 (decisions.md, X2 + X4, item 10): a closed list of
kinds, and generation byte-identical with and without annotations, because an
annotation that could steer generation is a second IR by the back door.
"""

import inspect

import pytest
from pydantic import ValidationError

from core.annotations import (
    Annotation,
    AnnotationKind,
    attach,
    validate_annotations,
)
from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp, apply_patch
from generators.rc_lowpass import RCLowPassGenerator
from generators.realize import canonical_json, realize

GEN = RCLowPassGenerator()


def intent():
    return IntentIR(
        requirements={
            "function": "low_pass_filter",
            "targets": {"cutoff_hz": 1000, "tolerance_pct": 5},
            "constraints": {"supply_v": 5},
        },
        provenance=Provenance(producer=Producer.FORM),
    )


def note(id_, kind, anchor_kind, anchor_id="", text="x"):
    return Annotation(id=id_, kind=kind, anchor={"kind": anchor_kind, "id": anchor_id}, text=text)


class TestClosedList:
    def test_exactly_four_kinds(self):
        assert {k.value for k in AnnotationKind} == {
            "net_name", "test_point", "placement_hint", "comment",
        }

    def test_an_unlisted_kind_is_refused(self):
        with pytest.raises(ValidationError):
            note("a", "pinned_part", "component", "R1")

    @pytest.mark.parametrize("kind, anchor_kind", [
        ("net_name", "component"),
        ("test_point", "design"),
        ("placement_hint", "node"),
    ])
    def test_each_kind_attaches_only_where_it_means_something(self, kind, anchor_kind):
        with pytest.raises(ValidationError):
            note("a", kind, anchor_kind, "OUT")

    def test_a_non_design_anchor_must_name_its_target(self):
        with pytest.raises(ValidationError):
            note("a", "comment", "component", "")

    def test_duplicate_ids_are_refused(self):
        raw = [note("a", "comment", "design").model_dump()] * 2
        with pytest.raises(ValueError, match="unique"):
            validate_annotations(raw)


class TestNeverAnInput:
    def test_realize_takes_no_annotations(self):
        # The signature is the enforcement. Widening it is a design change to
        # X2 and must be made on purpose, which this test forces.
        assert list(inspect.signature(realize).parameters) == ["generator", "intent"]

    def test_generation_is_byte_identical_with_and_without_them(self):
        base = intent()
        bare = canonical_json(realize(GEN, base))
        annotations = [
            note("n1", "net_name", "node", "OUT", "FILTERED"),
            note("t1", "test_point", "node", "OUT", "TP1"),
            note("p1", "placement_hint", "component", "C1", "close to the ADC pin"),
            note("c1", "comment", "design", text="bench build, rev A"),
        ]
        design = realize(GEN, base)
        attach(design, annotations)          # merging reads, never writes
        assert canonical_json(design) == bare
        assert canonical_json(realize(GEN, base)) == bare


class TestOrphans:
    def test_every_annotation_is_either_attached_or_orphaned(self):
        design = realize(GEN, intent())
        annotations = [
            note("a", "comment", "component", "R1"),
            note("b", "comment", "component", "U7"),
            note("c", "net_name", "node", "OUT"),
            note("d", "net_name", "node", "VREF"),
            note("e", "comment", "design"),
        ]
        report = attach(design, annotations)
        assert [a.id for a in report.attached] == ["a", "c", "e"]
        assert [a.id for a in report.orphaned] == ["b", "d"]
        assert {a.id for a in report.all} == {a.id for a in annotations}

    def test_an_orphan_is_kept_across_revisions_and_reattaches(self):
        # A patch that removes an anchor must not lose the user's note: the
        # next patch may bring the anchor back.
        design = realize(GEN, intent())
        placement = note("p", "placement_hint", "component", "R1", "keep near the op-amp")

        without_r1 = design.model_copy(update={
            "components": [c for c in design.components if c.id != "R1"],
        })
        stored = attach(without_r1, [placement]).all
        assert attach(without_r1, stored).orphaned == (placement,)
        assert attach(design, stored).attached == (placement,)

    def test_a_patch_leaves_annotations_on_surviving_anchors_attached(self):
        base = intent()
        comment = note("c", "comment", "component", "C1", "X7R only")
        out = apply_patch(base, [PatchOp(op="replace", path="/targets/cutoff_hz", value=2000)])
        report = attach(realize(GEN, out.intent), [comment])
        assert report.attached == (comment,) and report.orphaned == ()
