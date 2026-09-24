"""
Explanation by derivation rather than by model call. Task 0.5, PHASE_2_PLAN_v2.md §4.4.

The experiment this exists to settle:

> *"Test whether the explanation is derivable in Stage 0. If `predict()` returns
> closed-form performance and `IntentIR` holds the requirements, then 'R1 is
> 10 k because you specified 3.3 V logic and a 20 mA budget' is a template
> fill. If that holds, the dominant per-design cost disappears and the product
> works offline. It is cheap to test and it is the single highest-leverage
> experiment in Phase 2."*

The thing that makes it plausible is not clever templating. It is that under
this architecture **the generator already knows why it chose what it chose**: a
deterministic generator picks components from the requirements by a rule it can
state, and `rc_lowpass` writes that rule into each component's `justification`
as it builds the design. `predict()` then supplies the consequences in closed
form, over the tolerance box rather than at a nominal point. This module
assembles those into prose. Nothing here invents a reason; it reports reasons
that already exist as data.

**Scope of what this can and cannot settle.** `tests/test_explainer.py` scores
consequential language by keyword, and says of itself that keyword checks catch
a prompt regression rather than a quality regression. So this module can be
measured against *the bar the test suite enforces* — never against "as good as
the model". Criterion 12 exists precisely because no test measures whether an
explanation actually lands with a reader, and it is still open. Do not let a
passing marker count here be read as the explanation layer being solved.
"""

from __future__ import annotations

from typing import List, Optional

from ai.explainer import consequential_markers
from core.ir_schema import CircuitIR
from core.ir_validator import IRValidationResult
from generators.protocol import Interval, Prediction

#: Quantities whose units read better inline than as bare numbers.
_UNIT_HINT = {"Hz": "Hz", "V": "V", "A": "A", "ohm": "Ω", "F": "F", "dB": "dB"}


def _fmt(value: float, units: str) -> str:
    """Engineering-ish formatting. Readers do not want 9.959633e+03."""
    symbol = _UNIT_HINT.get(units, units)
    if units == "F":
        for suffix, scale in (("µF", 1e-6), ("nF", 1e-9), ("pF", 1e-12)):
            if abs(value) >= scale:
                return f"{value / scale:.6g} {suffix}"
        return f"{value:.3g} F"
    if units == "ohm":
        if abs(value) >= 1e6:
            return f"{value / 1e6:.6g} MΩ"
        if abs(value) >= 1e3:
            return f"{value / 1e3:.6g} kΩ"
        return f"{value:.6g} Ω"
    if units == "Hz" and abs(value) >= 1e3:
        return f"{value / 1e3:.6g} kHz"
    return f"{value:.6g} {symbol}"


def _spread_pct(band: Interval) -> float:
    if not band.nominal:
        return 0.0
    return max(abs(band.hi - band.nominal), abs(band.nominal - band.lo)) / abs(band.nominal) * 100.0


class DerivedExplainer:
    """
    Deterministic explanation. Zero API calls, zero network, works offline.

    Mirrors `ExplanationEngine.explain`'s shape so the two can be swapped and
    compared, with two extra inputs the model call does not get — the
    prediction and the requirements — because those are what make derivation
    possible at all.
    """

    def explain(
        self,
        ir: CircuitIR,
        validation_result: Optional[IRValidationResult] = None,
        simulation_results: Optional[dict] = None,
        prediction: Optional[Prediction] = None,
        requirements: Optional[dict] = None,
    ) -> str:
        sections: List[str] = [
            self._what_was_asked(ir, requirements),
            self._what_was_built(ir),
            self._what_it_will_do(prediction),
            self._what_breaks(ir, prediction, requirements),
            self._what_is_not_covered(prediction, simulation_results),
        ]
        if validation_result is not None:
            sections.insert(3, self._validation(validation_result))
        if simulation_results:
            sections.insert(4, self._simulation(simulation_results))
        return "\n\n".join(s for s in sections if s).strip()

    # ── Sections ──────────────────────────────────────────────────────────

    def _what_was_asked(self, ir: CircuitIR, requirements: Optional[dict]) -> str:
        if not requirements:
            return f"## What you asked for\n\n{ir.intent}"
        targets = requirements.get("targets") or {}
        constraints = requirements.get("constraints") or {}
        lines = [f"## What you asked for\n\n{ir.intent}", ""]
        for key, value in targets.items():
            lines.append(f"- **{key}**: {value}")
        for key, value in constraints.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _what_was_built(self, ir: CircuitIR) -> str:
        """
        The per-component reasons, which the generator authored as it chose
        each part. This is the section that would otherwise need a model.
        """
        lines = ["## Why each component"]
        for component in ir.components:
            value = f" — {component.value}" if component.value else ""
            lines.append(
                f"\n**{component.id}** ({component.part_number}{value})\n\n"
                f"{component.justification}"
            )
            if component.confidence < 0.9:
                lines.append(
                    f"\nConfidence on this choice is {component.confidence:.0%}. "
                    f"Check it against your own requirements before ordering — "
                    f"a wrong part here would not be caught by simulation, "
                    f"because simulation models the value, not the part."
                )
        return "\n".join(lines)

    def _what_it_will_do(self, prediction: Optional[Prediction]) -> str:
        if prediction is None:
            return ""
        lines = ["## What it will do"]
        for name, band in prediction.quantities.items():
            if band.is_point:
                lines.append(f"\n- **{name}**: {_fmt(band.nominal, band.units)}")
                continue
            lines.append(
                f"\n- **{name}**: {_fmt(band.nominal, band.units)} nominal, "
                f"and between {_fmt(band.lo, band.units)} and "
                f"{_fmt(band.hi, band.units)} across the full component "
                f"tolerance — a spread of ±{_spread_pct(band):.1f}%."
            )
        lines.append(
            f"\nThese are closed-form results over the whole tolerance box, not "
            f"a single simulated point, computed by {prediction.method.replace('_', ' ')}."
        )
        return "\n".join(lines)

    def _what_breaks(
        self,
        ir: CircuitIR,
        prediction: Optional[Prediction],
        requirements: Optional[dict] = None,
    ) -> str:
        """
        The consequential half — what fails if something changes. Derived from
        the tolerance spread and the component ratings already in the IR.
        """
        # Collected separately from the heading: an IR with no supply rail and
        # no component ratings produces nothing to say here, and a heading
        # promising consequences with nothing under it reads as "nothing
        # breaks" — a false reassurance is worse than an absent section.
        lines: List[str] = []

        if prediction is not None:
            widest = self._widest_contributor(prediction, requirements)
            if widest:
                name, band = widest
                lines.append(
                    f"\n- The **{name}** tolerance dominates the result at "
                    f"±{_spread_pct(band):.1f}%. Tightening anything else would barely "
                    f"move the outcome; if you need a narrower band, that is the "
                    f"part to change."
                )

        supply = ir.constraints.get("supply_voltage")
        for component in ir.components:
            if component.supply_voltage_max is None or supply is None:
                continue
            headroom = component.supply_voltage_max - supply
            if headroom <= 0:
                lines.append(
                    f"\n- **{component.id}** is rated "
                    f"{component.supply_voltage_max:g} V against a {supply:g} V rail. "
                    f"It is already at or past its rating and would fail in service."
                )
            elif headroom < supply * 0.25:
                lines.append(
                    f"\n- **{component.id}** has only {headroom:g} V of margin over "
                    f"the {supply:g} V rail. Raising the supply would exceed its "
                    f"{component.supply_voltage_max:g} V rating."
                )
            else:
                lines.append(
                    f"\n- **{component.id}** is rated {component.supply_voltage_max:g} V "
                    f"on a {supply:g} V rail, so it has margin; it would only become "
                    f"a risk if you raised the supply above "
                    f"{component.supply_voltage_max:g} V."
                )
        if not lines:
            return ""
        return "\n".join(["## What breaks if you change it"] + lines)

    def _widest_contributor(self, prediction: Prediction, requirements: Optional[dict]):
        """
        The widest *input* tolerance, not the widest quantity.

        `predict()` returns the predicted outputs alongside the component
        parameters that produced them, and the output band is necessarily
        wider than any single input. Taking the widest of everything named
        `cutoff_hz` as "the part to change" — which is the result, not a part.
        Anything the requirements asked for is a target, so it is excluded.
        """
        targets = set((requirements or {}).get("targets") or {})
        candidates = [
            (name, band)
            for name, band in prediction.quantities.items()
            if not band.is_point and band.nominal and name not in targets
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: _spread_pct(item[1]))

    def _validation(self, result: IRValidationResult) -> str:
        if not result.errors and not result.warnings:
            return (
                "## Validation\n\nEvery structural rule passed. That does not mean "
                "the design is correct — it means nothing it checks for is wrong."
            )
        lines = ["## Validation"]
        for error in result.errors:
            lines.append(f"\n- **Error** at `{error.field_path}`: {error.message}")
        for warning in result.warnings:
            lines.append(f"\n- Warning at `{warning.field_path}`: {warning.message}")
        return "\n".join(lines)

    def _simulation(self, simulation_results: dict) -> str:
        grade = str(simulation_results.get("grade", "")).upper()
        lines = ["## Simulation"]
        if grade == "FAIL":
            lines.append(
                "\nSimulation **failed**. The numbers below disagree with what "
                "was asked for, and shipping this without resolving that would "
                "risk a board that does not meet its own specification."
            )
        for key, value in simulation_results.items():
            if key == "grade":
                continue
            lines.append(f"\n- {key}: {value}")
        return "\n".join(lines)

    def _what_is_not_covered(
        self, prediction: Optional[Prediction], simulation_results: Optional[dict]
    ) -> str:
        """
        What the claim does *not* cover. EVIDENCE_CLASSES §4: "not assessed"
        and "out of scope" are printed rows — omission is how a validation
        report lies without stating a falsehood.
        """
        lines = ["## What this does not tell you"]
        if prediction is not None:
            scope = prediction.scope
            lines.append(
                f"\n- These numbers hold under the **{scope.model}** model, over "
                f"{scope.parameters.replace('_', ' ')}, at {scope.horizon.replace('_', ' ')}, "
                f"for a {scope.inputs.replace('_', ' ')}. Outside that they say nothing."
            )
            lines.append(
                "\n- The model is mathematics, not hardware. It cannot see parasitic "
                "inductance, board capacitance, contact resistance, or a part behaving "
                "outside its datasheet — any of those would shift the real result "
                "away from the numbers above."
            )
        lines.append(
            "\n- Thermal behaviour, EMI, and manufacturing yield are not assessed at all."
        )
        return "\n".join(lines)


def explanation_markers(text: str) -> List[str]:
    """
    The consequential-language markers this explanation is scored on.

    Delegates to `ai.explainer`, which owns the list, so the experiment is
    measured against the bar the repo already enforces on the model rather
    than a copy of it that can drift. An earlier version duplicated the list
    here — identical on the day it was written, and one edit away from two
    explainers being held to different standards without anyone noticing.
    """
    return consequential_markers(text)
