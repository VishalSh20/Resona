"""Bounded caller pool: the spawning layer for the pipecat caller.

Runs up to ``max_concurrent`` callers at once (env
``PIPECAT_CALLER_MAX_CONCURRENT``, default 5), either against an explicit set of
attempt ids or by claiming queued websocket attempts from the database.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Sequence

from voiceeval.auth.jwt import create_runner_token
from voiceeval.core.config import Settings, get_settings
from voiceeval.db.models import runtime
from voiceeval.db.repositories import CallAttemptRepository
from voiceeval.db.session import get_session_factory
from voiceeval.domain.enums import AttemptStatus
from voiceeval.runtime.pipecat_caller.agent import PipecatCallerAgent
from voiceeval.runtime.pipecat_caller.queue import claim_pending_attempts
from voiceeval.runtime.pipecat_caller.settings import (
    PipecatCallerSettings,
    get_pipecat_caller_settings,
)
from voiceeval.runtime.telemetry import build_stream_url

logger = logging.getLogger("voiceeval.pipecat_caller.supervisor")


class CallerSupervisor:
    """The caller spawning layer: claims attempts and caps concurrency."""

    def __init__(
        self,
        *,
        settings: PipecatCallerSettings | None = None,
        core: Settings | None = None,
    ) -> None:
        self._settings = settings or get_pipecat_caller_settings()
        self._core = core or get_settings()
        self._semaphore = asyncio.Semaphore(max(1, self._settings.max_concurrent))

    async def run_attempts(self, attempt_ids: Sequence[str]) -> list[str]:
        """Run an explicit set of attempts under the concurrency cap."""
        tasks = [
            asyncio.create_task(self._run_one(attempt_id), name=f"pipecat-caller:{attempt_id}")
            for attempt_id in attempt_ids
        ]
        try:
            return list(await asyncio.gather(*tasks))
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            raise

    async def run_once(self) -> list[str]:
        """Claim one batch of queued attempts and run it to completion."""
        claimed = await self._claim(self._settings.max_concurrent)
        return await self.run_attempts([attempt.id for attempt in claimed])

    async def run(self) -> None:
        """Poll the attempt queue, keeping up to ``max_concurrent`` calls live."""
        running: set[asyncio.Task] = set()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # pragma: no cover - non-unix
                pass

        logger.info(
            "pipecat caller supervisor started (max_concurrent=%d)",
            self._settings.max_concurrent,
        )
        try:
            while not stop.is_set():
                running = {task for task in running if not task.done()}
                capacity = self._settings.max_concurrent - len(running)
                if capacity > 0:
                    for attempt in await self._claim(capacity):
                        running.add(
                            asyncio.create_task(
                                self._run_one(attempt.id),
                                name=f"pipecat-caller:{attempt.id}",
                            )
                        )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self._settings.poll_interval_s)
                except asyncio.TimeoutError:
                    pass
        finally:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)

    async def _claim(self, limit: int) -> list[runtime.CallAttempt]:
        if limit <= 0:
            return []
        async with get_session_factory()() as session:
            claimed = await claim_pending_attempts(
                session, limit, allowed_transports=self._settings.allowed_transports
            )
            repo = CallAttemptRepository(session)
            for attempt in claimed:
                if attempt.status == AttemptStatus.QUEUED.value:
                    await repo.transition_attempt(attempt, AttemptStatus.STARTING)
            await session.commit()
            return claimed

    async def _run_one(self, attempt_id: str) -> str:
        async with self._semaphore:
            agent = PipecatCallerAgent(
                attempt_id,
                telemetry_url=self._telemetry_url(attempt_id),
                settings=self._settings,
                core=self._core,
            )
            try:
                reason = await agent.run()
            except Exception:
                logger.exception("attempt %s: caller agent failed", attempt_id)
                return "JOB_CRASH"
            logger.info("attempt %s finished: %s", attempt_id, reason)
            return reason

    def _telemetry_url(self, attempt_id: str) -> str:
        runner_id = f"runner-{attempt_id}"
        token = create_runner_token(runner_id, attempt_id)
        return build_stream_url(self._core.runner_backend_url, attempt_id, token)


__all__ = ["CallerSupervisor"]
