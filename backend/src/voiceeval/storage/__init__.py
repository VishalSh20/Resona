"""Object storage abstraction.

Media and large artifacts are kept out of PostgreSQL. The control plane talks to
an :class:`ObjectStore` protocol; ``local`` and ``s3`` implementations are
selected via ``OBJECT_STORAGE_MODE``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from voiceeval.storage.factory import get_object_store, set_object_store
from voiceeval.storage.local import LOCAL_URI_SCHEME, LocalObjectStore
from voiceeval.storage.s3 import S3ObjectStore
from voiceeval.storage.signing import (
    DEFAULT_EXPIRES_SECONDS,
    MEDIA_BLOB_PATH,
    sign_media_key,
    signed_media_path,
    verify_media_key,
)


@runtime_checkable
class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...
    def get(self, key: str) -> bytes: ...
    def url(self, key: str, *, expires_in_seconds: int = ...) -> str: ...


__all__ = [
    "DEFAULT_EXPIRES_SECONDS",
    "LOCAL_URI_SCHEME",
    "MEDIA_BLOB_PATH",
    "LocalObjectStore",
    "ObjectStore",
    "S3ObjectStore",
    "get_object_store",
    "set_object_store",
    "sign_media_key",
    "signed_media_path",
    "verify_media_key",
]
