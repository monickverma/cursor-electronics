"""
The middleware half of §4.5 instrumentation.

It exists so that "every request produces a log row" is a property of the
application rather than a habit of whoever wrote the handler. The context is
created here, enriched by the handler through `request.state.log_ctx`, and
flushed here in a `finally` — so a handler that raises, times out, or returns
early still leaves a row behind.

Outermost by design. Registered after CORS in `main.py`, which in Starlette
makes it the outer wrapper, so it sees rate-limit rejections and unhandled
exceptions too. Those are requests, and a request the system refused is data.
"""

from __future__ import annotations

import time
from typing import Iterable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from observability.request_log import Outcome, RequestLogContext, RequestLogger

# Routes that are not user intent. Logging these buries the signal in
# liveness probes and doc fetches.
_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/favicon")


class RequestLogMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        logger: Optional[RequestLogger] = None,
        skip_prefixes: Iterable[str] = _SKIP_PREFIXES,
    ) -> None:
        super().__init__(app)
        self._logger = logger or RequestLogger()
        self._skip = tuple(skip_prefixes)

    def _should_skip(self, request: Request) -> bool:
        # CORS preflight is a browser mechanic, not a request someone made.
        if request.method == "OPTIONS":
            return True
        return request.url.path.startswith(self._skip)

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._should_skip(request):
            return await call_next(request)

        ctx = RequestLogContext(route=f"{request.method} {request.url.path}")
        request.state.log_ctx = ctx

        started = time.perf_counter()
        try:
            response = await call_next(request)
            ctx.status_code = response.status_code
            # A handler that said nothing about its outcome, but returned 2xx,
            # completed. Anything else stays FAILED — the pessimistic default
            # in RequestLogContext is deliberate.
            if ctx.outcome == Outcome.FAILED and response.status_code < 400:
                ctx.outcome = Outcome.COMPLETED
            return response
        except Exception as exc:
            ctx.outcome = Outcome.FAILED
            ctx.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._flush(ctx, latency_ms)

    async def _flush(self, ctx: RequestLogContext, latency_ms: int) -> None:
        """
        Build and write the row. Row construction can itself raise — the
        validators in RequestLogRow are strict on purpose — and a validation
        error here must not become a 500 on a request that otherwise worked.
        Losing the row is bad; losing the request because of the row is worse.
        """
        try:
            row = ctx.to_row(latency_ms)
        except Exception as exc:
            # The row was inconsistent — a handler set circuit_id without a
            # prompt_hash, or refused without a reason. Record the breakage
            # itself rather than dropping the request silently: a missing row
            # is invisible, a row that says "the instrumentation is wrong" is
            # a bug report.
            ctx.circuit_id = None
            ctx.outcome = Outcome.FAILED
            ctx.refusal_reason = None
            ctx.error = f"log_row_invalid: {type(exc).__name__}: {exc}"
            try:
                row = ctx.to_row(latency_ms)
            except Exception:
                return
        try:
            await self._logger.record(row)
        except Exception:
            pass
