"""Execution orchestration job handlers (v0.4, run-centric).

``execution.run.start`` transitions a queued Run to RUNNING and expands it into
logical call runs; ``execution.call_run.start`` freezes the manifest and spawns
the first physical attempt; ``execution.attempt.start`` transitions the attempt
and hands it to the runner (inline/subprocess/LiveKit depending on settings).
"""

from __future__ import annotations

from voiceeval.core.logging import bind_execution_context
from voiceeval.db.session import get_session_factory
from voiceeval.observability.tracing import span
from voiceeval.orchestration.executor import ExecutionOrchestrator
from voiceeval.orchestration.simulation_handler import get_simulation_handler
from voiceeval.runtime.dispatch import get_dispatcher
from voiceeval.workers.enqueue import enqueue_execution_attempt


async def execution_run_start(ctx: dict, run_id: str) -> str:
    factory = get_session_factory()
    async with factory() as session:
        with bind_execution_context(plan_id=run_id):
            with span("orchestration.run.start", run_id=run_id):
                # The simulation handler expands the run (1 evaluator = 1 call)
                # and dispatches the first capacity-bounded batch.
                await get_simulation_handler().start(session, run_id)
                await session.commit()
        return run_id


async def execution_run_schedule(ctx: dict, run_id: str) -> str:
    factory = get_session_factory()
    async with factory() as session:
        with bind_execution_context(plan_id=run_id):
            with span("orchestration.run.schedule", run_id=run_id):
                # Top up dispatches after a call frees a slot.
                await get_simulation_handler().schedule(session, run_id)
                await session.commit()
        return run_id


async def execution_call_run_start(ctx: dict, call_run_id: str) -> str:
    factory = get_session_factory()
    async with factory() as session:
        orchestrator = ExecutionOrchestrator(session)
        with span("orchestration.call_run.start", call_run_id=call_run_id):
            attempt = await orchestrator.start_call_run(call_run_id)
            await session.commit()
        await enqueue_execution_attempt(attempt.id)
        return attempt.id


async def execution_attempt_start(ctx: dict, attempt_id: str) -> str:
    factory = get_session_factory()
    async with factory() as session:
        orchestrator = ExecutionOrchestrator(session)
        attempt = await orchestrator.start_attempt(attempt_id)
        await session.commit()
        # Hand the attempt to a disposable runner: the runner connects to the
        # target, runs the caller loop and streams canonical events back over
        # the control WebSocket. The attempt lifecycle above is already durable.
        with span("orchestration.dispatch", attempt_id=attempt.id):
            await get_dispatcher().dispatch(attempt.id)
        return attempt.status


__all__ = [
    "execution_attempt_start",
    "execution_call_run_start",
    "execution_run_schedule",
    "execution_run_start",
]
