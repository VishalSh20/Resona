"""ARQ worker settings.

Resolves the Redis connection for worker processes from the same settings object
as the control plane.
"""

from __future__ import annotations

import os

from arq.connections import RedisSettings

from voiceeval.core.config import get_settings

# Fallback queue for a bare `arq voiceeval.workers.arq.WorkerSettings`. Named
# queues are consumed by running one worker per queue (see
# scripts/run_workers.py); this default keeps a single-worker start-up usable.
DEFAULT_WORKER_QUEUE = "voiceeval:queue:execution"


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


def worker_queue_name() -> str:
    """The queue this worker process consumes.

    ARQ 0.28 workers listen on exactly one queue, so the multi-queue deployment
    launches one worker per queue with ``WORKER_QUEUE`` set accordingly.
    """
    return os.environ.get("WORKER_QUEUE") or DEFAULT_WORKER_QUEUE
