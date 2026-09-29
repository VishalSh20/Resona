"""Domain persistence layer.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

Creates the complete VoiceEval domain schema plus the infrastructure support
tables. Hand-written to mirror ``voiceeval.db.models`` exactly (foreign keys,
unique constraints, check constraints and indexes).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- support tables -----------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("scope", sa.String(128), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("key", name="uq_idempotency_keys_key"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("type", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("idempotency_key", "type", name="uq_jobs_idempotency_type"),
    )

    # --- configuration-domain tables ----------------------------------------
    op.create_table(
        "agent_target",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "agent_target_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_target_id", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("adapter_name", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("endpoint_config", postgresql.JSONB(), nullable=False),
        sa.Column("capability_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["agent_target_id"], ["agent_target.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_target_id", "revision_no", name="uq_target_rev_no"),
        sa.UniqueConstraint("agent_target_id", "config_hash", name="uq_target_rev_config_hash"),
        sa.CheckConstraint(
            "transport IN ('websocket', 'webrtc')", name="ck_target_rev_transport"
        ),
    )
    op.create_index(
        "ix_target_rev_target_revno", "agent_target_revision", ["agent_target_id", "revision_no"]
    )

    op.create_table(
        "test_descriptor",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "test_descriptor_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("test_descriptor_id", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("normalized_constraints", postgresql.JSONB(), nullable=True),
        sa.Column("generator_model", sa.Text(), nullable=True),
        sa.Column("generator_prompt_hash", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["test_descriptor_id"], ["test_descriptor.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("test_descriptor_id", "revision_no", name="uq_td_rev_no"),
    )

    op.create_table(
        "evaluator",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluator_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("suite_kind", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("evaluator_key", name="uq_evaluator_key"),
    )
    op.create_table(
        "evaluator_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluator_id", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'generated'")),
        sa.Column("parent_revision_id", sa.String(64), nullable=True),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("validator_version", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["evaluator_id"], ["evaluator.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_revision_id"], ["evaluator_revision.id"]),
        sa.UniqueConstraint("evaluator_id", "revision_no", name="uq_evaluator_rev_no"),
        sa.UniqueConstraint("content_hash", name="uq_evaluator_rev_content_hash"),
        sa.CheckConstraint(
            "status IN ('generated','draft','validating','validated','approved',"
            "'rejected','executed')",
            name="ck_evaluator_rev_status",
        ),
    )
    op.create_index(
        "ix_evaluator_rev_evaluator_revno", "evaluator_revision", ["evaluator_id", "revision_no"]
    )

    op.create_table(
        "validation_report",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluator_revision_id", sa.String(64), nullable=False),
        sa.Column("validator_version", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("blocking_error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("checks", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluator_revision_id"], ["evaluator_revision.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('passed','failed','error')", name="ck_validation_report_status"
        ),
    )

    op.create_table(
        "benchmark",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("benchmark_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("benchmark_key", name="uq_benchmark_key"),
    )
    op.create_table(
        "benchmark_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("benchmark_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("manifest", postgresql.JSONB(), nullable=True),
        sa.Column("manifest_hash", sa.Text(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmark.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("benchmark_id", "version", name="uq_benchmark_version"),
        sa.CheckConstraint(
            "status IN ('draft','frozen','retired')", name="ck_benchmark_version_status"
        ),
    )
    op.create_table(
        "benchmark_case",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("benchmark_version_id", sa.String(64), nullable=False),
        sa.Column("case_key", sa.Text(), nullable=False),
        sa.Column("evaluator_revision_id", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_version_id"], ["benchmark_version.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evaluator_revision_id"], ["evaluator_revision.id"]),
        sa.UniqueConstraint("benchmark_version_id", "case_key", name="uq_benchmark_case_key"),
        sa.UniqueConstraint(
            "benchmark_version_id", "sequence_no", name="uq_benchmark_case_seq"
        ),
    )

    op.create_table(
        "execution_manifest",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("target_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("evaluator_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("benchmark_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("caller_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("metric_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("judge_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("aggregation_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("composite_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("manifest_hash", name="uq_execution_manifest_hash"),
    )

    op.create_table(
        "evaluation_plan",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("test_descriptor_revision_id", sa.String(64), nullable=True),
        sa.Column("benchmark_version_id", sa.String(64), nullable=True),
        sa.Column("agent_target_revision_id", sa.String(64), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.Column("plan_status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("execution_manifest_id", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["test_descriptor_revision_id"], ["test_descriptor_revision.id"]
        ),
        sa.ForeignKeyConstraint(["benchmark_version_id"], ["benchmark_version.id"]),
        sa.ForeignKeyConstraint(
            ["agent_target_revision_id"], ["agent_target_revision.id"]
        ),
        sa.ForeignKeyConstraint(["execution_manifest_id"], ["execution_manifest.id"]),
        sa.CheckConstraint("kind IN ('custom','benchmark')", name="ck_plan_kind"),
        sa.CheckConstraint(
            "plan_status IN ('draft','ready','queued','running','partial','completed',"
            "'cancelled')",
            name="ck_plan_status",
        ),
        sa.CheckConstraint("repeat_count >= 1", name="ck_plan_repeat_count"),
        sa.CheckConstraint(
            "kind <> 'benchmark' OR benchmark_version_id IS NOT NULL",
            name="ck_plan_benchmark_requires_version",
        ),
    )
    op.create_index("ix_plan_status", "evaluation_plan", ["plan_status"])
    op.create_table(
        "evaluation_plan_item",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluation_plan_id", sa.String(64), nullable=False),
        sa.Column("evaluator_revision_id", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_plan_id"], ["evaluation_plan.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evaluator_revision_id"], ["evaluator_revision.id"]),
        sa.UniqueConstraint(
            "evaluation_plan_id", "evaluator_revision_id", name="uq_plan_item_evaluator"
        ),
        sa.UniqueConstraint(
            "evaluation_plan_id", "sequence_no", name="uq_plan_item_sequence"
        ),
    )
    op.create_index(
        "ix_plan_item_plan_seq", "evaluation_plan_item", ["evaluation_plan_id", "sequence_no"]
    )

    # --- runtime-domain tables ----------------------------------------------
    op.create_table(
        "call_run",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluation_plan_id", sa.String(64), nullable=False),
        sa.Column("plan_item_id", sa.String(64), nullable=False),
        sa.Column("evaluator_revision_id", sa.String(64), nullable=False),
        sa.Column("repetition_no", sa.Integer(), nullable=False),
        sa.Column("run_seed", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("selected_attempt_id", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_plan_id"], ["evaluation_plan.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["plan_item_id"], ["evaluation_plan_item.id"]),
        sa.ForeignKeyConstraint(["evaluator_revision_id"], ["evaluator_revision.id"]),
        sa.UniqueConstraint(
            "evaluation_plan_id", "plan_item_id", "repetition_no",
            name="uq_call_run_repetition",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','infrastructure_failed','cancelled')",
            name="ck_call_run_status",
        ),
    )
    op.create_index(
        "ix_call_run_plan_status", "call_run", ["evaluation_plan_id", "status"]
    )
    op.create_index(
        "ix_call_run_evaluator_rep", "call_run", ["evaluator_revision_id", "repetition_no"]
    )
    op.create_table(
        "call_attempt",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_run_id", sa.String(64), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("execution_manifest_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("terminal_status", sa.String(32), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("runner_version", sa.Text(), nullable=True),
        sa.Column("adapter_version", sa.Text(), nullable=True),
        sa.Column("transport_version", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "eligible_for_evaluation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("failure_class", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["call_run_id"], ["call_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_manifest_id"], ["execution_manifest.id"]),
        sa.UniqueConstraint("call_run_id", "attempt_no", name="uq_call_attempt_no"),
        sa.CheckConstraint(
            "status IN ('queued','starting','connecting','running','terminating','terminal')",
            name="ck_call_attempt_status",
        ),
        sa.CheckConstraint(
            "terminal_status IS NULL OR terminal_status IN "
            "('completed','failed','timed_out','cancelled')",
            name="ck_call_attempt_terminal_status",
        ),
        sa.CheckConstraint(
            "failure_class IS NULL OR failure_class IN ('infrastructure','provider',"
            "'transport','media','timeout','malformed_stream','runner_crash','cancelled')",
            name="ck_call_attempt_failure_class",
        ),
    )
    op.create_index("ix_call_attempt_run_no", "call_attempt", ["call_run_id", "attempt_no"])
    # Circular FK: call_run.selected_attempt_id -> call_attempt.id, added after
    # both tables exist.
    op.create_foreign_key(
        "fk_call_run_selected_attempt",
        "call_run",
        "call_attempt",
        ["selected_attempt_id"],
        ["id"],
    )

    op.create_table(
        "media_artifact",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("representation", sa.String(32), nullable=False),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("codec", sa.Text(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("clock_domain", sa.Text(), nullable=True),
        sa.Column("object_uri", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["call_attempt_id"], ["call_attempt.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "track IN ('caller','agent','mixed','provider_capture')", name="ck_media_track"
        ),
        sa.CheckConstraint(
            "representation IN ('original','analysis','clip','mixed')",
            name="ck_media_representation",
        ),
    )
    op.create_index("ix_media_attempt", "media_artifact", ["call_attempt_id"])

    op.create_table(
        "call_turn",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(32), nullable=False),
        sa.Column("start_ms", sa.BigInteger(), nullable=True),
        sa.Column("end_ms", sa.BigInteger(), nullable=True),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("observed_text", sa.Text(), nullable=True),
        sa.Column("reference_language_profile", postgresql.JSONB(), nullable=True),
        sa.Column("observed_language_profile", postgresql.JSONB(), nullable=True),
        sa.Column("reference_audio_artifact_id", sa.String(64), nullable=True),
        sa.Column("observed_audio_artifact_id", sa.String(64), nullable=True),
        sa.Column("transcript_source", sa.String(64), nullable=True),
        sa.Column("transcript_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["call_attempt_id"], ["call_attempt.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reference_audio_artifact_id"], ["media_artifact.id"]),
        sa.ForeignKeyConstraint(["observed_audio_artifact_id"], ["media_artifact.id"]),
        sa.UniqueConstraint("call_attempt_id", "sequence_no", name="uq_call_turn_seq"),
        sa.CheckConstraint("speaker IN ('caller','agent')", name="ck_call_turn_speaker"),
        sa.CheckConstraint(
            "transcript_source IS NULL OR transcript_source IN ('caller_reference',"
            "'provider_target_input','provider_target_output','independent_asr',"
            "'human','unknown')",
            name="ck_call_turn_transcript_source",
        ),
    )
    op.create_index(
        "ix_call_turn_attempt_seq", "call_turn", ["call_attempt_id", "sequence_no"]
    )

    op.create_table(
        "runtime_event",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("monotonic_ms", sa.BigInteger(), nullable=False),
        sa.Column("wall_clock_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("media_timestamp", sa.BigInteger(), nullable=True),
        sa.Column("turn_id", sa.String(64), nullable=True),
        sa.Column("provider_event_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["call_attempt_id"], ["call_attempt.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["call_turn.id"]),
        sa.UniqueConstraint("call_attempt_id", "sequence_no", name="uq_runtime_event_seq"),
        sa.UniqueConstraint("source", "provider_event_id", name="uq_runtime_event_provider"),
        sa.CheckConstraint(
            "source IN ('provider_raw','provider_normalized','runtime','derived',"
            "'caller','metric')",
            name="ck_runtime_event_source",
        ),
    )
    op.create_index(
        "ix_runtime_event_attempt_seq", "runtime_event", ["call_attempt_id", "sequence_no"]
    )

    op.create_table(
        "tool_call",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("turn_id", sa.String(64), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("arguments", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("start_ms", sa.BigInteger(), nullable=True),
        sa.Column("end_ms", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["call_attempt_id"], ["call_attempt.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["call_turn.id"]),
        sa.UniqueConstraint("call_attempt_id", "ordinal", name="uq_tool_call_ordinal"),
        sa.CheckConstraint(
            "status IS NULL OR status IN ('pending','succeeded','failed','cancelled')",
            name="ck_tool_call_status",
        ),
    )
    op.create_index(
        "ix_tool_call_attempt_ordinal", "tool_call", ["call_attempt_id", "ordinal"]
    )

    op.create_table(
        "state_transition",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("state_path", sa.Text(), nullable=False),
        sa.Column("previous_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("trigger_type", sa.Text(), nullable=True),
        sa.Column("trigger_event_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["call_attempt_id"], ["call_attempt.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["runtime_event.id"]),
        sa.UniqueConstraint(
            "call_attempt_id", "sequence_no", name="uq_state_transition_seq"
        ),
    )
    op.create_index(
        "ix_state_transition_attempt_seq",
        "state_transition",
        ["call_attempt_id", "sequence_no"],
    )

    # --- evaluation-result tables -------------------------------------------
    op.create_table(
        "metric_definition",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("scale_min", sa.Numeric(), nullable=True),
        sa.Column("scale_max", sa.Numeric(), nullable=True),
        sa.Column("required_capabilities", postgresql.JSONB(), nullable=True),
        sa.Column("required_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("implementation_version", sa.Text(), nullable=True),
        sa.Column("aggregation_config", postgresql.JSONB(), nullable=True),
        sa.Column("normalization_config", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("metric_key", "version", name="uq_metric_definition_key_version"),
        sa.CheckConstraint(
            "value_type IN ('numeric','boolean','text','category')",
            name="ck_metric_definition_value_type",
        ),
    )
    op.create_index("ix_metric_definition_key", "metric_definition", ["metric_key"])

    op.create_table(
        "judge_definition",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("judge_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.Text(), nullable=True),
        sa.Column("rubric_version", sa.Text(), nullable=True),
        sa.Column("output_schema_version", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("judge_key", "version", name="uq_judge_definition_key_version"),
        sa.CheckConstraint(
            "kind IN ('structured_judge','llm_judge')", name="ck_judge_definition_kind"
        ),
    )

    op.create_table(
        "judge_execution",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_run_id", sa.String(64), nullable=False),
        sa.Column("judge_definition_id", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("raw_output", postgresql.JSONB(), nullable=True),
        sa.Column("parsed_output", postgresql.JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["call_run_id"], ["call_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["judge_definition_id"], ["judge_definition.id"]),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','invalid','error')",
            name="ck_judge_execution_status",
        ),
    )

    op.create_table(
        "metric_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("call_run_id", sa.String(64), nullable=False),
        sa.Column("call_attempt_id", sa.String(64), nullable=False),
        sa.Column("metric_definition_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("value_type", sa.String(32), nullable=True),
        sa.Column("value_numeric", sa.Numeric(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_category", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("scale_min", sa.Numeric(), nullable=True),
        sa.Column("scale_max", sa.Numeric(), nullable=True),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("measurement_basis", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("judge_execution_id", sa.String(64), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["call_run_id"], ["call_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_attempt_id"], ["call_attempt.id"]),
        sa.ForeignKeyConstraint(["metric_definition_id"], ["metric_definition.id"]),
        sa.ForeignKeyConstraint(["judge_execution_id"], ["judge_execution.id"]),
        sa.CheckConstraint(
            "status IN ('computed','not_available','not_applicable','invalid','error')",
            name="ck_metric_result_status",
        ),
        sa.CheckConstraint(
            "value_type IS NULL OR value_type IN ('numeric','boolean','text','category')",
            name="ck_metric_result_value_type",
        ),
        sa.CheckConstraint(
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
    )
    op.create_index(
        "ix_metric_result_run_definition", "metric_result", ["call_run_id", "metric_definition_id"]
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("metric_result_id", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["metric_result_id"], ["metric_result.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "source_type IN ('turn','event','tool_call','audio','state_transition')",
            name="ck_evidence_source_type",
        ),
    )
    op.create_index("ix_evidence_metric_result", "evidence", ["metric_result_id"])

    op.create_table(
        "aggregate_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluation_plan_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("evaluator_revision_id", sa.String(64), nullable=True),
        sa.Column("metric_definition_id", sa.String(64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("coverage_count", sa.Integer(), nullable=False),
        sa.Column("availability_ratio", sa.Numeric(), nullable=True),
        sa.Column("mean", sa.Numeric(), nullable=True),
        sa.Column("median", sa.Numeric(), nullable=True),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("stddev", sa.Numeric(), nullable=True),
        sa.Column("p95", sa.Numeric(), nullable=True),
        sa.Column("percentile_status", sa.String(32), nullable=False),
        sa.Column("category_counts", postgresql.JSONB(), nullable=True),
        sa.Column("aggregation_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_plan_id"], ["evaluation_plan.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evaluator_revision_id"], ["evaluator_revision.id"]),
        sa.ForeignKeyConstraint(["metric_definition_id"], ["metric_definition.id"]),
        sa.CheckConstraint(
            "scope IN ('evaluator','suite','benchmark')", name="ck_aggregate_scope"
        ),
        sa.CheckConstraint(
            "percentile_status IN ('computed','insufficient_sample','not_applicable')",
            name="ck_aggregate_percentile_status",
        ),
    )
    op.create_index(
        "ix_aggregate_plan_definition",
        "aggregate_result",
        ["evaluation_plan_id", "metric_definition_id"],
    )

    op.create_table(
        "composite_score_definition",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("weights", postgresql.JSONB(), nullable=True),
        sa.Column("normalization", postgresql.JSONB(), nullable=True),
        sa.Column("coverage_policy", postgresql.JSONB(), nullable=True),
        sa.Column("critical_metrics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "composite_score_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("evaluation_plan_id", sa.String(64), nullable=False),
        sa.Column("definition_id", sa.String(64), nullable=False),
        sa.Column("score_0_100", sa.Numeric(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(), nullable=True),
        sa.Column("unavailable_weight", sa.Numeric(), nullable=True),
        sa.Column("category_scores", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_plan_id"], ["evaluation_plan.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["definition_id"], ["composite_score_definition.id"]),
        sa.UniqueConstraint(
            "evaluation_plan_id", "definition_id", name="uq_composite_plan_definition"
        ),
        sa.CheckConstraint(
            "status IN ('complete','incomplete','unavailable')",
            name="ck_composite_result_status",
        ),
    )


def downgrade() -> None:
    # Drop the circular FK before dropping the tables it links.
    op.drop_constraint("fk_call_run_selected_attempt", "call_run", type_="foreignkey")

    op.drop_table("composite_score_result")
    op.drop_table("composite_score_definition")
    op.drop_table("aggregate_result")
    op.drop_table("evidence")
    op.drop_table("metric_result")
    op.drop_table("judge_execution")
    op.drop_table("judge_definition")
    op.drop_table("metric_definition")
    op.drop_table("state_transition")
    op.drop_table("tool_call")
    op.drop_table("runtime_event")
    op.drop_table("call_turn")
    op.drop_table("media_artifact")
    op.drop_table("call_attempt")
    op.drop_table("call_run")
    op.drop_table("evaluation_plan_item")
    op.drop_table("evaluation_plan")
    op.drop_table("execution_manifest")
    op.drop_table("benchmark_case")
    op.drop_table("benchmark_version")
    op.drop_table("benchmark")
    op.drop_table("validation_report")
    op.drop_table("evaluator_revision")
    op.drop_table("evaluator")
    op.drop_table("test_descriptor_revision")
    op.drop_table("test_descriptor")
    op.drop_table("agent_target_revision")
    op.drop_table("agent_target")
    op.drop_table("jobs")
    op.drop_table("idempotency_keys")
    op.drop_table("user_roles")
    op.drop_table("users")
