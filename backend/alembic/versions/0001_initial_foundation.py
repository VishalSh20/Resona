"""Initial foundation migration.

Revision ID: 0001
Revises:
Create Date: 2026-09-29

This is the empty baseline migration that establishes the Alembic version
table. Domain tables arrive in Prompt 2.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
