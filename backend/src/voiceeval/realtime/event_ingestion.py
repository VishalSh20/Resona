"""Runtime event ingestion.

Appends raw events to the append-only ``runtime_event`` log, enforcing the two
documented deduplication rules: a sequence number never repeats within an
attempt, and a provider event id never repeats for a source. Duplicates are
safely ignored, never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.ids import EntityKind, ensure_kind
from voiceeval.db.models import runtime
from voiceeval.db.repositories import MaterializationRepository, RuntimeEventRepository
from voiceeval.realtime.protocol import RuntimeEventEnvelope

STATUS_STORED = "stored"
STATUS_DUPLICATE_SEQUENCE = "duplicate_sequence"
STATUS_DUPLICATE_PROVIDER = "duplicate_provider"


@dataclass
class IngestionResult:
    status: str
    event: runtime.RuntimeEvent | None = None

    @property
    def stored(self) -> bool:
        return self.status == STATUS_STORED


class RuntimeEventIngestor:
    def __init__(self, session: AsyncSession) -> None:
        self._events = RuntimeEventRepository(session)
        self._materialized = MaterializationRepository(session)

    async def ingest(self, envelope: RuntimeEventEnvelope) -> IngestionResult:
        if await self._events.event_exists(
            envelope.call_attempt_id, envelope.sequence
        ):
            return IngestionResult(STATUS_DUPLICATE_SEQUENCE)

        if envelope.provider_event_id and await self._events.provider_event_exists(
            envelope.source, envelope.provider_event_id
        ):
            return IngestionResult(STATUS_DUPLICATE_PROVIDER)

        ensure_kind(envelope.event_id, EntityKind.EVENT)

        wall_clock = envelope.wall_clock
        if wall_clock.tzinfo is None:
            wall_clock = wall_clock.replace(tzinfo=timezone.utc)

        # The turn FK is only populated when the referenced CallTurn has already
        # been materialized; the canonical turn reference is retained in payload
        # by the runner, so nothing is lost if the turn arrives later.
        turn_id = None
        if envelope.turn_id and await self._materialized.turn_exists(envelope.turn_id):
            turn_id = envelope.turn_id

        event = await self._events.add_event(
            event_id=envelope.event_id,
            call_attempt_id=envelope.call_attempt_id,
            sequence_no=envelope.sequence,
            event_type=envelope.type,
            source=envelope.source,
            monotonic_ms=envelope.monotonic_ms,
            wall_clock_at=wall_clock,
            payload=envelope.payload,
            media_timestamp=envelope.media_timestamp,
            turn_id=turn_id,
            provider_event_id=envelope.provider_event_id,
        )
        return IngestionResult(STATUS_STORED, event=event)
