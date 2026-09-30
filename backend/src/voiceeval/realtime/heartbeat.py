"""Runner heartbeat tracking + dead-runner detection (§10 caution 3).

The WebSocket handler acknowledges heartbeats but nothing times out a silent
runner, so a crashed job would leave the attempt hanging until the wall-clock
limit. This registry records the last heartbeat per attempt so a watchdog job can
classify a silent runner as an infrastructure failure and trigger retry.

The registry is process-local (matching the existing connection registry). A
multi-process deployment should back it with Redis.
"""

from __future__ import annotations

import time
from threading import Lock


class HeartbeatRegistry:
    def __init__(self, *, ttl_s: int = 900) -> None:
        self._ttl_s = ttl_s
        self._last: dict[str, float] = {}
        self._lock = Lock()

    def record(self, attempt_id: str, *, at: float | None = None) -> None:
        with self._lock:
            self._last[attempt_id] = at if at is not None else time.monotonic()

    def last_seen(self, attempt_id: str) -> float | None:
        with self._lock:
            return self._last.get(attempt_id)

    def forget(self, attempt_id: str) -> None:
        with self._lock:
            self._last.pop(attempt_id, None)

    def stale(self, *, now: float | None = None, timeout_s: float) -> list[str]:
        """Attempts whose last heartbeat is older than ``timeout_s``."""
        reference = now if now is not None else time.monotonic()
        with self._lock:
            return [
                attempt_id
                for attempt_id, seen in self._last.items()
                if reference - seen > timeout_s
            ]


_registry: HeartbeatRegistry | None = None


def get_heartbeat_registry() -> HeartbeatRegistry:
    global _registry
    if _registry is None:
        _registry = HeartbeatRegistry()
    return _registry


def set_heartbeat_registry(registry: HeartbeatRegistry | None) -> None:
    global _registry
    _registry = registry


__all__ = [
    "HeartbeatRegistry",
    "get_heartbeat_registry",
    "set_heartbeat_registry",
]
