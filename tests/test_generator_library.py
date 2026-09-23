"""
Stage 3 — the generator library: five generators, one contract, one gate.

PHASE_2_PLAN_v2.md §5 Stage 3. The gates this file owns:

- **All five at the Stage 0 grid gate** — `predict()` within 2% of ngspice at
  every declared grid point (G5), with the M1 fault-injection arms detected.
  `TestGridGate`, which runs through ngspice and auto-skips without it.
- **Every design emits claim objects** — for every generator, at every grid
  point, `realize()` attaches `validation_coverage` whose critical claims hold,
  with nothing left *not assessed* (X8 accounting complete).

And the properties Stage 2 established, extended from one generator to five:
determinism, strict inputs, pins honoured or refused by name, and locality
swept over every declared requirement path.

Decisions behind all of it: `brain/decisions.md` [2026-09-21] X6 + X8.
"""

import math

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from core.intent_patch import PatchOp, apply_patch
from core.ir_validator import validate_ir
from generators.bom.compiler import BOMCompiler
from generators.firmware.arduino import ArduinoFirmwareGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.protocol import Generator, conformance_gaps
from generators.realize import canonical_json, check_locality, realize
from generators.registry import default_registry
from test_simulation_accuracy import _skip_no_ngspice
from validation.envelope_grid import DEFAULT_TOLERANCE, run_matrix
from validation.grid_adapters import ADAPTERS, M1_COVERED, intent_at

REGISTRY = default_registry()
GENERATORS = {g.name: g for g in REGISTRY.generators}
NEW = ("voltage_divider", "led_indicator", "dht22_node", "rs485_node")
MCU_DESIGNS = ("led_indicator", "dht22_node", "rs485_node")


def form_intent(name, point=None, **sections):
    """An IntentIR at a grid point (default: the first), sections as declared."""
    generator = GENERATORS[name]
    grid = generator.grid()
    point = point if point is not None else next(iter(grid.points()))
    req = intent_at(generator.function, point, grid.sections).requirements
    if name in ("voltage_divider", "rc_lowpass"):
        req["constraints"].setdefault("supply_v", 5.0)
    # Overrides last: a test that sets a bad value must not have it silently
    # replaced by the grid point it started from.
    for section, values in sections.items():
        req[section].update(values)
    return IntentIR(requirements=req, provenance=Provenance(producer=Producer.FORM))


def every_grid_intent():
    for name, generator in GENERATORS.items():
        for point in generator.grid().points():
            yield name, point, form_intent(name, point)


GRID_CASES = list(every_grid_intent())
GRID_IDS = [f"{name}-{'-'.join(f'{v:g}' for v in point.values())}" for name, point, _ in GRID_CASES]


# ── The library itself ───────────────────────────────────────────────────────

class TestLibrary:
    def test_five_generators_one_per_phase1_template(self):
        assert set(GENERATORS) == {"rc_lowpass", *NEW}

    @pytest.mark.parametrize("name", sorted(GENERATORS))
    def test_each_satisfies_the_contract(self, name):
        generator = GENERATORS[name]
        assert isinstance(generator, Generator)
        assert conformance_gaps(generator) == []
        assert generator.version.count(".") == 2

    @pytest.mark.parametrize("name", sorted(GENERATORS))
    def test_each_implements_claims(self, name):
        # Not a protocol member (decisions.md: every fake generator in the
        # suite would break), so it is required here, for what is installed.
        assert callable(getattr(GENERATORS[name], "claims", None))

    def test_every_generator_is_under_the_m1_matrix(self):
        # Otherwise its claims carry D9 — a generator bug nothing would catch.
        assert M1_COVERED == set(GENERATORS)

    def test_functions_do_not_overlap(self):
        functions = [g.function for g in GENERATORS.values()]
        assert len(functions) == len(set(functions))


# ── At every grid point ──────────────────────────────────────────────────────

class TestEveryGridPoint:
    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_is_inside_its_own_envelope(self, name, point, intent):
        decision = GENERATORS[name].envelope(intent)
        assert decision.accepted, decision.reason
        assert decision.ports

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_dispatches_to_its_generator(self, name, point, intent):
        result = REGISTRY.dispatch(intent)
        assert result.accepted and result.generator.name == name
        assert not result.is_ambiguous

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_realises_a_structurally_valid_design(self, name, point, intent):
        design = realize(GENERATORS[name], intent)
        result = validate_ir(design)
        assert result.is_valid, result.errors

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_is_byte_identical_across_realisations(self, name, point, intent):
        generator = GENERATORS[name]
        assert canonical_json(realize(generator, intent)) == canonical_json(realize(generator, intent))

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_every_band_contains_its_nominal(self, name, point, intent):
        for quantity, band in GENERATORS[name].predict(intent).quantities.items():
            assert band.lo <= band.nominal <= band.hi, quantity
            assert all(math.isfinite(x) for x in (band.lo, band.hi, band.nominal)), quantity


# ── Claims (Stage 3 gate) ────────────────────────────────────────────────────

class TestClaimsAtEveryGridPoint:
    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_every_design_carries_validation_coverage(self, name, point, intent):
        coverage = realize(GENERATORS[name], intent).validation_coverage
        assert coverage is not None
        for field in ("claims", "coverage_le_g2", "grade_floor", "open_defeaters",
                      "not_assessed", "out_of_scope"):
            assert field in coverage

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_no_critical_claim_fails_on_an_accepted_design(self, name, point, intent):
        coverage = realize(GENERATORS[name], intent).validation_coverage
        failing = [c["id"] for c in coverage["claims"] if c["verdict"] == "fails" and c["critical"]]
        assert not failing, failing

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_every_rule_is_accounted_for(self, name, point, intent):
        # X8: nothing on an installed generator is left "not assessed".
        coverage = realize(GENERATORS[name], intent).validation_coverage
        assert coverage["not_assessed"] == []

    @pytest.mark.parametrize("name, point, intent", GRID_CASES, ids=GRID_IDS)
    def test_every_claim_has_four_fields_and_an_honest_verdict(self, name, point, intent):
        for claim in realize(GENERATORS[name], intent).validation_coverage["claims"]:
            if claim["verdict"] in ("holds", "holds_defeasible", "fails"):
                assert claim["kind"] and claim["grade"] and claim["scope"] and claim["method"]

    @pytest.mark.parametrize("name", sorted(GENERATORS))
    def test_the_floor_is_the_worst_critical_grade(self, name):
        coverage = realize(GENERATORS[name], form_intent(name)).validation_coverage
        grades = [c["grade"] for c in coverage["claims"]
                  if c["critical"] and c["grade"] and c["verdict"] not in ("not_applicable", "out_of_scope")]
        assert coverage["grade_floor"] == max(grades, key=lambda g: int(g[1:]))


class TestX6DerivedFromTheNetlist:
    @pytest.mark.parametrize("name", MCU_DESIGNS)
    def test_every_behavioural_claim_on_an_mcu_design_names_the_model(self, name):
        design = realize(GENERATORS[name], form_intent(name))
        assert "\nR_MCU_" in SpiceNetlistGenerator().generate(design)
        behavioural = [c for c in design.validation_coverage["claims"]
                       if c["scope"] and c["scope"]["model"] != "design_graph"]
        assert behavioural
        for claim in behavioural:
            assert "mcu_as_100R" in claim["scope"]["model"], claim["id"]
            assert "D2" in claim["defeaters"], claim["id"]
        assert "D2" in design.validation_coverage["open_defeaters"]

    def test_the_led_design_also_names_the_pin_model(self):
        design = realize(GENERATORS["led_indicator"], form_intent("led_indicator"))
        assert "\nR_PIN_" in SpiceNetlistGenerator().generate(design)
        for claim in design.validation_coverage["claims"]:
            if claim["scope"] and claim["scope"]["model"] != "design_graph":
                assert "mcu_pin_thevenin" in claim["scope"]["model"]

    @pytest.mark.parametrize("name", ("rc_lowpass", "voltage_divider"))
    def test_passive_designs_carry_no_mcu_model(self, name):
        design = realize(GENERATORS[name], form_intent(name))
        assert "D2" not in design.validation_coverage["open_defeaters"]
        for claim in design.validation_coverage["claims"]:
            if claim["scope"]:
                assert "mcu_as_100R" not in claim["scope"]["model"]

    def test_an_llm_written_intent_carries_d5(self):
        form = form_intent("voltage_divider")
        llm = IntentIR(requirements=form.requirements,
                       provenance=Provenance(producer=Producer.LLM, model="m"))
        assert "D5" not in realize(GENERATORS["voltage_divider"], form).validation_coverage["open_defeaters"]
        assert "D5" in realize(GENERATORS["voltage_divider"], llm).validation_coverage["open_defeaters"]


# ── Strict inputs and pins, per generator ────────────────────────────────────

BAD_INPUTS = {
    "voltage_divider": [({"targets": {"vout_v": "3.3"}}, "not a number"),
                        ({"constraints": {"supply_v": True}}, "not a number"),
                        ({"targets": {"vout_v": float("nan")}}, "not a finite number"),
                        ({"targets": {"vout_v": 12.0}}, "cannot step up"),
                        ({"constraints": {"supply_v": 60.0}}, "rating")],
    "led_indicator": [({"targets": {"led_current_ma": "10"}}, "not a number"),
                      ({"targets": {"led_current_ma": 30.0}}, "recommended per-pin"),
                      # Stage 3 + 4 verification: 64.7 mW in a 62.5 mW part, accepted by 0.1.0.
                      ({"targets": {"led_current_ma": 17.0}, "constraints": {"supply_v": 5.25}}, "mW rating"),
                      ({"constraints": {"supply_v": 3.3}}, "characterised at 5 V"),
                      ({"preferences": {"gpio_pin": "D0"}}, "not an Arduino Uno digital pin"),
                      ({"preferences": {"colour": "blue"}}, "no tabulated LED")],
    "dht22_node": [({"constraints": {"cable_length_m": "5"}}, "not a number"),
                   ({"constraints": {"cable_length_m": 25.0}}, "specified for"),
                   ({"constraints": {"cable_length_m": 20.0}}, "no pull-up meets"),
                   ({"constraints": {"supply_v": 3.3}}, "needs 4.5 V"),
                   ({"preferences": {"alert_threshold_c": "hot"}}, "not a temperature")],
    # Stage 3 + 4 verification: a source that moves f_c past tolerance, accepted by 0.2.1.
    "rc_lowpass": [({"constraints": {"source_impedance_ohm": 2000.0}}, "lowers f_c")],
    "rs485_node": [({"constraints": {"baud": 115200}}, "SoftwareSerial"),
                   ({"constraints": {"supply_v": 3.3}}, "MAX3485"),
                   ({"constraints": {"far_end_terminated": "yes"}}, "true or false"),
                   ({"preferences": {"modbus_slaves": [{"address": 0}]}}, "address 1–247"),
                   ({"constraints": {"pinned": {"R2": "10k", "R3": "10k"}}}, "threshold")],
}


class TestRefusedByName:
    @pytest.mark.parametrize("name, sections, fragment",
                             [(n, s, f) for n, cases in BAD_INPUTS.items() for s, f in cases])
    def test_bad_requirement_is_refused_naming_it(self, name, sections, fragment):
        decision = GENERATORS[name].envelope(form_intent(name, **sections))
        assert not decision.accepted
        assert fragment in decision.reason, decision.reason

    @pytest.mark.parametrize("name", NEW)
    def test_the_wrong_function_is_refused(self, name):
        intent = form_intent(name)
        wrong = IntentIR(requirements={**intent.requirements, "function": "band_pass_filter"},
                         provenance=intent.provenance)
        assert "band_pass_filter" in GENERATORS[name].envelope(wrong).reason

    @pytest.mark.parametrize("name", NEW)
    def test_an_unknown_pin_is_refused(self, name):
        decision = GENERATORS[name].envelope(form_intent(name, constraints={"pinned": {"Q9": "1k"}}))
        assert not decision.accepted and "Q9" in decision.reason


class TestFoundByTheStage34Verification:
    """An accepted design must never carry a failed claim of its own."""

    @pytest.mark.parametrize("supply", [4.75, 5.0, 5.25])
    def test_the_led_passes_its_rating_rule_across_its_supply_window(self, supply):
        intent = form_intent("led_indicator", constraints={"supply_v": supply})
        claims = {c["id"]: c for c in realize(GENERATORS["led_indicator"], intent).validation_coverage["claims"]}
        assert claims["rule.voltage_ratings_ok"]["verdict"] in ("holds", "holds_defeasible")

    def test_every_accepted_led_keeps_r1_inside_its_rating(self):
        g = GENERATORS["led_indicator"]
        for supply in (4.75, 5.0, 5.25):
            for tenths in range(10, 201, 5):
                intent = form_intent("led_indicator", targets={"led_current_ma": tenths / 10},
                                     constraints={"supply_v": supply})
                if g.envelope(intent).accepted:
                    assert g.predict(intent).quantities["r1_power_mw"].hi <= 62.5, (supply, tenths / 10)

    def test_an_rc_source_inside_tolerance_is_accepted_and_its_claim_holds(self):
        intent = form_intent("rc_lowpass", constraints={"source_impedance_ohm": 300.0})
        claims = {c["id"]: c for c in realize(GENERATORS["rc_lowpass"], intent).validation_coverage["claims"]}
        assert claims["rc.source_loading"]["verdict"] != "fails"


class TestPinsHonoured:
    def test_divider_pins(self):
        design = realize(GENERATORS["voltage_divider"],
                         form_intent("voltage_divider", {"vout_v": 5.0, "supply_v": 12.0},
                                     constraints={"pinned": {"R1": "14k", "R2": "10k"}}))
        parts = {c.id: c for c in design.components}
        assert float(parts["R1"].value) == 14_000 and float(parts["R2"].value) == 10_000
        assert "pinned" in parts["R1"].justification

    def test_led_pin(self):
        design = realize(GENERATORS["led_indicator"],
                         form_intent("led_indicator", {"led_current_ma": 10.0},
                                     constraints={"pinned": {"R1": "270"}}))
        assert float(next(c for c in design.components if c.id == "R1").value) == 270

    def test_dht22_pin(self):
        design = realize(GENERATORS["dht22_node"],
                         form_intent("dht22_node", constraints={"pinned": {"R1": "4k7"}}))
        assert float(next(c for c in design.components if c.id == "R1").value) == 4700

    def test_rs485_bias_pins(self):
        design = realize(GENERATORS["rs485_node"],
                         form_intent("rs485_node", constraints={"pinned": {"R2": "560", "R3": "560"}}))
        parts = {c.id: float(c.value) for c in design.components if c.value and c.id.startswith("R")}
        assert parts["R2"] == parts["R3"] == 560


# ── Locality, swept per generator ────────────────────────────────────────────

LOCALITY = [
    ("voltage_divider", "/targets/vout_v", 1.2),
    ("voltage_divider", "/constraints/divider_current_ma", 2.0),
    ("voltage_divider", "/constraints/load_ohm", 100_000.0),
    ("led_indicator", "/targets/led_current_ma", 5.0),
    ("led_indicator", "/preferences/gpio_pin", "D9"),
    ("led_indicator", "/constraints/supply_current_ma", 100.0),
    ("dht22_node", "/constraints/cable_length_m", 12.0),
    ("dht22_node", "/preferences/alert_threshold_c", 40.0),
    ("dht22_node", "/preferences/data_pin", "D4"),
    ("rs485_node", "/constraints/supply_v", 5.25),
    ("rs485_node", "/constraints/far_end_terminated", False),
    ("rs485_node", "/constraints/baud", 19200),
]


class TestLocality:
    @pytest.mark.parametrize("name, path, value", LOCALITY)
    def test_diff_stays_inside_the_declared_closure(self, name, path, value):
        generator = GENERATORS[name]
        base = form_intent(name)
        out = apply_patch(base, [PatchOp(op="add", path=path, value=value)])
        assert out.changed
        assert generator.envelope(out.intent).accepted, generator.envelope(out.intent).reason
        report = check_locality(generator, out.changed_paths,
                                realize(generator, base), realize(generator, out.intent))
        assert report.ok, (report.diff, report.closure)


# ── Downstream compilers still work on every new design ──────────────────────

class TestDownstream:
    @pytest.mark.parametrize("name", NEW)
    def test_bom_compiles(self, name):
        rows = BOMCompiler().compile(realize(GENERATORS[name], form_intent(name)))
        assert len(rows) >= 2

    @pytest.mark.parametrize("name", MCU_DESIGNS)
    def test_firmware_renders(self, name):
        firmware = ArduinoFirmwareGenerator().generate(realize(GENERATORS[name], form_intent(name)))
        assert "void setup()" in firmware and "void loop()" in firmware

    def test_rs485_wiring_matches_the_pins_its_firmware_drives(self):
        # Phase 1's IR_005 wired D0/D1 while the firmware used D10/D11.
        design = realize(GENERATORS["rs485_node"], form_intent("rs485_node"))
        mcu_pins = {c.node_id: c.pin for c in design.connections if c.component_id == "U1"}
        firmware = ArduinoFirmwareGenerator().generate(design)
        assert mcu_pins["UART_TX"] == "D11" and "RS485_TX_PIN     11" in firmware
        assert mcu_pins["UART_RX"] == "D10" and "RS485_RX_PIN     10" in firmware
        assert mcu_pins["RS485_DE_RE"] == "D2" and "RS485_DE_RE_PIN  2" in firmware

    def test_rs485_terminator_is_rated_for_a_full_swing(self):
        design = realize(GENERATORS["rs485_node"], form_intent("rs485_node"))
        term = next(c for c in design.components if c.id == "R1")
        assert term.package == "1206"

    def test_dht22_firmware_reads_the_pin_it_is_wired_to(self):
        design = realize(GENERATORS["dht22_node"],
                         form_intent("dht22_node", preferences={"data_pin": "D4"}))
        firmware = ArduinoFirmwareGenerator().generate(design)
        assert any(line.split() == ["#define", "DHTPIN", "4"] for line in firmware.splitlines())


# ── The Stage 3 grid gate, through ngspice ───────────────────────────────────

@_skip_no_ngspice
class TestGridGate:
    """
    `predict()` within 2% of ngspice at every grid point, for all five, and every
    seeded fault caught. The pair is the evidence (M1): agreement that never
    breaks under a perturbation would prove nothing.
    """

    @pytest.mark.parametrize("name", sorted(ADAPTERS))
    def test_matrix_is_sound(self, name):
        spec = ADAPTERS[name]
        report = run_matrix(spec.build(), spec.mutate)
        assert report.control.passed, report.summary()
        assert report.control.worst_error < 1e-3, report.summary()
        assert report.passed, report.summary()

    def test_rs485_five_percent_margin_is_recorded_not_assumed(self):
        # A 5% terminator fault moves idle V_AB by ~2.3% — just over the 2%
        # gate. Pinned so that if a model change shrinks it below the gate,
        # this fails loudly instead of the matrix silently going blind.
        spec = ADAPTERS["rs485_node"]
        report = run_matrix(spec.build(), spec.mutate, mutations={"P5": 1.05})
        assert report.mutations["P5"].worst_error > DEFAULT_TOLERANCE * 1.1
