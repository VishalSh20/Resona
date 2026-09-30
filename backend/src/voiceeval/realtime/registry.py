"""In-process registry of active runner control connections.

The runner WebSocket for an attempt registers an outgoing queue here. Control
commands (cancel/terminate) are delivered by pushing to every queue registered
for the attempt. The registry is intentionally process-local: a runner is
connected to exactly one control-plane process for the life of an attempt.
"""

from __future__ import annotations

import asyncio


class ConnectionRegistry:
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def register(self, attempt_id: str, queue: asyncio.Queue) -> None:
        self._queues.setdefault(attempt_id, []).append(queue)

    def unregister(self, attempt_id: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(attempt_id)
        if not queues:
            return
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._queues.pop(attempt_id, None)

    def is_connected(self, attempt_id: str) -> bool:
        return bool(self._queues.get(attempt_id))

    def signal(self, attempt_id: str, message: dict) -> int:
        """Deliver ``message`` to every connection for ``attempt_id``.

        Returns the number of connections the message was queued to.
        """
        queues = self._queues.get(attempt_id, [])
        for queue in queues:
            queue.put_nowait(message)
        return len(queues)


_registry = ConnectionRegistry()


def get_connection_registry() -> ConnectionRegistry:
    return _registry
