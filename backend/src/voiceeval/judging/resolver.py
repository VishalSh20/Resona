"""Media resolver (spec §2.1).

Loads the ``media_artifact`` rows for the attempt, maps the three logical roles,
fetches the objects and validates them against Postgres and the WAV contract.
The judge never reconstructs or rewrites an S3 key — the ``object_uri`` stored
on the row is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.repositories import MediaArtifactRepository
from voiceeval.judging.stage0.integrity import IntegrityResult, validate_artifact
from voiceeval.judging.stage0.wav import WavData, WavDecodeError, decode_wav
from voiceeval.storage.factory import get_object_store

ROLES = ("caller_original", "agent_original", "mixed")


@dataclass
class ResolvedMedia:
    role: str
    row: Any | None
    object_uri: str | None
    sha256: str | None
    size_bytes: int | None
    sample_rate: int | None
    channels: int | None
    duration_ms: int | None
    format: str | None
    data: bytes | None
    wav: WavData | None
    integrity: IntegrityResult

    @property
    def available(self) -> bool:
        return self.wav is not None and self.integrity.ok


@dataclass
class MediaBundle:
    attempt_id: str
    media: dict[str, ResolvedMedia] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def get(self, role: str) -> ResolvedMedia | None:
        return self.media.get(role)

    @property
    def caller_original(self) -> ResolvedMedia | None:
        return self.media.get("caller_original")

    @property
    def agent_original(self) -> ResolvedMedia | None:
        return self.media.get("agent_original")

    @property
    def mixed(self) -> ResolvedMedia | None:
        return self.media.get("mixed")

    @property
    def complete(self) -> bool:
        return all(role in self.media for role in ROLES)


def _key_from_uri(object_uri: str) -> str:
    if "://" in object_uri:
        return object_uri.split("://", 1)[1]
    return object_uri


def _select(artifacts: list[Any], role: str) -> Any | None:
    if role == "caller_original":
        candidates = [a for a in artifacts if a.track == "caller" and a.representation == "original"]
    elif role == "agent_original":
        candidates = [a for a in artifacts if a.track == "agent" and a.representation == "original"]
    else:  # mixed
        candidates = [
            a for a in artifacts if a.track == "mixed" and a.representation in {"mixed", "original"}
        ]
    if not candidates:
        return None
    # Most recent wins if a capture was rewritten.
    return sorted(candidates, key=lambda a: a.created_at, reverse=True)[0]


class MediaResolver:
    def __init__(self, session: AsyncSession, *, store=None) -> None:
        self._session = session
        self._store = store or get_object_store()
        self._artifacts = MediaArtifactRepository(session)

    async def resolve(self, attempt_id: str) -> MediaBundle:
        rows = await self._artifacts.list_artifacts(attempt_id)
        bundle = MediaBundle(attempt_id=attempt_id)
        for role in ROLES:
            row = _select(rows, role)
            if row is None:
                bundle.errors.append(f"{role}: media_artifact row missing")
                continue
            data = self._fetch(row.object_uri)
            wav = None
            decode_error: str | None = None
            if data is not None:
                try:
                    wav = decode_wav(data)
                except WavDecodeError as exc:
                    decode_error = str(exc)
            integrity = validate_artifact(
                role,
                object_uri=row.object_uri,
                sha256=row.sha256,
                size_bytes=row.size_bytes,
                sample_rate=row.sample_rate,
                channels=row.channels,
                duration_ms=row.duration_ms,
                format_=row.format,
                data=data,
                wav=wav,
            )
            if decode_error:
                integrity.fail(decode_error)
            bundle.media[role] = ResolvedMedia(
                role=role,
                row=row,
                object_uri=row.object_uri,
                sha256=row.sha256,
                size_bytes=row.size_bytes,
                sample_rate=row.sample_rate,
                channels=row.channels,
                duration_ms=row.duration_ms,
                format=row.format,
                data=data,
                wav=wav,
                integrity=integrity,
            )
        return bundle

    def _fetch(self, object_uri: str | None) -> bytes | None:
        if not object_uri:
            return None
        try:
            return self._store.get(_key_from_uri(object_uri))
        except Exception:  # pragma: no cover - depends on live object store
            return None


__all__ = ["MediaBundle", "MediaResolver", "ResolvedMedia", "ROLES"]
