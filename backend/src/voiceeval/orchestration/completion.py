"""Run completion detection (v0.4).

A Run is complete once every logical ``CallRun`` has reached a terminal status.
All-completed runs become ``COMPLETED``; anything else (infrastructure failures,
cancellations) becomes ``PARTIAL`` so the operator can resume the unfinished
work. Completion is the trigger for aggregation.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.repositories import CallRunRepository, RunRepository
from voiceeval.domain.enums import CallRunStatus, RunStatus
from voiceeval.realtime.pubsub import RUN_STATUS_CHANGED, publish_plan_event

_ACTIVE_CALL_RUN_STATUSES = {
    CallRunStatus.QUEUED.value,
    CallRunStatus.RUNNING.value,
}
_TERMINAL_RUN_STATUSES = {RunStatus.COMPLETED.value, RunStatus.CANCELLED.value}


class RunCompletionService:
    def __init__(self, session: AsyncSession) -> None:
        self._runs = RunRepository(session)
        self._call_runs = CallRunRepository(session)

    async def maybe_complete(self, run_id: str) -> RunStatus | None:
        """Return the terminal run status if the run just completed."""
        run = await self._runs.get_run(run_id)
        if run.status in _TERMINAL_RUN_STATUSES:
            return None
        if run.status not in {RunStatus.RUNNING.value, RunStatus.PARTIAL.value}:
            return None

        call_runs = await self._call_runs.list_runs(run_id)
        if not call_runs:
            return None
        if any(
            call_run.status in _ACTIVE_CALL_RUN_STATUSES for call_run in call_runs
        ):
            return None

        target = (
            RunStatus.COMPLETED
            if all(
                call_run.status == CallRunStatus.COMPLETED.value
                for call_run in call_runs
            )
            else RunStatus.PARTIAL
        )
        if run.status == target.value:
            return None
        await self._runs.transition_run(run, target)
        await publish_plan_event(
            run.id, RUN_STATUS_CHANGED, {"run_id": run.id, "status": run.status}
        )
        return target


__all__ = ["RunCompletionService"]
