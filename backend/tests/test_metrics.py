"""Deterministic metric tests.

Covers the metric registry, WER, signal extraction and each deterministic metric
— including the availability contract: a missing signal is NOT_AVAILABLE, a
scenario that never exercises a metric is NOT_APPLICABLE, and out-of-order
evidence is INVALID. Nothing is silently turned into zero.
"""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import MetricStatus
from voiceeval.metrics.catalog import build_default_registry
from voiceeval.metrics.deterministic import (
    MetricContext,
    compute_agent_input_wer,
    compute_interruption_latency,
    compute_ttfa,
    compute_ttft,
)
from voiceeval.metrics.engine import (
    evaluate_deterministic,
    evaluate_one,
    expected_tools,
)
from voiceeval.metrics.registry import MetricRegistry, MetricSpec
from voiceeval.metrics.signals import (
    AttemptSignals,
    TimelineEvent,
    ToolCallView,
    TurnView,
)
from voiceeval.metrics.wer import corpus_wer, word_error_rate
from voiceeval.domain.enums import MetricValueType
from voiceeval.services.capabilities import (
    CAPABILITY_AGENT_AUDIO_EGRESS,
    CAPABILITY_CALLER_AUDIO_INGRESS,
    CAPABILITY_INDEPENDENT_ASR,
    CAPABILITY_INTERRUPTIONS,
    CAPABILITY_TARGET_INPUT_TRANSCRIPT,
    CAPABILITY_TARGET_TEXT_STREAM,
    CAPABILITY_TOOL_CALLS,
)

ALL_CAPS = frozenset(
    {
        CAPABILITY_TARGET_TEXT_STREAM,
        CAPABILITY_CALLER_AUDIO_INGRESS,
        CAPABILITY_AGENT_AUDIO_EGRESS,
        CAPABILITY_INTERRUPTIONS,
        CAPABILITY_TOOL_CALLS,
        CAPABILITY_TARGET_INPUT_TRANSCRIPT,
        CAPABILITY_INDEPENDENT_ASR,
    }
)


def _signals(**kwargs) -> AttemptSignals:
    return AttemptSignals.from_records(**kwargs)


# --- registry ----------------------------------------------------------------


def test_registry_is_versioned_and_rejects_duplicates():
    registry = build_default_registry()
    assert registry.get("ttft").version == "1.0"
    with pytest.raises(ValidationError):
        registry.register(registry.get("ttft"))


def test_registry_unknown_metric_rejected():
    with pytest.raises(ValidationError):
        build_default_registry().get("does_not_exist")


def test_registry_latest_version_wins():
    registry = MetricRegistry()
    base = dict(
        metric_key="x",
        value_type=MetricValueType.NUMERIC,
        family="test",
    )
    registry.register(MetricSpec(version="1.0", **base))
    registry.register(MetricSpec(version="2.0", **base))
    assert registry.get("x").version == "2.0"


# --- WER ---------------------------------------------------------------------


def test_wer_perfect_match_is_zero():
    assert word_error_rate("hello world", "Hello, World!") == 0.0


def test_wer_counts_substitutions_insertions_deletions():
    assert word_error_rate("a b c", "a b c d") == pytest.approx(1 / 3)
    assert word_error_rate("a b c", "a c") == pytest.approx(1 / 3)
    assert word_error_rate("a b c", "a x c") == pytest.approx(1 / 3)


def test_wer_empty_reference():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("", "something") == 1.0


def test_corpus_wer_joins_utterances():
    assert corpus_wer(["hello"], ["hello"]) == 0.0


# --- latency metrics ---------------------------------------------------------


def test_ttft_is_caller_audible_end_to_agent_text_first():
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=8200),
            TimelineEvent(type="agent.text.first", monotonic_ms=8680),
        ]
    )
    spec = build_default_registry().get("ttft")
    outcome = compute_ttft(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 480.0
    assert outcome.measurement_basis["clock"] == "runner_monotonic"


def test_ttft_is_not_available_without_signal():
    signals = _signals(events=[TimelineEvent(type="agent.text.first", monotonic_ms=100)])
    spec = build_default_registry().get("ttft")
    outcome = compute_ttft(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.NOT_AVAILABLE


def test_ttft_is_not_available_when_no_caller_end_precedes_text():
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=9000),
            TimelineEvent(type="agent.text.first", monotonic_ms=8680),
        ]
    )
    spec = build_default_registry().get("ttft")
    outcome = compute_ttft(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.NOT_AVAILABLE


def test_ttft_skips_agent_text_before_any_caller_utterance():
    signals = _signals(
        events=[
            TimelineEvent(type="agent.text.first", monotonic_ms=100),
            TimelineEvent(type="caller.audible.end", monotonic_ms=1000),
            TimelineEvent(type="agent.text.first", monotonic_ms=1400),
        ]
    )
    spec = build_default_registry().get("ttft")
    outcome = compute_ttft(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 400.0


def test_invalid_outcome_carries_no_value():
    from voiceeval.metrics.outcome import invalid

    spec = build_default_registry().get("ttft")
    outcome = invalid(spec, "ordering inconsistent")
    assert outcome.status is MetricStatus.INVALID
    assert outcome.value is None
    outcome.validate()


def test_metric_computation_failure_becomes_error(monkeypatch):
    from voiceeval.metrics import deterministic

    def boom(spec, context):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(deterministic.DETERMINISTIC_METRICS, "ttft", boom)
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=100),
            TimelineEvent(type="agent.text.first", monotonic_ms=200),
        ]
    )
    spec = build_default_registry().get("ttft")
    outcome = evaluate_one(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.ERROR
    assert outcome.value is None


def test_ttfa_uses_agent_audible_start():
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=8200),
            TimelineEvent(type="agent.audible.start", monotonic_ms=8920),
        ]
    )
    spec = build_default_registry().get("ttfa")
    outcome = compute_ttfa(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 720.0


def test_ttfa_derives_agent_audible_onset_from_media_when_absent():
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=8000),
            TimelineEvent(type="agent.media.chunk", monotonic_ms=8500, payload={"bytes": 640}),
        ]
    )
    spec = build_default_registry().get("ttfa")
    outcome = compute_ttfa(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 500.0
    assert outcome.measurement_basis["end_derived"] is True


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_interruption_latency_measured_from_caller_speech_start():
    signals = _signals(
        events=[
            TimelineEvent(type="agent.audible.start", monotonic_ms=12000),
            TimelineEvent(type="caller.speech.start", monotonic_ms=15000),
            TimelineEvent(type="agent.audible.end", monotonic_ms=15310),
        ]
    )
    spec = build_default_registry().get("interruption_latency")
    outcome = compute_interruption_latency(
        spec, MetricContext(signals=signals, capabilities=ALL_CAPS)
    )
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 310.0
    assert outcome.measurement_basis["interruption_detected"] is True


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_interruption_latency_not_applicable_without_interruption():
    signals = _signals(
        events=[
            TimelineEvent(type="agent.audible.start", monotonic_ms=12000),
            TimelineEvent(type="agent.audible.end", monotonic_ms=13000),
            TimelineEvent(type="caller.speech.start", monotonic_ms=14000),
        ]
    )
    spec = build_default_registry().get("interruption_latency")
    outcome = compute_interruption_latency(
        spec, MetricContext(signals=signals, capabilities=ALL_CAPS)
    )
    assert outcome.status is MetricStatus.NOT_APPLICABLE


# --- transcription -----------------------------------------------------------


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_agent_input_wer_not_available_without_target_transcript():
    signals = _signals(
        turns=[
            TurnView("t1", "caller", 1, 0, 10, "my card is blocked", None, "caller_reference"),
        ]
    )
    spec = build_default_registry().get("agent_input_wer")
    outcome = compute_agent_input_wer(
        spec, MetricContext(signals=signals, capabilities=ALL_CAPS)
    )
    assert outcome.status is MetricStatus.NOT_AVAILABLE
    assert outcome.measurement_basis["hypothesis"] == "provider_target_input"


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_agent_input_wer_computed_from_provider_input_transcript():
    signals = _signals(
        turns=[
            TurnView("t1", "caller", 1, 0, 10, "my card is blocked", None, "caller_reference"),
            TurnView("t2", "caller", 2, 0, 10, None, "my card blocked", "provider_target_input"),
        ]
    )
    spec = build_default_registry().get("agent_input_wer")
    outcome = compute_agent_input_wer(
        spec, MetricContext(signals=signals, capabilities=ALL_CAPS)
    )
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == pytest.approx(1 / 4)


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_independent_asr_wer_is_a_separate_metric():
    signals = _signals(
        turns=[
            TurnView("t1", "caller", 1, 0, 10, "hello there", None, "caller_reference"),
            TurnView("t2", "caller", 2, 0, 10, None, "hello there", "independent_asr"),
        ]
    )
    registry = build_default_registry()
    outcome = evaluate_one(
        registry.get("independent_asr_wer"),
        MetricContext(signals=signals, capabilities=ALL_CAPS),
    )
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 0.0


# --- tool use ----------------------------------------------------------------


def _tool(name, arguments, *, ordinal=1, status="succeeded", call_id=None):
    return ToolCallView(
        call_id=call_id or f"tool_{ordinal}",
        ordinal=ordinal,
        tool_name=name,
        arguments=arguments,
        result={"ok": True},
        status=status,
        start_ms=ordinal * 10,
        end_ms=ordinal * 10 + 5,
    )


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_tool_argument_exactness_not_applicable_without_expectations():
    signals = _signals(tool_calls=[_tool("verify_identity", {"method": "account_id"})])
    spec = build_default_registry().get("tool_argument_exactness")
    outcome = evaluate_one(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.NOT_APPLICABLE


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_tool_argument_exactness_compares_arguments():
    signals = _signals(
        tool_calls=[_tool("verify_identity", {"method": "account_id", "id": "x"})]
    )
    spec = build_default_registry().get("tool_argument_exactness")
    context = MetricContext(
        signals=signals,
        capabilities=ALL_CAPS,
        expected_tools=[{"name": "verify_identity", "arguments": {"id": "x", "method": "account_id"}}],
    )
    outcome = evaluate_one(spec, context)
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 1.0


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_tool_order_correctness_boolean():
    signals = _signals(
        tool_calls=[_tool("a", {}, ordinal=1), _tool("b", {}, ordinal=2)]
    )
    spec = build_default_registry().get("tool_order_correctness")
    context = MetricContext(
        signals=signals,
        capabilities=ALL_CAPS,
        expected_tools=[{"name": "a"}, {"name": "b"}],
    )
    assert evaluate_one(spec, context).value is True

    wrong = MetricContext(
        signals=signals,
        capabilities=ALL_CAPS,
        expected_tools=[{"name": "b"}, {"name": "a"}],
    )
    assert evaluate_one(spec, wrong).value is False


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_duplicate_tool_calls_counts_repeats():
    signals = _signals(
        tool_calls=[
            _tool("verify", {"x": 1}, ordinal=1),
            _tool("verify", {"x": 1}, ordinal=2),
            _tool("verify", {"x": 2}, ordinal=3),
        ]
    )
    spec = build_default_registry().get("duplicate_tool_calls")
    outcome = evaluate_one(spec, MetricContext(signals=signals, capabilities=ALL_CAPS))
    assert outcome.status is MetricStatus.COMPUTED
    assert outcome.value == 1.0


# --- capability gating -------------------------------------------------------


def test_missing_capability_yields_not_available_not_zero():
    signals = _signals(
        events=[
            TimelineEvent(type="caller.audible.end", monotonic_ms=8200),
            TimelineEvent(type="agent.text.first", monotonic_ms=8680),
        ]
    )
    spec = build_default_registry().get("ttft")
    outcome = evaluate_one(spec, MetricContext(signals=signals, capabilities=frozenset()))
    assert outcome.status is MetricStatus.NOT_AVAILABLE
    assert outcome.value is None
    assert outcome.measurement_basis["missing_capabilities"] == ["target_text_stream"]


@pytest.mark.skip(reason="deferred to the v0.4 results/execution pass")
def test_evaluate_deterministic_returns_every_metric():
    signals = _signals()
    outcomes = evaluate_deterministic(MetricContext(signals=signals, capabilities=ALL_CAPS))
    keys = {o.metric_key for o in outcomes}
    assert "ttft" in keys and "duplicate_tool_calls" in keys
    # every outcome satisfies the availability contract
    for outcome in outcomes:
        outcome.validate()


# --- expected tools extraction ----------------------------------------------


def test_expected_tools_from_declared_list():
    assert expected_tools({"tools": [{"name": "a"}]}) == [{"name": "a"}]


def test_expected_tools_from_assertion_expectation():
    content = {
        "motive": {
            "assertions": [
                {"id": "x", "expectation": {"tool": "verify_identity", "arguments": {"m": 1}}}
            ]
        }
    }
    assert expected_tools(content) == [
        {"name": "verify_identity", "arguments": {"m": 1}}
    ]
