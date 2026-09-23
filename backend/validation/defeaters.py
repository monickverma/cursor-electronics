"""
The defeater register. EVIDENCE_CLASSES.md §3.4 and Table C; PHASE_2_PLAN_v2.md §7.

A defeater is a recorded doubt about a claim. Assurance 2.0's standard is
indefeasibility — no credible new information would change the claim — and a
claim that carries an open defeater is not "high confidence with a caveat", it
is **defeasible**, and is reported that way.

This is the machine-readable register: claims cite these IDs, and
`regen_state.py` counts open defeaters and their fan-out. v2 §7 is the prose
view. **One namespace** — `brain/decisions.md` [2026-09-21] X6 + X8 renumbered
the two collisions: EVIDENCE_CLASSES' π defeater is D8 here, and the assurance
case's D-G is D9.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class Status(str, Enum):
    OPEN = "open"
    DEFERRED = "deferred"
    ELIMINATED = "eliminated"
    #: The doubt is real but nothing it attacks exists yet (D6: no design is
    #: built from two generators). Not open, because no claim can be defeated
    #: by it today.
    NOT_YET_APPLICABLE = "not_yet_applicable"


class Defeater(BaseModel):
    model_config = ConfigDict(frozen=True, use_enum_values=True)

    id: str
    doubt: str
    applies_to: str
    status: Status
    eliminated_by: str
    trigger: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status in (Status.OPEN.value, Status.DEFERRED.value)


REGISTER: Dict[str, Defeater] = {d.id: d for d in (
    Defeater(
        id="D1",
        doubt="predict() is validated against mathematics and ngspice, not hardware",
        applies_to="every closed-form or simulated claim about circuit behaviour",
        status=Status.OPEN,
        eliminated_by="a bench measurement agreeing within tolerance",
        trigger="lab access; criterion 11 is met_by_substitute until then",
    ),
    Defeater(
        id="D2",
        doubt=("the MCU is represented by simplified electrical models — a "
               "resistive supply load sized from its run current (mcu_as_100R on "
               "the Uno, mcu_as_<R>R on other boards) and a Thevenin GPIO pin "
               "(mcu_pin_thevenin) — not the device"),
        applies_to="claims whose scope.model names an MCU model",
        status=Status.OPEN,
        eliminated_by="reachset conformance against the real device",
        trigger="nothing in Phase 2 is scheduled to close it",
    ),
    Defeater(
        id="D3",
        doubt="no external engineer has read a generated explanation cold",
        applies_to="the explanation layer",
        status=Status.DEFERRED,
        eliminated_by="criterion 12's review",
        trigger="before the first external user is shown an explanation",
    ),
    Defeater(
        id="D4",
        doubt="coverage growth cost may outrun one engineer",
        applies_to="the generator library as a whole",
        status=Status.OPEN,
        eliminated_by="measured authoring cost per generator (Stage 3 onward)",
    ),
    Defeater(
        id="D5",
        doubt="an LLM may write the IntentIR, so the specification is untrusted",
        applies_to="designs whose IntentIR provenance is llm and whose properties nobody has signed",
        status=Status.OPEN,
        eliminated_by=("per design: a person signs the back-translated properties "
                       "(POST /design/{id}/sign-off), which are then frozen"),
    ),
    Defeater(
        id="D6",
        doubt="block proofs may not compose into board claims",
        applies_to="any design built from more than one generator",
        status=Status.NOT_YET_APPLICABLE,
        eliminated_by="interface contracts, first tested when two generators share a rail",
    ),
    Defeater(
        id="D7",
        doubt="datasheet parameters feeding predict() and the rule tables are unverified",
        applies_to="claims that read ratings, forward voltages or pin tables",
        status=Status.OPEN,
        eliminated_by="provenance per parameter; no LLM-extracted rating gates a claim",
    ),
    Defeater(
        id="D8",
        doubt="pi is irrational, so a z3 encoding of f_c must bracket it",
        applies_to="z3-proved claims involving pi or another transcendental (Stage 4)",
        status=Status.ELIMINATED,
        eliminated_by=("rational bracketing in the proof compiler: proof/brackets.py encloses "
                       "pi, ln 9 and the LED logarithms with outward-rounded interval "
                       "arithmetic, and a refutation is certified at the bracket's adverse end"),
    ),
    Defeater(
        id="D9",
        doubt="a generator bug makes predict() confidently wrong and nothing catches it",
        applies_to="every generator not yet under the M1 mutation matrix",
        status=Status.OPEN,
        eliminated_by="the M1 matrix detecting seeded faults in that generator's output",
    ),
)}


def get(defeater_id: str) -> Defeater:
    return REGISTER[defeater_id]


def open_ids() -> tuple:
    return tuple(d.id for d in REGISTER.values() if d.is_open)
