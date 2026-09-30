"""Execution orchestrator (v0.4, run-centric).

Expands a ready ``Run`` into logical ``CallRun``s (one per RunEvaluator per
repetition), drives the run/call-run/attempt state machines, freezes the
execution manifest per call run, and applies the retry policy: infrastructure
failures spawn a new attempt on the same logical call run; semantic failures and
timeouts are recorded as valid outcomes, never retried.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.core.ids import new_plain_ulid
from voiceeval.db.models import domain, runtime
from voiceeval.db.repositories import (
    CallAttemptRepository,
    CallRunRepository,
    RunEvaluatorRepository,
    RunRepository,
)
from voiceeval.domain.enums import (
    AttemptFailureClass,
    AttemptStatus,
    AttemptTerminalStatus,
    CallRunStatus,
    RunStatus,
)
from voiceeval.orchestration.manifest_service import get_or_create_manifest_for_call_run
from voiceeval.orchestration.progress import run_progress_payload
from voiceeval.orchestration.retry import (
    ACTION_CANCELLED,
    ACTION_COMPLETED,
    ACTION_INFRASTRUCTURE_FAILED,
    ACTION_RETRY,
    derive_run_seed,
    resolve_attempt_termination,
)
from voiceeval.realtime.pubsub import (
    ATTEMPT_STATUS_CHANGED,
    CALL_RUN_STATUS_CHANGED,
    RUN_PROGRESS,
    RUN_STATUS_CHANGED,
    publish_plan_event,
)

#: One logical repetition per RunEvaluator by default. There is no repeat_count
#: in the v0.4 schema; this is the single place to widen it if that changes.
DEFAULT_REPETITIONS = 1


@dataclass
class TerminalOutcome:
    action: str
    run_status: str
    next_attempt_id: str | None = None
    call_run_id: str | None = None
    run_id: str | None = None


@dataclass
class ResumeOutcome:
    queued_call_run_ids: list[str] = field(default_factory=list)
    retry_attempt_ids: list[str] = field(default_factory=list)


class ExecutionOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        *,
        max_attempts_per_run: int = 3,
        repetitions: int = DEFAULT_REPETITIONS,
    ) -> None:
        self._session = session
        self._runs = RunRepository(session)
        self._evaluators = RunEvaluatorRepository(session)
        self._call_runs = CallRunRepository(session)
        self._attempts = CallAttemptRepository(session)
        self._max_attempts = max_attempts_per_run
        self._repetitions = max(1, repetitions)

    async def get_run(self, run_id: str) -> domain.Run:
        return await self._runs.get_run(run_id)

    @staticmethod
    async def _notify(run_id: str, event_type: str, data: dict) -> None:
        await publish_plan_event(run_id, event_type, data)

    async def mark_queued(self, run_id: str) -> domain.Run:
        run = await self._runs.get_run(run_id)
        if run.status == RunStatus.READY.value:
            await self._runs.transition_run(run, RunStatus.QUEUED)
        return run

    async def expand_call_runs(self, run: domain.Run) -> list[runtime.CallRun]:
        """Create one logical call run per RunEvaluator per repetition."""
        evaluators = await self._evaluators.list_evaluators(run.id)
        call_runs: list[runtime.CallRun] = []
        for evaluator in evaluators:
            for repetition_no in range(1, self._repetitions + 1):
                call_run = await self._call_runs.create_run(
                    run_id=run.id,
                    run_evaluator_id=evaluator.id,
                    repetition_no=repetition_no,
                    run_seed=derive_run_seed(run.id, evaluator.id, repetition_no),
                )
                call_runs.append(call_run)
        return call_runs

    async def ensure_call_runs(self, run: domain.Run) -> list[runtime.CallRun]:
        """Idempotent expansion: reuse existing call runs instead of duplicating."""
        existing = await self._call_runs.list_runs(run.id)
        if existing:
            return existing
        return await self.expand_call_runs(run)

    async def begin_run(self, run_id: str) -> list[str]:
        """Transition a queued run to RUNNING, expand it, return queued call runs."""
        run = await self._runs.get_run(run_id)
        if run.status == RunStatus.QUEUED.value:
            await self._runs.transition_run(run, RunStatus.RUNNING)
        call_runs = await self.ensure_call_runs(run)
        await self._notify(
            run.id, RUN_STATUS_CHANGED, {"run_id": run.id, "status": run.status}
        )
        return [
            call_run.id
            for call_run in call_runs
            if call_run.status == CallRunStatus.QUEUED.value
        ]

    async def start_call_run(self, call_run_id: str) -> runtime.CallAttempt:
        call_run = await self._call_runs.get_run(call_run_id)
        if call_run.status == CallRunStatus.QUEUED.value:
            await self._call_runs.start_run(call_run)
        run = await self._runs.get_run(call_run.run_id)
        evaluator = await self._evaluators.get_evaluator(call_run.run_evaluator_id)
        manifest = await get_or_create_manifest_for_call_run(
            self._session, call_run=call_run, run=run, evaluator=evaluator
        )
        await self._notify(
            run.id, RUN_STATUS_CHANGED, {"run_id": run.id, "status": run.status}
        )
        return await self._attempts.create_attempt(
            call_run_id=call_run.id,
            execution_manifest_id=manifest.id,
            trace_id=new_plain_ulid(),
        )

    async def start_attempt(self, attempt_id: str) -> runtime.CallAttempt:
        attempt = await self._attempts.get_attempt(attempt_id)
        if attempt.status == AttemptStatus.QUEUED.value:
            await self._attempts.transition_attempt(attempt, AttemptStatus.STARTING)
        call_run = await self._call_runs.get_run(attempt.call_run_id)
        await self._notify(
            call_run.run_id,
            ATTEMPT_STATUS_CHANGED,
            {
                "run_id": call_run.run_id,
                "call_run_id": call_run.id,
                "attempt_id": attempt.id,
                "status": attempt.status,
            },
        )
        await self._notify(
            call_run.run_id,
            RUN_PROGRESS,
            run_progress_payload(
                call_run.run_id, await self._call_runs.list_runs(call_run.run_id)
            ),
        )
        return attempt

    async def apply_attempt_lifecycle(
        self, attempt_id: str, status: AttemptStatus
    ) -> None:
        """Advance a live attempt (starting → connecting → running) from a
        runner-reported lifecycle signal. No-op on terminal or duplicate."""
        attempt = await self._attempts.get_attempt(attempt_id)
        if attempt.status in {status.value, AttemptStatus.TERMINAL.value}:
            return
        try:
            await self._attempts.transition_attempt(attempt, status)
        except InvalidStateTransitionError:
            return
        call_run = await self._call_runs.get_run(attempt.call_run_id)
        await self._notify(
            call_run.run_id,
            ATTEMPT_STATUS_CHANGED,
            {
                "run_id": call_run.run_id,
                "call_run_id": call_run.id,
                "attempt_id": attempt.id,
                "status": attempt.status,
            },
        )

    async def record_attempt_terminal(
        self,
        attempt_id: str,
        *,
        terminal_status: AttemptTerminalStatus,
        failure_class: str | None = None,
        termination_reason: str | None = None,
        eligible: bool = False,
    ) -> TerminalOutcome:
        attempt = await self._attempts.get_attempt(attempt_id)
        await self._attempts.record_terminal(
            attempt,
            terminal_status=terminal_status,
            failure_class=failure_class,
            termination_reason=termination_reason,
            eligible=eligible,
        )

        call_run = await self._call_runs.get_run(attempt.call_run_id)
        action = resolve_attempt_termination(
            terminal_status.value, failure_class, attempt.attempt_no, self._max_attempts
        )

        if action == ACTION_RETRY:
            next_attempt = await self._attempts.create_attempt(
                call_run_id=call_run.id,
                execution_manifest_id=attempt.execution_manifest_id,
                attempt_no=attempt.attempt_no + 1,
                trace_id=attempt.trace_id,
            )
            return TerminalOutcome(
                action=action,
                run_status=call_run.status,
                next_attempt_id=next_attempt.id,
                call_run_id=call_run.id,
                run_id=call_run.run_id,
            )

        if action == ACTION_CANCELLED:
            await self._call_runs.finish_run(call_run, CallRunStatus.CANCELLED)
        elif action == ACTION_INFRASTRUCTURE_FAILED:
            await self._call_runs.finish_run(
                call_run, CallRunStatus.INFRASTRUCTURE_FAILED
            )
        else:  # completed (success, timeout or semantic failure)
            await self._call_runs.finish_run(
                call_run, CallRunStatus.COMPLETED, selected_attempt_id=attempt.id
            )
        await self._notify(
            call_run.run_id,
            ATTEMPT_STATUS_CHANGED,
            {
                "run_id": call_run.run_id,
                "call_run_id": call_run.id,
                "attempt_id": attempt.id,
                "status": attempt.status,
                "terminal_status": attempt.terminal_status,
                "failure_class": attempt.failure_class,
            },
        )
        await self._notify(
            call_run.run_id,
            CALL_RUN_STATUS_CHANGED,
            {
                "run_id": call_run.run_id,
                "call_run_id": call_run.id,
                "run_evaluator_id": call_run.run_evaluator_id,
                "status": call_run.status,
            },
        )
        await self._notify(
            call_run.run_id,
            RUN_PROGRESS,
            run_progress_payload(
                call_run.run_id, await self._call_runs.list_runs(call_run.run_id)
            ),
        )
        return TerminalOutcome(
            action=action,
            run_status=call_run.status,
            call_run_id=call_run.id,
            run_id=call_run.run_id,
        )

    async def retry_call_run(self, call_run_id: str) -> runtime.CallAttempt:
        """Attach a new physical attempt to an infrastructure-failed call run.

        The logical call run (the statistical sample) is preserved: only its
        status is reopened and a fresh attempt is created.
        """
        call_run = await self._call_runs.get_run(call_run_id)
        if call_run.status == CallRunStatus.INFRASTRUCTURE_FAILED.value:
            await self._call_runs.reopen_run(call_run)
        elif call_run.status != CallRunStatus.RUNNING.value:
            raise InvalidStateTransitionError(
                f"call run '{call_run_id}' is '{call_run.status}', only an "
                "'infrastructure_failed' call run can be retried"
            )
        run = await self._runs.get_run(call_run.run_id)
        evaluator = await self._evaluators.get_evaluator(call_run.run_evaluator_id)
        manifest = await get_or_create_manifest_for_call_run(
            self._session, call_run=call_run, run=run, evaluator=evaluator
        )
        await self._notify(
            run.id, RUN_STATUS_CHANGED, {"run_id": run.id, "status": run.status}
        )
        return await self._attempts.create_attempt(
            call_run_id=call_run.id,
            execution_manifest_id=manifest.id,
            trace_id=new_plain_ulid(),
        )

    async def cancel_run(self, run_id: str) -> domain.Run:
        run = await self._runs.get_run(run_id)
        if run.status != RunStatus.CANCELLED.value:
            await self._runs.transition_run(run, RunStatus.CANCELLED)

        for call_run in await self._call_runs.list_runs(run_id):
            if call_run.status in {
                CallRunStatus.COMPLETED.value,
                CallRunStatus.INFRASTRUCTURE_FAILED.value,
                CallRunStatus.CANCELLED.value,
            }:
                continue
            # Cancel also terminalizes in-flight attempts (starting/connecting/
            # running), not only queued ones, so nothing is left hung.
            for attempt in await self._attempts.list_attempts(call_run.id):
                if attempt.status != AttemptStatus.TERMINAL.value:
                    await self._attempts.record_terminal(
                        attempt,
                        terminal_status=AttemptTerminalStatus.CANCELLED,
                        failure_class=AttemptFailureClass.CANCELLED.value,
                        termination_reason="RUN_CANCELLED",
                    )
            await self._call_runs.finish_run(call_run, CallRunStatus.CANCELLED)
        await self._notify(
            run.id, RUN_STATUS_CHANGED, {"run_id": run.id, "status": run.status}
        )
        return run

    async def resume_run(self, run_id: str) -> ResumeOutcome:
        run = await self._runs.get_run(run_id)
        if run.status == RunStatus.PARTIAL.value:
            await self._runs.transition_run(run, RunStatus.RUNNING)
        elif run.status != RunStatus.RUNNING.value:
            raise InvalidStateTransitionError(
                f"run '{run_id}' is '{run.status}', only a 'partial' or "
                "'running' run can be resumed"
            )

        outcome = ResumeOutcome()
        for call_run in await self._call_runs.list_runs(run_id):
            if call_run.status == CallRunStatus.QUEUED.value:
                outcome.queued_call_run_ids.append(call_run.id)
            elif call_run.status == CallRunStatus.INFRASTRUCTURE_FAILED.value:
                await self._call_runs.reopen_run(call_run)
                evaluator = await self._evaluators.get_evaluator(
                    call_run.run_evaluator_id
                )
                manifest = await get_or_create_manifest_for_call_run(
                    self._session, call_run=call_run, run=run, evaluator=evaluator
                )
                attempt = await self._attempts.create_attempt(
                    call_run_id=call_run.id,
                    execution_manifest_id=manifest.id,
                    trace_id=new_plain_ulid(),
                )
                outcome.retry_attempt_ids.append(attempt.id)
        return outcome


__all__ = ["DEFAULT_REPETITIONS", "ExecutionOrchestrator", "ResumeOutcome", "TerminalOutcome"]
