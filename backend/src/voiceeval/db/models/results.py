"""Evaluation-result tables.

Represents EVALUATION TRUTH: metric/judge definitions, per-run metric results,
evidence, aggregates and composite scores. Availability semantics are explicit —
a metric that could not be computed is ``NOT_AVAILABLE``/``NOT_APPLICABLE``/
``INVALID``/``ERROR``, never silently zero.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from voiceeval.db.base import Base
from voiceeval.db.models.mixins import CreatedAtMixin, ID_LENGTH, IdMixin


class MetricDefinition(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "metric_definition"
    __table_args__ = (
        UniqueConstraint("metric_key", "version", name="uq_metric_definition_key_version"),
        CheckConstraint(
            "value_type IN ('numeric','boolean','text','category')",
            name="ck_metric_definition_value_type",
        ),
        Index("ix_metric_definition_key", "metric_key"),
    )

    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    scale_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    scale_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    required_capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    required_evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    implementation_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    aggregation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalization_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class JudgeDefinition(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "judge_definition"
    __table_args__ = (
        UniqueConstraint("judge_key", "version", name="uq_judge_definition_key_version"),
        CheckConstraint(
            "kind IN ('structured_judge','llm_judge','probe_judge')",
            name="ck_judge_definition_kind",
        ),
    )

    judge_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class JudgeExecution(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "judge_execution"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','invalid','error')",
            name="ck_judge_execution_status",
        ),
    )

    call_run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_run.id", ondelete="CASCADE"), nullable=False
    )
    # The judge runs against one selected attempt; the link is kept so media,
    # probes and findings can be traced to the exact observed capture.
    call_attempt_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id", ondelete="SET NULL"), nullable=True
    )
    judge_definition_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("judge_definition.id"), nullable=False
    )
    input_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # Denormalized rubric version for querying without joining the definition.
    rubric_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full judge-spec result document (§9). raw_output retains the model text.
    raw_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parsed_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence_coverage: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    needs_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    alignment_conflict: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    media_validation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MetricResult(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "metric_result"
    __table_args__ = (
        CheckConstraint(
            "status IN ('computed','not_available','not_applicable','invalid','error')",
            name="ck_metric_result_status",
        ),
        CheckConstraint(
            "value_type IS NULL OR value_type IN ('numeric','boolean','text','category')",
            name="ck_metric_result_value_type",
        ),
        # Exactly the value column matching value_type may be populated. This
        # encodes the availability contract at the database level: a COMPUTED
        # result carries one typed value, a non-computed result carries none.
        CheckConstraint(
            "status <> 'computed' OR "
            "(value_type = 'numeric' AND value_numeric IS NOT NULL "
            " AND value_boolean IS NULL AND value_text IS NULL AND value_category IS NULL) OR "
            "(value_type = 'boolean' AND value_boolean IS NOT NULL "
            " AND value_numeric IS NULL AND value_text IS NULL AND value_category IS NULL) OR "
            "(value_type = 'text' AND value_text IS NOT NULL "
            " AND value_numeric IS NULL AND value_boolean IS NULL AND value_category IS NULL) OR "
            "(value_type = 'category' AND value_category IS NOT NULL "
            " AND value_numeric IS NULL AND value_boolean IS NULL AND value_text IS NULL)",
            name="ck_metric_result_value_representation",
        ),
        Index(
            "ix_metric_result_run_definition", "call_run_id", "metric_definition_id"
        ),
    )

    call_run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_run.id", ondelete="CASCADE"), nullable=False
    )
    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id"), nullable=False
    )
    metric_definition_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("metric_definition.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Denormalized snapshot of the metric's value_type at computation time, so
    # the value-representation CHECK can be enforced within a single row.
    value_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    scale_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    scale_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)
    measurement_basis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    judge_execution_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("judge_execution.id"), nullable=True
    )
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Evidence(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('turn','event','tool_call','audio','state_transition')",
            name="ck_evidence_source_type",
        ),
        Index("ix_evidence_metric_result", "metric_result_id"),
    )

    metric_result_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("metric_result.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class JudgeLedger(IdMixin, CreatedAtMixin, Base):
    """A Stage-1 evidence ledger produced during one judge execution (§3.2)."""

    __tablename__ = "judge_ledger"
    __table_args__ = (
        CheckConstraint(
            "ledger_type IN ('claim','fact','intent','instruction','goal',"
            "'emotion','preservation')",
            name="ck_judge_ledger_type",
        ),
        CheckConstraint(
            "status IN ('ok','unstable','invalid')",
            name="ck_judge_ledger_status",
        ),
        Index("ix_judge_ledger_execution", "judge_execution_id", "ledger_type"),
    )

    judge_execution_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("judge_execution.id", ondelete="CASCADE"),
        nullable=False,
    )
    ledger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    caveats: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class MetricProbe(IdMixin, CreatedAtMixin, Base):
    """One bounded decision that fed a metric value (§9 ``probes[]``)."""

    __tablename__ = "metric_probe"
    __table_args__ = (
        CheckConstraint(
            "type IN ('noul','choice','score','code')", name="ck_metric_probe_type"
        ),
        CheckConstraint(
            "resolver IN ('code','jev','llm_adjudicated','llm_fallback')",
            name="ck_metric_probe_resolver",
        ),
        Index("ix_metric_probe_metric_result", "metric_result_id"),
    )

    metric_result_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("metric_result.id", ondelete="CASCADE"),
        nullable=False,
    )
    probe_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    turn_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    probabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    resolver: Mapped[str] = mapped_column(String(32), nullable=False, default="jev")
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    variants_agree: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    jev_model: Mapped[str | None] = mapped_column(Text, nullable=True)


class JudgeFinding(IdMixin, CreatedAtMixin, Base):
    """A grounded finding supporting a metric score (§9 ``findings[]``)."""

    __tablename__ = "judge_finding"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('critical','major','minor')",
            name="ck_judge_finding_severity",
        ),
        Index("ix_judge_finding_metric_result", "metric_result_id"),
    )

    metric_result_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("metric_result.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    turn_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    t_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    t_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    probe_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class AggregateResult(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "aggregate_result"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('evaluator','run','benchmark')", name="ck_aggregate_scope"
        ),
        CheckConstraint(
            "percentile_status IN ('computed','insufficient_sample','not_applicable')",
            name="ck_aggregate_percentile_status",
        ),
        Index("ix_aggregate_run_definition", "run_id", "metric_definition_id"),
    )

    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("run.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    run_evaluator_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("run_evaluator.id"), nullable=True
    )
    metric_definition_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("metric_definition.id"), nullable=False
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_count: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_ratio: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    mean: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    median: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    min_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    stddev: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    p95: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    percentile_status: Mapped[str] = mapped_column(String(32), nullable=False)
    category_counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    aggregation_version: Mapped[str | None] = mapped_column(Text, nullable=True)


class CompositeScoreDefinition(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "composite_score_definition"

    version: Mapped[str] = mapped_column(Text, nullable=False)
    weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalization: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    coverage_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    critical_metrics: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class CompositeScoreResult(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "composite_score_result"
    __table_args__ = (
        UniqueConstraint("run_id", "definition_id", name="uq_composite_run_definition"),
        CheckConstraint(
            "status IN ('complete','incomplete','unavailable')",
            name="ck_composite_result_status",
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("run.id", ondelete="CASCADE"),
        nullable=False,
    )
    definition_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("composite_score_definition.id"), nullable=False
    )
    score_0_100: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    coverage_ratio: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    unavailable_weight: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    category_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
