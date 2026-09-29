"""Small shared column mixins.

Kept intentionally minimal: primary-key ids, and the two timestamp patterns the
domain uses. The id is a prefixed ULID string (see ``voiceeval.core.ids``), not
a database UUID — the prompt's global identifier contract overrides the raw
``UUID PK`` notation in the domain schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

# "prefix_" (max 10 chars) + ULID (26 chars) with headroom.
ID_LENGTH = 64


class IdMixin:
    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
