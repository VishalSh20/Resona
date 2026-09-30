"""Launch one ARQ worker process per named queue.

ARQ 0.28 workers consume a single queue name (``WorkerSettings.queue_name``).
The design keeps validation/execution/metrics/judges/aggregation work in
separate queues, so a complete deployment runs one worker per queue. This
launcher starts them all with a single command and shuts them down together.

    uv run python scripts/run_workers.py

Individual queues can still be run directly:

    WORKER_QUEUE=voiceeval:queue:execution arq voiceeval.workers.arq.WorkerSettings
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from voiceeval.workers.enqueue import ALL_QUEUES


def main() -> int:
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "arq", "voiceeval.workers.arq.WorkerSettings"],
            env={**os.environ, "WORKER_QUEUE": queue},
        )
        for queue in ALL_QUEUES
    ]

    def _shutdown(signum: int, frame: object) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        # Return as soon as any worker exits (a crash should fail the service)
        # so an orchestrator can restart the whole set.
        exit_code = 0
        for process in processes:
            code = process.wait()
            if code != 0 and exit_code == 0:
                exit_code = code
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
