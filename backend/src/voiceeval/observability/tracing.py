"""OpenTelemetry wiring.

The provider is configured once per process from ``OTEL_EXPORTER_OTLP_ENDPOINT``
(an OTLP/HTTP exporter) or with a no-op exporter when unset. ``span`` is the
single helper used to annotate the documented execution paths — API requests
(via FastAPI instrumentation), ARQ jobs, orchestrator dispatch, target
connection, caller execution, metric computation, judge invocation and
aggregation — with plan/run/attempt identifiers.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from voiceeval.core.config import get_settings

logger = logging.getLogger("voiceeval.observability")

_initialized = False


def init_tracing() -> None:
    """Configure the tracer provider once per process."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    endpoint = get_settings().otel_exporter_otlp_endpoint
    if not endpoint:
        trace.set_tracer_provider(TracerProvider())
        return

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({SERVICE_NAME: "voiceeval-backend"})
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logger.info("tracing initialised with OTLP exporter at %s", endpoint)


def get_tracer(name: str = "voiceeval"):
    if not _initialized:
        init_tracing()
    return trace.get_tracer(name)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[trace.Span]:
    """Start a span, attaching any non-null attributes.

    The span is a no-op when no exporter is configured, so callers can annotate
    hot paths without paying for a provider in tests.
    """
    with get_tracer().start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current


def current_trace_id() -> str | None:
    """Return the active span's trace id as hex, if a span is recording."""
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


__all__ = ["current_trace_id", "get_tracer", "init_tracing", "span"]
