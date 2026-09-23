"""
The microcontroller boards a design may target. Stage 5.

Data, in one place: `brain/decisions.md` [2026-09-23] Stage 5. Per target, the
PlatformIO environment that builds its firmware, the logic rail, and a pin
table — which pins the board exposes, what each can do, which are reserved
and why, and which are strapping pins and what they strap. The generators
pick pins from it, `validation/pin_rules.py` checks designs against it, and
the firmware generator reads the names firmware uses from it.

Transcribed from the datasheets and board schematics (defeater D7); the
labelled set in `tests/fixtures/pin_assignments.json` checks the rules
against hand-labelled cases, not the transcription against silicon.

Electrical figures for each MCU part — GPIO output resistance, recommended
pin current, supply-load model — live in `data/component_constraints.py`
with the Uno's, so the netlist, `predict()` and the prover read one table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

DEFAULT_TARGET = "arduino_uno"


@dataclass(frozen=True)
class Pin:
    name: str                      # canonical: "D13", "GPIO4", "PA5"
    firmware: str                  # what the sketch writes: "13", "4", "PA5"
    output: bool = True            # can drive
    input: bool = True             # can read
    pwm: bool = False
    adc: bool = False
    #: Hardware UART roles this pin can take through fixed alternate
    #: functions: (peripheral, "TX" | "RX").
    uart: Tuple[Tuple[str, str], ...] = ()
    reserved: Optional[str] = None     # why it must not be assigned
    strapping: Optional[str] = None    # what it straps at reset
    note: Optional[str] = None


@dataclass(frozen=True)
class Target:
    id: str
    board: str                     # the human name
    mcu_part: str                  # key into component_constraints
    platform: str                  # PlatformIO platform
    pio_board: str                 # PlatformIO board id
    logic_v: float                 # I/O and peripheral rail
    rail_node: str                 # the node the generators name for that rail
    #: How a UART reaches a pin: "software" (SoftwareSerial on any digital
    #: pin), "matrix" (any output-capable GPIO via the ESP32 GPIO matrix), or
    #: "fixed" (the pin's own alternate functions, `Pin.uart`).
    uart_mode: str
    #: The hardware UART the RS-485 design uses; None for SoftwareSerial.
    rs485_uart: Optional[str]
    #: The UART the USB console occupies; a peripheral may not use it.
    console_uart: Optional[str]
    #: Default pin per role, chosen to pass every pin rule.
    defaults: Mapping[str, str]
    pins: Mapping[str, Pin] = field(default_factory=dict)
    #: Extra platformio.ini lines for this environment.
    build_flags: Tuple[str, ...] = ()

    def pin(self, text: object) -> Optional[Pin]:
        """The pin a user or generator named, however they spelled it; None if none."""
        name = normalise(self, text)
        return self.pins.get(name) if name else None


# ── Arduino Uno ──────────────────────────────────────────────────────────────

def _uno() -> Target:
    pins: Dict[str, Pin] = {}
    for n in range(14):
        pins[f"D{n}"] = Pin(name=f"D{n}", firmware=str(n), pwm=n in (3, 5, 6, 9, 10, 11))
    pins["D0"] = Pin(name="D0", firmware="0", uart=(("USART0", "RX"),),
                     reserved="the USB serial port's RX — uploads and the console use it")
    pins["D1"] = Pin(name="D1", firmware="1", uart=(("USART0", "TX"),),
                     reserved="the USB serial port's TX — uploads and the console use it")
    pins["D13"] = Pin(name="D13", firmware="13", note="also drives the on-board LED")
    for n in range(6):
        pins[f"A{n}"] = Pin(name=f"A{n}", firmware=f"A{n}", adc=True)
    return Target(
        id="arduino_uno", board="Arduino Uno R3", mcu_part="ATmega328P-PU",
        platform="atmelavr", pio_board="uno", logic_v=5.0, rail_node="VCC_5V",
        uart_mode="software", rs485_uart=None, console_uart="USART0",
        defaults={"led": "D13", "dht_data": "D2", "rs485_tx": "D11", "rs485_rx": "D10", "rs485_de": "D2"},
        pins=pins,
    )


# ── ESP32-DevKitC (ESP32-WROOM-32E) ──────────────────────────────────────────

_ESP32_STRAPS = {
    0: "boot mode — must be high at reset; low enters the download bootloader",
    2: "boot mode — must be low or floating at reset for serial download",
    5: "SDIO slave timing at reset",
    12: "MTDI — sets the flash voltage at reset; pulled high selects 1.8 V and the module will not boot",
    15: "MTDO — at reset, low silences the boot log and changes SDIO timing",
}


def _esp32() -> Target:
    exposed = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
               21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
    adc = {0, 2, 4, 12, 13, 14, 15, 25, 26, 27, 32, 33, 34, 35, 36, 39}
    pins: Dict[str, Pin] = {}
    for n in exposed:
        input_only = n in (34, 35, 36, 39)
        reserved = None
        if 6 <= n <= 11:
            reserved = "wired to the module's SPI flash"
        elif n == 1:
            reserved = "UART0 TX — the USB console and uploads"
        elif n == 3:
            reserved = "UART0 RX — the USB console and uploads"
        pins[f"GPIO{n}"] = Pin(
            name=f"GPIO{n}", firmware=str(n), output=not input_only, pwm=not input_only,
            adc=n in adc, reserved=reserved, strapping=_ESP32_STRAPS.get(n),
            note="input only, no internal pull-up or pull-down" if input_only else None,
        )
    return Target(
        id="esp32_devkitc", board="ESP32-DevKitC (ESP32-WROOM-32E)", mcu_part="ESP32-WROOM-32E",
        platform="espressif32", pio_board="esp32dev", logic_v=3.3, rail_node="VCC_3V3",
        uart_mode="matrix", rs485_uart="UART2", console_uart="UART0",
        defaults={"led": "GPIO4", "dht_data": "GPIO4", "rs485_tx": "GPIO17", "rs485_rx": "GPIO16",
                  "rs485_de": "GPIO4"},
        pins=pins,
    )


# ── WeAct Black Pill (STM32F411CEU6) ─────────────────────────────────────────

_F411_PWM = {"PA0", "PA1", "PA2", "PA3", "PA5", "PA6", "PA7", "PA8", "PA9", "PA10", "PA11", "PA15",
             "PB0", "PB1", "PB3", "PB4", "PB5", "PB6", "PB7", "PB8", "PB9", "PB10", "PB13", "PB14", "PB15"}
_F411_ADC = {"PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7", "PB0", "PB1"}
_F411_UART = {
    "PA9": (("USART1", "TX"),), "PA15": (("USART1", "TX"),), "PB6": (("USART1", "TX"),),
    "PA10": (("USART1", "RX"),), "PB3": (("USART1", "RX"),), "PB7": (("USART1", "RX"),),
    "PA2": (("USART2", "TX"),), "PA3": (("USART2", "RX"),),
    "PA11": (("USART6", "TX"),), "PA12": (("USART6", "RX"),),
}
_F411_RESERVED = {
    "PA11": "USB D− — the USB serial console and DFU upload",
    "PA12": "USB D+ — the USB serial console and DFU upload",
    "PA13": "SWDIO — the debug and programming port",
    "PA14": "SWCLK — the debug and programming port",
    "PC14": "the board's 32.768 kHz crystal",
    "PC15": "the board's 32.768 kHz crystal",
    "PC13": "the on-board LED; PC13–PC15 may sink at most 3 mA and must not source current",
    "PA0": "the on-board KEY button — pressing it shorts the pin to GND",
}
_F411_NOTES = {
    "PA15": "a JTAG pin after reset; free when only SWD is used",
    "PB3": "a JTAG pin after reset; free when only SWD is used",
    "PB4": "a JTAG pin after reset; free when only SWD is used",
}


def _blackpill() -> Target:
    names = ([f"PA{n}" for n in range(16)] + [f"PB{n}" for n in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15)]
             + ["PC13", "PC14", "PC15"])
    pins = {
        n: Pin(name=n, firmware=n, pwm=n in _F411_PWM, adc=n in _F411_ADC, uart=_F411_UART.get(n, ()),
               reserved=_F411_RESERVED.get(n),
               strapping="BOOT1 — held at GND through 10 kΩ on the board" if n == "PB2" else None,
               note=_F411_NOTES.get(n))
        for n in names
    }
    return Target(
        id="blackpill_f411ce", board="WeAct Black Pill (STM32F411CEU6)", mcu_part="STM32F411CEU6",
        platform="ststm32", pio_board="blackpill_f411ce", logic_v=3.3, rail_node="VCC_3V3",
        uart_mode="fixed", rs485_uart="USART2", console_uart=None,
        defaults={"led": "PB0", "dht_data": "PB1", "rs485_tx": "PA2", "rs485_rx": "PA3", "rs485_de": "PB0"},
        pins=pins,
        # Serial is the USB CDC port, so no UART is the console.
        build_flags=("-D PIO_FRAMEWORK_ARDUINO_ENABLE_CDC", "-D USBCON"),
    )


TARGETS: Dict[str, Target] = {t.id: t for t in (_uno(), _esp32(), _blackpill())}


def get_target(target_id: object) -> Optional[Target]:
    return TARGETS.get(str(target_id)) if isinstance(target_id, str) else None


def target_for_part(mcu_part: str) -> Optional[Target]:
    return next((t for t in TARGETS.values() if t.mcu_part == mcu_part), None)


def normalise(target: Target, text: object) -> Optional[str]:
    """
    A pin name as the target's table spells it. Accepts what people write:
    "D13" or "13" on the Uno; "GPIO4", "IO4" or "4" on the ESP32; "PA5" or
    "pa5" on the STM32. None when it names no pin of this board.
    """
    if isinstance(text, bool) or not isinstance(text, (str, int)):
        return None
    s = str(text).strip().upper()
    if target.id == "arduino_uno":
        m = re.fullmatch(r"D?(\d{1,2})", s)
        if m:
            n = int(m.group(1))
            # D14–D19 are A0–A5 used as digital pins.
            s = f"A{n - 14}" if 14 <= n <= 19 else f"D{n}"
    elif target.id == "esp32_devkitc":
        m = re.fullmatch(r"(?:GPIO|IO)?(\d{1,2})", s)
        if m:
            s = f"GPIO{int(m.group(1))}"
    return s if s in target.pins else None
