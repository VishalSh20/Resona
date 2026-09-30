"""Runner process entrypoint.

Launched (by the dispatcher or manually) as ``python -m voiceeval.runtime``.
Resolves the attempt from the database, streams telemetry to the backend over
the control WebSocket, and exits when the attempt reaches its terminal state.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from voiceeval.core.logging import configure_logging
from voiceeval.db.session import get_session_factory
from voiceeval.observability.tracing import init_tracing
from voiceeval.runtime.loader import build_runner_for_attempt
from voiceeval.runtime.runner import RUNNER_VERSION
from voiceeval.runtime.telemetry import RunnerWebSocketClient

logger = logging.getLogger("voiceeval.runner")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voiceeval.runtime")
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--telemetry-url", required=True)
    parser.add_argument("--runner-id", default=None)
    parser.add_argument("--runner-version", default=RUNNER_VERSION)
    return parser


async def _run(args: argparse.Namespace) -> int:
    runner_id = args.runner_id or f"runner-{args.attempt_id}"
    telemetry = RunnerWebSocketClient(
        url=args.telemetry_url,
        attempt_id=args.attempt_id,
        runner_id=runner_id,
        runner_version=args.runner_version,
    )
    factory = get_session_factory()
    async with factory() as session:
        runner = await build_runner_for_attempt(
            session, args.attempt_id, telemetry=telemetry, runner_id=runner_id
        )
        outcome = await runner.run()
    logger.info(
        "attempt %s finished: %s (%s)",
        outcome.attempt_id,
        outcome.terminal_status,
        outcome.stop_reason,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    init_tracing()
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:  # pragma: no cover - signal handling
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
