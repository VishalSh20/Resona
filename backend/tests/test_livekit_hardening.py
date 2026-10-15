"""Heartbeat watchdog registry and telemetry sequence buffer/replay (§10.2–10.3)."""

from __future__ import annotations

import json

from voiceeval.realtime.heartbeat import HeartbeatRegistry
from voiceeval.runtime.events import CanonicalEventBuilder
from voiceeval.runtime.telemetry import RunnerWebSocketClient


def test_heartbeat_registry_records_and_detects_stale():
    registry = HeartbeatRegistry()
    registry.record("att_1", at=100.0)
    registry.record("att_2", at=190.0)
    assert registry.last_seen("att_1") == 100.0
    assert registry.stale(now=200.0, timeout_s=50.0) == ["att_1"]
    registry.forget("att_1")
    assert registry.last_seen("att_1") is None


class _FakeSocket:
    def __init__(self, incoming=None):
        self.sent: list[dict] = []
        self._incoming = list(incoming or [])

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def close(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)


def _client() -> RunnerWebSocketClient:
    return RunnerWebSocketClient(
        url="ws://x/internal/v1/attempts/att_1/stream",
        attempt_id="att_1",
        runner_id="runner-1",
        runner_version="runner.v1",
    )


def _event(builder: CanonicalEventBuilder):
    return builder.build("agent.text.final", source="provider_normalized", payload={"text": "hi"})


async def test_send_event_buffers_until_acked():
    client = _client()
    socket = _FakeSocket()
    client._socket = socket  # noqa: SLF001
    builder = CanonicalEventBuilder("att_1")
    event = _event(builder)
    await client.send_event(event)
    assert event.sequence in client._unacked  # noqa: SLF001
    assert socket.sent[0]["type"] == "runtime.event"


async def test_event_ack_removes_from_buffer():
    client = _client()
    builder = CanonicalEventBuilder("att_1")
    event = _event(builder)
    client._unacked[event.sequence] = {"type": "runtime.event"}  # noqa: SLF001
    socket = _FakeSocket(incoming=[json.dumps({"type": "runner.event_ack", "sequence": 1})])
    client._socket = socket  # noqa: SLF001
    await client._read_loop()  # noqa: SLF001
    assert event.sequence not in client._unacked  # noqa: SLF001


async def test_replay_resends_unacked_after_reconnect():
    client = _client()
    socket = _FakeSocket()
    client._socket = socket  # noqa: SLF001
    client._unacked[1] = {"type": "runtime.event", "event": {"sequence": 1}}  # noqa: SLF001
    client._unacked[2] = {"type": "runtime.event", "event": {"sequence": 2}}  # noqa: SLF001
    await client._replay_unacked()  # noqa: SLF001
    assert [m["event"]["sequence"] for m in socket.sent] == [1, 2]


def test_livekit_room_name_is_attempt_scoped():
    from voiceeval.runtime.livekit.rooms import room_name_for_attempt

    assert room_name_for_attempt("att_1") == "attempt-att_1"


def test_dispatcher_selects_livekit_mode(monkeypatch):
    import voiceeval.runtime.dispatch as dispatch

    class _Settings:
        runner_dispatch_mode = "livekit"
        runner_backend_url = "http://localhost:8000"

    monkeypatch.setattr(dispatch, "get_settings", lambda: _Settings())
    dispatch.set_dispatcher(None)
    try:
        assert isinstance(dispatch.get_dispatcher(), dispatch.LiveKitDispatcher)
    finally:
        dispatch.set_dispatcher(None)

