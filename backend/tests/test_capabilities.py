"""Capability extraction and negotiation tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.services.capabilities import (
    CAPABILITY_MATRIX,
    extract_capabilities,
    negotiate,
)


def _snapshot(**overrides):
    snapshot = {
        "audio": {"caller_ingress": True, "agent_egress": True},
        "transcript": {"target_input": False, "target_output": True, "independent_asr_possible": True},
        "events": {"turn_boundaries": True, "text_stream": True, "interruptions": False, "connection_events": True},
        "tools": {"calls": True, "results": True},
    }
    for key, value in overrides.items():
        section, field = key.split(".")
        snapshot[section][field] = value
    return snapshot


def test_extract_capabilities_flattens_snapshot():
    caps = extract_capabilities(_snapshot())
    assert "caller_audio_ingress" in caps
    assert "agent_audio_egress" in caps
    assert "target_text_stream" in caps
    assert "tool_calls" in caps
    assert "tool_results" in caps
    assert "interruptions" not in caps  # explicitly false


def test_extract_capabilities_rejects_non_object():
    with pytest.raises(ValidationError):
        extract_capabilities("not-a-dict")


def test_required_capability_missing_is_blocking():
    result = negotiate(
        _snapshot(**{"events.text_stream": False}),
        [{"metric": "ttft", "required": True}],
    )
    assert not result.ok
    assert any("ttft" in err for err in result.blocking_errors)


def test_optional_capability_missing_is_warning_not_available():
    result = negotiate(
        _snapshot(**{"events.text_stream": False}),
        [{"metric": "ttft", "required": False}],
    )
    assert result.ok
    assert result.warnings
    assert result.unavailable_metrics == ["ttft"]


def test_unknown_metric_is_blocking():
    result = negotiate(_snapshot(), [{"metric": "does_not_exist", "required": True}])
    assert not result.ok
    assert any("does_not_exist" in err for err in result.blocking_errors)


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_all_documented_metrics_have_a_rule():
    expected = {
        "ttft", "ttfa", "agent_input_wer", "independent_asr_wer",
        "interruption_latency", "tool_selection", "tool_argument_correctness",
        "tool_result_handling", "voice_quality", "language_adaptation",
        "motive_fulfillment",
    }
    assert set(CAPABILITY_MATRIX) == expected
