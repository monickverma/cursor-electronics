"""
Stage 4 — the proof compiler. `backend/proof/`.

PHASE_2_PLAN_v2.md §5 Stage 4 gates, each G1, and where each is pinned:

- Divider and LED claims proven over full tolerance       TestGates
- RC cutoff proven over full tolerance, π bracketed        TestGates
- Every property back-translated (signed: test_sign_off)   TestBackTranslation
- Adversarial weakening: the refine loop cannot change a
  frozen property                                          TestFrozenProperty
- Every proven property fails under an injected wrong value TestMutation

Plus what the gates rest on: the brackets really contain the transcendentals,
the netlist is read exactly, nodal analysis gives the textbook formulas, and a
"refuted" verdict is only ever a *certified* counterexample.

Design record: `brain/decisions.md` [2026-09-23].
"""

from fractions import Fraction

import mpmath
import pytest
import sympy

from ai.form_producer import FormProducer
from core.intent_ir import IntentIR, Producer, Provenance
from generators.led_indicator import LedIndicatorGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.realize import realize
from generators.registry import default_registry
from generators.voltage_divider import VoltageDividerGenerator
from proof import brackets, mna
from proof.netlist import parse, spice_value
from proof.properties import (
    BenchElement,
    PropertySpec,
    exact,
    outward,
    set_hash,
    si,
)
from proof.prover import (
    DEFAULT_STRATEGIES,
    Direct,
    FrozenPropertyViolation,
    Obligation,
    Problem,
    ProofResult,
    Strategy,
    _verdict,
    check,
    compile_statement,
    decide,
    falsify,
    mutate,
    part_value,
    prove,
)
from validation.claims import METHOD_GRADE, assess
from validation.defeaters import REGISTER, Status
from generators.protocol import boards_of, grid_of
from validation.grid_adapters import intent_at

REGISTRY = default_registry()
FORMS = FormProducer(REGISTRY)

DEFAULTS = {
    "low_pass_filter": {"cutoff_hz": 1000, "supply_v": 5},
    "voltage_divider": {"vout_v": 3.3, "supply_v": 5},
    "led_indicator": {"led_current_ma": 10, "supply_v": 5},
    "temperature_humidity_sensor": {"cable_length_m": 5, "supply_v": 5},
    "modbus_rtu_master": {"supply_v": 5},
}


def design(function):
    intent = FORMS.build(function, DEFAULTS[function])
    generator = REGISTRY.dispatch(intent).generator
    return generator, intent, generator.generate(intent)


def grid_designs():
    """Every accepted point of every generator's declared CI grid, on every board (Stage 5)."""
    for g in REGISTRY.generators:
        for board in boards_of(g):
            grid = grid_of(g, board)
            for point in grid.points():
                it = intent_at(g.function, point, grid.sections,
                               {"constraints": {"mcu": board}} if board else None)
                if g.envelope(it).accepted:
                    yield g, point, it, g.generate(it)


# ── The brackets ─────────────────────────────────────────────────────────────

def _encloses(bracket, true) -> bool:
    """Compare exact rationals with a value computed at 80 digits."""
    lo, hi = bracket
    with mpmath.workdps(80):
        return mpmath.mpf(lo.numerator) / lo.denominator < true() < mpmath.mpf(hi.numerator) / hi.denominator


class TestBrackets:
    """D8: π and the logarithms enter only as rational enclosures of the true value."""

    def test_pi_is_enclosed_and_tight(self):
        lo, hi = brackets.pi()
        assert isinstance(lo, Fraction) and isinstance(hi, Fraction)
        assert _encloses((lo, hi), lambda: +mpmath.pi)
        assert hi - lo < Fraction(1, 10**35)

    def test_ln_9_is_enclosed(self):
        assert _encloses(brackets.ln(Fraction(9)), lambda: mpmath.log(9))

    def test_expm1_is_enclosed(self):
        bracket = brackets.expm1_ratio(Fraction(17, 10), Fraction(5, 100))
        assert _encloses(bracket, lambda: mpmath.expm1(mpmath.mpf(17) / 10 / (mpmath.mpf(5) / 100)))

    def test_ln_refuses_a_non_positive_argument(self):
        with pytest.raises(ValueError):
            brackets.ln(Fraction(0))

    def test_d8_is_eliminated_by_the_brackets(self):
        assert REGISTER["D8"].status == Status.ELIMINATED.value
        assert not REGISTER["D8"].is_open


# ── Reading the netlist ──────────────────────────────────────────────────────

class TestNetlist:
    def test_values_are_exact(self):
        assert spice_value("4.7k") == 4700
        assert spice_value("1G") == 10**9
        assert spice_value("1MEG") == 10**6
        assert spice_value("100n") == Fraction(1, 10**7)
        assert spice_value("1e-07") == Fraction(1, 10**7)
        # Binary noise in the text is read as written, digit for digit.
        assert spice_value("4.7000000000000004e-08") != Fraction(47, 10**9)

    def test_part_value_removes_float_noise_only(self):
        assert part_value(spice_value("4.7000000000000004e-08")) == Fraction(47, 10**9)
        assert part_value(Fraction(1590)) == 1590

    def test_an_element_the_prover_cannot_read_is_refused_not_skipped(self):
        with pytest.raises(ValueError, match="not supported"):
            parse("V1 a 0 DC 5\nL1 a 0 1u\n.end")

    def test_a_diode_without_its_model_is_refused(self):
        with pytest.raises(ValueError, match="undefined model"):
            parse("V1 a 0 DC 5\nD1 a 0 DX\n.end")

    def test_every_generated_netlist_parses(self):
        for g, _, _, circuit in grid_designs():
            netlist = parse(SpiceNetlistGenerator().generate(circuit))
            assert netlist.elements, g.name

    def test_bench_elements_are_appended_not_merged(self):
        base = parse("V1 a 0 DC 5\nR1 a 0 1k\n.end")
        with_load = base.with_bench(["R_BENCH a 0 2k"])
        assert [e.name for e in with_load.elements] == ["V1", "R1", "R_BENCH"]
        assert [e.name for e in base.elements] == ["V1", "R1"]


# ── Nodal analysis ───────────────────────────────────────────────────────────

class TestMNA:
    R1, R2, C = sympy.symbols("R1 R2 C", positive=True)

    def test_divider_is_the_textbook_formula(self):
        net = parse("V_VIN vin 0 DC 5\nR1 vin vout 1k\nR2 vout 0 1k\n.end")
        v = mna.dc(net, {"R1": self.R1, "R2": self.R2}).v("vout")
        assert sympy.simplify(v - 5 * self.R2 / (self.R1 + self.R2)) == 0

    def test_thevenin_of_a_divider(self):
        net = parse("V_VIN vin 0 DC 5\nR1 vin vout 1k\nR2 vout 0 1k\n.end")
        v_th, r_th = mna.thevenin(net, {"R1": self.R1, "R2": self.R2}, "vout", "0")
        assert sympy.simplify(v_th - 5 * self.R2 / (self.R1 + self.R2)) == 0
        assert sympy.simplify(r_th - self.R1 * self.R2 / (self.R1 + self.R2)) == 0

    def test_rc_transfer_function(self):
        net = parse("V_IN in 0 AC 5\nR1 in out 1k\nC1 out 0 100n\n.end")
        h = mna.transfer(net, {"R1": self.R1, "C1": self.C}, "out")
        assert sympy.simplify(h - 1 / (1 + mna.S * self.R1 * self.C)) == 0

    def test_source_current_follows_spice_sign(self):
        net = parse("V1 a 0 DC 5\nR1 a 0 1k\n.end")
        # SPICE: current into the positive terminal, so a source delivering
        # power reads negative.
        assert mna.dc(net, {}).i("V1") == sympy.Rational(-5, 1000)

    def test_a_diode_is_never_stamped_linearly(self):
        net = parse("V1 a 0 DC 5\nR1 a b 1k\nD1 b 0 DX\n.model DX D (Is=1e-14 N=1)\n.end")
        with pytest.raises(ValueError, match="cannot be stamped linearly"):
            mna.dc(net, {})


# ── Back-translation ─────────────────────────────────────────────────────────

class TestBackTranslation:
    @pytest.mark.parametrize("lo,hi", [(896.43, 1117.2), (0.008194, 0.011371), (3.2791, 3.3363),
                                       (1e-3, 2.5e-3), (54.0, 54.0)])
    def test_outward_bounds_never_tighten_the_band(self, lo, hi):
        out_lo, out_hi = outward(lo, hi)
        assert Fraction(out_lo) <= Fraction(repr(lo)) and Fraction(out_hi) >= Fraction(repr(hi))
        assert "e" not in out_lo.lower() and "e" not in out_hi.lower()

    def test_ranges_are_rounded_inward(self):
        # A signed sentence may claim less than was proved, never more.
        assert si(Fraction("543.51"), "ohm", 4, "up") == "543.6 Ω"
        assert si(Fraction("554.49"), "ohm", 4, "down") == "554.4 Ω"

    def test_exact_writes_limits_without_binary_noise(self):
        assert exact(5.0, -6) == "0.000005"
        assert exact(270.0, -12) == "0.00000000027"
        assert exact(0.0625) == "0.0625"

    def test_every_property_on_every_grid_design_reads_as_its_bounds(self):
        for g, point, it, circuit in grid_designs():
            for spec in g.properties(it):
                statement, _, _ = check(circuit, spec)
                shown = [b for b in (spec.lo, spec.hi) if b is not None]
                for b in shown:
                    assert si(b, spec.units) in statement.english, (g.name, point, spec.id)
                for v in statement.variables:
                    assert v.label in statement.english
                assert statement.english[0].isupper() and statement.english.endswith(".")

    def test_the_hash_covers_the_bounds(self):
        _, intent, circuit = design("voltage_divider")
        spec = VoltageDividerGenerator().properties(intent)[0]
        looser = spec.model_copy(update={"hi": str(Fraction(spec.hi) + 1)})
        a, _ = compile_statement(circuit, spec, SpiceNetlistGenerator().generate(circuit))
        b, _ = compile_statement(circuit, looser, SpiceNetlistGenerator().generate(circuit))
        assert a.hash != b.hash and a.english != b.english

    def test_back_translation_is_deterministic(self):
        _, intent, circuit = design("led_indicator")
        netlist = SpiceNetlistGenerator().generate(circuit)
        for spec in LedIndicatorGenerator().properties(intent):
            first, _ = compile_statement(circuit, spec, netlist)
            second, _ = compile_statement(circuit, spec, netlist)
            assert first.english == second.english and first.hash == second.hash

    def test_a_boxed_bench_element_reads_as_a_range_not_a_condition(self):
        _, intent, circuit = design("modbus_rtu_master")
        spec = REGISTRY.by_name("rs485_node").properties(intent)[0]
        statement, _, _ = check(circuit, spec)
        assert "every far-end terminator from 118.8 Ω to 121.2 Ω" in statement.english
        assert statement.english.count("terminator") == 1


# ── The gates ────────────────────────────────────────────────────────────────

class TestGates:
    def test_divider_claims_proven_over_the_full_tolerance_box(self):
        seen = 0
        for g, point, it, circuit in grid_designs():
            if g.name != "voltage_divider":
                continue
            for spec in g.properties(it):
                statement, _, result = check(circuit, spec)
                assert result.status == "proven", (point, spec.id, result.detail)
                assert METHOD_GRADE[result.method] == "G1"
                for v in statement.variables:
                    # The full box: ±1% of the part, not a sample of it.
                    nominal = Fraction(v.hi) / Fraction(101, 100)
                    assert Fraction(v.lo) == nominal * Fraction(99, 100)
                seen += 1
        assert seen >= 9 * 3 - 3

    #: Stage 5: the one grid design whose R1 range straddles the dissipation
    #: peak (R1 = R_out + r_d). The Black Pill's pins span 20–65 Ω, and 13 mA
    #: needs R1 = 66.5 Ω, so no end of R1's range is the maximum and Task 4.5's
    #: lemma cannot pick one: the prover falls back to the sound enclosure, G2.
    #: Pinned, so a prover that closes the gap — or widens it — says so here.
    STRADDLES_THE_PEAK = {("blackpill_f411ce", 13.0)}

    def test_led_claims_proven_over_the_full_tolerance_box(self):
        seen, enclosed = 0, set()
        for g, point, it, circuit in grid_designs():
            if g.name != "led_indicator":
                continue
            board = it.requirements["constraints"].get("mcu", "arduino_uno")
            for spec in g.properties(it):
                statement, _, result = check(circuit, spec)
                assert result.status == "proven", (point, spec.id, result.detail)
                # R1's dissipation too, since Task 4.5: decided at the end of
                # R1's range a proven lemma puts the peak at — unless the
                # range straddles the peak.
                if METHOD_GRADE[result.method] != "G1":
                    assert (spec.id, result.method) == ("led.r1_power", "sound_enclosure"), spec.id
                    enclosed.add((board, point["led_current_ma"]))
                labels = {v.label for v in statement.variables}
                assert {"R1", "U1 pin resistance"} <= labels
                assert "forward voltage anywhere in its datasheet range of 1.7–2.4 V" in statement.english
                seen += 1
        assert seen == 4 * 4 * 3   # four properties, four points, three boards
        assert enclosed == self.STRADDLES_THE_PEAK

    def test_rc_cutoff_proven_with_pi_bracketed(self):
        seen = 0
        for g, point, it, circuit in grid_designs():
            if g.name != "rc_lowpass":
                continue
            (spec,) = g.properties(it)
            statement, problem, result = check(circuit, spec)
            assert result.status == "proven" and result.method == "z3_unsat", point
            assert statement.uses_pi and statement.bracketed
            pi_brackets = {b for ob in problem.obligations for b in ob.brackets if b[0] == "PI"}
            assert pi_brackets, "π must enter as a bracket, never as a float"
            for _, lo, hi in pi_brackets:
                assert _encloses((Fraction(lo), Fraction(hi)), lambda: +mpmath.pi)
            seen += 1
        assert seen == 7

    def test_the_rc_claim_cites_d8_as_answered(self):
        g, intent, _ = design("low_pass_filter")
        coverage = assess(g, intent, realize(g, intent))
        row = next(c for c in coverage.claims if c.id == "proof.rc.cutoff")
        assert "D8" in row.defeaters and "D8" not in coverage.open_defeaters

    def test_a_band_tighter_than_the_parts_is_refuted_with_a_certified_counterexample(self):
        g, intent, circuit = design("low_pass_filter")
        spec = PropertySpec(id="rc.hand_band", label="the cutoff", quantity="cutoff(out)",
                            relation="within", lo="900", hi="1130", units="Hz")
        _, _, result = check(circuit, spec)
        assert result.status == "refuted"
        assert "certified" in result.detail
        # The 10% capacitor at its top end pulls f_c below 900 Hz.
        assert float(result.counterexample["C_C1"]) > 50e-9

    def test_a_linear_quantity_on_a_circuit_with_a_diode_is_refused(self):
        _, _, circuit = design("led_indicator")
        spec = PropertySpec(id="x", label="x", quantity="v(led_anode)", relation="le", hi="5", units="V")
        with pytest.raises(ValueError, match="linear"):
            check(circuit, spec)


# ── Certified refutation ─────────────────────────────────────────────────────

class TestRefutationIsCertified:
    def test_led_dissipation_is_decided_exactly_either_side_of_its_worst_case(self):
        """
        Task 4.5. The bound the old enclosure could not decide — above the true
        worst case, below largest-current × largest-R1 — is now proven, and a
        hair under the true worst case is refuted with a certified point.
        """
        g, intent, circuit = design("led_indicator")
        worst = g.predict(intent).quantities["r1_power_mw"].hi / 1000
        for factor, status in ((1.0001, "proven"), (0.9999, "refuted")):
            spec = PropertySpec(id="led.tight_power", label="R1's dissipation",
                                quantity="series_power(R_R1,D_LED1)", relation="le",
                                hi=exact(round(worst * factor, 9)), units="W")
            _, problem, result = check(circuit, spec)
            assert result.status == status, (factor, result.detail)
            assert problem.method == "z3_unsat" and problem.witness is None
        assert "certified" in result.detail

    def test_an_enclosure_that_is_too_loose_is_undecided_not_refuted(self):
        """
        With R1 close to the rest of the loop's resistance, R1's range straddles
        the peak of I²·R1: neither monotone lemma holds, and the proof falls back
        to a current bound (G2). Choose P_max above the true worst case but
        below what that bound reaches: no point exceeds P_max, and the answer
        must be `unknown`.
        """
        from generators.led_indicator import r1_power_max_w
        from proof.prover import mutate

        _, _, circuit = design("led_indicator")
        text = SpiceNetlistGenerator().generate(circuit)
        r1 = float(parse(text).element("R_R1").value)
        factor = Fraction(30) / Fraction(str(r1))
        text = mutate(text, "R_R1", factor)
        r1 = float(parse(text).element("R_R1").value)
        worst = r1_power_max_w(5.0, r1 * 0.99, r1 * 1.01, 15.0, "min")
        spec = PropertySpec(id="led.tight_power", label="R1's dissipation", quantity="series_power(R_R1,D_LED1)",
                            relation="le", hi=exact(round(worst * 1.003, 9)), units="W")
        _, problem, result = check(circuit, spec, text)
        assert problem.method == "sound_enclosure" and problem.witness is not None
        assert result.status == "unknown", result.detail
        assert result.counterexample is None

    def test_a_counterexample_inside_the_bracket_slack_is_not_a_counterexample(self):
        g, intent, circuit = design("low_pass_filter")
        spec = g.properties(intent)[0]
        statement, _, _ = check(circuit, spec)
        lo, hi = brackets.pi()
        mid = (lo + hi) / 2
        # "PI ≤ mid" fails somewhere in the bracket, but whether it fails at π
        # itself the bracket cannot say. The refuter collapses PI to the end
        # that would make a violation certain — and there is none.
        ob = Obligation(label="PI <= mid", expr=sympy.srepr(sympy.Symbol("PI", positive=True)), op="le",
                        bound=sympy.srepr(sympy.Rational(mid.numerator, mid.denominator)),
                        brackets=(("PI", str(lo), str(hi)),), exact=False,
                        refute=Obligation(label="certified", expr=sympy.srepr(sympy.Rational(lo.numerator, lo.denominator)),
                                          op="le", bound=sympy.srepr(sympy.Rational(mid.numerator, mid.denominator))))
        result = prove(statement, Problem(obligations=(ob,), method="z3_unsat"))
        assert result.status == "unknown"

    def test_a_failed_lemma_is_unknown_never_refuted(self):
        g, intent, circuit = design("voltage_divider")
        statement, _, _ = check(circuit, g.properties(intent)[0])
        lemma = Obligation(label="false lemma", expr=sympy.srepr(sympy.Integer(-1)), op="gt",
                           bound=sympy.srepr(sympy.Integer(0)), lemma=True)
        result = prove(statement, Problem(obligations=(lemma,), method="z3_unsat"))
        assert result.status == "unknown" and "lemma" in result.detail


# ── The frozen property ──────────────────────────────────────────────────────

def _frozen(function="voltage_divider"):
    g, intent, circuit = design(function)
    spec = g.properties(intent)[0]
    netlist = SpiceNetlistGenerator().generate(circuit)
    statement, problem = compile_statement(circuit, spec, netlist)
    return circuit, spec, netlist, statement, problem


class TestFrozenProperty:
    """
    Stage 4 gate: the refine loop cannot change a frozen property. Each
    strategy below is an adversary that tries to report a proof of something
    easier; `prove()` must raise rather than accept it.
    """

    def test_the_honest_strategies_are_accepted(self):
        _, _, _, statement, problem = _frozen()
        for strategies in (DEFAULT_STRATEGIES, (Direct(),)):
            assert prove(statement, problem, strategies).status == "proven"

    def test_a_proof_of_a_looser_bound_is_refused(self):
        circuit, spec, netlist, statement, problem = _frozen()
        looser = spec.model_copy(update={"lo": "0", "hi": "100"})
        weak_statement, weak_problem = compile_statement(circuit, looser, netlist)

        class Loosen(Strategy):
            name = "loosen"

            def run(self, s, p, box):
                return _verdict(weak_statement, weak_problem, box, self.name, decide)

        with pytest.raises(FrozenPropertyViolation, match="different statement"):
            prove(statement, problem, (Loosen(),))

    def test_a_proof_that_keeps_the_hash_but_weakens_an_obligation_is_refused(self):
        _, _, _, statement, problem = _frozen()
        weakened = Problem(method=problem.method, obligations=tuple(
            ob.model_copy(update={"bound": sympy.srepr(sympy.Integer(0 if ob.op == "ge" else 100))})
            for ob in problem.obligations
        ))

        class Swap(Strategy):
            name = "swap"

            def run(self, s, p, box):
                return _verdict(s, weakened, box, self.name, decide)   # the frozen statement's hash, a weaker problem

        with pytest.raises(FrozenPropertyViolation, match="not the frozen property"):
            prove(statement, problem, (Swap(),))

    def test_a_proof_that_drops_an_obligation_is_refused(self):
        _, _, _, statement, problem = _frozen()
        assert len(problem.obligations) >= 2      # the bounds, plus a denominator lemma

        class Drop(Strategy):
            name = "drop"

            def run(self, s, p, box):
                return ProofResult(property_id=s.spec.id, statement_hash=s.hash, status="proven",
                                   method=p.method, strategy=self.name,
                                   discharged=(p.obligations[0].hash,))

        with pytest.raises(FrozenPropertyViolation, match="without discharging every obligation"):
            prove(statement, problem, (Drop(),))

    def test_a_smaller_box_is_a_different_statement(self):
        _, _, _, statement, _ = _frozen()
        # Narrowing a part's range changes what the sentence says, so it
        # changes the hash — the loop cannot shrink the domain silently.
        narrowed = statement.model_copy(update={"variables": tuple(
            v.model_copy(update={"lo": v.nominal, "hi": v.nominal}) for v in statement.variables)})
        assert narrowed.hash != statement.hash

    def test_frozen_objects_cannot_be_edited_in_place(self):
        _, _, _, statement, problem = _frozen()
        with pytest.raises(Exception):
            statement.spec.hi = "100"          # noqa: B018 - pydantic frozen
        with pytest.raises(Exception):
            problem.obligations[0].bound = "0"


def _false_band():
    """A property that is false over its box: the 10% capacitor breaks [900, 1130] Hz."""
    _, _, circuit = design("low_pass_filter")
    spec = PropertySpec(id="rc.hand_band", label="the cutoff", quantity="cutoff(out)",
                        relation="within", lo="900", hi="1130", units="Hz")
    return compile_statement(circuit, spec, SpiceNetlistGenerator().generate(circuit))


class TestTheCertificateIsChecked:
    """
    Found by the Stage 3 + 4 verification: the loop checked hashes only, so a
    strategy that decided the nominal point alone returned "proven" for a
    property that is false over the box — and was accepted. The loop now
    checks the certificate tiles the frozen box and re-decides every box.
    """

    def test_the_honest_loop_refutes_the_false_band(self):
        statement, problem = _false_band()
        assert prove(statement, problem).status == "refuted"

    def test_a_proof_over_a_smaller_box_is_refused(self):
        statement, problem = _false_band()

        class Nominal(Strategy):
            name = "nominal-only"

            def run(self, s, p, box):
                point = {k: ((lo + hi) / 2, (lo + hi) / 2) for k, (lo, hi) in box.items()}
                return _verdict(s, p, point, self.name, decide)

        with pytest.raises(FrozenPropertyViolation, match="undecided"):
            prove(statement, problem, (Nominal(),))

    def test_a_certificate_that_counts_half_the_box_twice_is_refused(self):
        # A true property, so every half really is UNSAT: only the tiling
        # check can see that the other half was never decided.
        _, _, _, statement, problem = _frozen()

        class Twice(Strategy):
            name = "twice"

            def run(self, s, p, box):
                name = sorted(box)[0]
                lo, hi = box[name]
                half = {**box, name: (lo, (lo + hi) / 2)}
                return _verdict(s, p, box, self.name, lambda ob, b: (*decide(ob, half), [half, half]))

        with pytest.raises(FrozenPropertyViolation, match="twice"):
            prove(statement, problem, (Twice(),))

    def test_a_certificate_box_that_is_not_unsat_is_refused(self):
        statement, problem = _false_band()

        class Claims(Strategy):
            name = "claims-without-deciding"

            def run(self, s, p, box):
                return _verdict(s, p, box, self.name, lambda ob, b: ("unsat", None, None))

        with pytest.raises(FrozenPropertyViolation, match="not UNSAT"):
            prove(statement, problem, (Claims(),))

    def test_an_honest_bisection_certificate_is_accepted(self, monkeypatch):
        import proof.prover as prover

        _, _, _, statement, problem = _frozen()
        real = prover.decide
        full = {prover._symbol(v.element).name: (Fraction(v.lo), Fraction(v.hi)) for v in statement.variables}
        # z3 "cannot decide" the whole box, so Direct gives up and Bisect splits it.
        monkeypatch.setattr(prover, "decide", lambda ob, box: ("unknown", None, None) if box == full else real(ob, box))
        result = prove(statement, problem)
        assert result.status == "proven" and result.strategy == "bisect"
        assert all(len(boxes) > 1 for _, boxes in result.certificate)

    def test_every_proof_carries_a_certificate_for_every_obligation(self):
        _, _, _, statement, problem = _frozen()
        result = prove(statement, problem)
        assert {h for h, _ in result.certificate} == {ob.hash for ob in problem.obligations}


class TestDenominators:
    """z3 reads x/0 as any value; a denominator that can vanish must not yield a proof."""

    def test_every_symbolic_denominator_is_a_lemma(self):
        _, _, _, _, problem = _frozen()
        labels = [ob.label for ob in problem.obligations if ob.lemma]
        assert any("denominator" in label for label in labels)

    def test_a_denominator_that_can_vanish_makes_the_property_unknown(self):
        _, intent, circuit = design("voltage_divider")
        # A negative "resistor" puts a pole inside R1's box: R1 − 3400 = 0 at nominal.
        netlist = "V_VIN vin 0 DC 5\nR_R1 vin vout 3400.0\nR_NEG vout 0 -3400\n.op\n.end"
        spec = PropertySpec(id="x", label="the voltage at VOUT", quantity="v(vout)", relation="le",
                            hi="1000", units="V")
        _, _, result = check(circuit, spec, netlist)
        assert result.status == "unknown" and "denominator" in result.detail


# ── Mutation ─────────────────────────────────────────────────────────────────

class TestMutation:
    """
    Stage 4 gate: every proven property fails under an injected wrong value.
    A property no wrong part can break says nothing about the parts.
    """

    def test_every_property_on_every_grid_design_is_falsified_by_a_wrong_part(self):
        checked = 0
        for g, point, it, circuit in grid_designs():
            for spec in g.properties(it):
                _, _, result = check(circuit, spec)
                assert result.status == "proven"
                witness = falsify(circuit, spec)
                assert witness is not None, f"{g.name} {point} {spec.id}: no wrong value refutes it"
                assert witness.result.status == "refuted" and witness.result.counterexample
                checked += 1
        assert checked >= 60

    def test_mutate_scales_one_element_and_refuses_a_missing_one(self):
        text = "V1 a 0 DC 5\nR_R1 a b 1000.0\nR_R2 b 0 1000.0\n.end"
        mutated = parse(mutate(text, "R_R1", Fraction(10)))
        assert mutated.element("R_R1").value == 10000 and mutated.element("R_R2").value == 1000
        assert parse(mutate(text, "V1", Fraction(2))).element("V1").value == 10
        with pytest.raises(KeyError):
            mutate(text, "R_R9", Fraction(2))


# ── Integration ──────────────────────────────────────────────────────────────

class TestRealizeCarriesProofs:
    def test_every_generator_declares_properties_and_every_one_is_proven(self):
        for function in DEFAULTS:
            g, intent, _ = design(function)
            coverage = realize(g, intent).validation_coverage
            assert coverage["properties"], g.name
            assert all(p["status"] == "proven" for p in coverage["properties"]), g.name
            assert coverage["properties_hash"] and coverage["properties_signed"] is False

    def test_the_proofs_are_deterministic(self):
        g, intent, _ = design("led_indicator")
        a, b = realize(g, intent), realize(g, intent)
        assert a.validation_coverage == b.validation_coverage

    def test_the_set_hash_is_over_the_statements(self):
        g, intent, _ = design("voltage_divider")
        circuit = realize(g, intent)
        statements = [check(circuit, spec)[0] for spec in g.properties(intent)]
        assert circuit.validation_coverage["properties_hash"] == set_hash(statements)

    def test_an_llm_written_intent_is_proved_the_same_way(self):
        form = FORMS.build("voltage_divider", DEFAULTS["voltage_divider"])
        llm = IntentIR(requirements=form.requirements,
                       provenance=Provenance(producer=Producer.LLM, model="claude-test"))
        g = REGISTRY.dispatch(llm).generator
        a = realize(g, form).validation_coverage
        b = realize(g, llm).validation_coverage
        assert [p["english"] for p in a["properties"]] == [p["english"] for p in b["properties"]]
        assert "D5" in b["open_defeaters"] and "D5" not in a["open_defeaters"]

    def test_the_divider_load_is_a_bench_condition_in_the_sentence(self):
        intent = IntentIR(requirements={"function": "voltage_divider", "targets": {"vout_v": 3.3},
                                        "constraints": {"supply_v": 5, "load_ohm": 100000}},
                          provenance=Provenance(producer=Producer.FORM))
        g = REGISTRY.dispatch(intent).generator
        spec = g.properties(intent)[0]
        assert spec.bench and isinstance(spec.bench[0], BenchElement)
        statement, _, result = check(g.generate(intent), spec)
        assert result.status == "proven"
        assert "a 100 kΩ load on VOUT" in statement.english
