"""Add structured caller scenario to ``run_evaluator``.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-04

The caller needs the scenario's structured details (objective, facts,
initial_state, allowed_actions, stop_conditions) to know what it is trying to
achieve and which facts it may reveal. The v0.4 ``RunEvaluator`` persisted only
rendered scenario text, so add ``scenario_config`` (canonical ``evaluator.v1``
shape, default ``{}``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_evaluator",
        sa.Column(
            "scenario_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("run_evaluator", "scenario_config")
