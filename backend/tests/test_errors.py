"""Error envelope and exception handler tests."""

from __future__ import annotations

from voiceeval.core.errors import (
    ResourceNotFoundError,
    ValidationError,
    VoiceEvalError,
)


def test_error_envelope_shape():
    err = ResourceNotFoundError("no such evaluator")
    env = err.envelope("req-1")
    assert env["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert env["error"]["message"] == "no such evaluator"
    assert env["error"]["request_id"] == "req-1"


def test_default_code_and_status():
    err = VoiceEvalError("boom")
    assert err.code == "INTERNAL_ERROR"
    assert err.status_code == 500


def test_validation_error_code():
    err = ValidationError("bad input")
    assert err.code == "VALIDATION_ERROR"
    assert err.status_code == 400
