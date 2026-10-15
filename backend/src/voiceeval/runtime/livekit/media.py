"""Persist attempt recordings to object storage and record their metadata.

The caller job owns the audio boundary, so it captures the caller/agent tracks
in-process and uploads the sealed captures (mono) plus the stereo call recording
to the configured object store, then writes a ``media_artifact`` row per
representation with its hash, size, sample rate, channels and duration.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.repositories.media import MediaArtifactRepository
from voiceeval.runtime.media.recorder import MediaArtifactRecord
from voiceeval.storage import get_object_store

MediaSink = Callable[[list[MediaArtifactRecord]], Awaitable[int]]

_CONTENT_TYPE = "audio/wav"


def media_object_key(attempt_id: str, record: MediaArtifactRecord) -> str:
    extension = "wav" if record.format == "wav" else record.format
    return (
        f"media/{attempt_id}/{record.track}-{record.representation}-"
        f"{record.sha256[:12]}.{extension}"
    )


async def persist_media_records(
    session: AsyncSession,
    attempt_id: str,
    records: list[MediaArtifactRecord],
) -> int:
    """Upload each capture and record its artifact metadata. Returns the count."""
    repo = MediaArtifactRepository(session)
    store = get_object_store()

    async def _put(record: MediaArtifactRecord) -> tuple[MediaArtifactRecord, str | None]:
        if not record.data:
            return record, None
        # The store's put is synchronous (boto3); run it off the event loop so a
        # slow upload neither blocks audio/turn handling nor stalls the job.
        uri = await asyncio.to_thread(
            store.put,
            media_object_key(attempt_id, record),
            record.data,
            content_type=_CONTENT_TYPE,
        )
        return record, uri

    # Upload in parallel: each put is latency-bound (~1-5s to the bucket), and the
    # call job must finish before LiveKit's hard-coded shutdown grace ends.
    uploaded = await asyncio.gather(*(_put(record) for record in records))

    stored = 0
    for record, object_uri in uploaded:
        await repo.record_artifact(attempt_id, record, object_uri=object_uri)
        stored += 1
    await session.commit()
    return stored


def build_media_sink(session: AsyncSession, attempt_id: str) -> MediaSink:
    async def _sink(records: list[MediaArtifactRecord]) -> int:
        return await persist_media_records(session, attempt_id, records)

    return _sink


__all__ = [
    "MediaSink",
    "build_media_sink",
    "media_object_key",
    "persist_media_records",
]
