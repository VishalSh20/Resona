"""Media artifact persistence.

Only originals are written here; derived representations reference the original
they came from. Records carry the content hash so a capture can be verified
independently of the object store.
"""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import runtime
from voiceeval.db.repositories.base import Repository
from voiceeval.runtime.media.recorder import MediaArtifactRecord


class MediaArtifactRepository(Repository):
    async def record_artifact(
        self,
        call_attempt_id: str,
        record: MediaArtifactRecord,
        *,
        artifact_id: str | None = None,
        object_uri: str | None = None,
    ) -> runtime.MediaArtifact:
        artifact = runtime.MediaArtifact(
            id=artifact_id or new_id(EntityKind.MEDIA),
            call_attempt_id=call_attempt_id,
            track=record.track,
            representation=record.representation,
            format=record.format,
            codec="pcm_s16le" if record.format == "wav" else record.format,
            sample_rate=record.sample_rate,
            channels=record.channels,
            duration_ms=record.duration_ms,
            clock_domain=record.clock_domain,
            object_uri=object_uri,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def get_artifact(self, artifact_id: str) -> runtime.MediaArtifact:
        return await self._get(runtime.MediaArtifact, artifact_id, name="media artifact")

    async def list_artifacts(self, call_attempt_id: str) -> list[runtime.MediaArtifact]:
        result = await self._session.execute(
            select(runtime.MediaArtifact).where(
                runtime.MediaArtifact.call_attempt_id == call_attempt_id
            )
        )
        return list(result.scalars().all())
