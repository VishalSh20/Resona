"""S3-compatible object store (MinIO in the local stack).

Uses presigned URLs so media never streams through the API or PostgreSQL. The
``boto3`` dependency is imported lazily: the local backend works without it, and
selecting S3 without it installed fails loudly rather than silently.
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import DependencyUnavailableError

DEFAULT_PRESIGN_SECONDS = 300


class S3ObjectStore:
    def __init__(
        self,
        *,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        self._bucket = bucket or settings.s3_bucket
        self._endpoint_url = endpoint_url or settings.s3_endpoint_url
        self._region = region or settings.s3_region
        self._access_key = access_key or settings.s3_access_key
        self._secret_key = secret_key or settings.s3_secret_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise DependencyUnavailableError(
                "OBJECT_STORAGE_MODE=s3 requires the 'boto3' package"
            ) from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            # Parallel uploads need a pool wider than the default; bounded
            # timeouts + a couple of retries recover a transient DNS/network blip
            # without hanging the call job past its shutdown grace.
            config=Config(
                max_pool_connections=32,
                connect_timeout=5,
                read_timeout=20,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        return self._client

    def warm(self) -> None:
        """Eagerly build the client so the first upload does not pay the
        botocore import + TLS handshake (which can exceed the job's exit grace)."""
        self._get_client()

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else None
        self._get_client().put_object(
            Bucket=self._bucket, Key=key, Body=data, **(extra or {})
        )
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        response = self._get_client().get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def url(
        self, key: str, *, expires_in_seconds: int = DEFAULT_PRESIGN_SECONDS
    ) -> str:
        return self._get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )


__all__ = ["DEFAULT_PRESIGN_SECONDS", "S3ObjectStore"]
