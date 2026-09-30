"""Materialize canonical runtime events into derived domain objects.

Raw events are append-only and canonical events are rebuildable, so every
materialized object here can be reconstructed from the event log. This covers
caller state transitions, call turns and tool calls; language and further
derived events are added as the caller runtime emits them (Prompt 6/7).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.models import runtime
from voiceeval.db.repositories import MaterializationRepository
from voiceeval.realtime.protocol import RuntimeEventEnvelope

# Tool event types that update an existing tool call rather than creating one.
_TOOL_UPDATE_TYPES = {"tool.call.args", "tool.call.result", "tool.call.end"}


def _json_object(value: Any) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"patch": value}
    return {"value": value}


class EventMaterializer:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MaterializationRepository(session)

    async def materialize(self, envelope: RuntimeEventEnvelope) -> list[object]:
        event_type = envelope.type
        payload = envelope.payload or {}

        if event_type.startswith("caller."):
            return [await self._state_transition(envelope, payload)]
        if event_type == "turn.start":
            turn = await self._turn_start(envelope, payload)
            return [turn] if turn is not None else []
        if event_type == "turn.end":
            turn = await self._turn_update(envelope, payload)
            return [turn] if turn is not None else []
        if event_type == "tool.call.start":
            return [await self._tool_start(envelope, payload)]
        if event_type in _TOOL_UPDATE_TYPES:
            tool = await self._tool_update(envelope, payload)
            return [tool] if tool is not None else []
        return []

    async def _state_transition(
        self, envelope: RuntimeEventEnvelope, payload: dict
    ) -> runtime.StateTransition:
        sequence_no = await self._repo.next_state_sequence_no(
            envelope.call_attempt_id
        )
        state_path = (
            payload.get("state_path") or payload.get("path") or envelope.type
        )
        return await self._repo.add_state_transition(
            envelope.call_attempt_id,
            sequence_no=sequence_no,
            state_path=state_path,
            previous_value=_json_object(
                payload.get("previous") if "previous" in payload else payload.get("from")
            ),
            new_value=_json_object(
                payload.get("new")
                if "new" in payload
                else payload.get("to") or payload.get("patch")
            ),
            trigger_type="runtime_event",
            trigger_event_id=envelope.event_id,
        )

    async def _turn_start(
        self, envelope: RuntimeEventEnvelope, payload: dict
    ) -> runtime.CallTurn | None:
        turn_id = payload.get("turn_id") or envelope.turn_id
        if turn_id and await self._repo.turn_exists(turn_id):
            return None
        sequence_no = payload.get("sequence_no")
        if sequence_no is None:
            sequence_no = await self._repo.next_turn_sequence_no(
                envelope.call_attempt_id
            )
        return await self._repo.create_turn(
            envelope.call_attempt_id,
            sequence_no=int(sequence_no),
            speaker=payload.get("speaker") or "agent",
            turn_id=turn_id,
            start_ms=envelope.monotonic_ms,
            reference_text=payload.get("reference_text"),
            observed_text=payload.get("observed_text"),
            transcript_source=payload.get("transcript_source"),
        )

    async def _turn_update(
        self, envelope: RuntimeEventEnvelope, payload: dict
    ) -> runtime.CallTurn | None:
        turn_id = envelope.turn_id or payload.get("turn_id")
        turn = await self._repo.get_turn(turn_id) if turn_id else None
        if turn is None:
            turn = await self._repo.latest_turn(envelope.call_attempt_id)
        if turn is None:
            return None
        return await self._repo.update_turn(
            turn,
            end_ms=envelope.monotonic_ms,
            observed_text=payload.get("observed_text"),
            reference_text=payload.get("reference_text"),
            transcript_source=payload.get("transcript_source"),
        )

    async def _tool_start(
        self, envelope: RuntimeEventEnvelope, payload: dict
    ) -> runtime.ToolCall:
        ordinal = payload.get("ordinal")
        if ordinal is None:
            ordinal = await self._repo.next_tool_ordinal(envelope.call_attempt_id)
        return await self._repo.create_tool_call(
            envelope.call_attempt_id,
            ordinal=int(ordinal),
            tool_name=payload.get("tool_name") or "unknown",
            arguments=payload.get("arguments"),
            status=payload.get("status") or "pending",
            source=envelope.source,
            start_ms=envelope.monotonic_ms,
        )

    async def _tool_update(
        self, envelope: RuntimeEventEnvelope, payload: dict
    ) -> runtime.ToolCall | None:
        tool = await self._repo.latest_tool_call(envelope.call_attempt_id)
        if tool is None:
            return None
        return await self._repo.update_tool_call(
            tool,
            arguments=payload.get("arguments"),
            result=payload.get("result"),
            status=payload.get("status"),
            end_ms=envelope.monotonic_ms if envelope.type == "tool.call.end" else None,
        )
