"""Structured JSON logging.

Every log record carries: timestamp, level, logger, message, request_id,
trace_id and the execution identifiers plan_id/run_id/attempt_id. All of them
are read from contextvars so they can be populated by middleware, worker jobs
and the orchestrator without threading them through every function signature.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
plan_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "plan_id", default=None
)
run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "run_id", default=None
)
attempt_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "attempt_id", default=None
)

_LOG_CONTEXT_VARS = {
    "request_id": request_id_var,
    "trace_id": trace_id_var,
    "plan_id": plan_id_var,
    "run_id": run_id_var,
    "attempt_id": attempt_id_var,
}


@contextmanager
def bind_execution_context(
    *,
    plan_id: str | None = None,
    run_id: str | None = None,
    attempt_id: str | None = None,
) -> Iterator[None]:
    """Bind execution identifiers to the log context for the enclosed block.

    Only fields that are explicitly provided are overwritten, so nested scopes
    (plan -> run -> attempt) accumulate correlation ids.
    """
    provided = {
        "plan_id": plan_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
    }
    tokens = [
        (_LOG_CONTEXT_VARS[name], _LOG_CONTEXT_VARS[name].set(value))
        for name, value in provided.items()
        if value is not None
    ]
    try:
        yield
    finally:
        for var, token in tokens:
            var.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
            "plan_id": plan_id_var.get(),
            "run_id": run_id_var.get(),
            "attempt_id": attempt_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid double-emitting by clearing existing handlers first.
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # uvicorn's own loggers inherit our root config.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
