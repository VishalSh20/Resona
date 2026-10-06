"""Drop the separate ``system_prompt`` column from ``agent_target_revision``.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04

The agent's instructions are no longer a separate canonical field: they are
carried inside ``llm_config`` (e.g. Vapi's ``model.messages``) and preserved
verbatim in ``source_config``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("agent_target_revision", "system_prompt")


def downgrade() -> None:
    op.add_column(
        "agent_target_revision",
        sa.Column("system_prompt", sa.Text(), nullable=True),
    )
