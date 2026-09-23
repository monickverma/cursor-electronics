"""
RC low-pass generator — the first generator on the Task 0.2 contract.

PHASE_2_PLAN_v2.md Stage 0: *"RC low-pass ported; `predict()` matches ngspice
across the declared grid — empirical, G5 ≤ 2%."*

This is the module that makes amendment X1 concrete rather than documentary.
`predict()` computes `f_c = 1 / (2π·R·C)` in closed form over the component
tolerance box, so the answer it gives is a statement about every R and C inside
tolerance — not a measurement of the one nominal point an ngspice run would
visit. Simulation still guards it, in CI, across the grid `grid()` declares.

The band is exact rather than an over-approximation. `f_c` is monotone
decreasing in both R and C, so the extremes sit at opposite corners of the box
and evaluating two corners gives the true worst case. The formal-verification
report reaches the same conclusion — "exploit monotonicity… the four tolerance
corners give the exact worst case" — and its worked example is this circuit:
R ∈ [1574, 1606] Ω with C ∈ [90, 110] nF yields roughly 900 to 1125 Hz. This
module reproduces that, and `tests/test_rc_lowpass_generator.py` pins it.

Component choice is deterministic: a fixed capacitor table in declaration
order, R snapped to E96, ties broken by table position. Same intent in, same
parts out — which is half of the determinism property in v2 §4.1. The other
half, byte-identical CircuitIR, needs a `circuit_id` derived from the intent;
`generators/realize.py` stamps it, so this module does not work around it.

**Pinned parts (0.2.0).** `constraints.pinned` names parts the user already
has — `{"R1": "4.7k"}`, `{"C1": "100nF"}` — and the generator either honours
every pin or refuses naming it. Pins are requirements, not annotations: the
Stage 2 decision in `brain/decisions.md` [2026-09-21] keeps annotations out of
generation entirely, so this is the only place "use the part in my drawer" can
live. A pinned value is parsed by the same functions the SPICE netlist uses to
read it back, so a pin cannot mean one thing here and another in simulation.
A pinned part is assumed to be from the same series as the unpinned choice
(1% resistor, 10% capacitor); `predict()` bands say so through that tolerance.
Unpinned intents produce exactly what 0.1.0 produced.

**Strict inputs (0.2.1).** A requirement that is present but not a real,
finite number in range — `"12"`, `true`, `NaN`, a negative tolerance — is
refused by name instead of read as a default or as 1. Every intent 0.2.0
accepted with well-formed values produces the same design; only the ones it
accepted by misreading are now refused, which is why the version moves.

**Source loading is refused, not only reported (0.2.2).** A declared
`source_impedance_ohm` adds in series with R1 and lowers f_c by R_s/(R1+R_s).
0.2.1 read the value, accepted any, and let `rc.source_loading` report the
shift as failing on the design it had just produced — an accepted design
carrying its own failed claim. Found by the Stage 3 + 4 verification. Every
design 0.2.1 produced with the shift inside tolerance is unchanged.

**…and swamped before it is refused (0.2.3).** When the source would move f_c
past tolerance, a smaller catalogue capacitor is chosen so R1 is large enough
to keep the source's effect inside it — what the series-resistance comment
below always said and nothing did. Refused only when no catalogue pair
manages it, or when a pin fixes R1. Every design 0.2.2 accepted is unchanged;
at 1 kHz and 5% the largest source handled goes from 179 Ω to about 1.8 kΩ.
Compensating R1 by R_s was rejected: it changes every design that declares a
source, and makes the design depend on a declared value nobody verified.
Chosen with a TypeSafe (Jev) consultation; `brain/decisions.md` [2026-09-23].
"""

from __future__ import annotations

import math
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from core.ir_schema import (
    ApplicationClass,
    CircuitIR,
    Component,
    ComponentType,
    Connection,
    Node,
    SignalType,
    SimulationAnalysis,
    SimulationSpec,
    ValidationRule,
)
from generators.common import (
    Unreadable as _Unreadable,
    read_number as _read_number,
    requirements as _requirements,
    snap_to_e96,
    value_string as _value_string,
    yageo_code as _yageo_code,
)
from generators.protocol import (
    ClaimScope,
    EnvelopeDecision,
    GridSpec,
    IntentLike,
    Interval,
    PortContract,
    Prediction,
)
# The netlist's own value parsers. Pins are read with them so a pinned value
# means the same thing here as when the SPICE netlist reads it back.
from generators.netlist.spice import _parse_farads, _parse_ohms

NAME = "rc_lowpass"
VERSION = "0.2.3"
#: The requirements.function this generator serves. The registry reads it to
#: build the form's catalogue without probing envelope() with guesses.
FUNCTION = "low_pass_filter"

# The declared envelope. Below 10 Hz the capacitor gets impractically large for
# an 0402 part; above 100 kHz the parasitics this model ignores stop being
# ignorable, and `ClaimScope.model = mna_ideal` would be a claim the circuit
# does not keep. The upper bound is a modelling honesty limit, not a maths one.
MIN_CUTOFF_HZ = 10.0
MAX_CUTOFF_HZ = 100_000.0

# Series resistance is kept well above the source impedance the intent declares
# (the loading error is R_src/(R+R_src); `select_components` swamps it since
# 0.2.3) and below the point where bias currents and noise start to matter.
MIN_SERIES_OHMS = 1_000.0
MAX_SERIES_OHMS = 100_000.0

# Tolerances carried by the parts chosen below: Yageo RC…F… is 1%, the Samsung
# CL05 K-code is 10%. These are the same figures the project's accuracy gate
# already names, and the pair the research report works by hand.
R_TOLERANCE = 0.01
C_TOLERANCE = 0.10

# Capacitor catalogue, in preference order. Real 0402 parts; the voltage rating
# is load-bearing because `envelope()` refuses an intent whose supply exceeds it.
_CAPACITORS: Tuple[Tuple[float, str, str, float], ...] = (
    (100e-9, "100nF", "CL05B104KO5NNNC", 16.0),
    (10e-9, "10nF", "CL05B103KB5NNNC", 50.0),
    (1e-6, "1uF", "CL05A105KQ5NNNC", 6.3),
    (1e-9, "1nF", "CL05B102KB5NNNC", 50.0),
    (22e-9, "22nF", "CL05B223KO5NNNC", 16.0),
    (220e-9, "220nF", "CL05A224KQ5NNNC", 6.3),
    (4.7e-9, "4.7nF", "CL05B472KB5NNNC", 50.0),
    (47e-9, "47nF", "CL05B473KO5NNNC", 16.0),
)


def cutoff_hz(ohms: float, farads: float) -> float:
    """f_c = 1 / (2·pi·R·C)."""
    return 1.0 / (2.0 * math.pi * ohms * farads)


class _Selection:
    """A chosen R/C pair and what it actually achieves."""

    __slots__ = ("ohms", "farads", "c_value", "c_part", "c_vmax", "achieved_hz")

    def __init__(self, ohms: float, farads: float, c_value: str, c_part: str, c_vmax: float):
        self.ohms = ohms
        self.farads = farads
        self.c_value = c_value
        self.c_part = c_part
        self.c_vmax = c_vmax
        self.achieved_hz = cutoff_hz(ohms, farads)


def _target_cutoff(intent: IntentLike) -> Optional[float]:
    return _read_number(intent, "targets", "cutoff_hz", None,
                        allow_zero=False, what="a cutoff frequency in Hz")


def _tolerance_pct(intent: IntentLike) -> float:
    return _read_number(intent, "targets", "tolerance_pct", 5.0,
                        allow_zero=False, what="a tolerance in percent")


def _supply_v(intent: IntentLike) -> float:
    return _read_number(intent, "constraints", "supply_v", 5.0,
                        allow_zero=False, what="a rail voltage in volts")


def _source_impedance(intent: IntentLike) -> float:
    return _read_number(intent, "constraints", "source_impedance_ohm", 0.0,
                        allow_zero=True, what="a source impedance in ohms")


#: The parts a pin may name. Anything else is refused by name — pinning a part
#: this topology does not have is a request for a different circuit.
PINNABLE = ("R1", "C1")

_Capacitor = Tuple[float, str, str, float]


def source_shift_pct(source_ohms: float, series_ohms: float) -> float:
    """How far a source in series with R1 lowers f_c, in percent."""
    return source_ohms / (series_ohms + source_ohms) * 100.0 if source_ohms else 0.0


def select_components(
    target_hz: float,
    supply_v: float,
    r_pin: Optional[float] = None,
    c_pin: Optional[_Capacitor] = None,
    source_ohms: float = 0.0,
    tolerance_pct: Optional[float] = None,
) -> Optional[_Selection]:
    """
    Pick R and C for a target cutoff. Deterministic: capacitors are tried in
    table order, R is snapped to E96, and ties are broken by table position —
    so the same target always yields the same parts.

    A pinned capacitor restricts the table to that one entry; a pinned
    resistor replaces the E96 snap with the pinned value, and the capacitor is
    then the one that gets closest to the target around it.

    With a declared source and tolerance (0.2.3): if the closest pair lets
    the source move f_c past tolerance, the closest pair that keeps both the
    source's shift and its own error inside tolerance is taken instead — a
    smaller capacitor, a larger R1. Nothing changes for a pair that already
    passes, and nothing is swapped around a pin. If no pair passes, the
    closest is returned and `envelope()` refuses it by name.

    Returns None when nothing in the catalogue lands inside the series-resistance
    window, which is a refusal the caller turns into a named reason.
    """
    best: Optional[_Selection] = None
    best_err = float("inf")
    candidates = []

    for farads, c_value, c_part, c_vmax in ((c_pin,) if c_pin else _CAPACITORS):
        if supply_v > c_vmax:
            continue
        if r_pin is not None:
            ohms = r_pin
        else:
            ideal_r = 1.0 / (2.0 * math.pi * target_hz * farads)
            if not (MIN_SERIES_OHMS <= ideal_r <= MAX_SERIES_OHMS):
                continue
            ohms = snap_to_e96(ideal_r)
            if not (MIN_SERIES_OHMS <= ohms <= MAX_SERIES_OHMS):
                continue
        candidate = _Selection(ohms, farads, c_value, c_part, c_vmax)
        err = abs(candidate.achieved_hz - target_hz) / target_hz
        candidates.append((err, candidate))
        # Strict `<` keeps the earlier table entry on a tie, which is what
        # makes the choice reproducible rather than dict-order dependent.
        if err < best_err:
            best_err, best = err, candidate

    swampable = (best is not None and source_ohms and tolerance_pct is not None
                 and r_pin is None and c_pin is None)
    if swampable and source_shift_pct(source_ohms, best.ohms) > tolerance_pct:
        passing = [(err, c) for err, c in candidates
                   if err * 100.0 <= tolerance_pct and source_shift_pct(source_ohms, c.ohms) <= tolerance_pct]
        if passing:
            # min() keeps the first of equals: table order again.
            best = min(passing, key=lambda pair: pair[0])[1]
    return best


class _Pins:
    """Resolved `constraints.pinned`, or the reason it cannot be honoured."""

    __slots__ = ("r_ohms", "capacitor", "refusal")

    def __init__(
        self,
        r_ohms: Optional[float] = None,
        capacitor: Optional[_Capacitor] = None,
        refusal: Optional[str] = None,
    ) -> None:
        self.r_ohms = r_ohms
        self.capacitor = capacitor
        self.refusal = refusal

    @property
    def any(self) -> bool:
        return self.r_ohms is not None or self.capacitor is not None


def _resolve_pins(intent: IntentLike, supply_v: float) -> _Pins:
    """
    Read `constraints.pinned` and check each pin can be honoured.

    Every failure is a named refusal rather than a silent fallback to an
    unpinned choice: a user who pinned the 4.7 k in their drawer and got a
    4.75 k back has been handed a design they cannot build, and told nothing.
    """
    constraints = _requirements(intent).get("constraints") or {}
    pinned = constraints.get("pinned") if isinstance(constraints, Mapping) else None
    if pinned is None:
        return _Pins()
    if not isinstance(pinned, Mapping):
        return _Pins(refusal=(
            f"constraints.pinned must map part ids to values, e.g. "
            f"{{'R1': '4.7k'}}; got {type(pinned).__name__}"
        ))

    unknown = sorted(set(pinned) - set(PINNABLE))
    if unknown:
        return _Pins(refusal=(
            f"constraints.pinned names {unknown}; this generator's parts are "
            f"{list(PINNABLE)}"
        ))

    r_ohms: Optional[float] = None
    if "R1" in pinned:
        r_ohms = _pinned_value(pinned["R1"], _parse_ohms)
        if r_ohms is None or not math.isfinite(r_ohms) or r_ohms <= 0:
            return _Pins(refusal=(
                f"constraints.pinned.R1={pinned['R1']!r} is not a resistance "
                f"this system can read (e.g. '4.7k', '4k7', 4700)"
            ))
        if not (MIN_SERIES_OHMS <= r_ohms <= MAX_SERIES_OHMS):
            return _Pins(refusal=(
                f"constraints.pinned.R1={r_ohms:g}Ω is outside the "
                f"{MIN_SERIES_OHMS:g}–{MAX_SERIES_OHMS:g}Ω series window this "
                f"generator will build with"
            ))

    capacitor: Optional[_Capacitor] = None
    if "C1" in pinned:
        farads = _pinned_value(pinned["C1"], _parse_farads)
        if farads is None or not math.isfinite(farads) or farads <= 0:
            return _Pins(refusal=(
                f"constraints.pinned.C1={pinned['C1']!r} is not a capacitance "
                f"this system can read (e.g. '100nF', 1e-7)"
            ))
        capacitor = next(
            (c for c in _CAPACITORS if math.isclose(c[0], farads, rel_tol=1e-3)),
            None,
        )
        if capacitor is None:
            return _Pins(refusal=(
                f"constraints.pinned.C1={pinned['C1']!r} is not in this "
                f"generator's capacitor catalogue "
                f"({', '.join(c[1] for c in _CAPACITORS)})"
            ))
        if supply_v > capacitor[3]:
            return _Pins(refusal=(
                f"constraints.pinned.C1={capacitor[1]} is rated {capacitor[3]:g}V, "
                f"below the supply_v={supply_v:g} it would sit across"
            ))

    return _Pins(r_ohms=r_ohms, capacitor=capacitor)


def _pinned_value(raw: object, parse) -> Optional[float]:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str) and raw.strip():
        return parse(raw)
    return None


class RCLowPassGenerator:
    """Single-pole passive RC low-pass. Implements `generators.protocol.Generator`."""

    name = NAME
    version = VERSION
    function = FUNCTION

    #: X8 accounting (Stage 3): unimplemented rules this topology cannot violate.
    not_applicable_rules = {
        "current_limits_ok": "a passive filter driven by its source; no GPIO or current-rated part",
        "power_supply_adequate": "no supply rail: IN is a signal port, not a rail",
        "pullup_on_open_drain": "no open-drain line",
    }

    # ── envelope() ────────────────────────────────────────────────────────

    def envelope(self, intent: IntentLike) -> EnvelopeDecision:
        """
        Accept with the interface contract, or refuse with a reason specific
        enough to be a backlog entry. §4.5 makes the refusal log the generator
        backlog, so "unsupported" is not an acceptable reason — the offending
        value has to appear.
        """
        requirements = _requirements(intent)
        function = requirements.get("function")
        if function != FUNCTION:
            return EnvelopeDecision.refuse(
                f"function={function!r} is not low_pass_filter — this generator "
                f"produces single-pole passive RC low-pass filters only"
            )

        # Every number this generator reads is read here, before anything
        # downstream can use it. A value that is present but unusable is a
        # named refusal — never a default, and never an exception: a negative
        # or non-finite supply would otherwise reach `_ports()` as
        # Interval(lo=0, hi=supply_v), which Pydantic rejects, breaking the
        # contract that envelope() never raises. generate() and predict() are
        # only reached after this has accepted, so they read clean values.
        try:
            target = _target_cutoff(intent)
            supply_v = _supply_v(intent)
            tolerance_pct = _tolerance_pct(intent)
            source = _source_impedance(intent)
        except _Unreadable as exc:
            return EnvelopeDecision.refuse(str(exc))

        if target is None:
            return EnvelopeDecision.refuse(
                "targets.cutoff_hz is missing — a low-pass filter without a "
                "cutoff is underdetermined, not out of envelope"
            )
        if not (MIN_CUTOFF_HZ <= target <= MAX_CUTOFF_HZ):
            return EnvelopeDecision.refuse(
                f"cutoff_hz={target:g} outside declared envelope "
                f"{MIN_CUTOFF_HZ:g} Hz – {MAX_CUTOFF_HZ:g} Hz"
            )

        pins = _resolve_pins(intent, supply_v)
        if pins.refusal:
            return EnvelopeDecision.refuse(pins.refusal)

        selection = select_components(target, supply_v, pins.r_ohms, pins.capacitor,
                                      source, tolerance_pct)
        if selection is None:
            return EnvelopeDecision.refuse(
                f"no catalogue R/C pair puts the series resistor inside "
                f"{MIN_SERIES_OHMS:g}–{MAX_SERIES_OHMS:g} Ω at cutoff_hz="
                f"{target:g} with supply_v={supply_v:g}"
            )

        achieved_err_pct = abs(selection.achieved_hz - target) / target * 100.0
        if achieved_err_pct > tolerance_pct:
            pair = "pinned pair" if pins.any else "nearest E96 pair"
            return EnvelopeDecision.refuse(
                f"{pair} achieves {selection.achieved_hz:.1f} Hz against "
                f"cutoff_hz={target:g}, a {achieved_err_pct:.2f}% error that exceeds "
                f"the requested tolerance_pct={tolerance_pct:g}"
            )

        shift_pct = source_shift_pct(source, selection.ohms)
        if shift_pct > tolerance_pct:
            why = ("R1 or C1 is pinned, so R1 cannot be raised" if pins.any
                   else f"no catalogue capacitor allows an R1 (≤ {MAX_SERIES_OHMS / 1000:g} kΩ) large "
                        f"enough to swamp it")
            return EnvelopeDecision.refuse(
                f"a {source:g} Ω source in series with R1={selection.ohms:g} Ω lowers f_c by "
                f"{shift_pct:.2f}%, beyond tolerance_pct={tolerance_pct:g}, and {why} — buffer the "
                f"source, or allow more tolerance"
            )

        return EnvelopeDecision.accept(self._ports(intent, selection))

    def _selection(self, intent: IntentLike) -> _Selection:
        """The parts an accepted intent resolves to. Callers check envelope() first."""
        supply_v = _supply_v(intent)
        pins = _resolve_pins(intent, supply_v)
        selection = select_components(
            _target_cutoff(intent), supply_v, pins.r_ohms, pins.capacitor,
            _source_impedance(intent), _tolerance_pct(intent),
        )
        if selection is None or pins.refusal:
            raise ValueError("no selection for an intent envelope() refuses")
        return selection

    def _ports(self, intent: IntentLike, selection: _Selection) -> Sequence[PortContract]:
        """
        The interface contract. Unused until composition in Stage 3, declared
        from the first generator so that stage does not begin by editing five
        of these.

        Input impedance is the series resistor: what the upstream stage sees.
        Output impedance is frequency dependent and bounded above by R, which
        is the conservative reading and the one a composition side condition
        should use. A passive filter draws no supply current.
        """
        supply_v = _supply_v(intent)
        r_lo = selection.ohms * (1 - R_TOLERANCE)
        r_hi = selection.ohms * (1 + R_TOLERANCE)
        return (
            PortContract(
                name="IN",
                direction="input",
                impedance_ohm=Interval(lo=r_lo, hi=r_hi, nominal=selection.ohms, units="ohm"),
                voltage_range_v=Interval(lo=0.0, hi=supply_v, nominal=supply_v, units="V"),
            ),
            PortContract(
                name="OUT",
                direction="output",
                impedance_ohm=Interval(lo=0.0, hi=r_hi, nominal=selection.ohms / 2.0, units="ohm"),
                voltage_range_v=Interval(lo=0.0, hi=supply_v, nominal=supply_v, units="V"),
                current_draw_a=Interval(lo=0.0, hi=0.0, nominal=0.0, units="A"),
            ),
            PortContract(name="GND", direction="ground"),
        )

    # ── predict() ─────────────────────────────────────────────────────────

    def predict(
        self, intent: IntentLike, box: Optional[Mapping[str, Interval]] = None
    ) -> Prediction:
        """
        Closed-form behaviour over a parameter box.

        With `box` omitted the box is the part tolerances: R ±1%, C ±10%. With
        `box` supplied — degenerate intervals from `Interval.at` — this
        evaluates a single point, which is how the CI harness compares against
        one ngspice run at known component values.

        `f_c` is monotone decreasing in R and in C, so the band edges are the
        opposite corners of the box and two evaluations give the exact worst
        case. That is why `method` is `monotone_corners` and not `sampled`:
        EVIDENCE_CLASSES §3.2 grades those differently, and the distinction is
        the difference between a G1 claim and a G6 one.
        """
        # The envelope is the authority on what this generator will speak to,
        # so predict() asks it rather than re-deriving a weaker version.
        # Checking only that a cutoff and a catalogue pair exist let a caller
        # obtain a confident claim for an intent the generator had already
        # refused — a band-pass request, or a tolerance the selected pair
        # cannot meet. A claim outside the declared envelope is exactly the
        # thing `envelope()` exists to prevent.
        decision = self.envelope(intent)
        if not decision.accepted:
            raise ValueError(f"predict() called on a refused intent: {decision.reason}")

        selection = self._selection(intent)

        r_band, c_band = self._boxes(selection, box)

        # Opposite corners: smallest R with smallest C gives the highest cutoff.
        f_hi = cutoff_hz(r_band.lo, c_band.lo)
        f_lo = cutoff_hz(r_band.hi, c_band.hi)
        f_nominal = cutoff_hz(r_band.nominal, c_band.nominal)

        vin = _supply_v(intent)
        # At f_c the single-pole response is exactly -3.0103 dB of the input,
        # independent of R and C — so this band is a point however wide the
        # component tolerances are.
        vout_at_fc = vin / math.sqrt(2.0)

        return Prediction(
            quantities={
                "cutoff_hz": Interval(lo=f_lo, hi=f_hi, nominal=f_nominal, units="Hz"),
                "resistance_ohm": r_band,
                "capacitance_f": c_band,
                "vout_at_cutoff_v": Interval.at(vout_at_fc, "V"),
                "attenuation_at_cutoff_db": Interval.at(-20.0 * math.log10(math.sqrt(2.0)), "dB"),
            },
            scope=ClaimScope(
                parameters="nominal" if (r_band.is_point and c_band.is_point) else "tolerance_box",
                horizon="steady_state",
                model="mna_ideal",
                inputs="single_stimulus",
            ),
            method="monotone_corners",
        )

    def _boxes(
        self, selection: _Selection, box: Optional[Mapping[str, Interval]]
    ) -> Tuple[Interval, Interval]:
        """
        Resolve the parameter box, axis by axis.

        A partial box is honoured rather than ignored: pinning R alone and
        leaving C at tolerance is a legitimate thing to ask for, and an earlier
        version silently discarded any box that did not name both axes — so a
        caller pinning one parameter got the full tolerance band back with no
        indication it had been overruled. An unknown axis name is rejected
        outright, because a typo is otherwise indistinguishable from a
        deliberate omission.
        """
        known = {"R", "C"}
        if box:
            unknown = set(box) - known
            if unknown:
                raise ValueError(
                    f"predict() box names unknown parameters {sorted(unknown)}; "
                    f"this generator takes {sorted(known)}"
                )

        r = selection.ohms
        c = selection.farads
        r_band = Interval(
            lo=r * (1 - R_TOLERANCE), hi=r * (1 + R_TOLERANCE), nominal=r, units="ohm"
        )
        c_band = Interval(
            lo=c * (1 - C_TOLERANCE), hi=c * (1 + C_TOLERANCE), nominal=c, units="F"
        )
        if box:
            r_band = box.get("R", r_band)
            c_band = box.get("C", c_band)
        return r_band, c_band

    # ── claims() ──────────────────────────────────────────────────────────

    def claims(self, intent: IntentLike):
        """
        Stage 3 claim objects. The band is the EVIDENCE_CLASSES Table A example
        row; source loading is a claim of its own because `predict()`'s
        `mna_ideal` model drives IN from an ideal source and so cannot see it.
        """
        from validation.claims import graded

        pred = self.predict(intent)
        band, scope = pred.quantities["cutoff_hz"], pred.scope
        target, tolerance = _target_cutoff(intent), _tolerance_pct(intent)
        error = abs(band.nominal - target) / target * 100.0
        source = _source_impedance(intent)
        r1 = pred.quantities["resistance_ohm"].nominal
        # The source adds in series with R1: f_c' = 1/(2π(R1+R_s)C).
        shift = source / (r1 + source) * 100.0
        nominal = scope.model_copy(update={"parameters": "nominal"})
        return [
            graded("rc.cutoff_nominal",
                   f"f_c at nominal parts is within ±{tolerance:g}% of {target:g} Hz",
                   error <= tolerance, "closed_form", nominal,
                   detail=f"{band.nominal:.1f} Hz ({error:.2f}% from target)"),
            graded("rc.cutoff_band",
                   f"f_c lies in [{band.lo:.1f}, {band.hi:.1f}] Hz for every R within 1% and C within 10%",
                   True, "monotone_corners", scope,
                   detail="the 10% capacitor dominates; a 2% C0G part would narrow it fivefold"),
            graded("rc.source_loading",
                   f"a {source:g} Ω source lowers f_c by no more than ±{tolerance:g}%",
                   shift <= tolerance, "closed_form", nominal,
                   detail=f"R_s/(R1+R_s) = {shift:.2f}%"),
        ]

    # ── properties() ──────────────────────────────────────────────────────

    def properties(self, intent: IntentLike):
        """
        Stage 4: the cutoff band, proved from the netlist's own transfer
        function with π rationally bracketed. predict()'s band, rounded outward.
        """
        from proof.properties import PropertySpec, outward

        band = self.predict(intent).quantities["cutoff_hz"]
        lo, hi = outward(band.lo, band.hi)
        return [
            PropertySpec(id="rc.cutoff", label="the −3 dB cutoff frequency at OUT", quantity="cutoff(out)",
                         relation="within", lo=lo, hi=hi, units="Hz", re_derives="rc.cutoff_band"),
        ]

    # ── generate() ────────────────────────────────────────────────────────

    def generate(self, intent: IntentLike) -> CircuitIR:
        """
        Deterministic given (intent, version). Callers call `envelope()` first.

        `circuit_id`, `version` and `generator` are stamped afterwards by
        `generators/realize.py`, which is what makes the result byte-identical
        across calls; everything this method controls is already reproducible.
        """
        target = _target_cutoff(intent)
        if target is None:
            raise ValueError("generate() requires targets.cutoff_hz — call envelope() first")
        supply_v = _supply_v(intent)
        pins = _resolve_pins(intent, supply_v)
        selection = select_components(target, supply_v, pins.r_ohms, pins.capacitor,
                                      _source_impedance(intent), _tolerance_pct(intent))
        if selection is None or pins.refusal:
            raise ValueError("generate() called on an intent envelope() refuses")

        achieved = selection.achieved_hz
        source_z = _source_impedance(intent)
        loading_pct = (source_z / selection.ohms * 100.0) if selection.ohms else 0.0

        r_part = f"RC0402FR-07{_yageo_code(selection.ohms)}L"
        r_reason = (
            f"{selection.ohms:g}Ω, pinned by the requirement (constraints.pinned.R1) — "
            f"the part in hand, assumed from the same 1% series"
            if pins.r_ohms is not None else
            f"{selection.ohms:g}Ω, nearest E96 (1%) value to the "
            f"{1.0 / (2.0 * math.pi * target * selection.farads):.1f}Ω ideal"
        )
        c_reason = (
            "Pinned by the requirement (constraints.pinned.C1)."
            if pins.capacitor is not None else
            f"Chosen first because it puts R1 inside "
            f"{MIN_SERIES_OHMS:g}–{MAX_SERIES_OHMS:g}Ω."
        )

        return CircuitIR(
            intent=f"RC low-pass filter with {target:g} Hz cutoff frequency",
            application_class=ApplicationClass.HOBBY_ARDUINO,
            components=[
                Component(
                    id="R1",
                    type=ComponentType.RESISTOR,
                    part_number=r_part,
                    manufacturer="Yageo",
                    package="0402",
                    value=_value_string(selection.ohms),
                    supply_voltage_max=50.0,
                    confidence=0.95,
                    justification=(
                        f"{r_reason}. With "
                        f"C1={selection.c_value} it gives f_c = 1/(2π·R·C) = {achieved:.1f} Hz "
                        f"against the {target:g} Hz asked for. Raising R lowers the cutoff and "
                        f"raises the source loading error, currently "
                        f"{loading_pct:.2f}% at a {source_z:g}Ω source impedance; the part number "
                        f"is encoded from the Yageo RC0402FR-07…L series and needs a stock check "
                        f"before ordering."
                    ),
                ),
                Component(
                    id="C1",
                    type=ComponentType.CAPACITOR,
                    part_number=selection.c_part,
                    manufacturer="Samsung",
                    package="0402",
                    value=selection.c_value,
                    supply_voltage_max=selection.c_vmax,
                    confidence=0.95,
                    justification=(
                        f"{selection.c_value} ceramic, rated {selection.c_vmax:g}V against a "
                        f"{supply_v:g}V supply. {c_reason} A 10% part, so it dominates "
                        f"the cutoff tolerance — the ±1% resistor contributes roughly a tenth as "
                        f"much spread."
                    ),
                ),
            ],
            nodes=[
                Node(id="IN", voltage_nominal=supply_v, type=SignalType.ANALOG),
                Node(id="OUT", type=SignalType.ANALOG),
                Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
            ],
            connections=[
                Connection(component_id="R1", pin="A", node_id="IN"),
                Connection(component_id="R1", pin="B", node_id="OUT"),
                Connection(component_id="C1", pin="+", node_id="OUT"),
                Connection(component_id="C1", pin="-", node_id="GND"),
            ],
            constraints={"supply_voltage": supply_v, "cutoff_hz": target},
            simulation_spec=SimulationSpec(
                analyses=[
                    SimulationAnalysis(
                        type="ac_sweep",
                        description=f"Verify -3dB cutoff at {achieved:.1f} Hz",
                        f_start=max(achieved / 100.0, 0.1),
                        f_stop=achieved * 100.0,
                        points_per_decade=20,
                    )
                ],
                expected_outputs={"OUT": supply_v / math.sqrt(2.0)},
            ),
            validation_rules=[
                ValidationRule.NO_FLOATING_NODES,
                ValidationRule.VOLTAGE_RATINGS_OK,
            ],
        )

    # ── CI grid and locality ──────────────────────────────────────────────

    def grid(self) -> GridSpec:
        """
        Three decades of the declared envelope. A single 1 kHz point passes on
        a generator with a decade-scaling bug, which is the same reason the
        criterion-11 harness sweeps rather than spot-checks.
        """
        return GridSpec(
            axes={"cutoff_hz": [100.0, 330.0, 1_000.0, 3_300.0, 10_000.0, 33_000.0, 100_000.0]},
            units={"cutoff_hz": "Hz"},
        )

    def dependency_closure(self, requirement_path: str) -> FrozenSet[str]:
        """
        Narrow where it can be. A conservative closure is sound but makes the
        Stage 2 locality check vacuous, so the real dependencies are declared
        here.

        **`supply_v` reaches R1, and the Stage 0 version said it could not.**
        It declared `{C1}` on the reasoning that only the capacitor carries a
        voltage rating. True, and incomplete: above 16 V the 100 nF part drops
        out of the catalogue, a different capacitor is chosen, and R1 is
        re-snapped around it. The Stage 2 locality check found it on its first
        sweep — a closure that is too narrow is worse than a conservative one,
        because it is believed. `test_realize.py` pins the crossing.

        A path is matched exactly, then by its longest declared prefix, so
        `constraints.pinned.R1` resolves through `constraints.pinned`.
        Anything undeclared gets the whole design — sound, and visibly vacuous.
        """
        closures: Dict[str, FrozenSet[str]] = {
            "targets.cutoff_hz": frozenset({"R1", "C1"}),
            "targets.tolerance_pct": frozenset({"R1", "C1"}),
            # A new rating can change the capacitor, which re-snaps R1.
            "constraints.supply_v": frozenset({"R1", "C1"}),
            # Since 0.2.3 a large source swaps the capacitor to raise R1.
            "constraints.source_impedance_ohm": frozenset({"R1", "C1"}),
            # A pin on either part re-chooses the other around it.
            "constraints.pinned": frozenset({"R1", "C1"}),
            "preferences.package": frozenset({"R1", "C1"}),
        }
        path = requirement_path
        while path:
            if path in closures:
                return closures[path]
            path = path.rpartition(".")[0]
        return frozenset({"R1", "C1"})
