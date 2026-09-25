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
- **The agent wrote these records and cannot verify them.** It did not open
  the documents in the session that wrote them; each `statement` is the
  agent's reading from memory, never a quotation. Only a person checking the
  document (`scripts/verify_figures.py`) makes a figure trusted.
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

RECORDED_BY = ("the agent (an LLM), 2026-09-25, from its reading of the document — the "
               "document was not opened; not verified")


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

_ATMEGA = Source("Microchip", "ATmega48A/PA/88A/PA/168A/PA/328/P datasheet (DS40002061)",
                 "§ Electrical Characteristics — DC Characteristics; Absolute Maximum Ratings")
_ESP32 = Source("Espressif", "ESP32-WROOM-32E & ESP32-WROOM-32UE datasheet",
                "§ Electrical Characteristics — Recommended Operating Conditions; DC Characteristics")
_STM32 = Source("STMicroelectronics", "STM32F411xC/xE datasheet (DS10314)",
                "§ Electrical characteristics — I/O port characteristics; operating conditions")
_LED = Source("Everlight", "67-21URC/S530-A3/TR8 datasheet", "Electro-Optical Characteristics; Absolute Maximum Ratings")
_DHT = Source("Aosong", "AM2302 (DHT22) product manual", "§ Electrical characteristics; single-bus timing")
_MAX485 = Source("Analog Devices (Maxim)", "MAX481/MAX483/MAX485/MAX487–MAX491/MAX1487 datasheet",
                 "Electrical Characteristics")
_MAX3485 = Source("Analog Devices (Maxim)", "MAX3483/MAX3485/MAX3486/MAX3488/MAX3490/MAX3491 datasheet",
                  "Electrical Characteristics")
_TIA485 = Source("TIA", "TIA/EIA-485-A", "receiver sensitivity; driver output into the specified load")
_YAGEO = Source("Yageo", "RC_L series (RC0100–RC2512) thick-film chip resistor datasheet",
                "ordering code; Electrical Characteristics table")
_SAMSUNG = Source("Samsung Electro-Mechanics", "CL series MLCC product specification",
                  "part-numbering system (size, dielectric, capacitance, tolerance, rated voltage)")


def _mcu(part: str, src: Source, vmax: str, rout: str, rec: str, run: str) -> List[Figure]:
    return [
        Figure(f"{part}/supply_voltage_max", Kind.GUARANTEED, vmax, src),
        Figure(f"{part}/gpio_output_resistance_ohm", Kind.TYPICAL, rout, src),
        Figure(f"{part}/gpio_recommended_current_ma", Kind.POLICY, rec, src),
        Figure(f"{part}/supply_model_ohm", Kind.ASSUMPTION, run, src),
    ]


def _transceiver(part: str, src: Source, supply: str) -> List[Figure]:
    return [
        Figure(f"{part}/supply_voltage_min", Kind.GUARANTEED, supply, src),
        Figure(f"{part}/supply_voltage_max", Kind.GUARANTEED, supply, src),
        Figure(f"{part}/current_draw_ma", Kind.TYPICAL,
               "supply current with the driver disabled — 0.3 mA is the datasheet's typical "
               "no-load figure; the maximum is higher", src),
        Figure(f"{part}/receiver_threshold_mv", Kind.STANDARD,
               "a receiver must resolve |V_AB| ≥ 200 mV (the part's own guaranteed input threshold "
               "is ±200 mV, matching the standard)", _TIA485),
        Figure(f"{part}/driver_rated_load_ohm", Kind.STANDARD,
               "a driver is specified into 54 Ω differential: two 120 Ω terminators and 32 unit loads",
               _TIA485),
        Figure(f"{part}/requires_termination_ohm", Kind.STANDARD,
               "terminate each end of the bus in the cable's characteristic impedance, nominally 120 Ω",
               _TIA485),
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
          "5.5 V maximum operating voltage (6.0 V absolute maximum)",
          "at most 40 Ω, derived: V_OH ≥ 4.2 V at I_OH = 20 mA with VCC = 5 V (guaranteed); the "
          "15 Ω minimum and 25 Ω typical are read from the typical output-drive curves",
          "20 mA — the current at which the datasheet specifies V_OH; 40 mA is the absolute maximum",
          "100 Ω on 5 V is 50 mA — the whole Uno board's run current (regulator, USB bridge, LEDs), "
          "not the ATmega328P's own few mA"),
    *_mcu("ESP32-WROOM-32E", _ESP32,
          "3.6 V maximum of the 3.0–3.6 V recommended operating range",
          "at most 33 Ω, derived: V_OH ≥ 0.8 × VDD at the default drive strength's 20 mA; the minimum "
          "and typical are estimates",
          "20 mA — the default drive strength's rated source current",
          "41 Ω on 3.3 V is 80 mA — the module's run current without the radio, rounded up from the "
          "modem-sleep figures"),
    *_mcu("STM32F411CEU6", _STM32,
          "3.6 V maximum operating supply",
          "at most 65 Ω, derived: V_OH ≥ VDD − 1.3 V at |I_IO| = 20 mA; the minimum and typical are "
          "estimates",
          "20 mA — inside the ±25 mA per-pin absolute maximum, where V_OH is specified",
          "132 Ω on 3.3 V is 25 mA — the run current at 100 MHz with peripherals off"),
    Figure("67-21URC/S530-A3/TR8/forward_voltage_v", Kind.GUARANTEED,
           "V_F 1.7 V minimum, 2.4 V maximum at I_F = 20 mA; 2.0 V typical", _LED),
    Figure("67-21URC/S530-A3/TR8/test_current_ma", Kind.GUARANTEED, "the forward-voltage test condition, 20 mA", _LED),
    Figure("67-21URC/S530-A3/TR8/max_continuous_current_ma", Kind.GUARANTEED,
           "25 mA continuous forward current, absolute maximum", _LED),
    Figure("67-21URC/S530-A3/TR8/ideality", Kind.ASSUMPTION,
           "the diode model's ideality factor, 2.0 — not published; chosen so one Shockley curve "
           "spans the V_F range", _LED),
    Figure("DHT22/supply_voltage_min", Kind.GUARANTEED, "3.3 V minimum supply", _DHT),
    Figure("DHT22/supply_voltage_max", Kind.GUARANTEED,
           "the agent recalls 3.3–6 V DC in the product manual; the table uses 5.5 V, the more "
           "conservative figure — the check should settle which", _DHT),
    Figure("DHT22/current_draw_ma", Kind.ASSUMPTION,
           "2.5 mA — above the manual's 1–1.5 mA while measuring; a conservative figure of the project's", _DHT),
    Figure("DHT22/bus_capacitance_pf_per_m", Kind.ASSUMPTION,
           "50–100 pF per metre of sensor cable, ribbon to twisted pair; the manual gives none", None),
    Figure("DHT22/input_capacitance_pf", Kind.ASSUMPTION,
           "10 pF each for the MCU pin and the sensor's pin; neither is published for this bus", None),
    Figure("DHT22/rise_time_limit_us", Kind.ASSUMPTION,
           "5 µs, a 5× margin inside the 26–28 µs high time of a '0' bit the manual gives", _DHT),
    Figure("DHT22/open_drain_sink_limit_ma", Kind.ASSUMPTION,
           "4 mA through the sensor's open-drain output — the conservative figure open-drain buses "
           "(I²C: 3 mA) are designed to; the manual gives none", None),
    *_transceiver("MAX485ECSA", _MAX485, "4.75–5.25 V supply"),
    *_transceiver("MAX3485ECSA", _MAX3485, "3.0–3.6 V supply"),
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
            out.append(Figure(f"board:{target_id}/{name}", Kind.GUARANTEED, "; ".join(parts),
                              _BOARD_SOURCES.get(target_id)))
        out.append(Figure(f"board:{target_id}/console_uart", Kind.GUARANTEED,
                          f"the USB console occupies {target.console_uart or 'no hardware UART'}",
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


# ── Verifications ────────────────────────────────────────────────────────────

VERIFICATIONS_PATH = Path(__file__).parent / "figure_verifications.json"


@lru_cache(maxsize=8)
def _load(path: str, mtime: float) -> Tuple[Tuple[str, str, str, str], ...]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return tuple((v["figure"], v["record_hash"], v["by"], v["at"]) for v in data.get("verifications", []))


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
    return any(f == figure_id and h == current for f, h, _, _ in (verifications() if rows is None else rows))


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
