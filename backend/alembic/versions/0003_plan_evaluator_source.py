"""Add evaluator source column to evaluation_plan.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29

Adds ``evaluation_plan.evaluator_revision_ids`` (JSONB, nullable). Custom plans
store the evaluator revisions they will execute here; benchmark plans leave it
NULL and resolve their evaluator revisions from the benchmark version's cases at
prepare time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_plan",
        sa.Column("evaluator_revision_ids", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_plan", "evaluator_revision_ids")
