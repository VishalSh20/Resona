"""Evaluation pipeline job handlers (v0.4).

These run outside the API request lifecycle and drive EVALUATION TRUTH:

    eligible attempt -> judges -> aggregates -> composite

The Voice-Agent Judge computes every metric (signal, probe and hybrid), so the
former deterministic metric stage is gone. Each stage is idempotent and
enqueued with a deterministic job identity, so a retried dispatch cannot
duplicate work. Run completion is detected once every call run's evaluation has
settled; aggregation is only enqueued at that point.
"""

from __future__ import annotations

import logging

from voiceeval.aggregation.engine import AggregationEngine
from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import ResourceNotFoundError, VoiceEvalError
from voiceeval.db.models.support import Job
from voiceeval.db.repositories import CallRunRepository, RunRepository
from voiceeval.db.session import get_session_factory
from voiceeval.domain.enums import RunStatus
from voiceeval.judging.engine import JudgeEngine
from voiceeval.observability.tracing import span
from voiceeval.orchestration.completion import RunCompletionService
from voiceeval.workers.enqueue import enqueue_aggregation

logger = logging.getLogger("voiceeval.workers.evaluation")


async def compute_call_run_judges(
    ctx: dict, call_run_id: str, job_id: str | None = None
) -> str:
    factory = get_session_factory()
    async with factory() as session:
        written = []
        with span("worker.compute_call_run_judges", call_run_id=call_run_id):
            try:
                written = await JudgeEngine(session).evaluate_run(call_run_id)
            except (VoiceEvalError, ResourceNotFoundError) as exc:
                logger.info("call run %s has nothing to judge: %s", call_run_id, exc)
            await _finish_job(session, job_id)
            await session.commit()
        await _finish_call_run(session, call_run_id)
        return f"{len(written)} judge metric results"


async def compute_run_aggregation(
    ctx: dict, run_id: str, job_id: str | None = None
) -> str:
    factory = get_session_factory()
    async with factory() as session:
        engine = AggregationEngine(session)
        with span("worker.compute_run_aggregation", run_id=run_id):
            if not await engine.is_run_evaluation_complete(run_id):
                await _finish_job(session, job_id)
                await session.commit()
                return "not_ready"
            aggregates = await engine.aggregate_run(run_id)
            composite = await engine.compute_composite(run_id)
            await _finish_job(session, job_id)
            await session.commit()
        return f"{len(aggregates)} aggregates, composite={composite.status}"


async def _finish_call_run(session, call_run_id: str) -> None:
    call_run = await CallRunRepository(session).get_run(call_run_id)
    await RunCompletionService(session).maybe_complete(call_run.run_id)
    await session.commit()

    run = await RunRepository(session).get_run(call_run.run_id)
    if run.status not in {RunStatus.COMPLETED.value, RunStatus.PARTIAL.value}:
        return
    if await AggregationEngine(session).is_run_evaluation_complete(run.id):
        try:
            await enqueue_aggregation(run.id)
        except Exception as exc:  # pragma: no cover - depends on live Redis
            logger.warning("failed to enqueue aggregation for run %s: %s", run.id, exc)


async def _finish_job(session, job_id: str | None) -> None:
    if not job_id:
        return
    job = await session.get(Job, job_id)
    if job is not None:
        job.status = "completed"
        job.finished_at = utc_now()


__all__ = [
    "compute_call_run_judges",
    "compute_run_aggregation",
]
