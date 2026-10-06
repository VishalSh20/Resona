"""Dead-runner watchdog job (§10 caution 3).

Two reaping passes so an attempt can never hang forever:

1. **Silent runners** — attempts whose runner registered a heartbeat and then
   went quiet are classified as an infrastructure failure.
2. **Never-registered runners** — attempts still non-terminal long past the
   wall-clock budget whose runner never emitted a terminal event (a crashed or
   LiveKit-cancelled job). This is a DB sweep, independent of the heartbeat
   registry, because such a runner is never registered there.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from voiceeval.core.clocks import utc_now
from voiceeval.core.config import get_settings
from voiceeval.orchestration.terminal import record_terminal_event
from voiceeval.realtime.heartbeat import get_heartbeat_registry

logger = logging.getLogger("voiceeval.watchdog")

#: Grace added on top of the wall-clock budget before a stuck attempt is reaped.
_REAP_GRACE_S = 120.0


def _watchdog_timeout_s() -> float:
    # A runner that has not heartbeated within the max wall-clock plus grace is
    # presumed dead.
    settings = get_settings()
    return settings.max_wall_clock_timeout_ms / 1000.0 + 30.0


async def _reap_attempt(session, attempt_id: str, reason: str) -> bool:
    from voiceeval.workers.enqueue import enqueue_execution_attempt

    try:
        outcome = await record_terminal_event(
            session,
            attempt_id,
            {
                "terminal_status": "failed",
                "failure_class": "infrastructure",
                "reason": reason,
                "eligible": False,
            },
        )
        await session.commit()
        if outcome.next_attempt_id:
            await enqueue_execution_attempt(outcome.next_attempt_id)
        logger.warning("watchdog reaped attempt %s (%s)", attempt_id, reason)
        return True
    except Exception as exc:  # pragma: no cover - depends on live DB/Redis
        await session.rollback()
        logger.warning("watchdog could not reap attempt %s: %s", attempt_id, exc)
        return False


async def _reap_silent_runners() -> int:
    registry = get_heartbeat_registry()
    stale = registry.stale(timeout_s=_watchdog_timeout_s())
    if not stale:
        return 0

    from voiceeval.db.session import get_session_factory

    factory = get_session_factory()
    reaped = 0
    async with factory() as session:
        for attempt_id in stale:
            try:
                if await _reap_attempt(session, attempt_id, "RUNNER_CRASH"):
                    reaped += 1
            finally:
                registry.forget(attempt_id)
    return reaped


async def _reap_stale_attempts() -> int:
    from voiceeval.db.repositories import CallAttemptRepository
    from voiceeval.db.session import get_session_factory

    settings = get_settings()
    timeout_s = settings.max_wall_clock_timeout_ms / 1000.0 + _REAP_GRACE_S
    cutoff = utc_now() - timedelta(seconds=timeout_s)

    factory = get_session_factory()
    reaped = 0
    async with factory() as session:
        attempts = await CallAttemptRepository(session).list_active_created_before(
            cutoff
        )
        for attempt in attempts:
            if await _reap_attempt(session, attempt.id, "RUNNER_CRASH"):
                reaped += 1
    return reaped


async def watchdog_scan(ctx: dict) -> int:
    return await _reap_silent_runners() + await _reap_stale_attempts()


async def room_reaper_scan(ctx: dict) -> int:
    """Delete stale ``attempt-*`` LiveKit rooms (§4.1). No-op without LiveKit."""
    settings = get_settings()
    if not settings.livekit_url:
        return 0
    try:
        from voiceeval.runtime.livekit.rooms import LiveKitRoomManager

        deleted = await LiveKitRoomManager().reap_stale_rooms(
            older_than_s=settings.livekit_room_reap_after_s
        )
        return len(deleted)
    except Exception as exc:  # pragma: no cover - depends on live LiveKit
        logger.warning("room reaper failed: %s", exc)
        return 0


__all__ = ["room_reaper_scan", "watchdog_scan"]
