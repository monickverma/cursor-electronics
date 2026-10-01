"""
`GET /design/{id}/bom` — the bill of materials and each line's checked substitutes.

Stage 6, `brain/decisions.md` [2026-09-25]. A row is priced only as the exact
part it names, with the date the price was recorded — or, when `MOUSER_API_KEY`
is set, with a live Mouser quote for that exact part number and the time it
was fetched (`pricing/live.py`; cached in PostgreSQL). A substitute is offered
only after it passed every check the original passed
(`generators/bom/substitution.py`), with the patch that applies it — accepting
one is `POST /design/{id}/patch` with those `ops`: zero model calls, a new
version, the design re-derived, and a signed design signed again.

No `from __future__ import annotations` here: slowapi wraps the endpoint, and
the pinned FastAPI resolves string annotations against the wrapper's module
(the CI failure fixed in e803a99).
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_user
from core.config import settings
from core.intent_ir import IntentIR
from core.ir_schema import CircuitIR
from db.crud import get_design
from db.models import get_db
from generators.bom.compiler import BOMCompiler, price_index
from generators.bom.substitution import substitutes
from generators.realize import generator_tag
from generators.registry import default_registry
from middleware.rate_limit import limiter
from pricing.live import price_view
from pricing.quotes import totals

router = APIRouter()

PRICING = "Static prices from the parts catalogue, each with the date it was recorded."


def bom_view(design: Any) -> Dict[str, Any]:
    """The BOM of a stored design, and its substitutes when they can be checked."""
    current = CircuitIR.model_validate(design.ir_json)
    compiler = BOMCompiler()
    rows = compiler.compile(current)
    view: Dict[str, Any] = {
        "circuit_id": current.circuit_id,
        "version": current.version,
        "rows": rows,
        # The static catalogue total, in USD; `totals` is what the rows show, per currency.
        "total_usd": compiler.total_cost(rows),
        "totals": list(totals(rows)),
        "coverage": compiler.pricing_coverage(rows),
        "pricing": PRICING,
        "substitutes": [],
        "rejected": [],
        "substitutes_unavailable": None,
    }
    if design.intent_ir is None:
        view["substitutes_unavailable"] = ("This design predates requirement patching, so a substitute "
                                           "cannot be re-derived through the gate. Generate it again.")
        return view
    name = (current.generator or "").split("@")[0]
    generator = default_registry().by_name(name) if name else None
    if generator is None or generator_tag(generator) != current.generator:
        view["substitutes_unavailable"] = (f"This design was built by {current.generator}; the installed generator "
                                           f"is {generator_tag(generator) if generator else 'missing'}. Patch "
                                           f"the design first, then its substitutes can be checked.")
        return view
    found, rejected = substitutes(generator, IntentIR.model_validate(design.intent_ir), current, price_index())
    view["substitutes"] = [s.model_dump(mode="json") for s in found]
    view["rejected"] = [r.model_dump(mode="json") for r in rejected]
    return view


@router.get("/{circuit_id}/bom")
@limiter.limit("60/hour")
async def get_bom(
    request: Request,
    circuit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),
):
    design = await get_design(db, circuit_id)
    if not design:
        raise HTTPException(404, detail="Design not found")
    if str(design.user_id) != str(user.id):
        raise HTTPException(403, detail="Access denied")
    # Each candidate is re-derived and re-proved: seconds of work, off the event loop.
    view = await run_in_threadpool(bom_view, design)
    # Live prices over it, when a key is set; a failure leaves the static prices and says why.
    return await price_view(db, view, api_key=settings.mouser_api_key, cache_hours=settings.price_cache_hours)
