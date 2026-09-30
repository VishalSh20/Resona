"""Observability tests.

Structured logs must carry the execution identifiers (plan/run/attempt) so a
worker or runner line can be correlated; the tracer must produce a usable trace
id and its initialisation must be idempotent.
"""

from __future__ import annotations

import json
import logging

from voiceeval.core.logging import (
    JsonFormatter,
    attempt_id_var,
    bind_execution_context,
    plan_id_var,
    run_id_var,
)
from voiceeval.observability.tracing import current_trace_id, init_tracing, span


def _record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("voiceeval.test", logging.INFO, __file__, 1, message, None, None)


def test_log_includes_execution_identifiers():
    with bind_execution_context(plan_id="plan_1", run_id="run_1", attempt_id="att_1"):
        payload = json.loads(JsonFormatter().format(_record()))
    assert payload["plan_id"] == "plan_1"
    assert payload["run_id"] == "run_1"
    assert payload["attempt_id"] == "att_1"


def test_execution_context_is_restored_after_block():
    with bind_execution_context(plan_id="plan_1"):
        assert plan_id_var.get() == "plan_1"
    assert plan_id_var.get() is None


def test_nested_context_accumulates_and_does_not_clobber():
    with bind_execution_context(plan_id="plan_1"):
        with bind_execution_context(run_id="run_1"):
            assert plan_id_var.get() == "plan_1"
            assert run_id_var.get() == "run_1"
        assert run_id_var.get() is None
        assert plan_id_var.get() == "plan_1"


def test_span_records_a_trace_id_and_clears_after():
    with span("test.span", plan_id="plan_1"):
        assert current_trace_id() is not None
    assert current_trace_id() is None


def test_span_attributes_are_optional():
    # A span with no attributes must not raise.
    with span("test.span"):
        assert True


def test_init_tracing_is_idempotent():
    init_tracing()
    init_tracing()  # must not raise / warn about overriding the provider
    assert current_trace_id() is None or isinstance(current_trace_id(), str)


def test_attempt_id_var_defaults_to_none():
    assert attempt_id_var.get() is None
