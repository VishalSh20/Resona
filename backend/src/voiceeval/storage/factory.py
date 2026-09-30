"""Object storage factory.

Selects the local or S3 implementation from ``OBJECT_STORAGE_MODE`` and exposes
a single process-wide :class:`ObjectStore` so media never streams through
PostgreSQL.
"""

from __future__ import annotations

from voiceeval.core.config import get_settings
from voiceeval.storage.local import LocalObjectStore
from voiceeval.storage.s3 import S3ObjectStore

_store = None


def get_object_store():
    global _store
    if _store is None:
        settings = get_settings()
        if settings.object_storage_mode == "s3":
            _store = S3ObjectStore(settings=settings)
        else:
            _store = LocalObjectStore(settings.local_object_storage_path)
    return _store


def set_object_store(store) -> None:
    global _store
    _store = store


__all__ = ["get_object_store", "set_object_store"]
