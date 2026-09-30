"""Standalone deterministic fake target server for local development.

Runs the same in-process websocket target the end-to-end smoke test uses, but as
a long-lived service on a fixed port so a real runner can connect to it:

    uv run python -m voiceeval.runtime.fake_target

Then create a target revision with ``adapter_name="fake"`` and
``endpoint_config={"url": "ws://localhost:8790/target"}``.

This is a local-development dependency only; it is not part of the control
plane and never runs in production.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from voiceeval.core.config import get_settings
from voiceeval.runtime.adapters.fake import FakeTargetServer

logger = logging.getLogger("voiceeval.runtime.fake_target")


async def _serve() -> None:
    settings = get_settings()
    server = await FakeTargetServer(port=settings.fake_target_port).start()
    logger.info("fake target listening at %s", server.url)
    print(f"fake target listening at {server.url}", flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - non-unix
            pass

    try:
        await stop.wait()
    finally:
        await server.stop()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
