"""
The form producer. PHASE_2_PLAN_v2.md §4.2 and §5 Stage 1.

> **The form** is the reference producer. Fields derive from the generator
> registry, so the form *is* the envelope catalogue — a user can see what the
> system covers before asking. Zero API calls. Works offline.
>
> **The LLM** is a convenience layer over the same schema, for free text.

Two consequences the plan states plainly, and this module is what makes them
true rather than aspirational. The system becomes **provably LLM-optional**,
which is the strongest available demonstration of the architecture and what an
offline college install depends on. And the refusal-rate problem softens:
users self-select against a visible catalogue instead of discovering the
envelope by being refused.

**The catalogue is derived, never written down beside the generators.** Fields
come from each generator's declared `function` and `grid()`, so a catalogue
that disagrees with what is installed is not expressible. A hand-maintained
list of "what we support" is the same stale-copy failure this project keeps
being bitten by, one layer out.

**The ranges shown are the grid's, and the grid is a subset of the envelope.**
A generator sweeps its declared grid in CI; its `envelope()` may accept beyond
the sampled points. Showing grid bounds is therefore conservative — the form
never advertises coverage that CI has not exercised, which is the direction an
honest catalogue should err in. `FormField.exercised_in_ci` says so explicitly
rather than leaving the reader to assume the bounds are hard limits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from core.intent_ir import IntentIR, Producer, Provenance
from generators.protocol import boards_of, grid_of
from generators.registry import GeneratorRegistry, default_registry


class FormField(BaseModel):
    """
    One thing the user can specify, and what the system will accept for it.

    `section` is which half of `requirements` it lands in. The split matters:
    a target is what `predict()` is checked against, a constraint bounds the
    design space, and a preference may be traded away. A form that flattened
    them would let a preference silently become a target.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    section: str  # targets | constraints | preferences
    units: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    required: bool = True
    #: Whether the declared range is one CI actually sweeps. False means the
    #: bounds are advisory and the envelope is the authority.
    exercised_in_ci: bool = True
    #: A categorical field's values (Stage 5: `constraints.mcu`, the board).
    #: None for a number.
    choices: Optional[Tuple[str, ...]] = None

    def describe(self) -> str:
        if self.choices:
            return f"{self.name} (one of {', '.join(self.choices)})"
        span = ""
        if self.minimum is not None and self.maximum is not None:
            unit = f" {self.units}" if self.units else ""
            span = f" ({self.minimum:g}–{self.maximum:g}{unit})"
        return f"{self.name}{span}"


class FormSpec(BaseModel):
    """What the form offers for one `requirements.function`."""

    model_config = ConfigDict(frozen=True)

    function: str
    generators: Sequence[str]
    fields: Sequence[FormField]

    def field_names(self) -> Tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def required_fields(self) -> Tuple[FormField, ...]:
        return tuple(f for f in self.fields if f.required)


#: Fields every circuit needs regardless of function. Kept here rather than
#: derived because they are properties of the deployment, not of a generator —
#: no generator declares "there is a supply rail"; they all assume one.
_UNIVERSAL_FIELDS: Tuple[FormField, ...] = (
    FormField(
        name="supply_v", section="constraints", units="V",
        required=True, exercised_in_ci=False,
    ),
    FormField(
        name="source_impedance_ohm", section="constraints", units="ohm",
        required=False, exercised_in_ci=False,
    ),
    FormField(
        name="tolerance_pct", section="targets", units="%",
        required=False, exercised_in_ci=False,
    ),
)


class FormProducer:
    """
    Builds IntentIR from structured input. Zero API calls, no network.

    The reference producer: if this and the LLM producer ever disagree about
    what a valid intent looks like, this one is right, because it is the one
    derived from what is installed.
    """

    def __init__(self, registry: Optional[GeneratorRegistry] = None) -> None:
        self._registry = registry if registry is not None else default_registry()

    # ── The catalogue ─────────────────────────────────────────────────────

    def catalogue(self) -> Tuple[FormSpec, ...]:
        """Every function the installed generators cover, with their fields."""
        return tuple(self.spec_for(fn) for fn in self._registry.functions())

    def spec_for(self, function: str) -> FormSpec:
        generators = self._registry.for_function(function)
        if not generators:
            raise ValueError(
                f"no installed generator provides {function!r}; the catalogue "
                f"covers {list(self._registry.functions())}"
            )

        fields: List[FormField] = []
        derived_names = set()
        sections = self._grid_sections(generators)
        for name, (minimum, maximum, units) in self._grid_bounds(generators).items():
            derived_names.add(name)
            fields.append(FormField(
                name=name, section=sections[name], units=units,
                minimum=minimum, maximum=maximum, required=True,
            ))

        # Stage 5: the board, when the function's generators design for more
        # than one. Offered only as far as CI sweeps: each generator's grid runs
        # on every board it declares. Optional — the default is the Uno.
        boards = self._boards(generators)
        if boards:
            fields.append(FormField(name="mcu", section="constraints", choices=boards, required=False))

        # A generator whose grid axis shares a name with a universal field
        # would otherwise produce the field twice, and `build()` keys by name —
        # so the second silently shadowed the first, routing the value into
        # the wrong section and losing the declared range. The generator's own
        # declaration wins: it is the one that knows the range it sweeps.
        fields.extend(f for f in _UNIVERSAL_FIELDS if f.name not in derived_names)

        return FormSpec(
            function=function,
            generators=tuple(g.name for g in generators),
            fields=tuple(fields),
        )

    def _boards(self, generators: Sequence[Any]) -> Tuple[str, ...]:
        """Every board any of the function's generators declares, in declaration order."""
        seen: List[str] = []
        for generator in generators:
            seen += [b for b in boards_of(generator) if b is not None and b not in seen]
        return tuple(seen)

    def _grids(self, generator: Any) -> List[Any]:
        """A generator's declared grid on each board it declares (one grid without)."""
        return [grid_of(generator, board) for board in boards_of(generator)]

    def _grid_bounds(
        self, generators: Sequence[Any]
    ) -> Dict[str, Tuple[float, float, Optional[str]]]:
        """
        The union of every generator's swept range, per axis.

        Union rather than intersection: if one generator covers 10–100 Hz and
        another 100 Hz–100 kHz, the function is offered across both. Dispatch
        decides which one takes a given request, and a refusal names why.
        """
        bounds: Dict[str, Tuple[float, float, Optional[str]]] = {}
        for grid in (g for generator in generators for g in self._grids(generator)):
            for axis, values in grid.axes.items():
                low, high = min(values), max(values)
                units = grid.units.get(axis)
                if axis in bounds:
                    prev_low, prev_high, prev_units = bounds[axis]
                    bounds[axis] = (min(prev_low, low), max(prev_high, high), prev_units or units)
                else:
                    bounds[axis] = (low, high, units)
        return bounds

    def _grid_sections(self, generators: Sequence[Any]) -> Dict[str, str]:
        """
        Which section each axis belongs in. Two generators placing one axis in
        different sections is a catalogue bug, refused rather than resolved:
        whichever won, one generator would read the value from the wrong place.
        """
        sections: Dict[str, str] = {}
        for grid in (g for generator in generators for g in self._grids(generator)):
            for axis in grid.axes:
                section = grid.section_of(axis)
                if sections.setdefault(axis, section) != section:
                    raise ValueError(
                        f"generators disagree on the section of {axis!r}: "
                        f"{sections[axis]!r} vs {section!r}"
                    )
        return sections

    # ── Production ────────────────────────────────────────────────────────

    def build(
        self,
        function: str,
        values: Mapping[str, Any],
        *,
        strict: bool = True,
    ) -> IntentIR:
        """
        Turn form input into an IntentIR. Never calls a model.

        Missing required fields become `underdetermined` entries rather than
        errors, because the Stage 1 gate is *"`underdetermined` non-empty →
        the system asks, never generates"* — a half-filled form is a question
        to put back to the user, not a failure.

        `strict` rejects field names the catalogue does not offer. A typo that
        silently lands in `requirements` would be read by no generator and
        would look like the user never asked for it.
        """
        spec = self.spec_for(function)
        known = {f.name: f for f in spec.fields}

        if strict:
            unknown = sorted(set(values) - set(known))
            if unknown:
                raise ValueError(
                    f"{function!r} does not take {unknown}; it takes "
                    f"{sorted(known)}"
                )

        requirements: Dict[str, Dict[str, Any]] = {
            "targets": {}, "constraints": {}, "preferences": {},
        }
        for name, value in values.items():
            field = known.get(name)
            if field is not None and field.choices and value is not None and value not in field.choices:
                raise ValueError(f"{name}={value!r} is not one of {list(field.choices)}")
            if field is None:
                requirements["preferences"][name] = value
                continue
            if value is not None:
                requirements[field.section][name] = value

        underdetermined = [
            f"{field.section}.{name}"
            for name, field in known.items()
            if field.required and values.get(name) is None
        ]

        return IntentIR(
            requirements={"function": function, **requirements},
            underdetermined=underdetermined,
            provenance=Provenance(producer=Producer.FORM),
        )
