"""Local filesystem object store.

Media is kept out of PostgreSQL; a local object store writes bytes under a
configured root and hands out short-lived signed URLs so the API contract is the
same as the S3 backend's presigned URLs.
"""

from __future__ import annotations

from pathlib import Path

from voiceeval.core.errors import ResourceNotFoundError, ValidationError
from voiceeval.storage.signing import DEFAULT_EXPIRES_SECONDS, signed_media_path

LOCAL_URI_SCHEME = "local://"


class LocalObjectStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, key: str) -> Path:
        safe = _validate_key(key)
        return self._root / safe

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{LOCAL_URI_SCHEME}{_validate_key(key)}"

    def get(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.exists():
            raise ResourceNotFoundError(f"object '{key}' not found")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()

    def url(
        self, key: str, *, expires_in_seconds: int = DEFAULT_EXPIRES_SECONDS
    ) -> str:
        return signed_media_path(_validate_key(key), expires_in_seconds=expires_in_seconds)


def _validate_key(key: str) -> str:
    if not key:
        raise ValidationError("object key must not be empty")
    normalized = key[len(LOCAL_URI_SCHEME):] if key.startswith(LOCAL_URI_SCHEME) else key
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValidationError(f"unsafe object key '{key}'")
    return normalized


__all__ = ["LOCAL_URI_SCHEME", "LocalObjectStore"]
