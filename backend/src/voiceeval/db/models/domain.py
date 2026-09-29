"""Configuration-domain tables.

Covers targets, simulations, runs, run evaluators, benchmarks and execution
manifests. ``Simulation`` is the reusable evaluation space; a ``Run``
instantiates one Simulation into concrete ``RunEvaluator`` scenarios. The
execution manifest remains the immutable record of exactly what was executed.

This mirrors ``docs/V2-changes/voiceeval_domain_schema_v0.4.md``. The previous
``Evaluator``/``EvaluatorRevision``/``EvaluationPlan``/``EvaluationPlanItem``
revision chain is intentionally absent: there is no evaluator revision lifecycle.
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from voiceeval.db.base import Base
from voiceeval.db.models.mixins import CreatedAtMixin, ID_LENGTH, IdMixin, UpdatedAtMixin


class IntegrationProvider(IdMixin, CreatedAtMixin, Base):
    """A provider platform (Retell, Vapi, ElevenLabs, LiveKit, Pipecat)."""

    __tablename__ = "integration_provider"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class IntegrationAccount(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """One configured provider account/project.

    Non-secret provider configuration lives in ``config``; credentials are held
    separately through a secret manager, never inside JSONB configuration.
    """

    __tablename__ = "integration_account"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_integration_account_status"
        ),
        Index("ix_integration_account_provider", "provider_id"),
    )

    provider_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("integration_provider.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class IntegrationSecret(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """An encrypted provider credential, referenced by ``secret:`` refs.

    Values are encrypted at rest with a deployment master key (see
    ``voiceeval.services.secrets``); ``config`` / ``source_config`` only ever
    hold the reference key, never the plaintext value.
    """

    __tablename__ = "integration_secret"
    __table_args__ = (
        UniqueConstraint(
            "integration_account_id", "key", name="uq_integration_secret_account_key"
        ),
        Index("ix_integration_secret_account", "integration_account_id"),
    )

    integration_account_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("integration_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)


class TransportType(IdMixin, CreatedAtMixin, Base):
    """How communication is carried (webrtc, websocket, sip, pstn, ...)."""

    __tablename__ = "transport_type"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AgentTarget(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """The stable logical identity of an agent inside the platform."""

    __tablename__ = "agent_target"
    __table_args__ = (
        UniqueConstraint(
            "integration_account_id",
            "external_agent_id",
            name="uq_agent_target_account_external_id",
        ),
        Index("ix_agent_target_provider", "provider_id"),
        Index("ix_agent_target_account", "integration_account_id"),
    )

    provider_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("integration_provider.id"), nullable=False
    )
    integration_account_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("integration_account.id"), nullable=False
    )
    external_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentTargetRevision(IdMixin, CreatedAtMixin, Base):
    """One exact version/snapshot of an agent being evaluated.

    Holds only revision-specific configuration: ``source_config`` preserves the
    provider's original configuration unchanged, ``canonical_config`` is our
    normalized representation that the simulation/evaluation layer consumes.
    Stable identity (``external_agent_id``, ``agent_url``) lives on the parent
    ``AgentTarget``; transport/endpoint details live on ``AgentEndpoint``.
    """

    __tablename__ = "agent_target_revision"
    __table_args__ = (
        UniqueConstraint("agent_target_id", "revision_no", name="uq_target_rev_no"),
        UniqueConstraint("agent_target_id", "config_hash", name="uq_target_rev_config_hash"),
        UniqueConstraint(
            "agent_target_id",
            "provider_revision_id",
            "source_branch_id",
            name="uq_target_rev_provider",
        ),
        CheckConstraint(
            "source_kind IN ('IMPORTED', 'MANUAL')",
            name="ck_target_rev_source_kind",
        ),
        CheckConstraint(
            "provider_revision_type IN ('AGENT_CONFIGURATION', 'DEPLOYMENT')",
            name="ck_target_rev_type",
        ),
        Index("ix_target_rev_target_revno", "agent_target_id", "revision_no"),
    )

    agent_target_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("agent_target.id", ondelete="CASCADE"), nullable=False
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stt_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tts_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    turn_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    conversation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tools_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    variables_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    knowledge_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    workflow_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    handoffs_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    guardrails_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    canonical_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider_revision_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_revision_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revision_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_branch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)


class AgentEndpoint(IdMixin, CreatedAtMixin, Base):
    """How to connect to a specific agent revision using a given transport."""

    __tablename__ = "agent_endpoint"
    __table_args__ = (
        Index("ix_agent_endpoint_revision", "agent_target_revision_id"),
    )

    agent_target_revision_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("agent_target_revision.id", ondelete="CASCADE"),
        nullable=False,
    )
    transport_type_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("transport_type.id"), nullable=False
    )
    connection_config: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ConnectionSession(IdMixin, CreatedAtMixin, Base):
    """One actual runtime connection during a test."""

    __tablename__ = "connection_session"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','connecting','connected','terminated','failed')",
            name="ck_connection_session_status",
        ),
        Index("ix_connection_session_endpoint", "endpoint_id"),
        Index("ix_connection_session_revision", "revision_id"),
    )

    endpoint_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("agent_endpoint.id"), nullable=False
    )
    revision_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("agent_target_revision.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    provider_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ephemeral_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Simulation(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """Reusable definition of the evaluation space.

    Describes what may be evaluated (target, languages, call ambience, metrics,
    personalities, knowledge base) without fixing a single caller scenario.
    """

    __tablename__ = "simulation"
    __table_args__ = (
        CheckConstraint(
            "evaluator_count >= 1 AND evaluator_count <= 100",
            name="ck_simulation_evaluator_count",
        ),
        Index("ix_simulation_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The agent being evaluated is a property of the Simulation; each Run picks a
    # concrete revision of this same agent.
    agent_target_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("agent_target.id"), nullable=False
    )
    languages: Mapped[list] = mapped_column(JSONB, nullable=False)
    call_ambience: Mapped[list] = mapped_column(JSONB, nullable=False)
    metric_set: Mapped[list] = mapped_column(JSONB, nullable=False)
    personalities: Mapped[list] = mapped_column(JSONB, nullable=False)
    knowledge_base: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)


class Run(IdMixin, CreatedAtMixin, Base):
    """One concrete instantiation/execution of a Simulation."""

    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','ready','queued','running','partial','completed','cancelled')",
            name="ck_run_status",
        ),
        CheckConstraint("evaluator_count >= 1", name="ck_run_evaluator_count"),
        Index("ix_run_simulation_status", "simulation_id", "status"),
        Index("ix_run_status", "status"),
        Index("ix_run_target_status", "target_revision_id", "status"),
    )

    simulation_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("simulation.id", ondelete="CASCADE"), nullable=False
    )
    # Concrete target configuration executed by this Run.
    target_revision_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("agent_target_revision.id"), nullable=False
    )
    evaluator_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEvaluator(IdMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """One concrete caller scenario inside a Run.

    Replaces both the old ``evaluator`` and ``evaluator_revision``. Mutable
    while the Run is editable; snapshotted into the execution manifest at start.
    """

    __tablename__ = "run_evaluator"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_no", name="uq_run_evaluator_seq"),
        Index("ix_run_evaluator_run_seq", "run_id", "sequence_no"),
        Index("ix_run_evaluator_run", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("run.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured caller scenario (objective, facts, initial_state,
    # allowed_actions, stop_conditions) in the canonical ``evaluator.v1`` shape.
    # The caller loads this to know the scenario and the facts to reveal; empty
    # for evaluators that only carry rendered scenario text.
    scenario_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_output_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[list] = mapped_column(JSONB, nullable=False)
    # major/minor language object: {"major": "hi", "minor": "en"}.
    languages: Mapped[dict] = mapped_column(JSONB, nullable=False)
    personality: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Judge input contract (judge spec §0.1). ``language_policy`` is one of
    # mirror_caller | fixed:<lang> | fixed_with_exceptions:<lang>[...];
    # ``kb_collection_id`` names the retrieval collection for kb_groundedness.
    language_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    kb_collection_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ValidationReport(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "validation_report"
    __table_args__ = (
        CheckConstraint(
            "status IN ('passed','failed','error')", name="ck_validation_report_status"
        ),
    )

    run_evaluator_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("run_evaluator.id", ondelete="CASCADE"), nullable=False
    )
    validator_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    blocking_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class Benchmark(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "benchmark"

    benchmark_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class BenchmarkVersion(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "benchmark_version"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version", name="uq_benchmark_version"),
        CheckConstraint(
            "status IN ('draft','frozen','retired')", name="ck_benchmark_version_status"
        ),
    )

    benchmark_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("benchmark.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    manifest_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BenchmarkCase(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "benchmark_case"
    __table_args__ = (
        UniqueConstraint("benchmark_version_id", "case_key", name="uq_benchmark_case_key"),
        UniqueConstraint(
            "benchmark_version_id", "sequence_no", name="uq_benchmark_case_seq"
        ),
    )

    benchmark_version_id: Mapped[str] = mapped_column(
        String(ID_LENGTH),
        ForeignKey("benchmark_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Immutable RunEvaluator-compatible case definition (scenario, expected
    # output prompt, metrics, languages, personality). Replaces the
    # removed evaluator_revision reference.
    case_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)


class ExecutionManifest(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "execution_manifest"

    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    target_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    simulation_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    run_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluator_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    benchmark_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    caller_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    judge_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    aggregation_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    composite_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
