"""
IntentIR — the user's requirement, materialized before the design exists.

PHASE_2_PLAN_v2.md §6 gives the schema; Stage 1 Task 1.1 builds it.

`ARCHITECTURE_ASSURANCE_CASE.md` §2 makes this the single analytic claim the
whole architecture rests on:

> **A1** *(analytic)*: Only Architecture C materializes the user's requirement
> as an inspectable artifact that exists before the design does.

Everything discriminating follows from that one fact. Spec-relative error
detection, intent-relative formal verification, a specification a human can
sign off, and a property that can be frozen against weakening are all just
consequences of the requirement being written down in a form a machine can
read. Where it is not written down, the proposition *"this circuit does what
was asked"* cannot be stated at all — not verified badly, but inexpressible.

So this module is deliberately small and deliberately strict. It is a record of
what was asked for, not a design and not a plan for one.

**On `requirements` being a plain dict.** It is validated against `Requirements`
and then stored as a mapping, rather than kept as a nested model. Generators
read it through the `IntentLike` protocol frozen in Task 0.2, which types it as
a `Mapping` — so keeping it a mapping is what lets every generator consume an
IntentIR without the protocol being reopened. Validation happens; the
convenience of attribute access does not, and that is the right trade when five
generators depend on the shape.

**On sign-off.** `signed_off.property_hash` pins the requirements as they stood
when a human agreed to them. Stage 4 makes the freeze load-bearing — a refine
loop may change the abstraction, the solver or the certificate, never the
property — and `is_intact()` is the cheap version of that check available now.
It is the mitigation for defeater **D-B**: the LLM writes IntentIR, so the
specification is untrusted, and materialized-and-signed is the answer rather
than trusted.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: Bumped when the IntentIR shape changes. Half of the §4.4 cache key
#: (prompt_hash + schema_version), so it must not vary per deployment.
#: 2.1.0 (Stage 2) added `revision`; a 2.0.0 dump without it still loads.
SCHEMA_VERSION = "2.1.0"


class Producer(str, Enum):
    """
    Which of the two producers wrote this. §4.2: the form is the reference
    producer and the LLM is a convenience layer over the same schema — which
    is what makes the system provably LLM-optional, and what an offline
    install depends on.
    """

    FORM = "form"
    LLM = "llm"


class Requirements(BaseModel):
    """
    What was asked for, split by how each part constrains the design.

    The split is not cosmetic. `targets` are what `predict()` is checked
    against and what a claim quantifies over; `constraints` bound the design
    space without being goals; `preferences` may be traded away and must never
    silently become a target. A generator that cannot meet a target refuses;
    one that cannot meet a preference proceeds and says so.
    """

    model_config = ConfigDict(extra="forbid")

    function: str
    targets: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("function")
    @classmethod
    def _function_is_named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("function must name what the circuit is for")
        return v.strip()


class SignOff(BaseModel):
    """A human agreeing to a specification, and to exactly this version of it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    by: str
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    property_hash: str

    @field_validator("by")
    @classmethod
    def _identified(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sign-off must identify who signed — an anonymous "
                             "sign-off cannot be followed up on")
        return v.strip()


class Provenance(BaseModel):
    """
    Where this IntentIR came from. Needed to answer the §4.5 questions —
    refusal rates by producer, whether anyone uses the LLM path, what a design
    cost — and to tell a form-authored specification from a model-authored one
    when auditing a claim.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    producer: Producer
    model: Optional[str] = None
    prompt_hash: Optional[str] = None

    @model_validator(mode="after")
    def _llm_names_its_model(self) -> "Provenance":
        if self.producer == Producer.LLM.value and not (self.model or "").strip():
            raise ValueError(
                "an LLM-produced intent must record which model produced it — "
                "without it a later claim cannot be attributed or reproduced"
            )
        return self


class IntentIR(BaseModel):
    """
    The requirement as an artifact. Satisfies `generators.protocol.IntentLike`.

    Frozen after construction: an IntentIR is a record of what was asked, and
    editing one in place would make `signed_off.property_hash` meaningless and
    the patch chain in Stage 2 unreadable. Changes go through
    `with_requirements()`, which returns a new version.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    #: Position in the patch chain. Stage 2: each accepted patch is revision
    #: n+1, and the CircuitIR realised from it carries the same number as its
    #: `version`. `intent_id` is the lineage and survives every revision.
    revision: int = Field(default=1, ge=1)
    requirements: Dict[str, Any]
    underdetermined: List[str] = Field(default_factory=list)
    signed_off: Optional[SignOff] = None
    provenance: Provenance

    @field_validator("requirements")
    @classmethod
    def _requirements_are_well_formed(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Validated through the typed model, stored as a mapping so generators
        # can read it through IntentLike without reopening the Task 0.2
        # protocol. Raises with the same field paths a nested model would.
        Requirements.model_validate(v)

        # And it has to survive `json.dumps`. `requirements` is typed `Any`, so
        # a caller can put a set or a datetime in it — which validates fine and
        # then blows up in `requirements_hash()` (sign-off, the §4.4 cache key)
        # and again when the request log serialises the intent. Failing here
        # names the field; failing there produces a bare TypeError from inside
        # an unrelated call.
        try:
            json.dumps(v, sort_keys=True)
        except TypeError as exc:
            raise ValueError(
                f"requirements must be JSON-serialisable — it is hashed for "
                f"sign-off and written to the request log: {exc}"
            ) from exc
        return v

    @model_validator(mode="after")
    def _underdetermined_fields_are_named(self) -> "IntentIR":
        for field_path in self.underdetermined:
            if not field_path.strip():
                raise ValueError(
                    "an underdetermined entry must name the field that is "
                    "missing — an unnamed gap cannot be turned into a question"
                )
        if self.underdetermined and self.signed_off is not None:
            raise ValueError(
                "cannot sign off an intent with unresolved underdetermined "
                f"fields {sorted(self.underdetermined)} — signing off on a "
                "specification that is still missing pieces is what sign-off "
                "exists to prevent"
            )
        return self

    # ── The Stage 1 gate ──────────────────────────────────────────────────

    @property
    def is_answerable(self) -> bool:
        """
        Whether this intent can be built from as it stands.

        Stage 1 gate: *"`underdetermined` non-empty → system asks, never
        generates"* — analytic, G1. Callers check this; `open_questions()`
        gives them what to ask.
        """
        return not self.underdetermined

    def open_questions(self) -> List[str]:
        """The fields the user still has to supply, in declared order."""
        return list(self.underdetermined)

    # ── Sign-off and freeze ───────────────────────────────────────────────

    def requirements_hash(self) -> str:
        """
        Stable hash of the requirements alone.

        Key-sorted and separator-normalised so it depends on the content and
        not on how the mapping was built — two producers that asked for the
        same thing must hash the same, or the §4.4 cache never hits and
        sign-off cannot be compared across a round trip.
        """
        canonical = json.dumps(self.requirements, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sign_off(self, by: str) -> "IntentIR":
        """
        Return a signed copy, pinned to the requirements as they stand now.

        Refuses while anything is underdetermined, because a signature on an
        incomplete specification is worse than none: it looks like agreement.
        """
        if not self.is_answerable:
            raise ValueError(
                f"cannot sign off while {sorted(self.underdetermined)} are "
                "underdetermined — ask first"
            )
        return self.model_copy(
            update={"signed_off": SignOff(by=by, property_hash=self.requirements_hash())}
        )

    @property
    def is_signed(self) -> bool:
        return self.signed_off is not None

    def is_intact(self) -> bool:
        """
        Whether the requirements still match what was signed.

        An unsigned intent is vacuously intact — there is nothing to violate.
        Stage 4 makes this load-bearing by freezing the property after
        sign-off; here it is the cheap check that the specification has not
        drifted out from under a signature.
        """
        if self.signed_off is None:
            return True
        return self.signed_off.property_hash == self.requirements_hash()

    # ── Versioning ────────────────────────────────────────────────────────

    def with_requirements(self, requirements: Mapping[str, Any]) -> "IntentIR":
        """
        A new version carrying different requirements, at revision n+1.

        The signature does not travel with it: changed requirements are by
        definition not the ones that were agreed to, and silently carrying a
        sign-off across an edit is exactly the weakening Stage 4's freeze
        exists to stop. `core/intent_patch.py` builds the patch chain on this.

        Revalidated rather than `model_copy`'d: a copy skips validation, so a
        patch that wrote a malformed requirement would otherwise produce an
        IntentIR that could never have been constructed directly.
        """
        data = self.model_dump()
        data.update(
            requirements=dict(requirements),
            signed_off=None,
            revision=self.revision + 1,
            # Written by this code, so it carries this code's shape even when
            # revision n was loaded from an older dump.
            schema_version=SCHEMA_VERSION,
        )
        return IntentIR.model_validate(data)
