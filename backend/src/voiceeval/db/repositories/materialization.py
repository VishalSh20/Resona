"""Materialized runtime objects: turns, tool calls, state transitions.

These are derived from the append-only runtime-event log and are therefore
rebuildable. The repository offers the small set of operations the materializer
needs (append a transition, create/update a turn, create/update a tool call).
"""

from __future__ import annotations

from sqlalchemy import func, select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import runtime
from voiceeval.db.repositories.base import Repository


class MaterializationRepository(Repository):
    async def add_state_transition(
        self,
        call_attempt_id: str,
        *,
        sequence_no: int,
        state_path: str,
        previous_value: dict | None = None,
        new_value: dict | None = None,
        trigger_type: str | None = None,
        trigger_event_id: str | None = None,
    ) -> runtime.StateTransition:
        transition = runtime.StateTransition(
            id=new_id(EntityKind.STATE),
            call_attempt_id=call_attempt_id,
            sequence_no=sequence_no,
            state_path=state_path,
            previous_value=previous_value,
            new_value=new_value,
            trigger_type=trigger_type,
            trigger_event_id=trigger_event_id,
        )
        self._session.add(transition)
        await self._session.flush()
        return transition

    async def next_state_sequence_no(self, call_attempt_id: str) -> int:
        result = await self._session.execute(
            select(
                func.coalesce(func.max(runtime.StateTransition.sequence_no), 0)
            ).where(runtime.StateTransition.call_attempt_id == call_attempt_id)
        )
        return int(result.scalar_one()) + 1

    async def list_state_transitions(
        self, call_attempt_id: str
    ) -> list[runtime.StateTransition]:
        result = await self._session.execute(
            select(runtime.StateTransition)
            .where(runtime.StateTransition.call_attempt_id == call_attempt_id)
            .order_by(runtime.StateTransition.sequence_no)
        )
        return list(result.scalars().all())

    async def create_turn(
        self,
        call_attempt_id: str,
        *,
        sequence_no: int,
        speaker: str,
        turn_id: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        reference_text: str | None = None,
        observed_text: str | None = None,
        transcript_source: str | None = None,
    ) -> runtime.CallTurn:
        turn = runtime.CallTurn(
            id=turn_id or new_id(EntityKind.TURN),
            call_attempt_id=call_attempt_id,
            sequence_no=sequence_no,
            speaker=speaker,
            start_ms=start_ms,
            end_ms=end_ms,
            reference_text=reference_text,
            observed_text=observed_text,
            transcript_source=transcript_source,
        )
        self._session.add(turn)
        await self._session.flush()
        return turn

    async def get_turn(self, turn_id: str) -> runtime.CallTurn | None:
        return await self._session.get(runtime.CallTurn, turn_id)

    async def turn_exists(self, turn_id: str) -> bool:
        return (await self._session.get(runtime.CallTurn, turn_id)) is not None

    async def update_turn(self, turn: runtime.CallTurn, **fields) -> runtime.CallTurn:
        for key, value in fields.items():
            if value is not None:
                setattr(turn, key, value)
        await self._session.flush()
        return turn

    async def latest_turn(self, call_attempt_id: str) -> runtime.CallTurn | None:
        result = await self._session.execute(
            select(runtime.CallTurn)
            .where(runtime.CallTurn.call_attempt_id == call_attempt_id)
            .order_by(runtime.CallTurn.sequence_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_turn_sequence_no(self, call_attempt_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(runtime.CallTurn.sequence_no), 0)).where(
                runtime.CallTurn.call_attempt_id == call_attempt_id
            )
        )
        return int(result.scalar_one()) + 1

    async def list_turns(self, call_attempt_id: str) -> list[runtime.CallTurn]:
        result = await self._session.execute(
            select(runtime.CallTurn)
            .where(runtime.CallTurn.call_attempt_id == call_attempt_id)
            .order_by(runtime.CallTurn.sequence_no)
        )
        return list(result.scalars().all())

    async def create_tool_call(
        self,
        call_attempt_id: str,
        *,
        ordinal: int,
        tool_name: str,
        arguments: dict | None = None,
        status: str | None = None,
        source: str | None = None,
        start_ms: int | None = None,
    ) -> runtime.ToolCall:
        tool = runtime.ToolCall(
            id=new_id(EntityKind.TOOL),
            call_attempt_id=call_attempt_id,
            ordinal=ordinal,
            tool_name=tool_name,
            arguments=arguments,
            status=status,
            source=source,
            start_ms=start_ms,
        )
        self._session.add(tool)
        await self._session.flush()
        return tool

    async def latest_tool_call(self, call_attempt_id: str) -> runtime.ToolCall | None:
        result = await self._session.execute(
            select(runtime.ToolCall)
            .where(runtime.ToolCall.call_attempt_id == call_attempt_id)
            .order_by(runtime.ToolCall.ordinal.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_tool_call(
        self, tool: runtime.ToolCall, **fields
    ) -> runtime.ToolCall:
        for key, value in fields.items():
            if value is not None:
                setattr(tool, key, value)
        await self._session.flush()
        return tool

    async def next_tool_ordinal(self, call_attempt_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(runtime.ToolCall.ordinal), 0)).where(
                runtime.ToolCall.call_attempt_id == call_attempt_id
            )
        )
        return int(result.scalar_one()) + 1

    async def list_tool_calls(self, call_attempt_id: str) -> list[runtime.ToolCall]:
        result = await self._session.execute(
            select(runtime.ToolCall)
            .where(runtime.ToolCall.call_attempt_id == call_attempt_id)
            .order_by(runtime.ToolCall.ordinal)
        )
        return list(result.scalars().all())
