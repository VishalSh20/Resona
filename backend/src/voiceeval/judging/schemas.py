"""Judge result document (spec §9) and the internal decision primitives.

The ``JudgeRunResult`` is the canonical record persisted on
``judge_execution.parsed_output``; the per-metric rows are also projected onto
``metric_result`` / ``metric_probe`` / ``judge_finding`` for aggregation and
forensics.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MetricStatus = Literal[
    "ok", "not_applicable", "not_measurable", "insufficient_evidence", "invalid"
]
ProbeType = Literal["choice", "noul", "score"]
ProbeResolver = Literal["jev", "llm_adjudicated", "llm_fallback"]
FindingSeverity = Literal["critical", "major", "minor"]
MetricDirection = Literal["higher_is_better", "lower_is_better"]
JudgeRunStatus = Literal["pending", "running", "completed", "invalid", "error"]


class ProbeRecord(BaseModel):
    """One bounded decision that fed a metric value (§9 ``probes[]``)."""

    model_config = ConfigDict(extra="allow")

    probe_id: str
    type: ProbeType
    turn_ids: list[int | str] | None = None
    probabilities: dict[str, float] | None = None
    confidence: float | None = None
    value: float | None = None
    weight: float | None = None
    resolver: ProbeResolver = "jev"
    escalated: bool = False
    variants_agree: bool | None = None
    jev_model: str | None = None


class FindingRecord(BaseModel):
    """A grounded finding supporting a metric score (§9 ``findings[]``)."""

    model_config = ConfigDict(extra="allow")

    severity: FindingSeverity
    type: str
    turn_ids: list[int | str] | None = None
    t_start_ms: int | None = None
    t_end_ms: int | None = None
    quote: str | None = None
    explanation: str | None = None
    probe_id: str | None = None


class SanityBlock(BaseModel):
    holistic_llm_score: int | None = None
    gap: int | None = None


class MetricProvenance(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_hashes: list[str] = Field(default_factory=list)
    jev_response_models: list[str] = Field(default_factory=list)
    llm_samples: int = 0
    media_sources: list[str] = Field(default_factory=list)


class MetricBlock(BaseModel):
    """One metric's contribution to the run result (§9 ``metrics[]``)."""

    model_config = ConfigDict(extra="allow")

    metric_key: str
    status: MetricStatus = "ok"
    value: float | str | bool | None = None
    scale: list[float] | None = None
    direction: MetricDirection | None = None
    normalized: float | None = None
    confidence: float | None = None
    method: str | None = None
    summary: str | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    sanity: SanityBlock | None = None
    probes: list[ProbeRecord] = Field(default_factory=list)
    findings: list[FindingRecord] = Field(default_factory=list)
    provenance: MetricProvenance = Field(default_factory=MetricProvenance)
    caveats: list[str] = Field(default_factory=list)


class MediaArtifactRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    media_artifact_id: str | None = None
    object_uri: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_ms: int | None = None
    format: str | None = None


class MediaValidation(BaseModel):
    integrity_ok: bool = False
    alignment_ok: bool = False
    caller_offset_ms: int | None = None
    agent_offset_ms: int | None = None
    drift_ms: int | None = None
    bleed_detected: bool = False
    caveats: list[str] = Field(default_factory=list)


class MediaBundleBlock(BaseModel):
    artifacts: dict[str, MediaArtifactRef] = Field(default_factory=dict)
    validation: MediaValidation = Field(default_factory=MediaValidation)


class DecisionModelsBlock(BaseModel):
    jev: list[str] = Field(default_factory=list)
    adjudicator: str | None = None
    verifier: str | None = None
    audio: str | None = None


class TimelineFlag(BaseModel):
    turn_id: int | str
    flags: list[str] = Field(default_factory=list)


class JudgeRunResult(BaseModel):
    """The full judge result document (spec §9)."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    rubric_version: str
    judge_version: str = "1.0"
    status: JudgeRunStatus = "completed"
    decision_models: DecisionModelsBlock = Field(default_factory=DecisionModelsBlock)
    media: MediaBundleBlock = Field(default_factory=MediaBundleBlock)
    evidence_coverage: float | None = None
    needs_human_review: bool = False
    alignment_conflict: bool = False
    flags: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    input_hash: str | None = None
    metrics: list[MetricBlock] = Field(default_factory=list)
    timeline: list[TimelineFlag] = Field(default_factory=list)


__all__ = [
    "DecisionModelsBlock",
    "FindingRecord",
    "FindingSeverity",
    "JudgeRunResult",
    "JudgeRunStatus",
    "MediaArtifactRef",
    "MediaBundleBlock",
    "MediaValidation",
    "MetricBlock",
    "MetricDirection",
    "MetricProvenance",
    "MetricStatus",
    "ProbeRecord",
    "ProbeResolver",
    "ProbeType",
    "SanityBlock",
    "TimelineFlag",
]
