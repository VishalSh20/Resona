"""Deterministic metric implementations.

These metrics are computed from observed truth alone — no model call, no
judgement. Each implementation returns a :class:`MetricOutcome` whose status
honours the availability contract: if the required signal was not observed the
metric is ``NOT_AVAILABLE`` (never zero), if the scenario does not exercise the
metric it is ``NOT_APPLICABLE``, and if observed evidence is self-inconsistent
(e.g. timestamps out of order) it is ``INVALID``.

Latency metrics use the runner monotonic clock explicitly; the clock domain and
the boundary events are recorded in the measurement basis.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from voiceeval.metrics.outcome import (
    EvidenceSpec,
    MetricOutcome,
    computed,
    not_applicable,
    not_available,
)
from voiceeval.metrics.registry import MetricSpec
from voiceeval.metrics.signals import CLOCK_RUNNER_MONOTONIC, AttemptSignals
from voiceeval.metrics.wer import corpus_wer
from voiceeval.runtime.events import EventType


@dataclass
class MetricContext:
    """Everything a deterministic metric may read for one attempt."""

    signals: AttemptSignals
    capabilities: frozenset[str] = frozenset()
    expected_tools: list[dict[str, Any]] = field(default_factory=list)
    evaluator_content: dict[str, Any] = field(default_factory=dict)


def _event_evidence(
    event: Any | None, *, rationale: str, quote: str | None = None
) -> EvidenceSpec | None:
    if event is None or getattr(event, "event_id", None) is None:
        return None
    return EvidenceSpec(
        source_type="event",
        source_id=event.event_id,
        start_ms=getattr(event, "monotonic_ms", None),
        end_ms=getattr(event, "monotonic_ms", None),
        quote=quote,
        rationale=rationale,
    )


def _normalize_arguments(arguments: dict[str, Any] | None) -> str:
    if not arguments:
        return "{}"
    return json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)


# -- latency ----------------------------------------------------------------


def compute_ttft(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    signals = context.signals
    basis: dict[str, Any] = {
        "start_event": EventType.CALLER_AUDIBLE_END.value,
        "end_event": EventType.AGENT_TEXT_FIRST.value,
        "clock": CLOCK_RUNNER_MONOTONIC,
    }
    text_events = signals.by_type(EventType.AGENT_TEXT_FIRST)
    if not text_events:
        return not_available(
            spec, "target text stream was not observed", measurement_basis=basis
        )
    end_points = signals.caller_audible_end_points()
    if not end_points:
        return not_available(
            spec, "caller audibility was not observed", measurement_basis=basis
        )
    for event in text_events:
        preceding = [point for point in end_points if point[0] <= event.monotonic_ms]
        if not preceding:
            continue
        start_ms, derived = max(preceding, key=lambda point: point[0])
        basis["start_derived"] = derived
        evidence = [
            item
            for item in (
                _event_evidence(event, rationale="first target text token"),
                _event_evidence(
                    signals.last(EventType.CALLER_AUDIBLE_END),
                    rationale="end of caller audibility",
                ),
            )
            if item is not None
        ]
        return computed(
            spec,
            float(event.monotonic_ms - start_ms),
            measurement_basis=basis,
            evidence=evidence,
        )
    return not_available(
        spec,
        "no caller.audible.end precedes agent.text.first",
        measurement_basis=basis,
    )


def compute_ttfa(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    signals = context.signals
    basis: dict[str, Any] = {
        "start_event": EventType.CALLER_AUDIBLE_END.value,
        "end_event": EventType.AGENT_AUDIBLE_START.value,
        "clock": CLOCK_RUNNER_MONOTONIC,
    }
    windows = signals.agent_audible_windows()
    if not windows:
        return not_available(
            spec,
            "agent audible onset was not observed",
            measurement_basis=basis,
        )
    ends = signals.caller_audible_end_points()
    if not ends:
        return not_available(
            spec,
            "caller audibility was not observed",
            measurement_basis=basis,
        )
    window = next(
        (
            (start, end, derived)
            for start, end, derived in windows
            if any(point[0] <= start for point in ends)
        ),
        None,
    )
    if window is None:
        return not_available(
            spec,
            "no caller.audible.end precedes an agent audible onset",
            measurement_basis=basis,
        )
    start_ms, _end_ms, end_derived = window
    start_point = max(
        (point for point in ends if point[0] <= start_ms), key=lambda point: point[0]
    )
    basis["start_derived"] = start_point[1]
    basis["end_derived"] = end_derived
    evidence = [
        item
        for item in (
            _event_evidence(
                signals.first(EventType.AGENT_AUDIBLE_START)
                or signals.first(EventType.AGENT_MEDIA_CHUNK),
                rationale="agent audible onset",
            ),
            _event_evidence(
                signals.last(EventType.CALLER_AUDIBLE_END),
                rationale="end of caller audibility",
            ),
        )
        if item is not None
    ]
    return computed(
        spec,
        float(start_ms - start_point[0]),
        measurement_basis=basis,
        evidence=evidence,
    )


def compute_interruption_latency(
    spec: MetricSpec, context: MetricContext
) -> MetricOutcome:
    signals = context.signals
    basis: dict[str, Any] = {
        "start_event": EventType.CALLER_SPEECH_START.value,
        "end_event": EventType.AGENT_AUDIBLE_END.value,
        "clock": CLOCK_RUNNER_MONOTONIC,
    }
    windows = signals.agent_audible_windows()
    valid_windows = [
        (start, end, derived)
        for start, end, derived in windows
        if end > start
    ]
    if not valid_windows:
        return not_available(
            spec,
            "no complete agent audibility window was observed",
            measurement_basis=basis,
        )
    onsets = signals.caller_speech_start_times()
    for start_ms, end_ms, _derived in valid_windows:
        interruptions = [onset for onset in onsets if start_ms < onset < end_ms]
        if not interruptions:
            continue
        onset = interruptions[0]
        basis["interruption_detected"] = True
        basis["agent_stopped"] = end_ms >= onset
        basis["caller_continued"] = True
        evidence = [
            item
            for item in (
                _event_evidence(
                    signals.first(EventType.CALLER_SPEECH_START),
                    rationale="caller began speaking over the agent",
                ),
                _event_evidence(
                    signals.last(EventType.AGENT_AUDIBLE_END),
                    rationale="agent audio ended after the interruption",
                ),
            )
            if item is not None
        ]
        return computed(
            spec,
            float(end_ms - onset),
            measurement_basis=basis,
            evidence=evidence,
        )
    return not_applicable(
        spec,
        "the caller did not interrupt the agent in this attempt",
        measurement_basis=basis,
    )


def compute_turn_duration(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    durations = context.signals.turn_durations_ms()
    if not durations:
        return not_available(spec, "no turn boundaries were materialized")
    basis = {
        "clock": CLOCK_RUNNER_MONOTONIC,
        "turn_count": len(durations),
        "aggregation": "mean",
    }
    return computed(
        spec,
        float(sum(durations) / len(durations)),
        measurement_basis=basis,
    )


def compute_call_duration(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    span = context.signals.span_ms()
    if span is None:
        return not_available(spec, "attempt has no measurable event window")
    return computed(
        spec,
        float(span),
        measurement_basis={"clock": CLOCK_RUNNER_MONOTONIC, "event_count": len(context.signals.events)},
    )


# -- transcription ----------------------------------------------------------


def _wer_outcome(
    spec: MetricSpec,
    *,
    references: list[str],
    hypotheses: list[str],
    reference_provenance: str,
    hypothesis_provenance: str,
) -> MetricOutcome:
    basis = {
        "reference": reference_provenance,
        "hypothesis": hypothesis_provenance,
    }
    if not references:
        return not_available(spec, "no caller reference text was recorded", measurement_basis=basis)
    if not hypotheses:
        return not_available(
            spec,
            f"no '{hypothesis_provenance}' transcript was exposed",
            measurement_basis=basis,
        )
    value = corpus_wer(references, hypotheses)
    basis["reference_utterances"] = len(references)
    basis["hypothesis_utterances"] = len(hypotheses)
    return computed(spec, float(value), measurement_basis=basis)


def compute_agent_input_wer(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    return _wer_outcome(
        spec,
        references=context.signals.caller_reference_texts(),
        hypotheses=context.signals.provider_target_input_texts(),
        reference_provenance="caller_reference",
        hypothesis_provenance="provider_target_input",
    )


def compute_independent_asr_wer(
    spec: MetricSpec, context: MetricContext
) -> MetricOutcome:
    return _wer_outcome(
        spec,
        references=context.signals.caller_reference_texts(),
        hypotheses=context.signals.independent_asr_texts(),
        reference_provenance="caller_reference",
        hypothesis_provenance="independent_asr",
    )


# -- tool use ---------------------------------------------------------------


def compute_tool_argument_exactness(
    spec: MetricSpec, context: MetricContext
) -> MetricOutcome:
    expected = context.expected_tools
    if not expected:
        return not_applicable(spec, "the evaluator defines no expected tool calls")
    actual = context.signals.tool_calls
    exact = 0
    evidence: list[EvidenceSpec] = []
    for expectation in expected:
        name = expectation.get("name") or expectation.get("tool_name")
        wanted = expectation.get("arguments") or {}
        match = next((call for call in actual if call.tool_name == name), None)
        if match is None:
            continue
        if _normalize_arguments(match.arguments) == _normalize_arguments(wanted):
            exact += 1
        if match.call_id:
            evidence.append(
                EvidenceSpec(
                    source_type="tool_call",
                    source_id=match.call_id,
                    start_ms=match.start_ms,
                    end_ms=match.end_ms,
                    rationale=f"tool '{name}' arguments compared to expectation",
                )
            )
    basis = {"expected_tools": len(expected), "actual_tools": len(actual)}
    return computed(
        spec,
        exact / len(expected),
        measurement_basis=basis,
        evidence=evidence,
    )


def compute_tool_order_correctness(
    spec: MetricSpec, context: MetricContext
) -> MetricOutcome:
    expected_names = [
        str(item.get("name") or item.get("tool_name"))
        for item in context.expected_tools
        if item.get("name") or item.get("tool_name")
    ]
    if len(expected_names) < 2:
        return not_applicable(
            spec, "ordering requires at least two expected tool calls"
        )
    expected_set = set(expected_names)
    actual_names = [call.tool_name for call in context.signals.tool_calls]
    relevant_actual = [name for name in actual_names if name in expected_set]
    basis = {"expected_order": expected_names, "actual_order": relevant_actual}
    return computed(spec, relevant_actual == expected_names, measurement_basis=basis)


def compute_duplicate_tool_calls(
    spec: MetricSpec, context: MetricContext
) -> MetricOutcome:
    actual = context.signals.tool_calls
    seen: dict[tuple[str, str], int] = {}
    duplicates = 0
    evidence: list[EvidenceSpec] = []
    for call in actual:
        key = (call.tool_name, _normalize_arguments(call.arguments))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1 and call.call_id:
            duplicates += 1
            evidence.append(
                EvidenceSpec(
                    source_type="tool_call",
                    source_id=call.call_id,
                    start_ms=call.start_ms,
                    end_ms=call.end_ms,
                    rationale=f"repeated call to '{call.tool_name}'",
                )
            )
    basis = {"total_tool_calls": len(actual)}
    return computed(
        spec,
        float(duplicates),
        measurement_basis=basis,
        evidence=evidence,
    )


DETERMINISTIC_METRICS: dict[str, Callable[[MetricSpec, MetricContext], MetricOutcome]] = {
    "ttft": compute_ttft,
    "ttfa": compute_ttfa,
    "interruption_latency": compute_interruption_latency,
    "turn_duration": compute_turn_duration,
    "call_duration": compute_call_duration,
    "agent_input_wer": compute_agent_input_wer,
    "independent_asr_wer": compute_independent_asr_wer,
    "tool_argument_exactness": compute_tool_argument_exactness,
    "tool_order_correctness": compute_tool_order_correctness,
    "duplicate_tool_calls": compute_duplicate_tool_calls,
}


__all__ = ["DETERMINISTIC_METRICS", "MetricContext"]
