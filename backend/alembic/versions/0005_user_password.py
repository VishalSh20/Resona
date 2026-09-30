"""Add password hash to users.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30

Enables real credential authentication (sign-up / sign-in). The column is
nullable so operator-provisioned accounts that never set a password remain
valid. See docs/decisions/0008-auth-signup-decisions.md.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
