"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata`` so
``alembic/env.py`` (and any autogenerate) sees the full schema. Keep support and
domain models imported here; no other side effects.
"""

from voiceeval.db.base import Base
from voiceeval.db.models import domain, results, runtime, support  # noqa: F401

__all__ = [
    "Base",
    "domain",
    "results",
    "runtime",
    "support",
]
