"""Seed the ``sip`` integration provider.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-06

SIP targets are dialed directly (or via a carrier trunk) through a LiveKit
outbound trunk. That trunk is provisioned once per integration account (see
``SipAdapter.provision_account``) and stored as non-secret account config, so no
new tables are required — only the provider row so targets can be created against
it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVIDER = {
    "id": "prov_sip",
    "slug": "sip",
    "display_name": "SIP",
    "capabilities": {},
}


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "integration_provider",
            sa.column("id", sa.String),
            sa.column("slug", sa.Text),
            sa.column("display_name", sa.Text),
            sa.column("capabilities", postgresql.JSONB),
        ),
        [_PROVIDER],
    )


def downgrade() -> None:
    op.execute("DELETE FROM integration_provider WHERE slug = 'sip'")
