"""Runner control WebSocket.

Handles the ``WS /internal/v1/attempts/{attempt_id}/stream`` channel: runner
registration, heartbeats and runtime-event streaming. The protocol logic lives
in :class:`RunnerSession` so it can be exercised without a live socket; the
endpoint wires it to the transport and the connection registry.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import AuthorizationError, VoiceEvalError
from voiceeval.db.session import get_session_factory
from voiceeval.domain.enums import AttemptStatus
from voiceeval.orchestration.terminal import record_terminal_event
from voiceeval.realtime.event_ingestion import RuntimeEventIngestor
from voiceeval.realtime.heartbeat import get_heartbeat_registry
from voiceeval.realtime.materializer import EventMaterializer
from voiceeval.realtime.protocol import (
    RunnerHeartbeat,
    RunnerRegister,
    RuntimeEventMessage,
    build_event_ack,
    build_heartbeat_ack,
    parse_runner_message,
)
from voiceeval.realtime.registry import get_connection_registry
from voiceeval.realtime.runner_auth import authenticate_runner

logger = logging.getLogger("voiceeval.realtime")

WS_POLICY_VIOLATION = 1008

#: Runner-reported lifecycle status → attempt status.
_LIFECYCLE_STATUS = {
    "connecting": AttemptStatus.CONNECTING,
    "running": AttemptStatus.RUNNING,
}


class RunnerSession:
    """Protocol state for one runner connection."""

    def __init__(self, *, attempt_id: str, session: AsyncSession) -> None:
        self.attempt_id = attempt_id
        self._session = session
        self._ingestor = RuntimeEventIngestor(session)
        self._materializer = EventMaterializer(session)
        self.registered = False
        self.runner_id: str | None = None
        self.runner_version: str | None = None

    async def handle(self, raw: dict) -> list[dict]:
        message = parse_runner_message(raw)
        if isinstance(message, RunnerRegister):
            return await self._on_register(message)
        if isinstance(message, RunnerHeartbeat):
            return await self._on_heartbeat(message)
        if isinstance(message, RuntimeEventMessage):
            return await self._on_event(message)
        return []

    async def commit(self) -> None:
        await self._session.commit()

    async def _on_register(self, message: RunnerRegister) -> list[dict]:
        if message.attempt_id != self.attempt_id:
            raise AuthorizationError("register attempt_id does not match connection")
        self.registered = True
        self.runner_id = message.runner_id
        self.runner_version = message.runner_version
        return []

    async def _on_heartbeat(self, message: RunnerHeartbeat) -> list[dict]:
        get_heartbeat_registry().record(self.attempt_id)
        return [build_heartbeat_ack()]

    async def _on_event(self, message: RuntimeEventMessage) -> list[dict]:
        envelope = message.event
        if envelope.call_attempt_id != self.attempt_id:
            raise AuthorizationError(
                "runtime event attempt_id does not match connection"
            )
        result = await self._ingestor.ingest(envelope)
        if result.stored:
            await self._materializer.materialize(envelope)
            if envelope.type == "attempt.terminal":
                await self._apply_terminal(envelope)
            elif envelope.type == "attempt.lifecycle":
                await self._apply_lifecycle(envelope)
        # Acknowledge so the runner can drop the event from its replay buffer.
        return [build_event_ack(envelope.sequence)]

    async def _apply_lifecycle(self, envelope: RuntimeEventMessage) -> None:
        """Advance the attempt (starting → connecting → running)."""
        raw = (envelope.payload or {}).get("status")
        status = _LIFECYCLE_STATUS.get(str(raw))
        if status is None:
            return
        from voiceeval.orchestration.executor import ExecutionOrchestrator

        try:
            await ExecutionOrchestrator(self._session).apply_attempt_lifecycle(
                self.attempt_id, status
            )
        except VoiceEvalError as exc:
            logger.warning(
                "failed to apply lifecycle %s for attempt %s: %s",
                status.value,
                self.attempt_id,
                exc,
            )

    async def _apply_terminal(self, envelope: RuntimeEventMessage) -> None:
        """Apply a runner-reported terminal outcome to the attempt/run."""
        try:
            outcome = await record_terminal_event(
                self._session, self.attempt_id, envelope.payload or {}
            )
        except VoiceEvalError as exc:
            logger.warning(
                "failed to record terminal outcome for attempt %s: %s",
                self.attempt_id,
                exc,
            )
            return
        if outcome.next_attempt_id:
            try:
                from voiceeval.workers.enqueue import enqueue_execution_attempt

                await enqueue_execution_attempt(outcome.next_attempt_id)
            except Exception as exc:  # pragma: no cover - depends on live Redis
                logger.warning(
                    "failed to enqueue retry attempt %s: %s",
                    outcome.next_attempt_id,
                    exc,
                )
        # Any terminal state always deletes the room (this also hangs up any SIP
        # leg) — the cross-process hard-cleanup path (§4.1, §10).
        await self._delete_livekit_room()
        # Free the admission slot so the next attempt can be dispatched.
        from voiceeval.runtime.livekit.admission import get_admission_controller

        get_admission_controller().release(self.attempt_id)

    async def _delete_livekit_room(self) -> None:
        from voiceeval.core.config import get_settings

        if not get_settings().livekit_url:
            return
        try:
            from voiceeval.runtime.livekit.rooms import (
                LiveKitRoomManager,
                room_name_for_attempt,
            )

            await LiveKitRoomManager().delete_room(room_name_for_attempt(self.attempt_id))
        except Exception as exc:  # pragma: no cover - depends on LiveKit being up
            logger.debug("livekit room cleanup skipped for %s: %s", self.attempt_id, exc)


async def _read_loop(websocket: WebSocket, runner: RunnerSession) -> None:
    while True:
        try:
            raw = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except (ValueError, TypeError):
            await websocket.close(code=WS_POLICY_VIOLATION, reason="invalid JSON")
            return
        try:
            replies = await runner.handle(raw)
        except (VoiceEvalError, PydanticValidationError) as exc:
            await websocket.close(code=WS_POLICY_VIOLATION, reason=str(exc))
            return
        await runner.commit()
        for reply in replies:
            await websocket.send_json(reply)


async def _write_loop(websocket: WebSocket, outbox: asyncio.Queue) -> None:
    while True:
        message = await outbox.get()
        await websocket.send_json(message)


async def runner_stream(
    websocket: WebSocket, attempt_id: str, token: str | None = None
) -> None:
    try:
        authenticate_runner(token, attempt_id)
    except VoiceEvalError as exc:
        await websocket.close(code=WS_POLICY_VIOLATION, reason=exc.code)
        return

    await websocket.accept()
    registry = get_connection_registry()
    outbox: asyncio.Queue = asyncio.Queue()
    registry.register(attempt_id, outbox)

    factory = get_session_factory()
    try:
        async with factory() as session:
            runner = RunnerSession(attempt_id=attempt_id, session=session)
            reader = asyncio.create_task(_read_loop(websocket, runner))
            writer = asyncio.create_task(_write_loop(websocket, outbox))
            done, pending = await asyncio.wait(
                {reader, writer}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    logger.warning("runner stream error: %s", exc)
    except WebSocketDisconnect:
        pass
    finally:
        registry.unregister(attempt_id, outbox)
