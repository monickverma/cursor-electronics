"""
Stage 5 gate 2 — pin-mux, peripheral-conflict and strapping-pin checks on a
labelled set. `validation/pin_rules.py` against `tests/fixtures/pin_assignments.json`.

The gate is zero disagreements between the checker and the labels. The labels
were written from the datasheets before the checker was run against them.
Writing them exposed one bug in the pin table — a Uno's D14 is A0, and the
resolver rejected it — fixed in the table, not relabelled.
"""

import json
from pathlib import Path

import pytest

from data.mcu_targets import TARGETS, get_target
from validation.pin_rules import RULES, Assignment, check_assignment, summarise

CASES = json.loads((Path(__file__).parent / "fixtures" / "pin_assignments.json").read_text(encoding="utf-8"))["cases"]


def _verdicts(case):
    target = get_target(case["target"])
    findings = check_assignment(target, [Assignment(pin=p, role=r, net=n) for p, r, n in case["assign"]])
    return "".join("T" if summarise(findings)[rule][0] else "F" for rule in RULES), findings


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_checker_agrees_with_the_label(case):
    got, findings = _verdicts(case)
    assert got == case["expect"], f"{case['id']}: expected {case['expect']}, got {got} — {case['why']}; {findings}"


def test_the_labelled_set_covers_every_target_and_both_outcomes_of_every_rule():
    for target in TARGETS:
        assert sum(c["target"] == target for c in CASES) >= 10, target
    for i, rule in enumerate(RULES):
        outcomes = {c["expect"][i] for c in CASES}
        assert outcomes == {"T", "F"}, f"{rule} is never {'violated' if 'F' not in outcomes else 'satisfied'}"


def test_every_default_pin_on_every_board_passes():
    for target in TARGETS.values():
        roles = {"led": "output", "dht_data": "bidirectional", "rs485_tx": "uart_tx",
                 "rs485_rx": "uart_rx", "rs485_de": "output"}
        # One design at a time: the LED, the DHT22 and the RS-485 node never share a board.
        for group in (("led",), ("dht_data",), ("rs485_tx", "rs485_rx", "rs485_de")):
            assignments = [Assignment(target.defaults[k], roles[k], k) for k in group]
            assert check_assignment(target, assignments) == [], (target.id, group)


def test_a_finding_names_its_pin_and_reason():
    target = get_target("esp32_devkitc")
    (finding,) = check_assignment(target, [Assignment("GPIO12", "bidirectional", "DHT22_DATA")])
    assert finding.rule == "strapping_pins_safe" and finding.pin == "GPIO12"
    assert "flash voltage" in finding.message


def test_an_unknown_role_is_a_programming_error():
    with pytest.raises(ValueError):
        check_assignment(get_target("arduino_uno"), [Assignment("D2", "teleport", "X")])
