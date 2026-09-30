"""Apply a runner-reported terminal outcome to an attempt.

When the runner streams an ``attempt.terminal`` event, the backend records the
attempt terminal class and applies the retry policy: an infrastructure failure
with budget remaining spawns the next physical attempt on the same logical
``CallRun``; a semantic outcome finalizes the call run. An eligible attempt then
triggers metric computation. This closes the loop between runner telemetry and
orchestration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.config import get_settings
from voiceeval.domain.enums import AttemptTerminalStatus
from voiceeval.orchestration.retry import ACTION_RETRY
from voiceeval.orchestration.trigger import get_evaluation_trigger

if TYPE_CHECKING:
    from voiceeval.orchestration.executor import TerminalOutcome

logger = logging.getLogger("voiceeval.orchestration")


async def record_terminal_event(
    session: AsyncSession, attempt_id: str, payload: dict
) -> "TerminalOutcome":
    from voiceeval.orchestration.executor import ExecutionOrchestrator

    terminal_status = AttemptTerminalStatus(
        payload.get("terminal_status") or AttemptTerminalStatus.FAILED.value
    )
    eligible = bool(payload.get("eligible", False))
    orchestrator = ExecutionOrchestrator(
        session, max_attempts_per_run=get_settings().max_attempts_per_run
    )
    outcome = await orchestrator.record_attempt_terminal(
        attempt_id,
        terminal_status=terminal_status,
        failure_class=payload.get("failure_class"),
        termination_reason=payload.get("reason"),
        eligible=eligible,
    )
    try:
        await get_evaluation_trigger().on_attempt_terminal(
            attempt_id,
            eligible=eligible,
            call_run_id=outcome.call_run_id,
            run_id=outcome.run_id,
        )
    except Exception as exc:  # pragma: no cover - depends on live Redis
        logger.warning(
            "failed to trigger evaluation for attempt %s: %s", attempt_id, exc
        )
    await _maybe_complete_run(session, outcome)
    # Commit the terminal (and the freed slot) BEFORE triggering the next batch:
    # otherwise the schedule pass can run against uncommitted state, see the call
    # run still RUNNING, find no free slot and strand the remaining calls.
    await session.commit()
    await _schedule_next_batch(outcome)
    return outcome


async def _schedule_next_batch(outcome: "TerminalOutcome") -> None:
    """Top up the run's dispatch batch after a call run frees a slot.

    A retry keeps the same call run RUNNING, so no slot was freed; only a
    terminal (non-retry) outcome triggers a new scheduling pass.
    """
    if outcome.action == ACTION_RETRY or not outcome.run_id:
        return
    try:
        from voiceeval.workers.enqueue import enqueue_execution_schedule

        await enqueue_execution_schedule(outcome.run_id)
    except Exception as exc:  # pragma: no cover - depends on live Redis
        logger.warning(
            "failed to schedule next batch for run %s: %s", outcome.run_id, exc
        )


async def _maybe_complete_run(
    session: AsyncSession, outcome: TerminalOutcome
) -> None:
    """Detect run completion for every terminal call run, not only judged ones.

    A call run can become terminal without ever producing metrics (an ineligible
    stochastic attempt such as a conversation stall). Run completion must not
    depend on that: the logical sample is still finished, so the run has to reach
    COMPLETED/PARTIAL and aggregation has to run.
    """
    if outcome.action == ACTION_RETRY or not outcome.run_id:
        return
    try:
        from voiceeval.aggregation.engine import AggregationEngine
        from voiceeval.orchestration.completion import RunCompletionService
        from voiceeval.workers.enqueue import enqueue_aggregation

        run_status = await RunCompletionService(session).maybe_complete(outcome.run_id)
        if run_status is None:
            return
        if await AggregationEngine(session).is_run_evaluation_complete(outcome.run_id):
            await enqueue_aggregation(outcome.run_id)
    except Exception as exc:  # pragma: no cover - depends on live Redis
        logger.warning(
            "failed to evaluate run completion for %s: %s", outcome.run_id, exc
        )


__all__ = ["record_terminal_event"]
