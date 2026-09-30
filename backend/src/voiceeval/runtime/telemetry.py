"""Runner telemetry.

The runner reports to the backend over the control WebSocket implemented in
Prompt 5: it registers, heartbeats, streams canonical runtime events, and reads
control commands (cancel/terminate). Telemetry is one-way for events; the only
inbound traffic is control. A recording sink backs tests and the in-process
runtime.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from urllib.parse import quote

from websockets.asyncio.client import connect

from voiceeval.core.clocks import monotonic_ms as default_monotonic_ms
from voiceeval.core.errors import ConnectionFailedError
from voiceeval.runtime.events import CanonicalEvent

CONTROL_CANCEL = "attempt.cancel"
CONTROL_TERMINATE = "attempt.terminate"
EVENT_ACK = "runner.event_ack"


@runtime_checkable
class TelemetrySink(Protocol):
    async def connect(self) -> None: ...

    async def send_event(self, event: CanonicalEvent) -> None: ...

    async def heartbeat(self) -> None: ...

    async def next_control(self, timeout: float = 0.0) -> dict[str, Any] | None: ...

    async def close(self) -> None: ...


def build_stream_url(base_url: str, attempt_id: str, token: str) -> str:
    """Build the runner control WebSocket URL with its query-param token."""
    base = base_url.rstrip("/")
    if base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    elif base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    return f"{base}/internal/v1/attempts/{attempt_id}/stream?token={quote(token)}"


@dataclass
class RecordingTelemetrySink:
    """In-memory telemetry sink (in-process runtime and tests)."""

    attempt_id: str
    runner_id: str
    runner_version: str
    events: list[CanonicalEvent] = field(default_factory=list)
    heartbeats: int = 0
    connected: bool = False
    closed: bool = False
    control: asyncio.Queue = field(default_factory=asyncio.Queue)

    async def connect(self) -> None:
        self.connected = True

    async def send_event(self, event: CanonicalEvent) -> None:
        self.events.append(event)

    async def heartbeat(self) -> None:
        self.heartbeats += 1

    async def next_control(self, timeout: float = 0.0) -> dict[str, Any] | None:
        try:
            if timeout <= 0:
                return self.control.get_nowait()
            return await asyncio.wait_for(self.control.get(), timeout=timeout)
        except (asyncio.QueueEmpty, asyncio.TimeoutError):
            return None

    async def push_control(self, message: dict[str, Any]) -> None:
        await self.control.put(message)

    async def close(self) -> None:
        self.closed = True


class RunnerWebSocketClient:
    """The real runner control client (telemetry + control)."""

    def __init__(
        self,
        *,
        url: str,
        attempt_id: str,
        runner_id: str,
        runner_version: str,
        clock: Callable[[], int] = default_monotonic_ms,
        open_timeout: float = 10.0,
    ) -> None:
        self._url = url
        self._attempt_id = attempt_id
        self._runner_id = runner_id
        self._runner_version = runner_version
        self._clock = clock
        self._open_timeout = open_timeout
        self._socket = None
        self._reader: asyncio.Task | None = None
        self._control: asyncio.Queue = asyncio.Queue()
        # Bounded buffer of unacknowledged event envelopes, replayed on reconnect
        # (§10 caution 2). Never resets the sequence — a single allocator per
        # attempt lives in CanonicalEventBuilder.
        self._unacked: dict[int, dict[str, Any]] = {}
        self._max_unacked = 512

    async def connect(self) -> None:
        try:
            self._socket = await connect(self._url, open_timeout=self._open_timeout)
        except Exception as exc:
            raise ConnectionFailedError(f"runner telemetry connect failed: {exc}") from exc
        self._reader = asyncio.create_task(self._read_loop())
        await self._send(
            {
                "type": "runner.register",
                "attempt_id": self._attempt_id,
                "runner_id": self._runner_id,
                "runner_version": self._runner_version,
            }
        )
        # Replay anything the server never acknowledged before the reconnect.
        await self._replay_unacked()

    async def send_event(self, event: CanonicalEvent) -> None:
        envelope = {"type": "runtime.event", "event": event.to_envelope()}
        self._unacked[event.sequence] = envelope
        if len(self._unacked) > self._max_unacked:
            self._unacked.pop(min(self._unacked), None)
        try:
            await self._send(envelope)
        except ConnectionFailedError:
            await self._reconnect()

    async def _reconnect(self) -> None:
        await self.close()
        self._control = asyncio.Queue()
        await self.connect()

    async def _replay_unacked(self) -> None:
        for sequence in sorted(self._unacked):
            try:
                await self._send(self._unacked[sequence])
            except ConnectionFailedError:
                return

    async def heartbeat(self) -> None:
        await self._send(
            {
                "type": "runner.heartbeat",
                "attempt_id": self._attempt_id,
                "monotonic_ms": self._clock(),
            }
        )

    async def next_control(self, timeout: float = 0.0) -> dict[str, Any] | None:
        try:
            if timeout <= 0:
                return self._control.get_nowait()
            return await asyncio.wait_for(self._control.get(), timeout=timeout)
        except (asyncio.QueueEmpty, asyncio.TimeoutError):
            return None

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
        if self._socket is not None:
            try:
                await self._socket.close()
            except Exception:
                pass
        self._socket = None

    async def _send(self, message: dict[str, Any]) -> None:
        if self._socket is None:
            raise ConnectionFailedError("runner telemetry is not connected")
        try:
            await self._socket.send(json.dumps(message))
        except Exception as exc:
            raise ConnectionFailedError(f"runner telemetry send failed: {exc}") from exc

    async def _read_loop(self) -> None:
        try:
            async for raw in self._socket:
                if isinstance(raw, bytes):
                    continue
                try:
                    message = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if message.get("type") == EVENT_ACK:
                    self._unacked.pop(int(message.get("sequence", -1)), None)
                elif message.get("type") in (CONTROL_CANCEL, CONTROL_TERMINATE):
                    await self._control.put(message)
        except Exception:
            return
