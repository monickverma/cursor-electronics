"""
Pin rules — what an MCU pin is asked to do, against what the board can do.
Stage 5; `brain/decisions.md` [2026-09-23] Stage 5, item 5.

Three rules, each an exact check of the design graph against the target's
table in `data/mcu_targets.py` (G1; the table is datasheet data, D7):

- `pin_assignment_valid`   — the pin exists on the board, is not reserved,
                             and can do what its connection needs (drive,
                             read, a UART role, PWM, ADC).
- `peripheral_conflict_free` — one net per pin; a hardware UART's TX and RX on
                             one peripheral, used once; nothing on the
                             console UART.
- `strapping_pins_safe`    — nothing external on a strapping pin. Deliberately
                             conservative: whether a given load changes the
                             boot mode depends on the load, and a rule that
                             guessed would be a rule that sometimes bricks.

`check_assignment` is the core, on plain (pin, role, net) triples, so a
generator can refuse a requested pin by name before it builds anything;
`check_design` derives the triples from a CircuitIR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core.ir_schema import CircuitIR, ComponentType, SignalType
from data.mcu_targets import DEFAULT_TARGET, Target, get_target, target_for_part

RULES = ("pin_assignment_valid", "peripheral_conflict_free", "strapping_pins_safe")
ROLES = ("output", "input", "bidirectional", "uart_tx", "uart_rx", "pwm", "adc")

#: MCU pins that are not GPIOs: supply and ground.
_POWER_PINS = {"VCC", "VDD", "GND", "5V", "3V3", "3.3V", "VIN", "AVCC", "AREF", "VBAT", "EN", "RESET", "NRST"}


@dataclass(frozen=True)
class Assignment:
    pin: str                       # as written
    role: str                      # one of ROLES
    net: str                       # the node it drives or reads


@dataclass(frozen=True)
class Finding:
    rule: str
    pin: str
    message: str


def check_assignment(target: Target, assignments: Sequence[Assignment]) -> List[Finding]:
    """Every rule violation, each naming its pin and why. Empty means all three hold."""
    out: List[Finding] = []
    resolved: List[Tuple[Assignment, Optional[str]]] = []
    for a in assignments:
        if a.role not in ROLES:
            raise ValueError(f"unknown pin role {a.role!r}")
        pin = target.pin(a.pin)
        resolved.append((a, pin.name if pin else None))
        if pin is None:
            out.append(Finding("pin_assignment_valid", a.pin, f"{target.board} has no pin {a.pin!r}"))
            continue
        if pin.reserved:
            out.append(Finding("pin_assignment_valid", pin.name, f"{pin.name} is reserved: {pin.reserved}"))
        needs_out = a.role in ("output", "bidirectional", "uart_tx", "pwm")
        needs_in = a.role in ("input", "bidirectional", "uart_rx", "adc")
        if needs_out and not pin.output:
            out.append(Finding("pin_assignment_valid", pin.name, f"{pin.name} cannot drive an output"
                                                                  + (f" ({pin.note})" if pin.note else "")))
        if needs_in and not pin.input:
            out.append(Finding("pin_assignment_valid", pin.name, f"{pin.name} cannot read an input"))
        if a.role == "pwm" and not pin.pwm:
            out.append(Finding("pin_assignment_valid", pin.name, f"{pin.name} has no PWM output"))
        if a.role == "adc" and not pin.adc:
            out.append(Finding("pin_assignment_valid", pin.name, f"{pin.name} has no ADC input"))
        if a.role in ("uart_tx", "uart_rx") and target.uart_mode == "fixed":
            want = "TX" if a.role == "uart_tx" else "RX"
            if not any(role == want for _, role in pin.uart):
                out.append(Finding("pin_assignment_valid", pin.name,
                                   f"{pin.name} is not a UART {want} pin on {target.board}"))
        if pin.strapping:
            out.append(Finding("strapping_pins_safe", pin.name,
                               f"{pin.name} is a strapping pin ({pin.strapping}); an external circuit on it "
                               f"can change how the board boots"))

    # One net per pin.
    nets: Dict[str, set] = {}
    for a, name in resolved:
        if name:
            nets.setdefault(name, set()).add(a.net)
    for name, on_pin in sorted(nets.items()):
        if len(on_pin) > 1:
            out.append(Finding("peripheral_conflict_free", name,
                               f"{name} is assigned to {len(on_pin)} nets: {', '.join(sorted(on_pin))}"))

    # A hardware UART: TX and RX on one peripheral, used once, never the console.
    if target.uart_mode == "fixed":
        uart_pins = [(a, target.pins[name]) for a, name in resolved if name and a.role in ("uart_tx", "uart_rx")]
        peripherals: Dict[str, List[str]] = {}
        for a, pin in uart_pins:
            want = "TX" if a.role == "uart_tx" else "RX"
            options = {p for p, role in pin.uart if role == want}
            for p in options:
                peripherals.setdefault(p, []).append(a.role)
        tx = [(a, p) for a, p in uart_pins if a.role == "uart_tx"]
        rx = [(a, p) for a, p in uart_pins if a.role == "uart_rx"]
        if tx and rx:
            tx_units = {u for _, p in tx for u, r in p.uart if r == "TX"}
            rx_units = {u for _, p in rx for u, r in p.uart if r == "RX"}
            if not tx_units & rx_units:
                out.append(Finding("peripheral_conflict_free", tx[0][1].name,
                                   f"UART TX on {'/'.join(sorted(tx_units)) or '—'} and RX on "
                                   f"{'/'.join(sorted(rx_units)) or '—'}: one UART needs both on the same peripheral"))
        for unit, roles in sorted(peripherals.items()):
            if roles.count("uart_tx") > 1 or roles.count("uart_rx") > 1:
                out.append(Finding("peripheral_conflict_free", unit, f"{unit} is claimed by more than one UART user"))
            if unit == target.console_uart:
                out.append(Finding("peripheral_conflict_free", unit, f"{unit} is the board's console UART"))
    return out


def summarise(findings: Sequence[Finding]) -> Dict[str, Tuple[bool, str]]:
    """Per rule: (holds, detail)."""
    out = {}
    for rule in RULES:
        mine = [f for f in findings if f.rule == rule]
        out[rule] = (not mine, "; ".join(f.message for f in mine) or "every assigned pin passes")
    return out


# ── From a design ────────────────────────────────────────────────────────────

def design_target(ir: CircuitIR) -> Optional[Target]:
    """The board a design is built for: its declared target, else its MCU's part."""
    mcu = next((c for c in ir.components if c.type == ComponentType.MICROCONTROLLER), None)
    if mcu is None:
        return None
    return get_target(ir.target_mcu) or target_for_part(mcu.part_number) or get_target(DEFAULT_TARGET)


def assignments_of(ir: CircuitIR) -> List[Assignment]:
    """What each MCU pin in the design is asked to do, from its node and direction."""
    mcu_ids = {c.id for c in ir.components if c.type == ComponentType.MICROCONTROLLER}
    nodes = {n.id: n for n in ir.nodes}
    out = []
    for conn in ir.connections:
        if conn.component_id not in mcu_ids or conn.pin.upper() in _POWER_PINS:
            continue
        node = nodes.get(conn.node_id)
        kind = getattr(node.type, "value", node.type) if node else None
        if kind == SignalType.UART_TX.value and conn.direction != "input":
            role = "uart_tx"
        elif kind == SignalType.UART_RX.value and conn.direction != "output":
            role = "uart_rx"
        elif kind == SignalType.PWM.value:
            role = "pwm"
        elif kind == SignalType.ANALOG.value and conn.direction == "input":
            role = "adc"
        else:
            role = {"output": "output", "input": "input"}.get(conn.direction, "bidirectional")
        out.append(Assignment(pin=conn.pin, role=role, net=conn.node_id))
    return out


def check_design(ir: CircuitIR) -> Optional[Dict[str, Tuple[bool, str]]]:
    """Per rule (holds, detail) for a design with an MCU; None for one without."""
    target = design_target(ir)
    if target is None:
        return None
    return summarise(check_assignment(target, assignments_of(ir)))
