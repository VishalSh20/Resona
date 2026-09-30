"""In-process telemetry sink.

Used by the inline dispatcher: instead of streaming events over the control
WebSocket, it feeds them straight into the same ingestion and materialization
path the backend uses. The terminal ``attempt.terminal`` event is applied to the
attempt through the orchestrator, so an inline run is indistinguishable from a
dispatched one in the persisted event log.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.orchestration.terminal import record_terminal_event
from voiceeval.realtime.event_ingestion import RuntimeEventIngestor
from voiceeval.realtime.materializer import EventMaterializer
from voiceeval.realtime.protocol import RuntimeEventEnvelope
from voiceeval.runtime.events import CanonicalEvent

logger = logging.getLogger("voiceeval.runner.local")


class LocalTelemetrySink:
    def __init__(self, session: AsyncSession, *, attempt_id: str) -> None:
        self._session = session
        self._attempt_id = attempt_id
        self._ingestor = RuntimeEventIngestor(session)
        self._materializer = EventMaterializer(session)
        self.events: list[CanonicalEvent] = []
        self.closed = False

    async def connect(self) -> None:
        return None

    async def send_event(self, event: CanonicalEvent) -> None:
        self.events.append(event)
        envelope = RuntimeEventEnvelope(**event.to_envelope())
        result = await self._ingestor.ingest(envelope)
        if not result.stored:
            return
        await self._materializer.materialize(envelope)
        if event.type == "attempt.terminal":
            await record_terminal_event(
                self._session, self._attempt_id, event.payload or {}
            )
        await self._session.flush()

    async def heartbeat(self) -> None:
        return None

    async def next_control(self, timeout: float = 0.0) -> dict | None:
        return None

    async def close(self) -> None:
        self.closed = True
