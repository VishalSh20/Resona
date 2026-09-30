"""Capability matrix and plan-time negotiation.

A target revision stores a capability snapshot; every metric declares the
capabilities it requires. Negotiation happens before execution so that missing
observability is discovered up front, never halfway through a benchmark.

Required metrics with a missing capability are BLOCKING. Optional metrics with a
missing capability become ``NOT_AVAILABLE`` during evaluation — never zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voiceeval.core.errors import ValidationError

# Canonical flat capability keys, extracted from the nested capability snapshot.
CAPABILITY_CALLER_AUDIO_INGRESS = "caller_audio_ingress"
CAPABILITY_AGENT_AUDIO_EGRESS = "agent_audio_egress"
CAPABILITY_TARGET_INPUT_TRANSCRIPT = "target_input_transcript"
CAPABILITY_TARGET_OUTPUT_TRANSCRIPT = "target_output_transcript"
CAPABILITY_INDEPENDENT_ASR = "independent_asr_possible"
CAPABILITY_TURN_BOUNDARIES = "turn_boundaries"
CAPABILITY_TARGET_TEXT_STREAM = "target_text_stream"
CAPABILITY_INTERRUPTIONS = "interruptions"
CAPABILITY_CONNECTION_EVENTS = "connection_events"
CAPABILITY_TOOL_CALLS = "tool_calls"
CAPABILITY_TOOL_RESULTS = "tool_results"


@dataclass(frozen=True)
class MetricRequirement:
    metric_key: str
    required_capabilities: frozenset[str] = frozenset()


# The documented capability rules. Judge-backed and hybrid metrics need
# evaluator content rather than a target capability, so they have no capability
# set here.
CAPABILITY_MATRIX: dict[str, MetricRequirement] = {
    "ttft": MetricRequirement("ttft", frozenset({CAPABILITY_TARGET_TEXT_STREAM})),
    "ttfa": MetricRequirement(
        "ttfa",
        frozenset({CAPABILITY_CALLER_AUDIO_INGRESS, CAPABILITY_AGENT_AUDIO_EGRESS}),
    ),
    "barge_in_latency": MetricRequirement(
        "barge_in_latency", frozenset({CAPABILITY_INTERRUPTIONS})
    ),
    "barge_in_success_rate": MetricRequirement(
        "barge_in_success_rate", frozenset({CAPABILITY_INTERRUPTIONS})
    ),
    "language_detection_accuracy": MetricRequirement("language_detection_accuracy"),
    "relevancy": MetricRequirement("relevancy"),
    "context_retention": MetricRequirement("context_retention"),
    "instruction_following": MetricRequirement("instruction_following"),
    "empathy": MetricRequirement("empathy"),
    "hallucination": MetricRequirement("hallucination"),
    "semantic_preservation": MetricRequirement("semantic_preservation"),
    "language_consistency": MetricRequirement("language_consistency"),
    "repetition": MetricRequirement("repetition"),
    "task_completion": MetricRequirement("task_completion"),
    "kb_groundedness": MetricRequirement("kb_groundedness"),
    "code_switching_accuracy": MetricRequirement("code_switching_accuracy"),
}


@dataclass
class NegotiationResult:
    blocking_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unavailable_metrics: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking_errors


def _section(snapshot: dict, key: str) -> dict:
    value = snapshot.get(key) or {}
    if not isinstance(value, dict):
        raise ValidationError(f"capability_snapshot.{key} must be an object")
    return value


def extract_capabilities(snapshot: dict) -> set[str]:
    """Flatten a nested capability snapshot into canonical capability keys."""
    if not isinstance(snapshot, dict):
        raise ValidationError("capability_snapshot must be an object")
    capabilities: set[str] = set()

    audio = _section(snapshot, "audio")
    transcript = _section(snapshot, "transcript")
    events = _section(snapshot, "events")
    tools = _section(snapshot, "tools")

    if audio.get("caller_ingress"):
        capabilities.add(CAPABILITY_CALLER_AUDIO_INGRESS)
    if audio.get("agent_egress"):
        capabilities.add(CAPABILITY_AGENT_AUDIO_EGRESS)
    if transcript.get("target_input"):
        capabilities.add(CAPABILITY_TARGET_INPUT_TRANSCRIPT)
    if transcript.get("target_output"):
        capabilities.add(CAPABILITY_TARGET_OUTPUT_TRANSCRIPT)
    if transcript.get("independent_asr_possible"):
        capabilities.add(CAPABILITY_INDEPENDENT_ASR)
    if events.get("turn_boundaries"):
        capabilities.add(CAPABILITY_TURN_BOUNDARIES)
    if events.get("text_stream"):
        capabilities.add(CAPABILITY_TARGET_TEXT_STREAM)
    if events.get("interruptions"):
        capabilities.add(CAPABILITY_INTERRUPTIONS)
    if events.get("connection_events"):
        capabilities.add(CAPABILITY_CONNECTION_EVENTS)
    if tools.get("calls"):
        capabilities.add(CAPABILITY_TOOL_CALLS)
    if tools.get("results"):
        capabilities.add(CAPABILITY_TOOL_RESULTS)

    return capabilities


def negotiate(snapshot: dict, criteria: list[dict]) -> NegotiationResult:
    """Negotiate evaluator metric requirements against a target snapshot.

    ``criteria`` is the evaluator's ``evaluation_criteria`` list, i.e.
    ``[{"metric": "motive_fulfillment", "required": true}, ...]``.
    """
    capabilities = extract_capabilities(snapshot)
    result = NegotiationResult()

    for item in criteria:
        metric_key = item.get("metric")
        required = bool(item.get("required", False))

        requirement = CAPABILITY_MATRIX.get(metric_key)
        if requirement is None:
            result.blocking_errors.append(f"unknown metric '{metric_key}'")
            continue

        missing = requirement.required_capabilities - capabilities
        if not missing:
            continue

        detail = (
            f"metric '{metric_key}' requires missing capabilities: "
            f"{sorted(missing)}"
        )
        if required:
            result.blocking_errors.append(detail)
        else:
            result.warnings.append(detail)
            result.unavailable_metrics.append(metric_key)

    return result
