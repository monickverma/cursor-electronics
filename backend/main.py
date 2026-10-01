from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.routes import auth, bom, design, firmware, patch, pcb, simulate
from core.config import settings
from middleware.instrumentation import RequestLogMiddleware
from middleware.rate_limit import limiter


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(int(retry_after))} if retry_after else {}
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Try again later."},
        headers=headers,
    )


def sentry_options() -> dict:
    """
    Sentry, without the Mouser key. Mouser takes the key in the query string,
    and Sentry's httpx integration records the query on every outgoing span and
    breadcrumb — so it is off, and every event, transaction and breadcrumb is
    scrubbed besides ([2026-10-01] #1).
    """
    from sentry_sdk.integrations.httpx import HttpxIntegration

    from pricing.mouser import scrub

    return dict(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        disabled_integrations=[HttpxIntegration()],
        before_send=lambda event, hint: scrub(event),
        before_send_transaction=lambda event, hint: scrub(event),
        before_breadcrumb=lambda crumb, hint: scrub(crumb),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.sentry_dsn:
        sentry_sdk.init(**sentry_options())
    # schema.sql only runs on an empty volume; columns added since then come
    # from here. Never raises — see db/migrations.py.
    from db.migrations import apply_migrations
    from db.models import engine

    await apply_migrations(engine)
    yield


app = FastAPI(
    title="Circuit OS API",
    version="0.1.0",
    description="AI hardware compiler — natural language to validated circuit design",
    lifespan=lifespan,
)

# Rate limiter state must be attached before SlowAPIMiddleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last, so it is the outermost wrapper and sees every request — including
# rate-limit rejections and unhandled exceptions. PHASE_2_PLAN_v2.md §4.5:
# a request the system refused is data, not noise.
app.add_middleware(RequestLogMiddleware)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(design.router, prefix="/design", tags=["design"])
app.include_router(simulate.router, prefix="/design", tags=["simulation"])
app.include_router(patch.router, prefix="/design", tags=["patch"])
app.include_router(firmware.router, prefix="/design", tags=["firmware"])
app.include_router(bom.router, prefix="/design", tags=["bom"])
app.include_router(pcb.router, prefix="/pcb", tags=["pcb"])


@app.get("/health")
async def health():
    # pcb_engine_enabled is here so the frontend can hide the PCB tab rather
    # than render a tab whose every click returns 501. Unauthenticated by
    # design: it reveals nothing a caller could not learn by hitting
    # /pcb/compile, and the tab list is decided before login.
    return {
        "status": "ok",
        "environment": settings.environment,
        "pcb_engine_enabled": settings.pcb_engine_enabled,
    }
