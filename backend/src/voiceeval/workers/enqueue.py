"""ARQ enqueue helpers.

Single source of truth for queue names, job names and deterministic job
identities. Both the API layer and the worker job handlers import from here, so
dispatch and consumption share one vocabulary without circular imports.
"""

from __future__ import annotations

from arq import create_pool

from voiceeval.workers.settings import get_redis_settings

QUEUE_GENERATION = "voiceeval:queue:generation"
QUEUE_VALIDATION = "voiceeval:queue:validation"
QUEUE_EXECUTION = "voiceeval:queue:execution"
QUEUE_METRICS = "voiceeval:queue:metrics"
QUEUE_JUDGES = "voiceeval:queue:judges"
QUEUE_AGGREGATION = "voiceeval:queue:aggregation"

# Every queue a worker process must consume. ARQ workers listen on a single
# queue name, so one worker process is launched per entry (see
# scripts/run_workers.py). Kept next to the producers so dispatch and
# consumption can never drift apart.
ALL_QUEUES: tuple[str, ...] = (
    QUEUE_GENERATION,
    QUEUE_VALIDATION,
    QUEUE_EXECUTION,
    QUEUE_METRICS,
    QUEUE_JUDGES,
    QUEUE_AGGREGATION,
)


async def _enqueue(
    function: str,
    *args: str,
    queue_name: str,
    dedupe_id: str | None = None,
    defer_by: float | None = None,
) -> None:
    redis = await create_pool(get_redis_settings())
    try:
        await redis.enqueue_job(
            function,
            *args,
            _job_id=dedupe_id,
            _queue_name=queue_name,
            _defer_by=defer_by,
        )
    finally:
        await redis.aclose()


async def enqueue_validation(run_evaluator_id: str, job_id: str) -> None:
    await _enqueue(
        "validate_run_evaluator",
        run_evaluator_id,
        job_id,
        queue_name=QUEUE_VALIDATION,
    )


async def enqueue_execution_run(run_id: str) -> None:
    await _enqueue(
        "execution_run_start",
        run_id,
        queue_name=QUEUE_EXECUTION,
        dedupe_id=f"execution:run:{run_id}",
    )


async def enqueue_execution_call_run(call_run_id: str) -> None:
    await _enqueue(
        "execution_call_run_start",
        call_run_id,
        queue_name=QUEUE_EXECUTION,
        dedupe_id=f"execution:callrun:{call_run_id}",
    )


async def enqueue_execution_schedule(run_id: str) -> None:
    # Deliberately NOT deduped: ARQ keeps a job id after it completes, so a fixed
    # id would let the top-up run only once per run and strand the remaining
    # calls. The pass is idempotent (DB-gated), so running it per terminal is safe.
    await _enqueue(
        "execution_run_schedule",
        run_id,
        queue_name=QUEUE_EXECUTION,
    )


async def enqueue_execution_attempt(
    attempt_id: str, *, defer_by: float | None = None
) -> None:
    # A deferred dispatch is a re-enqueue of a job that may still be running, so
    # it needs a distinct id (the plain id would be deduped away by ARQ).
    dedupe_id = f"execution:attempt:{attempt_id}"
    if defer_by is not None:
        from voiceeval.core.ids import new_plain_ulid

        dedupe_id = f"{dedupe_id}:defer:{new_plain_ulid()}"
    await _enqueue(
        "execution_attempt_start",
        attempt_id,
        queue_name=QUEUE_EXECUTION,
        dedupe_id=dedupe_id,
        defer_by=defer_by,
    )


async def enqueue_judges(call_run_id: str) -> None:
    await _enqueue(
        "compute_call_run_judges",
        call_run_id,
        queue_name=QUEUE_JUDGES,
        dedupe_id=f"evaluation:judges:{call_run_id}",
    )


async def enqueue_aggregation(run_id: str) -> None:
    await _enqueue(
        "compute_run_aggregation",
        run_id,
        queue_name=QUEUE_AGGREGATION,
        dedupe_id=f"evaluation:aggregation:{run_id}",
    )
