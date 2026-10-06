"""Make ``simulation.agent_target_id`` required.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03

The target/agent is now a property of the Simulation (not of each Run). The Run
keeps its concrete ``target_revision_id``, but that revision must belong to the
Simulation's agent. This migration makes ``agent_target_id`` NOT NULL.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "simulation",
        "agent_target_id",
        existing_type=sa.String(64),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "simulation",
        "agent_target_id",
        existing_type=sa.String(64),
        nullable=True,
    )
