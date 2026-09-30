"""Short-lived signed URLs for local object storage.

The S3 backend hands out presigned URLs natively. Local storage needs an
equivalent so the media URL contract is identical regardless of backend: the
API returns a URL carrying an expiry and an HMAC signature, and the blob route
refuses anything unsigned or expired.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from voiceeval.core.config import get_settings
from voiceeval.core.errors import AuthorizationError

MEDIA_BLOB_PATH = "/api/v1/media/blob"
DEFAULT_EXPIRES_SECONDS = 300


def _secret() -> bytes:
    return get_settings().jwt_secret.encode("utf-8")


def _sign(key: str, expires_at: int) -> str:
    message = f"{key}|{expires_at}".encode("utf-8")
    digest = hmac.new(_secret(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def sign_media_key(
    key: str, *, expires_in_seconds: int = DEFAULT_EXPIRES_SECONDS, now: int | None = None
) -> tuple[int, str]:
    issued = int(now if now is not None else time.time())
    expires_at = issued + max(1, expires_in_seconds)
    return expires_at, _sign(key, expires_at)


def verify_media_key(
    key: str, *, expires_at: int, signature: str, now: int | None = None
) -> None:
    current = int(now if now is not None else time.time())
    if current > expires_at:
        raise AuthorizationError("media URL has expired")
    if not hmac.compare_digest(_sign(key, expires_at), signature):
        raise AuthorizationError("media URL signature is invalid")


def signed_media_path(
    key: str, *, expires_in_seconds: int = DEFAULT_EXPIRES_SECONDS, now: int | None = None
) -> str:
    expires_at, signature = sign_media_key(
        key, expires_in_seconds=expires_in_seconds, now=now
    )
    return f"{MEDIA_BLOB_PATH}?key={key}&exp={expires_at}&sig={signature}"


__all__ = [
    "DEFAULT_EXPIRES_SECONDS",
    "MEDIA_BLOB_PATH",
    "sign_media_key",
    "signed_media_path",
    "verify_media_key",
]
