"""Physical call-attempt persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import runtime
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import AttemptStatus, AttemptTerminalStatus
from voiceeval.domain.state_machines import transition_call_attempt


class CallAttemptRepository(Repository):
    async def create_attempt(
        self,
        *,
        call_run_id: str,
        execution_manifest_id: str,
        attempt_no: int | None = None,
        trace_id: str | None = None,
    ) -> runtime.CallAttempt:
        if attempt_no is None:
            attempt_no = await self._next_attempt_no(call_run_id)
        attempt = runtime.CallAttempt(
            id=new_id(EntityKind.ATTEMPT),
            call_run_id=call_run_id,
            attempt_no=attempt_no,
            execution_manifest_id=execution_manifest_id,
            status=AttemptStatus.QUEUED.value,
            trace_id=trace_id,
        )
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_attempt(self, attempt_id: str) -> runtime.CallAttempt:
        return await self._get(runtime.CallAttempt, attempt_id, name="call attempt")

    async def list_attempts(self, call_run_id: str) -> list[runtime.CallAttempt]:
        result = await self._session.execute(
            select(runtime.CallAttempt)
            .where(runtime.CallAttempt.call_run_id == call_run_id)
            .order_by(runtime.CallAttempt.attempt_no)
        )
        return list(result.scalars().all())

    async def transition_attempt(
        self,
        attempt: runtime.CallAttempt,
        target: AttemptStatus,
        *,
        terminal_status: AttemptTerminalStatus | None = None,
    ) -> runtime.CallAttempt:
        current = AttemptStatus(attempt.status)
        try:
            _, resolved_terminal = transition_call_attempt(
                current, target, terminal_status=terminal_status
            )
        except InvalidStateTransitionError:
            raise
        attempt.status = target.value
        if resolved_terminal is not None:
            attempt.terminal_status = resolved_terminal.value
        await self._session.flush()
        return attempt

    async def record_terminal(
        self,
        attempt: runtime.CallAttempt,
        *,
        terminal_status: AttemptTerminalStatus,
        failure_class: str | None = None,
        termination_reason: str | None = None,
        eligible: bool = False,
    ) -> runtime.CallAttempt:
        """Transition an attempt to TERMINAL and record its terminal class."""
        current = AttemptStatus(attempt.status)
        try:
            _, resolved_terminal = transition_call_attempt(
                current, AttemptStatus.TERMINAL, terminal_status=terminal_status
            )
        except InvalidStateTransitionError:
            raise
        attempt.status = AttemptStatus.TERMINAL.value
        attempt.terminal_status = resolved_terminal.value
        attempt.failure_class = failure_class
        attempt.termination_reason = termination_reason
        attempt.eligible_for_evaluation = eligible
        attempt.finished_at = utc_now()
        await self._session.flush()
        return attempt

    async def list_active_created_before(
        self, cutoff: datetime
    ) -> list[runtime.CallAttempt]:
        """Attempts still in a non-terminal status that were created before
        ``cutoff`` — used by the watchdog to reap attempts that never emitted a
        terminal event (a crashed/cancelled runner leaves no other trace)."""
        result = await self._session.execute(
            select(runtime.CallAttempt)
            .where(
                runtime.CallAttempt.status.in_(
                    (
                        AttemptStatus.QUEUED.value,
                        AttemptStatus.STARTING.value,
                        AttemptStatus.CONNECTING.value,
                        AttemptStatus.RUNNING.value,
                    )
                )
            )
            .where(runtime.CallAttempt.created_at < cutoff)
        )
        return list(result.scalars().all())

    async def _next_attempt_no(self, call_run_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(runtime.CallAttempt.attempt_no), 0)).where(
                runtime.CallAttempt.call_run_id == call_run_id
            )
        )
        return int(result.scalar_one()) + 1
