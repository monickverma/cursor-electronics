"""GET /parts — search the component catalogue as someone types.

The catalogue is data/component_db.json, read once. This is a lookup and
nothing more: no model is called, no price is fetched, and finding a part here
puts it in no design. A part enters a design only through the requirement
(`constraints.pinned`), re-derived and re-proved like any other change.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from api.routes.auth import get_current_user
from middleware.rate_limit import limiter

router = APIRouter()

_DB = Path(__file__).resolve().parents[2] / "data" / "component_db.json"
#: What a search reads. A value like "10k" or a package like "0402" is as good a query as a part number.
_SEARCHED = ("part_number", "description", "manufacturer", "category", "value", "package")
_SHOWN = ("part_number", "manufacturer", "category", "package", "value", "description",
          "supply_voltage_min", "supply_voltage_max", "current_draw_ma",
          "unit_price_usd", "price_asof", "price_source", "lcsc_pn", "digikey_pn")
MAX_RESULTS = 25


@lru_cache(maxsize=1)
def catalogue() -> tuple[dict, ...]:
    return tuple(json.loads(_DB.read_text(encoding="utf-8")))


def search(query: str, category: Optional[str] = None, limit: int = MAX_RESULTS) -> list[dict]:
    """Parts whose searched fields contain every word of the query, part-number matches first."""
    words = [w for w in query.lower().split() if w]
    wanted = (category or "").strip().lower()
    hits: list[tuple[int, int, dict]] = []
    for order, part in enumerate(catalogue()):
        if wanted and str(part.get("category", "")).lower() != wanted:
            continue
        haystack = " ".join(str(part.get(k) or "") for k in _SEARCHED).lower()
        if not all(w in haystack for w in words):
            continue
        number = str(part.get("part_number", "")).lower()
        rank = 0 if words and number.startswith(words[0]) else 1 if words and words[0] in number else 2
        hits.append((rank, order, part))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [{k: part.get(k) for k in _SHOWN} for _, _, part in hits[:max(1, min(limit, MAX_RESULTS))]]


@router.get("")
@limiter.limit("600/hour")
async def find_parts(
    request: Request,
    q: Annotated[str, Query(max_length=80)] = "",
    category: Annotated[Optional[str], Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS)] = 12,
    user=Depends(get_current_user),
):
    results = search(q, category, limit)
    return {
        "query": q,
        "results": results,
        "catalogue_size": len(catalogue()),
        "categories": sorted({str(p.get("category")) for p in catalogue() if p.get("category")}),
    }
