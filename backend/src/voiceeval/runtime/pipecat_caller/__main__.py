"""CLI entrypoint: ``python -m voiceeval.runtime.pipecat_caller``.

With ``--attempt-id`` it runs those attempts and exits; otherwise it supervises
the database attempt queue, keeping ``--max-concurrent`` calls live (default from
``PIPECAT_CALLER_MAX_CONCURRENT``, 5).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from voiceeval.core.logging import configure_logging
from voiceeval.observability.tracing import init_tracing
from voiceeval.runtime.pipecat_caller.settings import (
    PipecatCallerSettings,
    get_pipecat_caller_settings,
)
from voiceeval.runtime.pipecat_caller.supervisor import CallerSupervisor

logger = logging.getLogger("voiceeval.pipecat_caller")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voiceeval.runtime.pipecat_caller")
    parser.add_argument(
        "--attempt-id",
        action="append",
        default=None,
        help="run specific attempt id(s) instead of polling the queue",
    )
    parser.add_argument("--max-concurrent", type=int, default=None)
    parser.add_argument(
        "--once", action="store_true", help="claim one batch from the queue and exit"
    )
    return parser


def _settings_from(args: argparse.Namespace) -> PipecatCallerSettings:
    settings = get_pipecat_caller_settings()
    if args.max_concurrent is not None:
        settings = settings.model_copy(update={"max_concurrent": args.max_concurrent})
    return settings


async def _run(args: argparse.Namespace) -> int:
    supervisor = CallerSupervisor(settings=_settings_from(args))
    if args.attempt_id:
        await supervisor.run_attempts(args.attempt_id)
    elif args.once:
        await supervisor.run_once()
    else:
        await supervisor.run()
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
