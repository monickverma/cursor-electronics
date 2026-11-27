"""
tests/test_pcb_dropped_parts.py — a part the board left out fails verification
(F-S2-R005-2).

The judge's RS-485 board for an ESP32-DevKitC had no U1: package MODULE has no
footprint, so from_netlist warned and built the board without it. UART_TX,
UART_RX and RS485_DE_RE then ended at the transceiver, and verification said
ok — connectivity ran on the reduced board, and the parity check visited only
the parts that were there. III.4a now compares the netlist's parts with the
board's, on the exact rung.
"""
from pcb_engine import compile_board, verify_board

NETLIST = {
    "name": "rs485_esp32", "board": {"width": 50, "height": 40}, "ground_net": "GND",
    "power_nets": ["VCC_3V3", "GND"],
    "components": [
        {"ref": "U1", "mpn": "ESP32-WROOM-32E", "package": "MODULE", "type": "microcontroller",
         "pins": {"TXD0": "UART_TX", "RXD0": "UART_RX", "IO4": "RS485_DE_RE",
                  "3V3": "VCC_3V3", "GND": "GND"}},
        {"ref": "R1", "mpn": "", "package": "0603", "pins": {"1": "UART_TX", "2": "UART_RX"}},
        {"ref": "R2", "mpn": "", "package": "0603", "pins": {"1": "RS485_DE_RE", "2": "GND"}},
    ],
}


def _finding(rep, check):
    return next((f for f in rep["findings"] if f["check"] == check), None)


def test_a_part_with_no_footprint_fails_verification():
    result = compile_board(NETLIST)
    assert any("U1" in w for w in result.warnings)
    f = _finding(result.verification, "III.4a")
    assert f is not None and f["status"] == "fail" and f["rung"] == "exact"
    assert "U1" in f["detail"]
    assert result.stats["verified"] is False
    assert result.verification["gate"]["emit"] is False


def test_every_part_present_passes():
    nl = {**NETLIST, "components": NETLIST["components"][1:]}
    result = compile_board(nl)
    assert _finding(result.verification, "III.4a")["status"] == "pass"


def test_the_check_reads_the_netlist_not_the_warnings():
    """A board handed to the verifier with a netlist naming a part it lacks."""
    nl = {**NETLIST, "components": NETLIST["components"][1:]}
    board = compile_board(nl).board
    rep = verify_board(board, NETLIST).to_dict()
    assert _finding(rep, "III.4a")["status"] == "fail"
