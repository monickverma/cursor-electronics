"""BOM compiler — static pricing from component_db.json (Phase 1).

No live Digikey/LCSC API calls in Phase 1. That is Phase 2.
Returns a list of dicts, one per component.

WHY THIS WAS REWRITTEN
======================
The previous version held an 11-entry hardcoded `_STATIC_PRICES` dict keyed by
LCSC part number. Two things made it useless in practice:

  1. All 11 of those LCSC part numbers already exist in `component_db.json`,
     which carries `unit_price_usd` on all 100 entries. The dict was pure
     duplication of a subset of the real database.

  2. It keyed on `Component.lcsc_pn`, which is `Optional` and which the AI
     usually does not populate. The lookup key was therefore `""`, every
     component fell through to `_UNKNOWN_PRICE = 0.0`, and the UI showed a
     confident "Estimated total: $0.00 USD" with every price column blank.

Silently pricing an unknown part at $0.00 is worse than admitting ignorance —
it makes an incomplete BOM look complete. Rows now carry `price_known` so the
UI can distinguish "free" from "not in the database", and `price_source` so it
is always clear how a price was obtained.

LOOKUP ORDER
============
  1. exact part_number match (case-insensitive)
  2. exact lcsc_pn match, when the IR supplied one
  3. part_number prefix match — the AI often writes a generic part number
     ("ATmega328P") where the database holds the orderable one
     ("ATmega328P-PU")
  4. category + electrical value match for passives — a 10k resistor is a 10k
     resistor whether the AI picked Yageo CFR-25JB-52-10K or the database holds
     RC0402FR-0710KL. Values are compared numerically, so "10k" / "10K" /
     "4K7" / "4.7k" / "100R" all resolve correctly.
  5. unmatched -> price 0.0 with price_known=False
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.ir_schema import CircuitIR

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "component_db.json"

# Categories where an equivalent part with the same electrical value is a valid
# substitute for pricing purposes. Never do this for actives — an ATmega328P is
# not interchangeable with an ATmega2560.
_VALUE_SUBSTITUTABLE = {"resistor", "capacitor", "inductor"}

_UNKNOWN_PRICE = 0.0


# ── Value parsing ────────────────────────────────────────────────────────────

_R_MULT = {"R": 1.0, "": 1.0, "K": 1e3, "M": 1e6}
_C_MULT = {"P": 1e-12, "N": 1e-9, "U": 1e-6, "M": 1e-3, "": 1.0}


def _parse_resistance(raw: Optional[str]) -> Optional[float]:
    """'10k' '10K' '4K7' '4.7k' '100R' '1K59' '1M' -> ohms."""
    if not raw:
        return None
    s = str(raw).strip().upper().replace("Ω", "").replace("OHM", "").replace(" ", "")
    if not s:
        return None

    # Embedded-multiplier form: 4K7 = 4.7k, 1K59 = 1.59k
    m = re.fullmatch(r"(\d+)([RKM])(\d+)", s)
    if m:
        whole, mult, frac = m.groups()
        return float(f"{whole}.{frac}") * _R_MULT[mult]

    # Trailing-multiplier form: 10K, 100R, 1M, 4.7K, or bare 470
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([RKM]?)", s)
    if m:
        val, mult = m.groups()
        return float(val) * _R_MULT[mult]

    return None


def _parse_capacitance(raw: Optional[str]) -> Optional[float]:
    """'100nF' '1uF' '22pF' '4.7nF' '10uF/25V' -> farads."""
    if not raw:
        return None
    s = str(raw).strip().upper().replace(" ", "")
    s = s.split("/")[0]  # drop voltage rating: 10uF/25V -> 10uF
    if not s:
        return None

    m = re.fullmatch(r"(\d+(?:\.\d+)?)([PNUM]?)F?", s)
    if m:
        val, mult = m.groups()
        return float(val) * _C_MULT[mult]
    return None


def _parse_value(category: str, raw: Optional[str]) -> Optional[float]:
    if category == "resistor":
        return _parse_resistance(raw)
    if category == "capacitor":
        return _parse_capacitance(raw)
    return None


# ── Database ─────────────────────────────────────────────────────────────────

class ComponentDatabase:
    """Indexed read-only view over component_db.json."""

    def __init__(self, entries: List[Dict[str, Any]]) -> None:
        self._entries = entries
        self._by_pn: Dict[str, Dict[str, Any]] = {}
        self._by_lcsc: Dict[str, Dict[str, Any]] = {}
        self._by_value: Dict[Tuple[str, float], List[Dict[str, Any]]] = {}

        for e in entries:
            pn = str(e.get("part_number", "")).strip()
            if pn:
                self._by_pn.setdefault(pn.upper(), e)

            lcsc = e.get("lcsc_pn")
            if lcsc:
                self._by_lcsc.setdefault(str(lcsc).strip().upper(), e)

            cat = str(e.get("category", ""))
            val = _parse_value(cat, e.get("value"))
            if val is not None:
                self._by_value.setdefault((cat, val), []).append(e)

    # -- individual strategies ------------------------------------------------

    def by_part_number(self, pn: Optional[str]) -> Optional[Dict[str, Any]]:
        if not pn:
            return None
        return self._by_pn.get(str(pn).strip().upper())

    def by_lcsc(self, lcsc: Optional[str]) -> Optional[Dict[str, Any]]:
        if not lcsc:
            return None
        return self._by_lcsc.get(str(lcsc).strip().upper())

    def by_part_number_prefix(self, pn: Optional[str],
                              package: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """'ATmega328P' -> 'ATmega328P-PU'.

        Matches when a database part number *starts with* the requested one.

        A bare prefix is often ambiguous: 'ATmega328P' matches both
        'ATmega328P-PU' (DIP-28) and 'ATmega328P-AU' (TQFP-32), which are the
        same silicon in different packages at different prices. When the IR
        specifies a package, it disambiguates them. If the prefix is still
        ambiguous after filtering, return None rather than guessing — picking a
        package the engineer did not ask for would put the wrong part on a
        physical order.
        """
        if not pn:
            return None
        key = str(pn).strip().upper()
        if len(key) < 4:  # too short to be a meaningful prefix
            return None

        hits = [e for k, e in self._by_pn.items() if k.startswith(key)]
        if not hits:
            return None
        if len(hits) == 1:
            return hits[0]

        if package:
            pkg = str(package).strip().upper()
            exact = [e for e in hits
                     if str(e.get("package", "")).strip().upper() == pkg]
            if len(exact) == 1:
                return exact[0]

        return None

    def by_category_value(self, category: str,
                          value: Optional[str]) -> Optional[Dict[str, Any]]:
        """A 10k resistor is a 10k resistor, whatever the manufacturer."""
        if category not in _VALUE_SUBSTITUTABLE:
            return None
        parsed = _parse_value(category, value)
        if parsed is None:
            return None
        hits = self._by_value.get((category, parsed))
        if not hits:
            return None
        # Cheapest equivalent — deterministic tie-break on part number.
        return sorted(hits, key=lambda e: (e.get("unit_price_usd", 0.0),
                                           e.get("part_number", "")))[0]


@lru_cache(maxsize=1)
def load_database(path: str = str(_DB_PATH)) -> ComponentDatabase:
    """Loaded once per process — the file is static in Phase 1."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    entries = data if isinstance(data, list) else list(data.values())
    return ComponentDatabase(entries)


# ── Compiler ─────────────────────────────────────────────────────────────────

class BOMCompiler:
    def __init__(self, db: Optional[ComponentDatabase] = None) -> None:
        self._db = db or load_database()

    def _lookup(self, comp) -> Tuple[Optional[Dict[str, Any]], str]:
        """Returns (database entry or None, price_source label)."""
        hit = self._db.by_part_number(comp.part_number)
        if hit:
            return hit, "part_number"

        hit = self._db.by_lcsc(comp.lcsc_pn)
        if hit:
            return hit, "lcsc_pn"

        hit = self._db.by_part_number_prefix(comp.part_number, comp.package)
        if hit:
            return hit, "part_number_prefix"

        category = comp.type.value if hasattr(comp.type, "value") else str(comp.type)
        hit = self._db.by_category_value(category, comp.value)
        if hit:
            return hit, "equivalent_value"

        return None, "unknown"

    def compile(self, ir: CircuitIR) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        for comp in ir.components:
            entry, source = self._lookup(comp)

            if entry is not None:
                price = float(entry.get("unit_price_usd") or 0.0)
                price_known = entry.get("unit_price_usd") is not None
                # Backfill distributor part numbers the AI left empty — this is
                # what left the LCSC PN column blank in the UI.
                lcsc_pn = comp.lcsc_pn or entry.get("lcsc_pn")
                digikey_pn = comp.digikey_pn or entry.get("digikey_pn")
                matched_pn = entry.get("part_number")
            else:
                price = _UNKNOWN_PRICE
                price_known = False
                lcsc_pn = comp.lcsc_pn
                digikey_pn = comp.digikey_pn
                matched_pn = None

            rows.append({
                "id": comp.id,
                "part_number": comp.part_number,
                "manufacturer": comp.manufacturer,
                "package": comp.package,
                "value": comp.value,
                "quantity": 1,
                "lcsc_pn": lcsc_pn,
                "digikey_pn": digikey_pn,
                "unit_price_usd": price,
                "total_price_usd": price,
                # Pricing provenance — lets the UI show "unknown" rather than
                # presenting an unpriced part as if it were free.
                "price_known": price_known,
                "price_source": source,
                "priced_as": matched_pn if source in ("part_number_prefix",
                                                      "equivalent_value") else None,
                "confidence": comp.confidence,
                "justification": comp.justification,
            })

        return rows

    def total_cost(self, rows: List[Dict[str, Any]]) -> float:
        return round(sum(r["total_price_usd"] for r in rows), 4)

    def pricing_coverage(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """How much of this BOM is actually priced.

        The UI should surface this: a $0.00 total across 9 unpriced components
        is not the same statement as a genuinely free BOM.
        """
        known = sum(1 for r in rows if r["price_known"])
        total = len(rows)
        return {
            "priced": known,
            "total": total,
            "complete": known == total,
            "unpriced_ids": [r["id"] for r in rows if not r["price_known"]],
        }
