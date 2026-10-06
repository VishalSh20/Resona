"""Seed the canonical ``transport_type`` rows.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-04

``transport_type`` was created in 0008 but never seeded. The caller migration
resolves an ``agent_endpoint`` into a TargetLink by transport slug
(``room`` / ``sip`` / ``bridge``), so seed the canonical set up front.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRANSPORT_TYPES = [
    {"id": "transport_room", "slug": "room", "display_name": "LiveKit Room", "category": "webrtc"},
    {"id": "transport_sip", "slug": "sip", "display_name": "SIP", "category": "pstn"},
    {"id": "transport_bridge", "slug": "bridge", "display_name": "Protocol Bridge", "category": "websocket"},
    {"id": "transport_webrtc", "slug": "webrtc", "display_name": "WebRTC", "category": "webrtc"},
    {"id": "transport_websocket", "slug": "websocket", "display_name": "WebSocket", "category": "websocket"},
]


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "transport_type",
            sa.column("id", sa.String),
            sa.column("slug", sa.Text),
            sa.column("display_name", sa.Text),
            sa.column("category", sa.Text),
            sa.column("capabilities", postgresql.JSONB),
        ),
        [{**row, "capabilities": None} for row in _TRANSPORT_TYPES],
    )


def downgrade() -> None:
    slugs = ", ".join(f"'{row['slug']}'" for row in _TRANSPORT_TYPES)
    op.execute(f"DELETE FROM transport_type WHERE slug IN ({slugs})")
