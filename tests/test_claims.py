"""
Stage 3 — claim objects, `validation_coverage`, and the defeater register.

`validation/claims.py` and `validation/defeaters.py`; EVIDENCE_CLASSES.md §3–§5
and amendments X6 + X8 (`brain/decisions.md` [2026-09-21]).

The invariants worth pinning, each one a way a validation report could lie
without stating a falsehood:

- a grade is **derived from method**, never typed — a hand-assigned G1 is a G7
- a claim citing an **open defeater** cannot say plain "holds"
- **nothing is averaged**: the floor is the worst critical grade
- **not assessed** is the catalogue minus what was actually checked; checking
  less can never look better
- implemented rules run **whether or not a design lists them** — the silent
  skip X8 exists to end
"""

import pytest
from pydantic import ValidationError

from core.ir_examples import IR_001, IR_002, IR_003, IR_005
from core.ir_schema import ValidationRule
from generators.netlist.models import VT, solve_series_diode
from generators.protocol import ClaimScope, EnvelopeDecision, GridSpec, PortContract
from simulation.parser import SpiceResultParser
from validation.claims import (
    METHOD_GRADE,
    UNIMPLEMENTED_RULES,
    Claim,
    Kind,
    ValidationCoverage,
    Verdict,
    assess,
    graded,
    netlist_models,
)
from validation.defeaters import REGISTER, Status

SCOPE = ClaimScope(model="mna_ideal")


def row(id_, grade_method="monotone_corners", holds=True, critical=True, defeaters=("D1",)):
    return graded(id_, f"claim {id_}", holds, grade_method, SCOPE, defeaters=defeaters, critical=critical)


# ── The claim itself ─────────────────────────────────────────────────────────

class TestClaimInvariants:
    def test_grade_follows_from_method(self):
        assert row("a", "monotone_corners").grade == "G1"
        assert row("b", "sound_enclosure").grade == "G2"
        assert row("c", "ngspice_nominal").grade == "G5"

    def test_a_typed_grade_that_disagrees_with_its_method_is_refused(self):
        with pytest.raises(ValidationError, match="derived, never typed"):
            Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.HOLDS,
                  method="sampled", grade="G1", scope=SCOPE)

    def test_an_unknown_method_is_refused(self):
        with pytest.raises(ValidationError, match="unknown method"):
            Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.HOLDS,
                  method="vibes", grade="G1", scope=SCOPE)

    def test_an_open_defeater_makes_a_claim_defeasible(self):
        assert row("a", defeaters=("D1",)).verdict == Verdict.HOLDS_DEFEASIBLE.value
        with pytest.raises(ValidationError, match="defeasible"):
            Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.HOLDS,
                  method="closed_form", grade="G1", scope=SCOPE, defeaters=("D1",))

    def test_a_claim_with_no_open_defeater_holds_plainly(self):
        # D8 is not yet applicable (no z3 proofs until Stage 4), so not open.
        assert row("a", defeaters=("D8",)).verdict == Verdict.HOLDS.value

    def test_an_unregistered_defeater_is_refused(self):
        with pytest.raises(ValidationError, match="unregistered"):
            row("a", defeaters=("D99",))

    def test_a_verdict_needs_a_method_and_a_scope(self):
        with pytest.raises(ValidationError, match="no method or scope"):
            Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.FAILS)

    def test_not_assessed_is_g7(self):
        with pytest.raises(ValidationError, match="G7"):
            Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.NOT_ASSESSED)
        Claim(id="x", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.NOT_ASSESSED, grade="G7")

    def test_every_method_maps_to_a_known_grade(self):
        assert set(METHOD_GRADE.values()) <= {f"G{i}" for i in range(8)}


# ── Coverage: never averaged ─────────────────────────────────────────────────

class TestCoverage:
    def test_floor_is_the_worst_critical_grade_not_an_average(self):
        cov = ValidationCoverage.summarise([
            row("a", "monotone_corners"), row("b", "monotone_corners"), row("c", "ngspice_nominal"),
        ])
        assert cov.grade_floor == "G5"
        assert cov.coverage_le_g2 == pytest.approx(2 / 3, abs=1e-3)

    def test_a_non_critical_row_does_not_move_the_floor(self):
        cov = ValidationCoverage.summarise([row("a"), row("b", "sampled", critical=False)])
        assert cov.grade_floor == "G1"

    def test_not_applicable_and_out_of_scope_rows_do_not_count(self):
        na = Claim(id="na", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.NOT_APPLICABLE)
        oos = Claim(id="oos", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.OUT_OF_SCOPE, critical=False)
        cov = ValidationCoverage.summarise([row("a"), na, oos])
        assert cov.coverage_le_g2 == 1.0 and cov.out_of_scope == ("oos",)

    def test_a_not_assessed_row_is_the_floor(self):
        gap = Claim(id="gap", claim="x", kind=Kind.ANALYTIC, verdict=Verdict.NOT_ASSESSED, grade="G7")
        cov = ValidationCoverage.summarise([row("a"), gap])
        assert cov.grade_floor == "G7" and cov.not_assessed == ("gap",)
        assert cov.coverage_le_g2 == 0.5

    def test_open_defeaters_are_reported_beside_the_floor_never_folded_in(self):
        cov = ValidationCoverage.summarise([row("a", defeaters=("D2", "D1"))])
        assert cov.grade_floor == "G1"
        assert cov.open_defeaters == ("D1", "D2")

    def test_failures_are_listed(self):
        cov = ValidationCoverage.summarise([row("a"), row("b", holds=False)])
        assert [c.id for c in cov.failures] == ["b"]


# ── X8 on designs no generator vouches for ───────────────────────────────────

class _Bare:
    """A generator with no claims and no accounting — the worst case for X8."""

    name = "bare"
    version = "0.0.1"
    function = "bare"

    def envelope(self, intent):
        return EnvelopeDecision.accept((PortContract(name="P", direction="input"),))


class TestX8:
    def test_unaccounted_rules_are_printed_as_not_assessed(self):
        cov = assess(_Bare(), object(), IR_003)
        assert set(cov.not_assessed) == {f"rule.{r}" for r in UNIMPLEMENTED_RULES}
        assert cov.grade_floor == "G7"

    def test_listing_a_rule_does_not_make_it_checked(self):
        # IR_001 lists pullup_on_open_drain and power_supply_adequate. Neither
        # has an implementation; both must read "not assessed", not "passed".
        cov = assess(_Bare(), object(), IR_001)
        assert "rule.pullup_on_open_drain" in cov.not_assessed
        assert "rule.power_supply_adequate" in cov.not_assessed

    def test_implemented_rules_run_whether_or_not_they_are_listed(self):
        # IR_005 has RS-485 lines; strip its listing and the rules still run.
        unlisted = IR_005.model_copy(update={"validation_rules": [ValidationRule.NO_FLOATING_NODES]})
        by_id = {c.id: c for c in assess(_Bare(), object(), unlisted).claims}
        assert by_id["rule.rs485_termination_present"].verdict in ("holds", "holds_defeasible")
        assert by_id["rule.rs485_bias_resistors"].verdict in ("holds", "holds_defeasible")

    def test_a_missing_terminator_fails_even_unlisted(self):
        no_term = IR_005.model_copy(update={
            "components": [c for c in IR_005.components if c.id != "R1"],
            "connections": [c for c in IR_005.connections if c.component_id != "R1"],
            "validation_rules": [],
        })
        by_id = {c.id: c for c in assess(_Bare(), object(), no_term).claims}
        assert by_id["rule.rs485_termination_present"].verdict == "fails"

    def test_a_declared_port_counts_as_a_connection(self):
        # IR_003's IN node has one connection. Declared as a port by the real
        # generator's envelope, it is where the next stage attaches — not
        # floating. Undeclared (the bare generator's only port is "P"), the
        # same node is floating and the rule fails.
        from core.intent_ir import IntentIR, Producer, Provenance
        from generators.rc_lowpass import RCLowPassGenerator

        intent = IntentIR(requirements={"function": "low_pass_filter", "targets": {"cutoff_hz": 1000}},
                          provenance=Provenance(producer=Producer.FORM))
        with_port = {c.id: c for c in assess(RCLowPassGenerator(), intent, IR_003).claims}
        without = {c.id: c for c in assess(_Bare(), object(), IR_003).claims}
        assert with_port["rule.no_floating_nodes"].verdict == "holds"
        assert without["rule.no_floating_nodes"].verdict == "fails"
        assert "IN" in without["rule.no_floating_nodes"].detail

    def test_out_of_scope_is_always_printed(self):
        cov = assess(_Bare(), object(), IR_003)
        assert "scope.thermal" in cov.out_of_scope and "rule.operating_temp_range" in cov.out_of_scope

    def test_a_generator_outside_the_m1_matrix_carries_d9(self):
        # D9: a generator bug that makes predict() confidently wrong, with
        # nothing to catch it. Every physics claim from an uncovered generator
        # cites it; the same claim from a covered one does not.
        class _Uncovered(_Bare):
            def claims(self, intent):
                return [row("physics", defeaters=("D1",))]

        class _Covered(_Uncovered):
            name = "rc_lowpass"

        uncovered = {c.id: c for c in assess(_Uncovered(), object(), IR_003).claims}
        covered = {c.id: c for c in assess(_Covered(), object(), IR_003).claims}
        assert "D9" in uncovered["physics"].defeaters
        assert "D9" not in covered["physics"].defeaters


class TestX6:
    def test_models_are_read_from_the_netlist(self):
        assert netlist_models(IR_001) == ("mcu_as_100R",)
        assert netlist_models(IR_003) == ()

    def test_the_phase1_led_template_has_no_driven_pin(self):
        # Its GPIO node declares no voltage, so the pin model does not apply —
        # the finding that the Phase 1 simulation never lit the LED.
        assert netlist_models(IR_002) == ("mcu_as_100R",)


# ── The register ─────────────────────────────────────────────────────────────

class TestDefeaterRegister:
    def test_one_namespace_d1_to_d9(self):
        assert list(REGISTER) == [f"D{i}" for i in range(1, 10)]

    def test_the_renumbered_collisions(self):
        # EVIDENCE_CLASSES' D4 (pi) is D8; the assurance case's D-G is D9.
        assert "pi" in REGISTER["D8"].doubt and REGISTER["D8"].status == Status.NOT_YET_APPLICABLE.value
        assert "generator bug" in REGISTER["D9"].doubt
        assert "coverage growth" in REGISTER["D4"].doubt

    def test_d2_names_both_mcu_models(self):
        assert "mcu_as_100R" in REGISTER["D2"].doubt and "mcu_pin_thevenin" in REGISTER["D2"].doubt

    def test_deferred_counts_as_open(self):
        assert REGISTER["D3"].status == Status.DEFERRED.value and REGISTER["D3"].is_open


# ── Supporting pieces ────────────────────────────────────────────────────────

class TestParserBranchCurrents:
    STDOUT = (
        "\tNode                                  Voltage\n"
        "\t----                                  -------\n"
        "\tdata                             0.000000e+00\n"
        "\tvcc                              5.000000e+00\n"
        "\tSource\tCurrent\n"
        "\t------\t-------\n"
        "\tv_vcc#branch                     -5.05000e-02\n"
        "\tv_probe#branch                   5.000000e-04\n"
    )

    def test_source_currents_are_read(self):
        data = SpiceResultParser().parse(self.STDOUT, "")
        assert data.branch_currents == {"v_vcc": -0.0505, "v_probe": 0.0005}

    def test_branch_rows_do_not_leak_into_node_voltages(self):
        data = SpiceResultParser().parse(self.STDOUT, "")
        assert data.dc_voltages == {"data": 0.0, "vcc": 5.0}


class TestGridSections:
    def test_axes_default_to_targets(self):
        assert GridSpec(axes={"x": [1.0]}).section_of("x") == "targets"

    def test_an_unknown_section_is_refused(self):
        with pytest.raises(ValidationError):
            GridSpec(axes={"x": [1.0]}, sections={"x": "wishes"})

    def test_a_section_for_a_missing_axis_is_refused(self):
        with pytest.raises(ValidationError):
            GridSpec(axes={"x": [1.0]}, sections={"y": "constraints"})

    def test_the_form_places_a_divider_rail_in_constraints(self):
        from ai.form_producer import FormProducer

        fields = {f.name: f for f in FormProducer().spec_for("voltage_divider").fields}
        assert fields["supply_v"].section == "constraints"
        assert fields["vout_v"].section == "targets"


class TestDeviceModels:
    def test_thermal_voltage_is_ngspices_27_degrees(self):
        # k·T/q at 300.15 K. ngspice's default TEMP is 27 °C; using 25 °C
        # would put ~0.7% into every diode comparison before any real error.
        assert VT == pytest.approx(1.380649e-23 * 300.15 / 1.602176634e-19, rel=1e-12)
        assert VT == pytest.approx(0.0258649, rel=1e-5)

    def test_series_diode_solution_satisfies_its_equation(self):
        i_s, n, v, r = 3.2e-19, 2.0, 5.0, 175.0
        import math

        i = solve_series_diode(v, r, i_s, n)
        assert i * r + n * VT * math.log1p(i / i_s) == pytest.approx(v, abs=1e-9)
