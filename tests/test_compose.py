"""
Composition M1 — several blocks on one board (`COMPOSITION_PLAN.md`,
`brain/decisions.md` [2026-10-03]).

What it must hold: one MCU, one bypass, one rail; pins never shared and
re-allocated where board defaults collide; every block still built — and
proved — by its own generator, unchanged; refusals by name; deterministic;
and the merged board compiles downstream and simulates to each block's own
expectation.
"""

import shutil

import pytest

from generators.compose import CompositionRefused, Project, compose
from generators.realize import canonical_json, realize
from generators.registry import default_registry
from ai.form_producer import FormProducer
from generators.bom.compiler import BOMCompiler
from generators.netlist.spice import SpiceNetlistGenerator
from generators.schematic.kicad import KiCadSchematicGenerator
from validation.pin_rules import check_design

BOARDS = ("arduino_uno", "esp32_devkitc", "blackpill_f411ce")
CLIMATE = {"id": "climate", "function": "temperature_humidity_sensor", "constraints": {"cable_length_m": 0.3}}
STATUS = {"id": "status", "function": "led_indicator", "targets": {"led_current_ma": 10}}


def project(mcu="arduino_uno", blocks=(CLIMATE, STATUS)):
    return Project(intent="DHT22 + status LED", mcu=mcu, blocks=list(blocks))


@pytest.fixture(scope="module")
def registry():
    return default_registry()


def test_one_mcu_one_bypass_one_rail(registry):
    board = compose(registry, project()).circuit
    ids = [c.id for c in board.components]
    assert ids == ["U1", "U2", "R1", "C1", "LED1", "R2"]
    assert sum(c.type == "microcontroller" for c in board.components) == 1
    assert sorted((c.pin, c.node_id) for c in board.connections if c.component_id == "C1") == \
        [("+", "VCC_5V"), ("-", "GND")]
    assert sorted((c.pin, c.node_id) for c in board.connections if c.component_id == "U1") == \
        [("D13", "LED_CTRL"), ("D2", "DHT22_DATA"), ("GND", "GND"), ("VCC", "VCC_5V")]
    assert [n.id for n in board.nodes].count("VCC_5V") == 1


@pytest.mark.parametrize("mcu", BOARDS)
def test_pins_distinct_and_board_rules_hold(registry, mcu):
    result = compose(registry, project(mcu))
    pins = [b.pin for b in result.blocks]
    assert len(set(pins)) == len(pins)
    assert all(holds for holds, _ in check_design(result.circuit).values())


def test_colliding_defaults_are_reallocated(registry):
    # On the ESP32 both the LED and the DHT22 default to GPIO4.
    pins = {b.id: b.pin for b in compose(registry, project("esp32_devkitc")).blocks}
    assert pins["climate"] == "GPIO4" and pins["status"] != "GPIO4"


def test_requested_pin_is_kept(registry):
    status = {**STATUS, "preferences": {"gpio_pin": "D9"}}
    pins = {b.id: b.pin for b in compose(registry, project(blocks=(CLIMATE, status))).blocks}
    assert pins == {"climate": "D2", "status": "D9"}


def test_two_blocks_asking_for_one_pin_are_refused(registry):
    status = {**STATUS, "preferences": {"gpio_pin": "D2"}}
    climate = {**CLIMATE, "preferences": {"data_pin": "D2"}}
    with pytest.raises(CompositionRefused, match="D2 is already climate's pin"):
        compose(registry, project(blocks=(climate, status)))


def test_console_pin_is_refused(registry):
    status = {**STATUS, "preferences": {"gpio_pin": "D1"}}
    with pytest.raises(CompositionRefused, match="USB console"):
        compose(registry, project(blocks=(status,)))


def test_two_of_one_block_get_their_own_nets(registry):
    other = {**STATUS, "id": "alarm"}
    result = compose(registry, project(blocks=(STATUS, other)))
    nets = {n.id for n in result.circuit.nodes}
    assert {"STATUS_LED_CTRL", "ALARM_LED_CTRL", "STATUS_LED_ANODE", "ALARM_LED_ANODE"} <= nets
    assert [c.id for c in result.circuit.components if c.type == "led"] == ["LED1", "LED2"]
    assert result.blocks[1].parts["R1"] == "R2"


def test_uncomposable_block_is_refused_by_name(registry):
    divider = {"id": "ref", "function": "voltage_divider", "targets": {"vout_v": 3.3}}
    with pytest.raises(CompositionRefused, match="ref: 'voltage_divider' is not composable yet"):
        compose(registry, project(blocks=(STATUS, divider)))


def test_block_its_generator_refuses_is_refused_with_its_reason(registry):
    hot = {**STATUS, "targets": {"led_current_ma": 100}}
    with pytest.raises(CompositionRefused) as caught:
        compose(registry, project(blocks=(CLIMATE, hot)))
    assert len(caught.value.reasons) == 1 and caught.value.reasons[0].startswith("status:")


def test_block_on_another_board_is_refused(registry):
    stray = {**STATUS, "constraints": {"mcu": "esp32_devkitc"}}
    with pytest.raises(CompositionRefused, match="the board is 'arduino_uno'"):
        compose(registry, project(blocks=(stray,)))


def test_deterministic(registry):
    a, b = compose(registry, project()).circuit, compose(registry, project()).circuit
    assert canonical_json(a) == canonical_json(b)
    assert a.circuit_id != compose(registry, project("esp32_devkitc")).circuit.circuit_id


def test_each_block_keeps_its_own_proofs(registry):
    """Composition changes nothing a block's generator proves: same properties, same hashes."""
    form = FormProducer(registry)
    alone = {
        "climate": form.build("temperature_humidity_sensor", {"mcu": "arduino_uno", "cable_length_m": 0.3}),
        "status": form.build("led_indicator", {"led_current_ma": 10, "mcu": "arduino_uno"}),
    }
    for block in compose(registry, project()).blocks:
        intent = alone[block.id]
        standalone = realize(registry.dispatch(intent).generator, intent).validation_coverage
        composed = block.circuit.validation_coverage
        assert composed["properties_hash"] == standalone["properties_hash"]
        assert [p["status"] for p in composed["properties"]] == [p["status"] for p in standalone["properties"]]


def test_compiles_downstream(registry):
    board = compose(registry, project()).circuit
    assert "R_MCU_U1" in SpiceNetlistGenerator().generate(board)
    assert "LED1" in KiCadSchematicGenerator().generate(board)
    assert len(BOMCompiler().compile(board)) == len(board.components)


_NGSPICE = shutil.which("ngspice_con") or shutil.which("ngspice")


@pytest.mark.skipif(_NGSPICE is None, reason="ngspice not installed")
@pytest.mark.parametrize("mcu", BOARDS)
def test_board_simulates_to_each_blocks_expectation(registry, mcu):
    from simulation.grader import SimulationGrader
    from simulation.parser import SpiceResultParser
    from simulation.runner import NgspiceRunner

    board = compose(registry, project(mcu)).circuit
    run = NgspiceRunner()._run_sync(SpiceNetlistGenerator().generate(board))
    grade = SimulationGrader().grade(board, SpiceResultParser().parse(run.get("stdout", ""), run.get("stderr", "")))
    assert grade.passed, grade.failures
    assert {"DHT22_DATA", "LED_ANODE"} <= set(board.simulation_spec.expected_outputs)
