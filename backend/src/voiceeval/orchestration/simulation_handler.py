"""Simulation execution handler.

A ``Run`` of a ``Simulation`` is executed by dispatching one logical call per
``RunEvaluator`` (1 evaluator = 1 call). This module is the seam that owns that
lifecycle: it expands the run, dispatches the calls **in capacity-aware batches**
(so a run with many evaluators never opens more concurrent calls than the target
or the deployment can absorb), and emits live status/progress events for the UI.

The caller itself is still spawned by the existing dispatcher
(``runtime.dispatch.get_dispatcher``); this handler only decides *when* and *how
many* calls to hand over. Selection mirrors the other pluggable seams
(``trigger``, ``dispatch``): a process-wide singleton with ``get``/``set``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.config import get_settings
from voiceeval.db.repositories import CallRunRepository, RunRepository
from voiceeval.domain.enums import CallRunStatus
from voiceeval.orchestration.executor import ExecutionOrchestrator
from voiceeval.orchestration.progress import run_progress_payload
from voiceeval.realtime.pubsub import (
    CALL_RUN_STATUS_CHANGED,
    RUN_PROGRESS,
    publish_run_event,
)


@runtime_checkable
class SimulationHandler(Protocol):
    async def start(self, session: AsyncSession, run_id: str) -> None: ...

    async def schedule(self, session: AsyncSession, run_id: str) -> None: ...


class BatchedSimulationHandler:
    """Default handler: expand the run, then top up dispatches to capacity.

    Capacity is the deployment/target limit already used by the LiveKit admission
    controller (``livekit_max_concurrent_calls`` / ``livekit_max_concurrent_per_target``).
    A run has a single target revision, so the per-target limit is enforced as the
    per-run limit here; the dispatcher's admission check remains the hard backstop.
    """

    def __init__(
        self,
        *,
        max_concurrent_calls: int | None = None,
        max_concurrent_per_target: int | None = None,
        max_attempts_per_run: int | None = None,
    ) -> None:
        settings = get_settings()
        self._max_calls = max(
            1,
            max_concurrent_calls
            if max_concurrent_calls is not None
            else settings.livekit_max_concurrent_calls,
        )
        self._max_per_target = max(
            1,
            max_concurrent_per_target
            if max_concurrent_per_target is not None
            else settings.livekit_max_concurrent_per_target,
        )
        self._max_attempts = (
            max_attempts_per_run
            if max_attempts_per_run is not None
            else settings.max_attempts_per_run
        )

    async def start(self, session: AsyncSession, run_id: str) -> None:
        orchestrator = ExecutionOrchestrator(
            session, max_attempts_per_run=self._max_attempts
        )
        await orchestrator.begin_run(run_id)
        await session.commit()
        await self.schedule(session, run_id)

    async def schedule(self, session: AsyncSession, run_id: str) -> None:
        run = await RunRepository(session).get_run(run_id)
        repo = CallRunRepository(session)
        call_runs = await repo.list_runs(run_id)
        queued = [
            call_run
            for call_run in call_runs
            if call_run.status == CallRunStatus.QUEUED.value
        ]
        # Gate on the shared DB tally (global + per-target), not an in-process
        # counter: acquire happens in the worker but release happens in the API,
        # so a process-local counter would leak and starve every later dispatch.
        active_global = await repo.count_active()
        active_target = await repo.count_active(
            target_revision_id=run.target_revision_id
        )
        slots = min(
            self._max_calls - active_global,
            self._max_per_target - active_target,
        )
        chosen = queued[: max(0, slots)]

        # Mark the chosen call runs RUNNING and commit *before* enqueuing their
        # dispatch, so the RUNNING count is an accurate in-flight tally and
        # overlapping schedule passes can never over-dispatch.
        for call_run in chosen:
            await CallRunRepository(session).start_run(call_run)
        if chosen:
            await session.commit()

        from voiceeval.workers.enqueue import enqueue_execution_call_run

        for call_run in chosen:
            await enqueue_execution_call_run(call_run.id)
            await publish_run_event(
                run_id,
                CALL_RUN_STATUS_CHANGED,
                {
                    "run_id": run_id,
                    "call_run_id": call_run.id,
                    "run_evaluator_id": call_run.run_evaluator_id,
                    "status": call_run.status,
                },
            )
        await publish_run_event(
            run_id, RUN_PROGRESS, run_progress_payload(run_id, call_runs)
        )


_handler: SimulationHandler | None = None


def get_simulation_handler() -> SimulationHandler:
    global _handler
    if _handler is None:
        _handler = BatchedSimulationHandler()
    return _handler


def set_simulation_handler(handler: SimulationHandler | None) -> None:
    global _handler
    _handler = handler


__all__ = [
    "BatchedSimulationHandler",
    "SimulationHandler",
    "get_simulation_handler",
    "set_simulation_handler",
]
