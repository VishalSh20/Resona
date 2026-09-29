"""ARQ worker queue definitions, job handlers and worker settings.

Queue names and enqueue helpers live in ``voiceeval.workers.enqueue`` so
enqueue/dispatch share one vocabulary. Job handlers live in
``voiceeval.workers.jobs`` and are registered on ``WorkerSettings.functions``.
"""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from voiceeval.core.config import get_settings
from voiceeval.workers.enqueue import enqueue_validation  # noqa: F401 (re-export)
from voiceeval.workers.jobs.evaluation import (
    compute_call_run_judges,
    compute_run_aggregation,
)
from voiceeval.workers.jobs.execution import (
    execution_attempt_start,
    execution_call_run_start,
    execution_run_schedule,
    execution_run_start,
)
from voiceeval.workers.jobs.validation import validate_run_evaluator
from voiceeval.workers.jobs.watchdog import room_reaper_scan, watchdog_scan
from voiceeval.workers.settings import get_redis_settings, worker_queue_name

__all__ = [
    "enqueue_validation",
    "get_redis_settings",
]


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    functions: list = [
        ping,
        validate_run_evaluator,
        execution_run_start,
        execution_run_schedule,
        execution_call_run_start,
        execution_attempt_start,
        compute_call_run_judges,
        compute_run_aggregation,
        watchdog_scan,
        room_reaper_scan,
    ]
    # Dead-runner watchdog: scan for silent runners every 30s (§10 caution 3).
    cron_jobs: list = [
        cron(watchdog_scan, second={0, 30}, run_at_startup=False),
        # Sweep stale attempt-* rooms every 5 minutes (§4.1).
        cron(room_reaper_scan, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    redis_settings: RedisSettings = RedisSettings.from_dsn(get_settings().redis_url)
    # One worker process consumes one queue; run_workers.py starts one per queue.
    queue_name: str = worker_queue_name()
    max_jobs: int = 10
    # The Voice-Agent Judge runs media alignment, evidence ledgers and parallel
    # probes, so it needs a longer budget than the other stages.
    job_timeout: int = 900

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        from voiceeval.observability.tracing import init_tracing
        from voiceeval.realtime.pubsub import RedisPubSub, set_pubsub

        init_tracing()
        set_pubsub(RedisPubSub())
