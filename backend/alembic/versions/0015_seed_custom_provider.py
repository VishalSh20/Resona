"""Seed the ``custom`` (generic WebSocket) integration provider.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-15

A "custom" agent is any agent reached over a raw WebSocket endpoint supplied by
the user (``wss://...``). It needs no provider account credentials; the adapter
(``voiceeval.integrations.custom.CustomAdapter``) has an empty credential spec,
so a target can be created against a "custom" account and the reachable URL
attached as a client-supplied websocket connection. No schema change is needed
— only the provider row so targets can be created against it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVIDER = {
    "id": "prov_custom",
    "slug": "custom",
    "display_name": "Custom / WebSocket",
    "capabilities": {"websocket": True},
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
    op.execute("DELETE FROM integration_provider WHERE slug = 'custom'")