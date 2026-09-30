"""Result and forensics response contracts.

These are dedicated Pydantic models; SQLAlchemy models never cross the API
boundary. Nested observed-truth objects are projected into plain shapes so the
frontend can reconstruct an execution without knowing the persistence layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricResultRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    call_run_id: str
    call_attempt_id: str
    metric_key: str
    metric_version: str
    status: str
    value_type: str | None = None
    value: float | bool | str | None = None
    unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    method: str | None = None
    measurement_basis: dict[str, Any] | None = None
    confidence: float | None = None
    judge_execution_id: str | None = None
    computed_at: datetime | None = None


class EvidenceRead(BaseModel):
    id: str
    metric_result_id: str
    source_type: str
    source_id: str
    start_ms: int | None = None
    end_ms: int | None = None
    quote: str | None = None
    rationale: str | None = None


class JudgeExecutionRead(BaseModel):
    """A judge execution row and its full §9 result document.

    ``parsed_output`` is the judge's own result contract
    (``voiceeval.judging.schemas.JudgeRunResult``). It is kept as a JSON object
    here so the API layer never imports the judging runtime.
    """

    id: str
    call_run_id: str
    call_attempt_id: str | None = None
    status: str
    rubric_version: str | None = None
    evidence_coverage: float | None = None
    needs_human_review: bool = False
    alignment_conflict: bool = False
    latency_ms: int | None = None
    parsed_output: dict[str, Any] | None = None


class AggregateRead(BaseModel):
    id: str
    run_id: str
    scope: str
    run_evaluator_id: str | None = None
    metric_key: str
    metric_version: str
    sample_count: int
    coverage_count: int
    availability_ratio: float | None = None
    mean: float | None = None
    median: float | None = None
    min: float | None = None
    max: float | None = None
    stddev: float | None = None
    p95: float | None = None
    percentile_status: str
    category_counts: dict[str, Any] | None = None
    aggregation_version: str | None = None


class CompositeRead(BaseModel):
    run_id: str
    status: str
    score_0_100: float | None = None
    coverage_ratio: float | None = None
    unavailable_weight: float | None = None
    category_scores: dict[str, float | None] | None = None
    missing_metrics: list[str] = Field(default_factory=list)


class CallRunRead(BaseModel):
    id: str
    run_id: str
    run_evaluator_id: str
    repetition_no: int
    status: str
    run_seed: str | None = None
    selected_attempt_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class CallAttemptRead(BaseModel):
    id: str
    call_run_id: str
    attempt_no: int
    execution_manifest_id: str | None = None
    status: str
    terminal_status: str | None = None
    failure_class: str | None = None
    termination_reason: str | None = None
    eligible_for_evaluation: bool
    runner_version: str | None = None
    adapter_version: str | None = None
    transport_version: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class TurnRead(BaseModel):
    id: str
    call_attempt_id: str
    sequence_no: int
    speaker: str
    start_ms: int | None = None
    end_ms: int | None = None
    reference_text: str | None = None
    observed_text: str | None = None
    reference_language_profile: dict[str, Any] | None = None
    observed_language_profile: dict[str, Any] | None = None
    reference_audio_artifact_id: str | None = None
    observed_audio_artifact_id: str | None = None
    transcript_source: str | None = None
    transcript_confidence: float | None = None


class ToolCallRead(BaseModel):
    id: str
    call_attempt_id: str
    turn_id: str | None = None
    ordinal: int
    tool_name: str
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    status: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class StateTransitionRead(BaseModel):
    id: str
    call_attempt_id: str
    sequence_no: int
    state_path: str
    previous_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    trigger_type: str | None = None
    trigger_event_id: str | None = None


class EventRead(BaseModel):
    id: str
    call_attempt_id: str
    sequence_no: int
    type: str
    source: str
    monotonic_ms: int
    wall_clock_at: datetime
    media_timestamp: int | None = None
    turn_id: str | None = None
    provider_event_id: str | None = None
    payload: dict[str, Any]


class PaginatedEvents(BaseModel):
    items: list[EventRead]
    total: int
    limit: int
    offset: int


class MediaArtifactRead(BaseModel):
    id: str
    call_attempt_id: str
    track: str
    representation: str
    format: str | None = None
    codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None
    clock_domain: str | None = None
    object_uri: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None


class MediaUrlRead(BaseModel):
    media_artifact_id: str
    url: str
    expires_in_seconds: int


class ManifestRead(BaseModel):
    """The sealed execution manifest, exposed read-only for forensics."""

    id: str
    schema_version: str
    target_snapshot: dict[str, Any]
    simulation_snapshot: dict[str, Any]
    run_snapshot: dict[str, Any]
    evaluator_snapshot: dict[str, Any]
    benchmark_snapshot: dict[str, Any] | None = None
    caller_snapshot: dict[str, Any]
    metric_snapshot: Any
    judge_snapshot: Any
    aggregation_snapshot: Any
    composite_snapshot: Any
    manifest_hash: str
    created_at: datetime | None = None


class ConversationRead(BaseModel):
    attempt_id: str
    turns: list[TurnRead]
    tool_calls: list[ToolCallRead]
    state_transitions: list[StateTransitionRead]


class EvaluatorRunResults(BaseModel):
    run_evaluator_id: str
    runs: list[CallRunRead]
    metrics: list[AggregateRead]
    metric_results: list[MetricResultRead]


class RunResultsRead(BaseModel):
    run_id: str
    status: str
    evaluators: list[EvaluatorRunResults]
    composite: CompositeRead | None = None


class ForensicsSummary(BaseModel):
    metrics: list[MetricResultRead]
    scores: list[AggregateRead]
    composite: CompositeRead | None = None


class ForensicsConversation(BaseModel):
    turns: list[TurnRead]
    events: list[EventRead]
    tool_calls: list[ToolCallRead]


class ForensicsRead(BaseModel):
    run: dict[str, Any]
    evaluator: dict[str, Any]
    selection: dict[str, Any]
    attempt: dict[str, Any]
    summary: ForensicsSummary
    conversation: ForensicsConversation
    evidence: list[EvidenceRead]
    media: list[MediaArtifactRead]
