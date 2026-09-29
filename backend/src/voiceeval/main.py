"""FastAPI application entrypoint.

Wires request-id middleware, global exception handling and the health/ready
routes. Domain routes are added by later prompts; this module remains the
single place the ASGI server imports.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from voiceeval.core.errors import VoiceEvalError
from voiceeval.core.logging import configure_logging, request_id_var, trace_id_var
from voiceeval.api.router import api_router
from voiceeval.observability.tracing import current_trace_id, init_tracing, span
from voiceeval.realtime.pubsub import RedisPubSub, set_pubsub
from voiceeval.realtime.routes import internal_router, live_router

configure_logging()
init_tracing()
logger = logging.getLogger("voiceeval")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Install the real Redis-backed pub/sub for live plan observation. Tests and
    # workers that do not run this lifespan keep the no-op implementation.
    set_pubsub(RedisPubSub())
    yield


app = FastAPI(title="VoiceEval Backend", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # Bind the request id so every log line and span in this request carries it.
    request_id_var.set(request_id)
    with span("api.request", request_id=request_id):
        # Prefer the real OTel trace id; fall back to an upstream ``X-Trace-ID``
        # header (for cross-service correlation) or the request id.
        trace_id = (
            current_trace_id()
            or request.headers.get("X-Trace-ID")
            or request_id
        )
        trace_id_var.set(trace_id)
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@app.exception_handler(VoiceEvalError)
async def voiceeval_error_handler(request: Request, exc: VoiceEvalError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.envelope(request_id),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "internal server error",
                "request_id": request_id,
            }
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Process liveness — no external dependencies required."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness — verifies control-plane dependencies (Postgres, Redis)."""
    from voiceeval.core.config import get_settings
    from voiceeval.db.session import get_engine
    from voiceeval.api.dependencies import redis_available

    s = get_settings()

    postgres_ok = True
    try:
        async with get_engine().connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    except Exception:  # pragma: no cover - depends on live infra
        postgres_ok = False

    redis_ok = await redis_available()

    ok = postgres_ok and redis_ok
    status = "ok" if ok else "not_ready"
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": status,
            "checks": {
                "postgres": "ok" if postgres_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
                "object_storage": s.object_storage_mode,
            },
        },
    )


app.include_router(api_router)

# Runner control/telemetry WebSocket. Must be mounted at the app root so the
# path matches ``runtime.telemetry.build_stream_url`` exactly:
# ``/internal/v1/attempts/{attempt_id}/stream``.
app.include_router(internal_router)

# Browser live-observation WebSocket for a run:
# ``/api/v1/runs/{run_id}/live``.
app.include_router(live_router)
