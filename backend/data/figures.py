"""
Part-figure provenance — defeater D7, made closable per figure.

`brain/decisions.md` [2026-09-24] D1, D2, D7: D7 doubts the datasheet
parameters feeding `predict()`, the proofs and the rule tables, and is
eliminated by "provenance per parameter; no LLM-extracted rating gates a
claim". This module is the provenance: one record per figure a claim reads.

- **Values stay in their owning tables** — `component_constraints.py`,
  `parts.py`, `mcu_targets.py`. A record points at one by id
  (`<owner>/<key>`); `value()` reads it. Nothing here restates a number.
- **`record_hash`** covers the record *and* the current value, so editing
  either voids a verification.
- **The agent wrote these records and cannot verify them.** It first wrote
  them from memory; on 2026-09-25 it opened the makers' documents it could
  obtain, corrected what they contradicted, and recorded page by page what it
  found in `data/figure_evidence.json` ([2026-09-25]). A `statement` is the
  agent's reading, never a quotation. Only a person — reading the document,
  or confirming the agent's cited evidence (`scripts/verify_figures.py`) —
  makes a figure trusted.
- **Trusted** means verified *and* a guaranteed limit, a standard's figure, or
  a policy the project sets for itself (verification confirms the citation);
  or derived from trusted inputs. A typical or a stated assumption is never
  trusted — verifying it confirms what it is, not that it is a guarantee.

A claim cites D7 while any figure it reads is untrusted
(`validation/claims.py`). With nothing verified that is every figure-reading
claim, exactly as before this module existed.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


class Kind(str, Enum):
    GUARANTEED = "guaranteed_limit"   # a datasheet min/max or absolute rating
    TYPICAL = "typical"               # a datasheet typical or characterisation curve
    DERIVED = "derived"               # computed from other figures (`inputs`)
    STANDARD = "standard"             # set by a published standard, not the part
    POLICY = "policy"                 # a limit the project sets, citing what it follows
    ASSUMPTION = "stated_assumption"  # the project's own figure; no document gives it


TRUSTABLE = (Kind.GUARANTEED, Kind.STANDARD, Kind.POLICY)

RECORDED_BY = ("the agent (an LLM), 2026-09-25; its check against the document, where it could get "
               "one, is in data/figure_evidence.json — not a person's verification")


@dataclass(frozen=True)
class Source:
    maker: str
    document: str
    location: str


@dataclass(frozen=True)
class Figure:
    id: str
    kind: Kind
    statement: str
    source: Optional[Source] = None
    inputs: Tuple[str, ...] = ()
    recorded_by: str = RECORDED_BY


# ── Sources ──────────────────────────────────────────────────────────────────

_ATMEGA = Source("Microchip", "ATmega48A/PA/88A/PA/168A/PA/328/P datasheet (DS40002061B)",
                 "§29.1 Absolute Maximum Ratings; Table 29-8; Table 30-1 Common DC characteristics; "
                 "Figure 31-355")
_ESP32 = Source("Espressif", "ESP32-WROOM-32E & ESP32-WROOM-32UE datasheet v2.1; ESP32 Series datasheet v5.3",
                "module Tables 13–15 (ratings, operating conditions, DC characteristics); series datasheet "
                "§5 power consumption and the notes on the ESP32 pin lists")
_STM32 = Source("STMicroelectronics", "STM32F411xC/xE datasheet (DS10314)",
                "§ Electrical characteristics — I/O port characteristics; operating conditions")
_LED = Source("Everlight", "67-21URC/S530-A3/TR8 datasheet", "Electro-Optical Characteristics; Absolute Maximum Ratings")
_DHT = Source("Aosong (ASAIR)", "AM2302 Technical Manual V1.0", "Table 2 Electric Specification; single-bus timing table")
_MAX485 = Source("Analog Devices (Maxim)", "MAX481/MAX483/MAX485/MAX487–MAX491/MAX1487 datasheet",
                 "Electrical Characteristics")
_MAX3485 = Source("Analog Devices (Maxim)", "MAX3483/MAX3485/MAX3486/MAX3488/MAX3490/MAX3491 datasheet",
                  "Electrical Characteristics")
_TIA485 = Source("TIA", "TIA/EIA-485-A", "receiver sensitivity; driver output into the specified load")
_YAGEO = Source("Yageo", "General purpose chip resistors RC_L series, product specification V.14 (2025-11-14)",
                "ordering information (tolerance code); Tables 2 and 3 (power, maximum working voltage)")
_SAMSUNG = Source("Samsung Electro-Mechanics", "component library data sheet for the part",
                  "capacitance, tolerance, rated voltage, TCC and size")


def _mcu(part: str, src: Source, vmax: str, rout: str, rec: str, run: str, leak: str) -> List[Figure]:
    return [
        Figure(f"{part}/supply_voltage_max", Kind.GUARANTEED, vmax, src),
        Figure(f"{part}/gpio_output_resistance_ohm", Kind.TYPICAL, rout, src),
        Figure(f"{part}/gpio_recommended_current_ma", Kind.POLICY, rec, src),
        Figure(f"{part}/supply_model_ohm", Kind.ASSUMPTION, run, src),
        Figure(f"{part}/pin_leakage_ua", Kind.GUARANTEED, leak, src),
    ]


def _transceiver(part: str, src: Source, supply: str, icc: str) -> List[Figure]:
    return [
        Figure(f"{part}/supply_voltage_min", Kind.GUARANTEED, supply, src),
        Figure(f"{part}/supply_voltage_max", Kind.GUARANTEED, supply, src),
        Figure(f"{part}/current_draw_ma", Kind.TYPICAL, icc, src),
        Figure(f"{part}/receiver_threshold_mv", Kind.STANDARD,
               "a receiver must resolve |V_AB| ≥ 200 mV (the part's own guaranteed input threshold "
               "is ±200 mV, matching the standard)", _TIA485),
        Figure(f"{part}/driver_rated_load_ohm", Kind.STANDARD,
               "a driver is specified into 54 Ω differential: two 120 Ω terminators and 32 unit loads",
               _TIA485),
        Figure(f"{part}/requires_termination_ohm", Kind.STANDARD,
               "terminate each end of the bus in the cable's characteristic impedance, nominally 120 Ω",
               _TIA485),
        Figure(f"{part}/logic_input_vil_v", Kind.GUARANTEED,
               "input low voltage of DE, RE and DI: 0.8 V maximum", src),
        Figure(f"{part}/logic_input_current_ua", Kind.GUARANTEED,
               "input current of DE, RE and DI: ±2 µA maximum", src),
    ]


def _resistor_series(code: str, tol: str, power: str, volts: str) -> List[Figure]:
    return [
        Figure(f"{code}/tolerance", Kind.GUARANTEED, f"tolerance letter in the part number: {tol}", _YAGEO),
        Figure(f"{code}/power_w", Kind.GUARANTEED, f"rated power {power} at 70 °C ambient, derated above", _YAGEO),
        Figure(f"{code}/voltage_max", Kind.GUARANTEED, f"maximum working voltage {volts}", _YAGEO),
    ]


def _capacitor(part: str, what: str) -> List[Figure]:
    return [
        Figure(f"{part}/tolerance", Kind.GUARANTEED, f"{what}: tolerance letter K = ±10%", _SAMSUNG),
        Figure(f"{part}/voltage_max", Kind.GUARANTEED, f"{what}: rated-voltage letter in the part number",
               _SAMSUNG),
    ]


_SCALARS: List[Figure] = [
    *_mcu("ATmega328P-PU", _ATMEGA,
          "5.5 V maximum operating voltage (the DC tables' VCC = 1.8–5.5 V); 6.0 V is the absolute maximum",
          "at most 40 Ω, derived: V_OH ≥ 4.2 V at I_OH = 20 mA with VCC = 5 V (guaranteed, Table 30-1); "
          "25 Ω typical from the 25 °C output-drive curve (about 26 Ω, Figure 31-355); the 15 Ω minimum "
          "is the project's conservative figure — the curves show about 22 Ω at −40 °C",
          "20 mA — the current at which the datasheet specifies V_OH; 40 mA is the absolute maximum",
          "100 Ω on 5 V is 50 mA — the whole Uno board's run current (regulator, USB bridge, LEDs), a "
          "figure of the project's; the ATmega328P's own is about 10 mA at 16 MHz",
          "I/O pin input leakage |I_IL|, |I_IH|: 1 µA maximum at VCC = 5.5 V"),
    *_mcu("ESP32-WROOM-32E", _ESP32,
          "3.6 V maximum of the 3.0–3.6 V recommended operating range",
          "about 33 Ω typical at the default drive strength, estimated from typicals: the module gives "
          "I_OH = 40 mA typical at V_OH ≥ 2.64 V with the drive strength at its maximum (about 16.5 Ω), "
          "and the default strength is 2 of 0–3 (~20 mA); up to about 66 Ω on the VDD_SDIO pins (20 mA "
          "typical) or with several pins sourcing; no maximum is published — 10 Ω is the project's low end",
          "20 mA — the nominal (~20 mA) label of the default drive strength, not a guaranteed current",
          "41 Ω on 3.3 V is 80 mA — rounded up from the chip's modem-sleep maximum (68 mA at 240 MHz); "
          "the chip table leaves out the module's flash",
          "input current I_IH, I_IL: 50 nA maximum, specified at 3.3 V and 25 °C only"),
    *_mcu("STM32F411CEU6", _STM32,
          "3.6 V maximum operating supply",
          "at most 65 Ω, derived: V_OH ≥ VDD − 1.3 V at |I_IO| = 20 mA; the minimum and typical are "
          "estimates",
          "20 mA — inside the ±25 mA per-pin absolute maximum, where V_OH is specified",
          "132 Ω on 3.3 V is 25 mA — above the 24.4 mA maximum run current at 100 MHz from flash with "
          "all peripherals enabled (Table 23, V_DD = 3.6 V, 125 °C); 11.6 mA typical with them disabled",
          "input leakage I_lkg of a standard I/O pin: ±1 µA maximum for V_SS ≤ V_IN ≤ V_DD"),
    Figure("67-21URC/S530-A3/TR8/forward_voltage_v", Kind.GUARANTEED,
           "V_F 1.7 V minimum, 2.4 V maximum at I_F = 20 mA; 2.0 V typical", _LED),
    Figure("67-21URC/S530-A3/TR8/test_current_ma", Kind.GUARANTEED, "the forward-voltage test condition, 20 mA", _LED),
    Figure("67-21URC/S530-A3/TR8/max_continuous_current_ma", Kind.GUARANTEED,
           "25 mA continuous forward current, absolute maximum", _LED),
    Figure("67-21URC/S530-A3/TR8/ideality", Kind.ASSUMPTION,
           "the diode model's ideality factor, 2.0 — not published; chosen so one Shockley curve "
           "spans the V_F range", _LED),
    Figure("DHT22/supply_voltage_min", Kind.GUARANTEED, "3.3 V minimum supply", _DHT),
    Figure("DHT22/supply_voltage_max", Kind.GUARANTEED, "5.5 V maximum supply (3.3 V minimum, 5 V typical)",
           _DHT),
    Figure("DHT22/current_draw_ma", Kind.ASSUMPTION,
           "2.5 mA — above the manual's 1.2 mA typical while measuring, for which it gives no maximum; a "
           "conservative figure of the project's", _DHT),
    Figure("DHT22/bus_capacitance_pf_per_m", Kind.ASSUMPTION,
           "50–100 pF per metre of sensor cable, ribbon to twisted pair; the manual gives none", None),
    Figure("DHT22/input_capacitance_pf", Kind.ASSUMPTION,
           "10 pF each for the MCU pin and the sensor's pin — the ATmega328P's maximum per I/O pin "
           "(Table 29-14, characterised); the ESP32 module gives 2 pF typical; the AM2302 manual gives "
           "none for its pin", None),
    Figure("DHT22/rise_time_limit_us", Kind.ASSUMPTION,
           "5 µs — over a 4× margin inside the 22 µs minimum high time of a '0' bit (T_H0 22–30 µs, "
           "26 µs typical)", _DHT),
    Figure("DHT22/open_drain_sink_limit_ma", Kind.ASSUMPTION,
           "4 mA through the sensor's data output — half the manual's 8 mA typical output current, and "
           "under its ±10 mA per-pin absolute maximum (Table 5); about what open-drain buses (I²C: 3 mA) "
           "are designed to",
           _DHT),
    *_transceiver("MAX485ECSA", _MAX485, "4.75–5.25 V supply",
                  "no-load supply current with the driver disabled (DE = 0 V): 0.3 mA typical, "
                  "0.5 mA maximum"),
    *_transceiver("MAX3485ECSA", _MAX3485, "3.0–3.6 V supply",
                  "no-load supply current with the driver disabled (DE = 0 V, RE = 0 V): 0.95 mA typical, "
                  "1.9 mA maximum"),
    *_resistor_series("RC0402FR", "F = ±1%", "62.5 mW (1/16 W)", "50 V"),
    *_resistor_series("RC0402JR", "J = ±5%", "62.5 mW (1/16 W)", "50 V"),
    *_resistor_series("RC0603FR", "F = ±1%", "100 mW (1/10 W)", "75 V"),
    *_resistor_series("RC0805FR", "F = ±1%", "125 mW (1/8 W)", "150 V"),
    *_resistor_series("RC1206FR", "F = ±1%", "250 mW (1/4 W)", "200 V"),
    *_capacitor("CL05B104KO5NNNC", "0402 X7R 100 nF, O = 16 V"),
    *_capacitor("CL05B103KB5NNNC", "0402 X7R 10 nF, B = 50 V"),
    *_capacitor("CL05A105KQ5NNNC", "0402 X5R 1 µF, Q = 6.3 V"),
    *_capacitor("CL05B102KB5NNNC", "0402 X7R 1 nF, B = 50 V"),
    *_capacitor("CL05B223KO5NNNC", "0402 X7R 22 nF, O = 16 V"),
    *_capacitor("CL05A224KQ5NNNC", "0402 X5R 220 nF, Q = 6.3 V"),
    *_capacitor("CL05B472KB5NNNC", "0402 X7R 4.7 nF, B = 50 V"),
    *_capacitor("CL05B473KO5NNNC", "0402 X7R 47 nF, O = 16 V"),
]

_BOARD_SOURCES = {
    "arduino_uno": Source("Arduino", "Arduino Uno Rev3 schematic and pin reference; ATmega328P datasheet",
                          "pin functions (PWM, USART0), USB-serial wiring"),
    "esp32_devkitc": Source("Espressif", "ESP32-DevKitC V4 user guide; ESP32 series datasheet",
                            "pin layout; strapping pins; flash pins; input-only pins"),
    "blackpill_f411ce": Source("WeAct Studio / STMicroelectronics",
                               "BlackPill STM32F411CEU6 V3.0 pinout; STM32F411xC/xE datasheet (DS10314)",
                               "pin table; on-board button, LED, crystal, USB and SWD pins"),
}


#: What each `Target.uart_mode` asserts about the board — the pin rules branch on it.
_UART_MODES = {
    "software": "UART roles are served by SoftwareSerial: any digital pin can be TX or RX",
    "matrix": "a hardware UART can be routed to any output-capable GPIO (TX) or input-capable GPIO (RX) "
              "through the GPIO matrix",
    "fixed": "a hardware UART is reachable only on the pins listed as its alternate functions, "
             "and TX and RX must belong to the same peripheral",
}


def _pin_records() -> List[Figure]:
    from data.mcu_targets import TARGETS

    out = []
    for target_id, target in TARGETS.items():
        for name, pin in target.pins.items():
            can = [w for w, ok in (("output", pin.output), ("input", pin.input), ("PWM", pin.pwm),
                                   ("ADC", pin.adc)) if ok]
            can += [f"{u} {r}" for u, r in pin.uart]
            parts = [f"{name}: " + (", ".join(can) or "no function")]
            if pin.reserved:
                parts.append(f"reserved — {pin.reserved}")
            if pin.strapping:
                parts.append(f"strapping — {pin.strapping}")
            if pin.reset_note:
                parts.append(pin.reset_note)
            else:
                parts.append(f"weak pull-{pin.reset_pull} from reset until firmware sets the pin" if pin.reset_pull
                             else "high-impedance, no pull, from reset until firmware sets the pin")
            out.append(Figure(f"board:{target_id}/{name}", Kind.GUARANTEED, "; ".join(parts),
                              _BOARD_SOURCES.get(target_id)))
        out.append(Figure(f"board:{target_id}/console_uart", Kind.GUARANTEED,
                          f"the USB console occupies {target.console_uart or 'no hardware UART'}",
                          _BOARD_SOURCES.get(target_id)))
        out.append(Figure(f"board:{target_id}/uart_mode", Kind.GUARANTEED, _UART_MODES[target.uart_mode],
                          _BOARD_SOURCES.get(target_id)))
    return out


FIGURES: Dict[str, Figure] = {f.id: f for f in (*_SCALARS, *_pin_records())}


# ── Values, read from their owners ───────────────────────────────────────────

def owner_and_key(figure_id: str) -> Tuple[str, str]:
    owner, _, key = figure_id.rpartition("/")
    return owner, key


def value(figure_id: str) -> Any:
    """The figure's current value, from the table that owns it. KeyError if there is none."""
    from data.component_constraints import COMPONENT_CONSTRAINTS
    from data.mcu_targets import TARGETS
    from data.parts import CAPACITORS, RESISTOR_SERIES

    owner, key = owner_and_key(figure_id)
    if owner.startswith("board:"):
        target = TARGETS[owner[len("board:"):]]
        return asdict(target.pins[key]) if key in target.pins else getattr(target, key)
    if owner in RESISTOR_SERIES:
        return getattr(RESISTOR_SERIES[owner], key)
    if owner in CAPACITORS:
        return getattr(CAPACITORS[owner], key)
    return COMPONENT_CONSTRAINTS[owner][key]


def record_hash(figure_id: str) -> str:
    record = FIGURES[figure_id]
    payload = {"record": asdict(record), "value": value(figure_id)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


# ── The agent's evidence ([2026-09-25]) — never a verification ───────────────

EVIDENCE_PATH = Path(__file__).parent / "figure_evidence.json"


def evidence(path: Optional[str] = None) -> Dict[str, Any]:
    """The agent's check of each record against its document; {} if there is none. Read by
    scripts/verify_figures.py and the tests — never by a claim."""
    path = str(path or EVIDENCE_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Verifications ────────────────────────────────────────────────────────────

VERIFICATIONS_PATH = Path(__file__).parent / "figure_verifications.json"

#: Names that are the documentation's, not a person's. A row signed with one is no
#: verification: it is never counted, whichever tool wrote it ([2026-10-01] #16).
PLACEHOLDERS = frozenset({"your name", "<your name>", "name", "<name>", "your-name", "<your-name>"})


def names_a_person(by: Any) -> bool:
    return isinstance(by, str) and bool(by.strip()) and by.strip().lower() not in PLACEHOLDERS


@lru_cache(maxsize=8)
def _load(path: str, mtime: float) -> Tuple[Tuple[str, str, str, str], ...]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return tuple((v["figure"], v["record_hash"], v["by"], v["at"]) for v in data.get("verifications", [])
                 if names_a_person(v.get("by")))


def verifications(path: Optional[str] = None) -> Tuple[Tuple[str, str, str, str], ...]:
    """(figure, record_hash, by, at) rows. Cached on the file's mtime."""
    path = str(path or os.environ.get("CIRCUITOS_FIGURE_VERIFICATIONS") or VERIFICATIONS_PATH)
    if not os.path.exists(path):
        return ()
    return _load(path, os.path.getmtime(path))


def verified(figure_id: str, rows: Optional[Iterable[Tuple[str, str, str, str]]] = None) -> bool:
    """Verified, and the record and value are still the ones that were checked."""
    if figure_id not in FIGURES:
        return False
    current = record_hash(figure_id)
    return any(f == figure_id and h == current and names_a_person(by)
               for f, h, by, _ in (verifications() if rows is None else rows))


def trusted(figure_id: str, rows: Optional[Iterable[Tuple[str, str, str, str]]] = None,
            _seen: Tuple[str, ...] = ()) -> bool:
    record = FIGURES.get(figure_id)
    if record is None or figure_id in _seen:
        return False
    rows = tuple(verifications() if rows is None else rows)
    if not verified(figure_id, rows):
        return False
    if record.kind in TRUSTABLE:
        return True
    if record.kind == Kind.DERIVED:
        return all(trusted(i, rows, _seen + (figure_id,)) for i in record.inputs)
    return False


def untrusted(figures: Iterable[str], rows: Optional[Iterable[Tuple[str, str, str, str]]] = None) -> Tuple[str, ...]:
    rows = tuple(verifications() if rows is None else rows)
    return tuple(f for f in dict.fromkeys(figures) if not trusted(f, rows))


# ── Helpers generators use to name what a claim reads ────────────────────────

def of(owner: str, *keys: str) -> Tuple[str, ...]:
    """Figure ids `<owner>/<key>`; KeyError for one with no record — a claim may not read an unrecorded figure."""
    ids = tuple(f"{owner}/{k}" for k in keys)
    missing = [i for i in ids if i not in FIGURES]
    if missing:
        raise KeyError(f"no provenance record for {missing} (data/figures.py)")
    return ids


def passive(part_number: str, *keys: str) -> Tuple[str, ...]:
    """Figures of a tabulated passive: its resistor series, or the capacitor itself."""
    from data.parts import passive_figures

    found = passive_figures(part_number)
    if found is None:
        raise KeyError(f"{part_number} is not in data/parts.py; its figures have no owner")
    return of(found[0], *keys)
