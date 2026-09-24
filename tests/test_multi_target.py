"""
Stage 5 — one requirement, three boards. `brain/decisions.md` [2026-09-23].

`constraints.mcu` picks the board (`data/mcu_targets.py`); the default is the
Arduino Uno, whose designs are Phase 1's byte for byte. What changes with the
board is physics, not just pin names: the rail (5 V or 3.3 V), the MCU's
supply model, the pin's output resistance and current limit, the RS-485
transceiver. The ngspice grid gate and the Stage 4 proofs run on every board
(`test_generator_library.py`, `test_proof.py`); this file pins what a board
does to a design, what the catalogue offers, and what is refused by name.
"""

import re

import pytest

from ai.form_producer import FormProducer
from ai.intent_producer import IntentProducer
from core.intent_ir import IntentIR, Producer, Provenance
from data.mcu_targets import DEFAULT_TARGET, TARGETS
from generators.firmware.arduino import ArduinoFirmwareGenerator
from generators.netlist.spice import SpiceNetlistGenerator
from generators.realize import realize
from generators.registry import default_registry
from test_generator_library import GENERATORS, MCU_DESIGNS, form_intent
from validation.pin_rules import assignments_of, design_target

REGISTRY = default_registry()
FORMS = FormProducer(REGISTRY)
PASSIVE = ("rc_lowpass", "voltage_divider")
PIN_RULES = ("rule.pin_assignment_valid", "rule.peripheral_conflict_free", "rule.strapping_pins_safe")


def design(name, board=None, **sections):
    return realize(GENERATORS[name], form_intent(name, board=board, **sections))


def refusal(name, board, **sections):
    decision = GENERATORS[name].envelope(form_intent(name, board=board, **sections))
    assert not decision.accepted
    return decision.reason


# ── What the board changes ────────────────────────────────────────────────────

class TestTheBoardIsPhysics:
    @pytest.mark.parametrize("name", MCU_DESIGNS)
    @pytest.mark.parametrize("board", list(TARGETS))
    def test_the_rail_mcu_and_supply_model_are_the_boards(self, name, board):
        target = TARGETS[board]
        ir = design(name, board)
        assert ir.target_mcu == board
        (mcu,) = [c for c in ir.components if c.type.value == "microcontroller"]
        assert mcu.part_number == target.mcu_part
        assert target.rail_node in {n.id for n in ir.nodes}
        netlist = SpiceNetlistGenerator().generate(ir)
        (line,) = [l for l in netlist.splitlines() if l.startswith("R_MCU_")]
        assert line.split()[1] == target.rail_node.lower()

    def test_each_mcu_has_its_own_supply_resistance(self):
        # V / I at the datasheet's active current: 5 V / 50 mA, 3.3 V / 80 mA, 3.3 V / 25 mA.
        ohms = {b: SpiceNetlistGenerator().generate(design("led_indicator", b)).split("R_MCU_U1 ")[1].split()[2]
                for b in TARGETS}
        assert ohms == {"arduino_uno": "100", "esp32_devkitc": "41", "blackpill_f411ce": "132"}

    def test_the_supply_model_is_named_in_the_claims(self):
        for board, model in (("esp32_devkitc", "mcu_as_41R"), ("blackpill_f411ce", "mcu_as_132R")):
            claims = design("led_indicator", board).validation_coverage["claims"]
            assert any(model in (c.get("scope") or {}).get("model", "") for c in claims), board

    @pytest.mark.parametrize("board, part", [("arduino_uno", "MAX485ECSA"),
                                             ("esp32_devkitc", "MAX3485ECSA"),
                                             ("blackpill_f411ce", "MAX3485ECSA")])
    def test_a_3v3_board_gets_a_3v3_transceiver(self, board, part):
        parts = {c.part_number for c in design("rs485_node", board).components}
        assert part in parts

    def test_the_same_led_current_needs_a_smaller_resistor_on_3v3(self):
        r1 = {b: next(c.value for c in design("led_indicator", b).components if c.id == "R1") for b in TARGETS}
        assert r1["arduino_uno"] == "1540"          # Phase 1's value at 2 mA
        assert float(r1["esp32_devkitc"]) < float(r1["arduino_uno"])
        assert float(r1["blackpill_f411ce"]) < float(r1["arduino_uno"])


class TestTheUnoIsUnchanged:
    @pytest.mark.parametrize("name", MCU_DESIGNS)
    def test_naming_the_uno_builds_the_default_design(self, name):
        default, named = design(name), design(name, DEFAULT_TARGET)
        # The requirement differs (it names the board), so the ids do; the circuit does not.
        assert [c.model_dump() for c in default.components] == [c.model_dump() for c in named.components]
        assert [n.model_dump() for n in default.nodes] == [n.model_dump() for n in named.nodes]
        assert SpiceNetlistGenerator().generate(default) == SpiceNetlistGenerator().generate(named)


# ── The firmware drives the pins the design wires ───────────────────────────

#: Which `#define` names which net, per sketch.
DEFINES = {
    "led_indicator": {"LED_PIN": "LED_CTRL"},
    "dht22_node": {"DHTPIN": "DHT22_DATA"},
    "rs485_node": {"RS485_TX_PIN": "UART_TX", "RS485_RX_PIN": "UART_RX", "RS485_DE_RE_PIN": "RS485_DE_RE"},
}
#: A pin other than the board's default, so a sketch that ignores the design
#: and writes its own default is caught.
OTHER_PIN = {
    "led_indicator": ("gpio_pin", {"arduino_uno": "D5", "esp32_devkitc": "GPIO27", "blackpill_f411ce": "PB5"}),
    "dht22_node": ("data_pin", {"arduino_uno": "D4", "esp32_devkitc": "GPIO27", "blackpill_f411ce": "PB5"}),
}
FIRMWARE_CASES = [(n, b, None) for n in MCU_DESIGNS for b in TARGETS] + [
    (n, b, pins[b]) for n, (field, pins) in OTHER_PIN.items() for b in TARGETS]


class TestTheFirmwareDrivesTheDesignsPins:
    """
    Found by Stage 5: the LED sketch looked for the MCU on the LED's own net,
    never found it (the MCU drives R1's other end), and wrote pin 13 — right on
    the Uno's default D13, wrong everywhere else. A sketch that compiles can
    still drive the wrong pin; the compile gate cannot see this, so this does.
    """

    @pytest.mark.parametrize("name, board, pin", FIRMWARE_CASES,
                             ids=[f"{n}-{b}-{p or 'default'}" for n, b, p in FIRMWARE_CASES])
    def test_every_pin_define_is_the_pin_wired_to_its_net(self, name, board, pin):
        sections = {"preferences": {OTHER_PIN[name][0]: pin}} if pin else {}
        ir = design(name, board, **sections)
        target = design_target(ir)
        wired = {a.net: target.pin(a.pin).firmware for a in assignments_of(ir)}
        sketch = ArduinoFirmwareGenerator().generate(ir)
        written = dict(re.findall(r"^#define\s+(\w+)\s+(\S+)", sketch, re.M))
        for define, net in DEFINES[name].items():
            assert written[define] == wired[net], (define, net, written[define], wired[net])
        if pin:
            assert target.pin(pin).firmware in written.values()


# ── Pin rules are claims on every MCU design ─────────────────────────────────

class TestPinRulesAreClaims:
    @pytest.mark.parametrize("name", MCU_DESIGNS)
    @pytest.mark.parametrize("board", list(TARGETS))
    def test_every_mcu_design_carries_the_three_pin_claims(self, name, board):
        claims = {c["id"]: c for c in design(name, board).validation_coverage["claims"]}
        for rule in PIN_RULES:
            assert claims[rule]["verdict"] in ("holds", "holds_defeasible"), (rule, claims[rule])
            assert claims[rule]["grade"] == "G1"
        assert "D7" in design(name, board).validation_coverage["open_defeaters"]

    @pytest.mark.parametrize("name", PASSIVE)
    def test_a_design_without_an_mcu_has_no_pins_to_check(self, name):
        claims = {c["id"]: c for c in design(name).validation_coverage["claims"]}
        for rule in PIN_RULES:
            assert claims[rule]["verdict"] == "not_applicable"


class TestBadPinsAreRefusedByName:
    @pytest.mark.parametrize("name, board, sections, words", [
        ("led_indicator", "esp32_devkitc", {"preferences": {"gpio_pin": "GPIO34"}}, "input only"),
        ("led_indicator", "esp32_devkitc", {"preferences": {"gpio_pin": "GPIO0"}}, "strapping pin"),
        ("led_indicator", "esp32_devkitc", {"preferences": {"gpio_pin": "GPIO6"}}, "SPI flash"),
        ("led_indicator", "blackpill_f411ce", {"preferences": {"gpio_pin": "PA13"}}, "SWDIO"),
        ("led_indicator", "blackpill_f411ce", {"preferences": {"gpio_pin": "PB2"}}, "BOOT1"),
        ("dht22_node", "esp32_devkitc", {"preferences": {"data_pin": "GPIO12"}}, "flash voltage"),
        ("led_indicator", "arduino_uno", {"preferences": {"gpio_pin": "D0"}}, "D0 is reserved"),
    ])
    def test_refused_with_the_pin_and_the_reason(self, name, board, sections, words):
        reason = refusal(name, board, **sections)
        assert words in reason and TARGETS[board].board in reason

    def test_a_3v3_bus_on_the_uno_names_the_fix(self):
        reason = refusal("rs485_node", "arduino_uno", constraints={"supply_v": 3.3})
        assert "MAX3485" in reason and "constraints.mcu" in reason

    @pytest.mark.parametrize("name", MCU_DESIGNS)
    def test_an_unknown_board_is_refused_not_defaulted(self, name):
        intent = form_intent(name, constraints={"mcu": "esp32_s3"})
        dispatch = REGISTRY.dispatch(intent)
        assert not dispatch.accepted
        assert "esp32_s3" in dispatch.refusal_summary()


# ── The catalogue offers exactly the boards CI sweeps ────────────────────────

class TestTheCatalogueOffersTheBoards:
    @pytest.mark.parametrize("name", MCU_DESIGNS)
    def test_an_mcu_function_offers_every_board(self, name):
        spec = FORMS.spec_for(GENERATORS[name].function)
        (field,) = [f for f in spec.fields if f.name == "mcu"]
        assert field.section == "constraints" and not field.required and field.exercised_in_ci
        assert field.choices == tuple(TARGETS) == tuple(GENERATORS[name].boards)

    @pytest.mark.parametrize("name", PASSIVE)
    def test_a_passive_function_offers_none(self, name):
        assert "mcu" not in FORMS.spec_for(GENERATORS[name].function).field_names()

    def test_the_form_builds_a_board_and_refuses_one_it_does_not_offer(self):
        intent = FORMS.build("led_indicator", {"led_current_ma": 5, "mcu": "blackpill_f411ce", "supply_v": 3.3})
        assert intent.requirements["constraints"]["mcu"] == "blackpill_f411ce"
        assert realize(REGISTRY.dispatch(intent).generator, intent).target_mcu == "blackpill_f411ce"
        with pytest.raises(ValueError, match="not one of"):
            FORMS.build("led_indicator", {"led_current_ma": 5, "mcu": "esp32_s3", "supply_v": 3.3})

    def test_the_form_range_covers_every_boards_grid(self):
        (supply,) = [f for f in FORMS.spec_for("modbus_rtu_master").fields if f.name == "supply_v"]
        assert (supply.minimum, supply.maximum) == (3.135, 5.25)

    def test_the_llm_sees_the_same_choices(self, monkeypatch):
        monkeypatch.setattr("ai.intent_producer.make_client", lambda: None)
        producer = IntentProducer(REGISTRY)
        line = next(l for l in producer.catalogue_text().splitlines() if l.startswith("- led_indicator:"))
        assert "constraints.mcu one of arduino_uno|esp32_devkitc|blackpill_f411ce optional" in line


def test_every_board_grid_is_inside_its_own_envelope():
    # The per-board grids are declared by the generators; a point a board
    # refuses would be a grid failure, not a skip.
    for name in MCU_DESIGNS:
        generator = GENERATORS[name]
        for board in generator.boards:
            for point in generator.grid(board).points():
                decision = generator.envelope(form_intent(name, point, board))
                assert decision.accepted, (name, board, point, decision.reason)


def test_intent_with_board_round_trips_through_the_form_producer():
    intent = IntentIR(requirements={"function": "temperature_humidity_sensor", "targets": {},
                                    "constraints": {"cable_length_m": 5, "mcu": "esp32_devkitc"},
                                    "preferences": {}},
                      provenance=Provenance(producer=Producer.FORM))
    ir = realize(REGISTRY.dispatch(intent).generator, intent)
    assert ir.target_mcu == "esp32_devkitc" and "VCC_3V3" in {n.id for n in ir.nodes}
