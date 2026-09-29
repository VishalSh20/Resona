"""Runtime-domain tables.

Represents OBSERVED TRUTH: logical call runs, physical attempts, turns, raw
runtime events, tool calls, state transitions and media artifacts. Raw events
are append-only; turns and derived objects are rebuildable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from voiceeval.db.base import Base
from voiceeval.db.models.mixins import CreatedAtMixin, ID_LENGTH, IdMixin


class CallRun(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "call_run"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "run_evaluator_id", "repetition_no",
            name="uq_call_run_repetition",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','infrastructure_failed','cancelled')",
            name="ck_call_run_status",
        ),
        Index("ix_call_run_run_status", "run_id", "status"),
        Index("ix_call_run_evaluator_rep", "run_evaluator_id", "repetition_no"),
    )

    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("run.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_evaluator_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("run_evaluator.id"), nullable=False
    )
    repetition_no: Mapped[int] = mapped_column(Integer, nullable=False)
    run_seed: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # Selected attempt references call_attempt. Circular FK, so it is declared
    # with use_alter and emitted as a separate ALTER TABLE in migrations.
    selected_attempt_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH),
        ForeignKey(
            "call_attempt.id", use_alter=True, name="fk_call_run_selected_attempt"
        ),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CallAttempt(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "call_attempt"
    __table_args__ = (
        UniqueConstraint("call_run_id", "attempt_no", name="uq_call_attempt_no"),
        CheckConstraint(
            "status IN ('queued','starting','connecting','running','terminating','terminal')",
            name="ck_call_attempt_status",
        ),
        CheckConstraint(
            "terminal_status IS NULL OR terminal_status IN "
            "('completed','failed','timed_out','cancelled')",
            name="ck_call_attempt_terminal_status",
        ),
        CheckConstraint(
            "failure_class IS NULL OR failure_class IN ('infrastructure','provider',"
            "'transport','media','timeout','malformed_stream','runner_crash','cancelled')",
            name="ck_call_attempt_failure_class",
        ),
        Index("ix_call_attempt_run_no", "call_run_id", "attempt_no"),
    )

    call_run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_run.id", ondelete="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_manifest_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("execution_manifest.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    terminal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    runner_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    eligible_for_evaluation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)


class MediaArtifact(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "media_artifact"
    __table_args__ = (
        CheckConstraint(
            "track IN ('caller','agent','mixed','provider_capture')",
            name="ck_media_track",
        ),
        CheckConstraint(
            "representation IN ('original','analysis','clip','mixed')",
            name="ck_media_representation",
        ),
        Index("ix_media_attempt", "call_attempt_id"),
    )

    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("call_attempt.id", ondelete="CASCADE"),
        nullable=False,
    )
    track: Mapped[str] = mapped_column(String(32), nullable=False)
    representation: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    codec: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clock_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CallTurn(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "call_turn"
    __table_args__ = (
        UniqueConstraint("call_attempt_id", "sequence_no", name="uq_call_turn_seq"),
        CheckConstraint("speaker IN ('caller','agent')", name="ck_call_turn_speaker"),
        CheckConstraint(
            "transcript_source IS NULL OR transcript_source IN ('caller_reference',"
            "'provider_target_input','provider_target_output','independent_asr',"
            "'human','unknown')",
            name="ck_call_turn_transcript_source",
        ),
        Index("ix_call_turn_attempt_seq", "call_attempt_id", "sequence_no"),
    )

    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(32), nullable=False)
    start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_language_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    observed_language_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reference_audio_artifact_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("media_artifact.id"), nullable=True
    )
    observed_audio_artifact_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("media_artifact.id"), nullable=True
    )
    transcript_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class RuntimeEvent(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "runtime_event"
    __table_args__ = (
        UniqueConstraint("call_attempt_id", "sequence_no", name="uq_runtime_event_seq"),
        CheckConstraint(
            "source IN ('provider_raw','provider_normalized','runtime','derived',"
            "'caller','metric')",
            name="ck_runtime_event_source",
        ),
        # Provider event ids, when present, must be unique per source.
        UniqueConstraint("source", "provider_event_id", name="uq_runtime_event_provider"),
        Index("ix_runtime_event_attempt_seq", "call_attempt_id", "sequence_no"),
    )

    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    monotonic_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wall_clock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    media_timestamp: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    turn_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_turn.id"), nullable=True
    )
    provider_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ToolCall(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "tool_call"
    __table_args__ = (
        UniqueConstraint("call_attempt_id", "ordinal", name="uq_tool_call_ordinal"),
        CheckConstraint(
            "status IS NULL OR status IN ('pending','succeeded','failed','cancelled')",
            name="ck_tool_call_status",
        ),
        Index("ix_tool_call_attempt_ordinal", "call_attempt_id", "ordinal"),
    )

    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id", ondelete="CASCADE"), nullable=False
    )
    turn_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_turn.id"), nullable=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class StateTransition(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "state_transition"
    __table_args__ = (
        UniqueConstraint(
            "call_attempt_id", "sequence_no", name="uq_state_transition_seq"
        ),
        Index("ix_state_transition_attempt_seq", "call_attempt_id", "sequence_no"),
    )

    call_attempt_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("call_attempt.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state_path: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trigger_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_event_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("runtime_event.id"), nullable=True
    )
