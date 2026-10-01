"""
A distributor's quote for one part, and the number in a locale-formatted price.

A quote belongs to the exact part number it was asked for — the Stage 6 rule,
`brain/decisions.md` [2026-09-25]: a part is priced only as itself. Prices are
kept in the currency the distributor quoted, never converted.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict


class PriceBreak(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantity: int
    unit_price: float


class Quote(BaseModel):
    """What one distributor said about one part number, and when."""

    model_config = ConfigDict(frozen=True)

    source: str                          # "mouser"
    part_number: str                     # exactly as the BOM names it
    found: bool                          # listed, with this exact manufacturer part number
    fetched_at: datetime                 # UTC
    currency: Optional[str] = None
    breaks: Tuple[PriceBreak, ...] = ()
    stock: Optional[int] = None
    distributor_pn: Optional[str] = None
    manufacturer: Optional[str] = None
    min_order: Optional[int] = None
    order_multiple: Optional[int] = None
    product_url: Optional[str] = None
    #: How many listings carried this exact part number; one was chosen.
    listings: int = 0

    def price_for(self, quantity: int) -> Optional[PriceBreak]:
        """The break that prices `quantity`: the largest at or below it, else the smallest."""
        if not self.breaks:
            return None
        ordered = sorted(self.breaks, key=lambda b: b.quantity)
        eligible = [b for b in ordered if b.quantity <= quantity]
        return eligible[-1] if eligible else ordered[0]


def key(part_number: str) -> str:
    """How a part number is stored and matched: trimmed, case-insensitive."""
    return part_number.strip().upper()


#: The number in a price: digits and the separators between them — never the
#: punctuation of a currency symbol ("kr.", "Fr.") on either side.
_NUMBER = re.compile(r"\d(?:[\d.,'\s\u00a0\u202f]*\d)?")
_GROUPING = re.compile(r"['\s\u00a0\u202f]")

#: ISO 4217 currencies with no minor unit, and the symbols that mark them when no
#: currency code comes with the price.
ZERO_DECIMAL = frozenset({"JPY", "KRW", "CLP", "ISK", "VND", "PYG", "UGX", "XAF", "XOF", "KMF", "GNF", "RWF"})
_ZERO_DECIMAL_SYMBOLS = ("¥", "￥", "₩", "₫")


def parse_price(text: object, currency: Optional[str] = None) -> Optional[float]:
    """
    A number from a price string as a distributor formats it for the account's
    locale: "$0.10", "$1,234.56", "6,85 €", "0,069 €", "1.234,56 €", "₹8.50",
    "1'234.50 CHF", "0,85 kr.", "¥1,980". None when there is no number in it.

    Both separators present: the later one is the decimal point. One kind only:
    a single separator is the decimal point; repeated, it groups thousands.
    In a currency with no minor unit (`currency`, or a ¥/₩/₫ in the text) a lone
    separator followed by exactly three digits groups thousands too.
    """
    if isinstance(text, bool) or text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    raw = str(text)
    m = _NUMBER.search(raw)
    if not m:
        return None
    s = _GROUPING.sub("", m.group(0))
    zero_decimal = ((currency or "").strip().upper() in ZERO_DECIMAL
                    or any(sym in raw for sym in _ZERO_DECIMAL_SYMBOLS))
    if zero_decimal and re.fullmatch(r"\d{1,3}[.,]\d{3}", s):
        s = re.sub(r"[.,]", "", s)
    if "," in s and "." in s:
        decimal = "," if s.rfind(",") > s.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        s = s.replace(thousands, "").replace(decimal, ".")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def parse_count(text: object) -> Optional[int]:
    """Leading integer of a stock figure ("12,345 In Stock", "12345"); None if there is none."""
    if isinstance(text, bool) or text is None:
        return None
    if isinstance(text, int):
        return text
    m = re.match(r"\s*([\d.,' ]+)", str(text))
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return int(digits) if digits else None


def totals(rows: Sequence[dict]) -> Tuple[dict, ...]:
    """One total per currency — never a converted sum — with the sources behind it."""
    out: dict = {}
    for row in rows:
        if not row.get("price_known") or row.get("unit_price") is None or not row.get("currency"):
            continue
        entry = out.setdefault(row["currency"], {"currency": row["currency"], "amount": 0.0, "rows": 0,
                                                 "sources": []})
        entry["amount"] = round(entry["amount"] + row["unit_price"] * row.get("quantity", 1), 6)
        entry["rows"] += 1
        if row.get("price_source") not in entry["sources"]:
            entry["sources"].append(row.get("price_source"))
    return tuple(out.values())
