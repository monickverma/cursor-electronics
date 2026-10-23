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
from pcb_engine import compile_board, kicad_package

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
    # The KiCad project, KiCad DRC, read-back and fab files (pcb_engine/kicad_fab.py).
    # On by default; it adds a few seconds of kicad-cli to the request.
    kicad: bool = True

    model_config = {"extra": "allow"}


class CompileResponse(BaseModel):
    svg: str
    stats: dict
    warnings: list[str]
    violations: list[str]
    # The independent verification report (pcb_engine/verify.py): every check,
    # the rung it stands on, and whether generation should emit or refuse.
    # decisions.md [2026-10-09].
    verification: dict = Field(default_factory=dict)
    # The routed Board IR (pcb_engine/board_ir.py) — the source of truth — and
    # the 3D scene derived from it (pcb_engine/scene3d.py). decisions.md [2026-10-06].
    board: dict
    scene: dict
    # The board as KiCad sees it, so anyone can open it and run KiCad's own DRC
    # (finding F-S2-R001-4): `kicad_pcb` / `kicad_pro` / `kicad_dru` text, KiCad's
    # DRC and the Gerber read-back verdicts, and `fab.files` — Gerber, drill,
    # position, IPC-D-356 and a hashed manifest. Owner decision 2026-10-17: a
    # failed board is still returned, but `fab.files` is empty and
    # `fab.refusals` says why.
    kicad: dict = Field(default_factory=dict)


@router.post("/compile", response_model=CompileResponse)
@limiter.limit(settings.rate_limit_pcb)
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
    want_kicad = netlist.pop("kicad", True)

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

    out = result.to_dict()
    kicad: dict = {}
    if want_kicad:
        try:
            kicad = await run_in_threadpool(kicad_package, result.board,
                                            out.get("verification"), result.board.name)
        except Exception as exc:  # noqa: BLE001
            # The board is still shown; only the KiCad side failed, and says so.
            kicad = {"available": False, "error": f"{type(exc).__name__}: {exc}",
                     "fab": {"ok": False, "files": {},
                             "refusals": [f"KiCad export failed: {type(exc).__name__}"]}}
    return CompileResponse(
        svg=out["svg"],
        stats=out["stats"],
        warnings=out["warnings"],
        violations=out["violations"],
        verification=out.get("verification", {}),
        board=out["board"],
        scene=out["scene"],
        kicad=kicad,
    )
