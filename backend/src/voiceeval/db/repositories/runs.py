"""Logical call-run persistence (v0.4).

A ``CallRun`` is one logical repetition of a ``RunEvaluator`` within a ``Run``.
It owns the physical ``CallAttempt``s that execute it; retries attach a new
attempt to the same call run, never a new logical sample.
"""

from __future__ import annotations

from sqlalchemy import func, select

from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain, runtime
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import CallRunStatus
from voiceeval.domain.state_machines import (
    reopen_call_run_for_retry,
    transition_call_run,
)


class CallRunRepository(Repository):
    async def create_run(
        self,
        *,
        run_id: str,
        run_evaluator_id: str,
        repetition_no: int,
        run_seed: str | None = None,
    ) -> runtime.CallRun:
        run = runtime.CallRun(
            id=new_id(EntityKind.CALL_RUN),
            run_id=run_id,
            run_evaluator_id=run_evaluator_id,
            repetition_no=repetition_no,
            run_seed=run_seed,
            status=CallRunStatus.QUEUED.value,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, call_run_id: str) -> runtime.CallRun:
        return await self._get(runtime.CallRun, call_run_id, name="call run")

    async def list_runs(self, run_id: str) -> list[runtime.CallRun]:
        result = await self._session.execute(
            select(runtime.CallRun)
            .where(runtime.CallRun.run_id == run_id)
            .order_by(runtime.CallRun.repetition_no)
        )
        return list(result.scalars().all())

    async def list_runs_for_evaluator(
        self, run_id: str, run_evaluator_id: str
    ) -> list[runtime.CallRun]:
        result = await self._session.execute(
            select(runtime.CallRun)
            .where(runtime.CallRun.run_id == run_id)
            .where(runtime.CallRun.run_evaluator_id == run_evaluator_id)
            .order_by(runtime.CallRun.repetition_no)
        )
        return list(result.scalars().all())

    async def transition_run(
        self, run: runtime.CallRun, target: CallRunStatus
    ) -> runtime.CallRun:
        current = CallRunStatus(run.status)
        try:
            transition_call_run(current, target)
        except InvalidStateTransitionError:
            raise
        run.status = target.value
        await self._session.flush()
        return run

    async def start_run(self, run: runtime.CallRun) -> runtime.CallRun:
        """Transition a queued call run to RUNNING and stamp its start time."""
        current = CallRunStatus(run.status)
        try:
            transition_call_run(current, CallRunStatus.RUNNING)
        except InvalidStateTransitionError:
            raise
        run.status = CallRunStatus.RUNNING.value
        if run.started_at is None:
            run.started_at = utc_now()
        await self._session.flush()
        return run

    async def finish_run(
        self,
        run: runtime.CallRun,
        target: CallRunStatus,
        *,
        selected_attempt_id: str | None = None,
    ) -> runtime.CallRun:
        """Transition a call run to a terminal status and record completion."""
        current = CallRunStatus(run.status)
        try:
            transition_call_run(current, target)
        except InvalidStateTransitionError:
            raise
        run.status = target.value
        if selected_attempt_id is not None:
            run.selected_attempt_id = selected_attempt_id
        run.finished_at = utc_now()
        await self._session.flush()
        return run

    async def reopen_run(self, run: runtime.CallRun) -> runtime.CallRun:
        """Reopen an infrastructure-failed call run so a retry can attach."""
        reopen_call_run_for_retry(CallRunStatus(run.status))
        run.status = CallRunStatus.RUNNING.value
        run.finished_at = None
        await self._session.flush()
        return run

    async def count_active(self, *, target_revision_id: str | None = None) -> int:
        """In-flight call runs (RUNNING), globally or for one target revision.

        A call run is RUNNING for the whole call, so this is the cross-process
        in-flight tally the batcher gates on (the DB is shared; the in-process
        admission counter is not).
        """
        stmt = (
            select(func.count())
            .select_from(runtime.CallRun)
            .where(runtime.CallRun.status == CallRunStatus.RUNNING.value)
        )
        if target_revision_id is not None:
            stmt = stmt.join(
                domain.Run, domain.Run.id == runtime.CallRun.run_id
            ).where(domain.Run.target_revision_id == target_revision_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_runs_by_status(
        self, run_id: str, status: CallRunStatus
    ) -> list[runtime.CallRun]:
        result = await self._session.execute(
            select(runtime.CallRun)
            .where(runtime.CallRun.run_id == run_id)
            .where(runtime.CallRun.status == status.value)
            .order_by(runtime.CallRun.repetition_no)
        )
        return list(result.scalars().all())


__all__ = ["CallRunRepository"]
