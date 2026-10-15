"""Rename simulation caller backgrounds to call ambience.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-04

The ``simulation.backgrounds`` axis was mislabelled: it never described the
caller's contextual profile. It selects the environmental conditions mixed into
a call (noise, people talking, etc.), so rename it to ``call_ambience``.
``run_evaluator.background`` duplicated the caller-profile notion per evaluator
and is no longer produced by generation, so drop it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("simulation", "backgrounds", new_column_name="call_ambience")
    op.drop_column("run_evaluator", "background")


def downgrade() -> None:
    op.add_column(
        "run_evaluator",
        sa.Column(
            "background",
            sa.String(32),
            nullable=False,
            server_default="",
        ),
    )
    op.alter_column("run_evaluator", "background", server_default=None)
    op.alter_column("simulation", "call_ambience", new_column_name="backgrounds")
