"""Runtime-event persistence (append-only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.guards import ensure_runtime_event_append_only
from voiceeval.db.models import runtime
from voiceeval.db.repositories.base import Repository


class RuntimeEventRepository(Repository):
    async def add_event(
        self,
        *,
        call_attempt_id: str,
        sequence_no: int,
        event_type: str,
        source: str,
        monotonic_ms: int,
        wall_clock_at: datetime,
        payload: dict,
        event_id: str | None = None,
        media_timestamp: int | None = None,
        turn_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> runtime.RuntimeEvent:
        event = runtime.RuntimeEvent(
            id=event_id or new_id(EntityKind.EVENT),
            call_attempt_id=call_attempt_id,
            sequence_no=sequence_no,
            event_type=event_type,
            source=source,
            monotonic_ms=monotonic_ms,
            wall_clock_at=wall_clock_at,
            media_timestamp=media_timestamp,
            turn_id=turn_id,
            provider_event_id=provider_event_id,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_event(self, event_id: str) -> runtime.RuntimeEvent:
        return await self._get(runtime.RuntimeEvent, event_id, name="runtime event")

    async def list_events(
        self,
        call_attempt_id: str,
        *,
        limit: int = 1000,
        offset: int = 0,
        source: str | None = None,
        event_type: str | None = None,
        from_ms: int | None = None,
        to_ms: int | None = None,
    ) -> list[runtime.RuntimeEvent]:
        stmt = select(runtime.RuntimeEvent).where(
            runtime.RuntimeEvent.call_attempt_id == call_attempt_id
        )
        stmt = self._apply_filters(
            stmt, source=source, event_type=event_type, from_ms=from_ms, to_ms=to_ms
        )
        result = await self._session.execute(
            stmt.order_by(runtime.RuntimeEvent.sequence_no).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    def _apply_filters(
        stmt,
        *,
        source: str | None,
        event_type: str | None,
        from_ms: int | None,
        to_ms: int | None,
    ):
        if source:
            stmt = stmt.where(runtime.RuntimeEvent.source == source)
        if event_type:
            stmt = stmt.where(runtime.RuntimeEvent.event_type == event_type)
        if from_ms is not None:
            stmt = stmt.where(runtime.RuntimeEvent.monotonic_ms >= from_ms)
        if to_ms is not None:
            stmt = stmt.where(runtime.RuntimeEvent.monotonic_ms <= to_ms)
        return stmt

    async def event_exists(self, call_attempt_id: str, sequence_no: int) -> bool:
        """Whether an event with this ``(attempt, sequence)`` already exists."""
        result = await self._session.execute(
            select(runtime.RuntimeEvent.id)
            .where(runtime.RuntimeEvent.call_attempt_id == call_attempt_id)
            .where(runtime.RuntimeEvent.sequence_no == sequence_no)
            .limit(1)
        )
        return result.first() is not None

    async def count_events(
        self,
        call_attempt_id: str,
        *,
        source: str | None = None,
        event_type: str | None = None,
        from_ms: int | None = None,
        to_ms: int | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(runtime.RuntimeEvent)
            .where(runtime.RuntimeEvent.call_attempt_id == call_attempt_id)
        )
        stmt = self._apply_filters(
            stmt, source=source, event_type=event_type, from_ms=from_ms, to_ms=to_ms
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def provider_event_exists(self, source: str, provider_event_id: str) -> bool:
        """Whether this provider event id was already ingested for the source."""
        result = await self._session.execute(
            select(runtime.RuntimeEvent.id)
            .where(runtime.RuntimeEvent.source == source)
            .where(runtime.RuntimeEvent.provider_event_id == provider_event_id)
            .limit(1)
        )
        return result.first() is not None

    def ensure_append_only(self) -> None:
        """Runtime events are append-only; mutation/deletion is rejected."""
        ensure_runtime_event_append_only()
