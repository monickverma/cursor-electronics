"""POST /pcb/compile — PCB netlist in, routed board + SVG out.

The engine used to run as a separate process (``compile_board.py --serve 8001``)
that the browser called directly. That cannot work in a deployed environment:
the frontend fell back to ``http://localhost:8001``, which in a visitor's
browser means *their* machine, and an ``http://`` call from an HTTPS page is
blocked as mixed content anyway. Folding it into the API removes the extra
service, the CORS surface, and the mixed-content problem in one move.

``compile_board`` is synchronous and CPU-bound (A* routing over several
candidate placements), so it runs in a threadpool. Calling it directly in an
``async def`` would block the event loop for every other request — the same
mistake the simulation pipeline avoids by using Celery.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from api.routes.auth import get_current_user
from core.config import settings
from middleware.rate_limit import limiter
from pcb_engine import compile_board

router = APIRouter()

# A board with more parts than this is out of Phase 1 scope, and the router's
# candidate search grows badly with pad count. Reject early with a clear
# message rather than tying up a worker thread for minutes.
_MAX_COMPONENTS = 40


class CompileRequest(BaseModel):
    """The ``pcb_netlist`` object produced by PcbNetlistGenerator.

    Accepts the netlist shape as-is rather than re-modelling it, so the
    contract stays owned by the generator on the other side.
    """

    name: Optional[str] = None
    board: Optional[dict] = None
    ground_net: Optional[str] = None
    power_nets: Optional[list] = None
    components: list[dict] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class CompileResponse(BaseModel):
    svg: str
    stats: dict
    warnings: list[str]
    violations: list[str]


@router.post("/compile", response_model=CompileResponse)
@limiter.limit("60/hour")
async def compile_pcb(
    request: Request,
    body: CompileRequest,
    user=Depends(get_current_user),
):
    if not settings.pcb_engine_enabled:
        # 501, not 404: the endpoint exists and the client is not at fault —
        # this build simply does not offer it. 404 would read as a wrong URL
        # and send the caller looking for a typo.
        raise HTTPException(
            501,
            detail="PCB layout is experimental and disabled in this build.",
        )

    netlist: dict[str, Any] = body.model_dump(exclude_none=True)

    if not netlist.get("components"):
        raise HTTPException(422, detail="Netlist contains no components.")
    if len(netlist["components"]) > _MAX_COMPONENTS:
        raise HTTPException(
            422,
            detail=(
                f"Netlist has {len(netlist['components'])} components; "
                f"the Phase 1 layout engine handles up to {_MAX_COMPONENTS}."
            ),
        )

    try:
        result = await run_in_threadpool(compile_board, netlist)
    except KeyError as exc:
        # from_netlist raises KeyError for a missing required field, e.g. a
        # component with no "ref". That is a bad request, not a server fault.
        raise HTTPException(422, detail=f"Malformed netlist: missing {exc}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, detail=f"PCB compilation failed: {type(exc).__name__}: {exc}")

    return CompileResponse(
        svg=result.svg,
        stats=result.stats,
        warnings=result.warnings,
        violations=result.violations,
    )
