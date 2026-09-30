"""Deterministic fake target adapter and server.

This is the local integration environment: a real websocket server that speaks
the generic JSON provider protocol and emits audio, text, turns, tool calls and
connection events on a fixed script. Because the script is fixed, an end-to-end
call is fully reproducible with no third-party dependency.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import serve

from voiceeval.runtime.adapters.websocket import (
    JsonProviderProtocolDecoder,
    WebSocketAdapter,
    WebSocketTransport,
)
from voiceeval.runtime.connections import CapabilitySnapshot
from voiceeval.runtime.providers.deterministic import pcm_s16le_tone

FAKE_CAPABILITY_SNAPSHOT: dict[str, Any] = {
    "audio": {"caller_ingress": True, "agent_egress": True},
    "transcript": {
        "target_input": True,
        "target_output": True,
        "independent_asr_possible": True,
    },
    "events": {
        "turn_boundaries": True,
        "text_stream": True,
        "interruptions": True,
        "connection_events": True,
    },
    "tools": {"calls": True, "results": True},
}


@dataclass
class FakeScript:
    """A deterministic response script.

    ``greeting`` is emitted as soon as the caller connects; each subsequent
    batch is emitted when the runner signals the end of a caller turn.
    """

    greeting: list[dict[str, Any]] = field(default_factory=list)
    batches: list[list[dict[str, Any]]] = field(default_factory=list)

    def batch_for(self, caller_turn_index: int) -> list[dict[str, Any]]:
        if 1 <= caller_turn_index <= len(self.batches):
            return self.batches[caller_turn_index - 1]
        return []


def agent_turn(
    turn_id: str,
    *,
    text: str,
    assertions: Iterable[str] = (),
) -> list[dict[str, Any]]:
    return [
        {
            "type": "turn.start",
            "turn_id": turn_id,
            "provider_event_id": f"fake-turn-start-{turn_id}",
            "payload": {"speaker": "agent"},
        },
        {"type": "agent.speech.start", "turn_id": turn_id, "payload": {}},
        {
            "type": "agent.text.first",
            "turn_id": turn_id,
            "payload": {"text": text},
        },
        {
            "type": "agent.text.final",
            "turn_id": turn_id,
            "provider_event_id": f"fake-text-final-{turn_id}",
            "payload": {"text": text, "assertions": list(assertions)},
        },
        {"type": "agent.audio", "turn_id": turn_id, "payload": {"text": text}},
        {"type": "agent.speech.end", "turn_id": turn_id, "payload": {}},
        {"type": "turn.end", "turn_id": turn_id, "payload": {"speaker": "agent"}},
    ]


def tool_turn(turn_id: str, tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "turn.start",
            "turn_id": turn_id,
            "payload": {"speaker": "agent"},
        },
        {"type": "agent.speech.start", "turn_id": turn_id, "payload": {}},
        {
            "type": "tool.call.start",
            "turn_id": turn_id,
            "provider_event_id": f"fake-tool-start-{turn_id}",
            "payload": {"tool_name": tool_name, "arguments": arguments, "status": "pending"},
        },
        {
            "type": "tool.call.result",
            "turn_id": turn_id,
            "provider_event_id": f"fake-tool-result-{turn_id}",
            "payload": {"result": {"ok": True}, "status": "succeeded"},
        },
        {"type": "tool.call.end", "turn_id": turn_id, "payload": {"status": "succeeded"}},
        {"type": "agent.speech.end", "turn_id": turn_id, "payload": {}},
        {"type": "turn.end", "turn_id": turn_id, "payload": {"speaker": "agent"}},
    ]


def default_script() -> FakeScript:
    """The standard deterministic authentication-support conversation."""
    return FakeScript(
        greeting=agent_turn(
            "turn_agent_0",
            text="Thank you for calling. How can I help you today?",
        ),
        batches=[
            agent_turn(
                "turn_agent_1",
                text="Before I can help, I need to verify your identity.",
                assertions=[],
            ),
            tool_turn("turn_agent_2", "verify_identity", {"method": "account_id"}),
            agent_turn(
                "turn_agent_3",
                text="You are verified and your request has been handled.",
                assertions=["authentication_complete", "objective_fulfilled"],
            ),
        ],
    )


class FakeTargetServer:
    """An in-process websocket server implementing the fake protocol."""

    def __init__(
        self,
        script: FakeScript | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        audio_sample_rate: int = 16000,
    ) -> None:
        self._script = script or default_script()
        self._host = host
        self._port = port
        self._sample_rate = audio_sample_rate
        self._server = None
        self._connections: set = set()
        self.received_audio_bytes = 0
        self.caller_turns_seen = 0

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("fake target server is not running")
        port = self._server.sockets[0].getsockname()[1]
        return f"ws://{self._host}:{port}/target"

    async def start(self) -> "FakeTargetServer":
        self._server = await serve(self._handle, self._host, self._port, max_size=None)
        return self

    async def stop(self) -> None:
        for websocket in list(self._connections):
            await websocket.close()
        self._connections.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, websocket) -> None:
        self._connections.add(websocket)
        # Turn counting is per-connection: concurrent calls to the same fake
        # target each replay the script from the beginning.
        caller_turns_seen = 0
        try:
            for message in self._script.greeting:
                if not await self._send(websocket, message):
                    return
            async for raw in websocket:
                if isinstance(raw, bytes):
                    self.received_audio_bytes += len(raw)
                    continue
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                message_type = payload.get("type")
                if message_type == "caller.turn.end":
                    caller_turns_seen += 1
                    self.caller_turns_seen = caller_turns_seen
                    for message in self._script.batch_for(caller_turns_seen):
                        if not await self._send(websocket, self._materialize(message)):
                            return
                elif message_type == "close":
                    break
        except Exception:  # pragma: no cover - transport teardown races
            pass
        finally:
            self._connections.discard(websocket)

    @staticmethod
    async def _send(websocket, message: dict[str, Any]) -> bool:
        try:
            await websocket.send(json.dumps(message))
            return True
        except Exception:
            return False

    def _materialize(self, message: dict[str, Any]) -> dict[str, Any]:
        """Attach deterministic media for audio messages."""
        if message.get("type") == "agent.audio":
            text = (message.get("payload") or {}).get("text", "")
            audio = pcm_s16le_tone(
                330.0,
                max(20, len(text) * 8),
                sample_rate=self._sample_rate,
            )
            enriched = dict(message)
            enriched["payload"] = {
                "data": base64.b64encode(audio).decode("ascii"),
                "bytes": len(audio),
            }
            return enriched
        return message


class FakeTargetAdapter(WebSocketAdapter):
    """The deterministic fake target, exposed through the adapter contract."""

    name = "fake"
    version = "1.0.0"
    transport = "websocket"

    def __init__(self, *, sample_rate: int = 16000) -> None:
        super().__init__(
            sample_rate=sample_rate, decoder=JsonProviderProtocolDecoder()
        )

    def build_connection(
        self, endpoint_config: dict[str, Any], *, sample_rate: int | None = None
    ) -> WebSocketTransport:
        snapshot = endpoint_config.get("capability_snapshot") or FAKE_CAPABILITY_SNAPSHOT
        return WebSocketTransport(
            decoder=self._decoder,
            capabilities=CapabilitySnapshot.from_dict(snapshot),
        )
