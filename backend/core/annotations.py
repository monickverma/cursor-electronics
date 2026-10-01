"""
The annotation layer. PHASE_2_PLAN_v2.md §4.1, Stage 2; amendment X2.

> **Annotations** carry what IntentIR cannot express — custom net names, test
> points, placement hints, comments. Keyed to stable IDs, merged *after*
> generation, never an input to it. If an anchor disappears the annotation is
> **orphaned and surfaced**, never silently dropped.

**A closed list, on purpose.** The council's warning about this layer was that
"whatever IntentIR cannot hold" is an open-ended set that turns into a second
IR feeding generation by the back door. So the kinds are fixed here, and
anything that should change the circuit — "use the 4.7 k in my drawer" — is a
requirement (`constraints.pinned`), not an annotation. Adding a kind is a
deliberate edit to this file, not a free-form string.

**Never an input.** `generators/realize.py::realize` takes no annotations, and
`tests/test_annotations.py` asserts both that its signature stays that way and
that a design is byte-identical with and without them.

**Orphans are kept, not only reported.** An annotation whose anchor vanished in
revision n+1 may find it again in n+2 — a resistor removed by one patch and
restored by the next. Dropping it at n+1 would lose the user's note for good;
the placement-warning lesson is that silence reads as success.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.ir_schema import CircuitIR


class AnnotationKind(str, Enum):
    NET_NAME = "net_name"
    TEST_POINT = "test_point"
    PLACEMENT_HINT = "placement_hint"
    COMMENT = "comment"


class AnchorKind(str, Enum):
    COMPONENT = "component"
    NODE = "node"
    DESIGN = "design"


#: Which anchors each kind may attach to. A net name belongs to a node; a
#: placement hint to a part; a comment to anything.
_ALLOWED_ANCHORS = {
    AnnotationKind.NET_NAME: {AnchorKind.NODE},
    AnnotationKind.TEST_POINT: {AnchorKind.NODE},
    AnnotationKind.PLACEMENT_HINT: {AnchorKind.COMPONENT},
    AnnotationKind.COMMENT: {AnchorKind.COMPONENT, AnchorKind.NODE, AnchorKind.DESIGN},
}


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    kind: AnchorKind
    #: Component or node id. Ignored for a design anchor, which always resolves.
    id: str = ""

    @model_validator(mode="after")
    def _id_when_needed(self) -> "Anchor":
        if self.kind != AnchorKind.DESIGN.value and not self.id.strip():
            raise ValueError(f"a {self.kind} anchor must name the {self.kind} it attaches to")
        return self


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    id: str
    kind: AnnotationKind
    anchor: Anchor
    text: str = Field(min_length=1, max_length=500)

    @field_validator("id")
    @classmethod
    def _id_named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("an annotation needs an id so it can be edited or removed")
        return v.strip()

    @model_validator(mode="after")
    def _anchor_fits_kind(self) -> "Annotation":
        allowed = {a.value for a in _ALLOWED_ANCHORS[AnnotationKind(self.kind)]}
        if self.anchor.kind not in allowed:
            raise ValueError(
                f"a {self.kind} annotation attaches to {sorted(allowed)}, "
                f"not to a {self.anchor.kind}"
            )
        return self


class AnnotationReport(BaseModel):
    """Every annotation, sorted into those that found their anchor and those that did not."""

    model_config = ConfigDict(frozen=True)

    attached: Tuple[Annotation, ...] = ()
    orphaned: Tuple[Annotation, ...] = ()

    @property
    def all(self) -> Tuple[Annotation, ...]:
        """Both lists, in the order they were stored. What gets persisted."""
        return self.attached + self.orphaned


def attach(circuit: CircuitIR, annotations: Sequence[Annotation]) -> AnnotationReport:
    """Resolve each anchor against `circuit`. Nothing is dropped."""
    components = {c.id for c in circuit.components}
    nodes = {n.id for n in circuit.nodes}
    attached: List[Annotation] = []
    orphaned: List[Annotation] = []
    for annotation in annotations:
        anchor = annotation.anchor
        found = (
            anchor.kind == AnchorKind.DESIGN.value
            or (anchor.kind == AnchorKind.COMPONENT.value and anchor.id in components)
            or (anchor.kind == AnchorKind.NODE.value and anchor.id in nodes)
        )
        (attached if found else orphaned).append(annotation)
    return AnnotationReport(attached=tuple(attached), orphaned=tuple(orphaned))


def validate_annotations(raw: Sequence[object]) -> List[Annotation]:
    """Parse stored or submitted annotations, refusing duplicate ids."""
    parsed = [Annotation.model_validate(item) for item in raw]
    ids = [a.id for a in parsed]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"annotation ids must be unique; repeated: {duplicates}")
    return parsed
