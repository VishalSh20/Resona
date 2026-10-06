"""Voice-Agent Judge schema.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-04

Replaces the single-shot ``StructuredJudge`` persistence with the Voice-Agent
Judge (docs/V2-changes/judge-implementation.md):

* ``judge_definition`` gains the ``probe_judge`` kind.
* ``judge_execution`` links to the judged attempt and records run-level outcome
  (rubric version, evidence coverage, human-review flag, alignment conflict,
  media validation).
* New per-run forensic tables: ``judge_ledger`` (Stage-1 evidence), and
  ``metric_probe`` / ``judge_finding`` (per-metric decision provenance).
* ``run_evaluator`` gains the judge input contract columns (``language_policy``,
  ``kb_collection_id``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_LENGTH = 64


def upgrade() -> None:
    # --- judge_definition: allow the new kind -----------------------------
    op.drop_constraint("ck_judge_definition_kind", "judge_definition", type_="check")
    op.create_check_constraint(
        "ck_judge_definition_kind",
        "judge_definition",
        "kind IN ('structured_judge','llm_judge','probe_judge')",
    )

    # --- judge_execution: attempt link + run-level outcome ----------------
    op.add_column(
        "judge_execution",
        sa.Column("call_attempt_id", sa.String(ID_LENGTH), nullable=True),
    )
    op.create_foreign_key(
        "fk_judge_execution_attempt",
        "judge_execution",
        "call_attempt",
        ["call_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("judge_execution", sa.Column("rubric_version", sa.Text(), nullable=True))
    op.add_column(
        "judge_execution", sa.Column("evidence_coverage", sa.Numeric(), nullable=True)
    )
    op.add_column(
        "judge_execution",
        sa.Column(
            "needs_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "judge_execution",
        sa.Column(
            "alignment_conflict",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "judge_execution",
        sa.Column("media_validation", postgresql.JSONB(), nullable=True),
    )

    # --- judge_ledger -----------------------------------------------------
    op.create_table(
        "judge_ledger",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column(
            "judge_execution_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("judge_execution.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ledger_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("caveats", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "ledger_type IN ('claim','fact','intent','instruction','goal',"
            "'emotion','preservation')",
            name="ck_judge_ledger_type",
        ),
        sa.CheckConstraint(
            "status IN ('ok','unstable','invalid')", name="ck_judge_ledger_status"
        ),
    )
    op.create_index(
        "ix_judge_ledger_execution",
        "judge_ledger",
        ["judge_execution_id", "ledger_type"],
    )

    # --- metric_probe -----------------------------------------------------
    op.create_table(
        "metric_probe",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column(
            "metric_result_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("metric_result.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("probe_id", sa.Text(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("turn_ids", postgresql.JSONB(), nullable=True),
        sa.Column("probabilities", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.Column("resolver", sa.String(32), nullable=False, server_default="jev"),
        sa.Column(
            "escalated", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("variants_agree", sa.Boolean(), nullable=True),
        sa.Column("jev_model", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "type IN ('noul','choice','score','code')", name="ck_metric_probe_type"
        ),
        sa.CheckConstraint(
            "resolver IN ('code','jev','llm_adjudicated','llm_fallback')",
            name="ck_metric_probe_resolver",
        ),
    )
    op.create_index("ix_metric_probe_metric_result", "metric_probe", ["metric_result_id"])

    # --- judge_finding ----------------------------------------------------
    op.create_table(
        "judge_finding",
        sa.Column("id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column(
            "metric_result_id",
            sa.String(ID_LENGTH),
            sa.ForeignKey("metric_result.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("turn_ids", postgresql.JSONB(), nullable=True),
        sa.Column("t_start", sa.Integer(), nullable=True),
        sa.Column("t_end", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("probe_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "severity IN ('critical','major','minor')", name="ck_judge_finding_severity"
        ),
    )
    op.create_index("ix_judge_finding_metric_result", "judge_finding", ["metric_result_id"])

    # --- run_evaluator: judge input contract ------------------------------
    op.add_column(
        "run_evaluator", sa.Column("language_policy", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "run_evaluator", sa.Column("kb_collection_id", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("run_evaluator", "kb_collection_id")
    op.drop_column("run_evaluator", "language_policy")

    op.drop_index("ix_judge_finding_metric_result", table_name="judge_finding")
    op.drop_table("judge_finding")
    op.drop_index("ix_metric_probe_metric_result", table_name="metric_probe")
    op.drop_table("metric_probe")
    op.drop_index("ix_judge_ledger_execution", table_name="judge_ledger")
    op.drop_table("judge_ledger")

    op.drop_column("judge_execution", "media_validation")
    op.drop_column("judge_execution", "alignment_conflict")
    op.drop_column("judge_execution", "needs_human_review")
    op.drop_column("judge_execution", "evidence_coverage")
    op.drop_column("judge_execution", "rubric_version")
    op.drop_constraint("fk_judge_execution_attempt", "judge_execution", type_="foreignkey")
    op.drop_column("judge_execution", "call_attempt_id")

    op.drop_constraint("ck_judge_definition_kind", "judge_definition", type_="check")
    op.create_check_constraint(
        "ck_judge_definition_kind",
        "judge_definition",
        "kind IN ('structured_judge','llm_judge')",
    )
