"""WebSocket target transport and provider protocol decoding.

The pipeline is deliberately layered so no assumption leaks from one layer to the
next: a websocket *message* is decoded into zero or more *frames*
(:class:`FrameDecoder`), and each frame is decoded by a provider-specific
:class:`ProviderProtocolDecoder` into zero or more provider observations. A
single message is never assumed to be a single audio frame or a single turn.
"""

from __future__ import annotations

import base64
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from websockets.asyncio.client import connect

from voiceeval.core.errors import ConnectionFailedError, ValidationError
from voiceeval.runtime.adapters.base import TargetAdapter
from voiceeval.runtime.connections import (
    AgentConnection,
    AudioChunk,
    CapabilitySnapshot,
    CloseReason,
    ConnectionConfig,
    RawAgentEvent,
)
from voiceeval.runtime.events import EventSource

DEFAULT_AUDIO_FRAME_BYTES = 640  # 20ms of 16kHz s16le mono


@dataclass(frozen=True)
class Frame:
    """A single unit produced by the frame decoder.

    ``kind`` is ``audio`` for media bytes or ``control`` for a structured
    provider message.
    """

    kind: str
    payload: bytes | dict[str, Any]
    media_timestamp: int | None = None


class FrameDecoder:
    """Splits a websocket message into frames.

    Binary messages are sliced into fixed-duration audio frames (a message may
    carry many frames). Text messages are parsed as JSON; a message that carries
    an explicit ``frames`` array yields one frame per element, otherwise it is a
    single control frame.
    """

    def __init__(self, *, audio_frame_bytes: int = DEFAULT_AUDIO_FRAME_BYTES) -> None:
        if audio_frame_bytes <= 0:
            raise ValidationError("audio_frame_bytes must be positive")
        self._audio_frame_bytes = audio_frame_bytes

    def decode(self, message: str | bytes) -> list[Frame]:
        if isinstance(message, bytes):
            return self._decode_binary(message)
        return self._decode_text(message)

    def _decode_binary(self, message: bytes) -> list[Frame]:
        frames: list[Frame] = []
        size = self._audio_frame_bytes
        for offset in range(0, len(message), size):
            chunk = message[offset : offset + size]
            if chunk:
                frames.append(Frame(kind="audio", payload=chunk))
        return frames

    def _decode_text(self, message: str) -> list[Frame]:
        text = message.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return [Frame(kind="control", payload={"type": "provider.text", "text": message})]
        if isinstance(parsed, dict) and isinstance(parsed.get("frames"), list):
            return [
                Frame(kind="control", payload=item)
                for item in parsed["frames"]
                if isinstance(item, dict)
            ]
        if isinstance(parsed, dict):
            return [Frame(kind="control", payload=parsed)]
        return [Frame(kind="control", payload={"type": "provider.value", "value": parsed})]


class ProviderProtocolDecoder(ABC):
    """Translates frames into provider observations.

    Different providers frame and name things differently; only the adapter
    knows how. This is the seam that keeps provider semantics out of the runner.
    """

    @abstractmethod
    def decode(self, frame: Frame) -> list[RawAgentEvent]: ...

    def responses(self, frame: Frame) -> list[str | bytes]:
        """Raw websocket payloads to send back in reply to an inbound frame.

        Used for protocol-level keepalives (e.g. ElevenLabs ``ping`` → ``pong``)
        that are not runtime events. Default is no reply.
        """
        return []


class JsonProviderProtocolDecoder(ProviderProtocolDecoder):
    """A JSON control protocol with an explicit ``type`` per message.

    This is the generic WebSocket provider shape used for v1 and for the
    deterministic fake target. Audio frames map to ``agent.media.chunk``;
    provider-specific media aliases are translated to their canonical names.
    """

    _DEFAULT_SOURCE = EventSource.PROVIDER_NORMALIZED.value

    # Provider media aliases -> canonical media event types.
    _TYPE_ALIASES = {
        "agent.audio": "agent.media.chunk",
        "caller.audio": "caller.media.chunk",
    }

    def decode(self, frame: Frame) -> list[RawAgentEvent]:
        if frame.kind == "audio":
            data = bytes(frame.payload)
            return [
                RawAgentEvent(
                    type="agent.media.chunk",
                    source=EventSource.PROVIDER_RAW.value,
                    monotonic_ms=frame.media_timestamp or 0,
                    payload={"data": data, "bytes": len(data)},
                    media_timestamp=frame.media_timestamp,
                )
            ]

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        event_type = payload.get("type")
        if not isinstance(event_type, str) or not event_type:
            return []
        event_type = self._TYPE_ALIASES.get(event_type, event_type)
        raw_payload = payload.get("payload")
        if event_type == "agent.media.chunk" and isinstance(raw_payload, dict):
            raw_payload = dict(raw_payload)
            data = raw_payload.get("data")
            if isinstance(data, str):
                try:
                    decoded = base64.b64decode(data)
                except (ValueError, TypeError):
                    decoded = None
                if decoded is not None:
                    raw_payload["data"] = decoded
                    raw_payload.setdefault("bytes", len(decoded))
        source = payload.get("source") or self._DEFAULT_SOURCE
        if source not in {member.value for member in EventSource}:
            source = self._DEFAULT_SOURCE
        return [
            RawAgentEvent(
                type=event_type,
                source=source,
                monotonic_ms=int(payload.get("monotonic_ms") or 0),
                payload=dict(raw_payload or {}),
                media_timestamp=payload.get("media_timestamp"),
                turn_id=payload.get("turn_id"),
                provider_event_id=payload.get("provider_event_id"),
                raw=source == EventSource.PROVIDER_RAW.value,
            )
        ]


class ProviderProtocolEncoder:
    """Translates outbound caller audio into the provider's websocket framing.

    The inbound side is a :class:`ProviderProtocolDecoder`; this is its outbound
    counterpart. The default (:class:`RawPcmEncoder`) sends raw PCM bytes, which
    is what the generic/fake target expects.
    """

    def encode_audio(self, chunk: AudioChunk) -> str | bytes:
        """The websocket payload for one caller audio chunk."""
        return chunk.data

    def initial_messages(self) -> list[str | bytes]:
        """Messages to send immediately after the socket opens. Default none."""
        return []


class RawPcmEncoder(ProviderProtocolEncoder):
    """Sends raw PCM bytes — the v1 / deterministic-fake framing."""


class WebSocketTransport(AgentConnection):
    """``AgentConnection`` over a websocket, with frame/protocol decoding."""

    def __init__(
        self,
        *,
        decoder: ProviderProtocolDecoder | None = None,
        encoder: ProviderProtocolEncoder | None = None,
        frame_decoder: FrameDecoder | None = None,
        capabilities: CapabilitySnapshot | None = None,
    ) -> None:
        self._decoder = decoder or JsonProviderProtocolDecoder()
        self._encoder = encoder or RawPcmEncoder()
        self._frame_decoder = frame_decoder or FrameDecoder()
        self._capabilities = capabilities or CapabilitySnapshot()
        self._socket = None
        self._config: ConnectionConfig | None = None
        self._closed = False

    @property
    def connected(self) -> bool:
        return self._socket is not None and not self._closed

    async def connect(self, config: ConnectionConfig) -> None:
        self._config = config
        try:
            self._socket = await connect(
                config.url,
                additional_headers=config.headers or None,
                open_timeout=config.timeout_s,
                max_size=None,
            )
        except Exception as exc:
            raise ConnectionFailedError(
                f"failed to connect target websocket: {exc}"
            ) from exc
        for message in self._encoder.initial_messages():
            try:
                await self._socket.send(message)
            except Exception as exc:
                raise ConnectionFailedError(
                    f"failed to send initial message: {exc}"
                ) from exc

    async def send_audio(self, chunk: AudioChunk) -> None:
        if self._socket is None:
            raise ConnectionFailedError("target websocket is not connected")
        try:
            await self._socket.send(self._encoder.encode_audio(chunk))
        except Exception as exc:
            raise ConnectionFailedError(f"failed to send audio: {exc}") from exc

    async def send_control(self, message: dict[str, Any]) -> None:
        if self._socket is None:
            raise ConnectionFailedError("target websocket is not connected")
        try:
            await self._socket.send(json.dumps(message))
        except Exception as exc:
            raise ConnectionFailedError(f"failed to send control: {exc}") from exc

    async def receive(self) -> AsyncIterator[RawAgentEvent]:
        if self._socket is None:
            raise ConnectionFailedError("target websocket is not connected")
        try:
            async for message in self._socket:
                for frame in self._frame_decoder.decode(message):
                    for reply in self._decoder.responses(frame):
                        await self._socket.send(reply)
                    for event in self._decoder.decode(frame):
                        yield event
        except ConnectionFailedError:
            raise
        except Exception as exc:
            raise ConnectionFailedError(f"target websocket closed: {exc}") from exc

    async def close(self, reason: CloseReason) -> None:
        self._closed = True
        if self._socket is None:
            return
        try:
            await self._socket.send(
                json.dumps({"type": "close", "reason": str(reason)})
            )
        except Exception:
            pass
        try:
            await self._socket.close()
        except Exception:
            pass


class WebSocketAdapter(TargetAdapter):
    """v1 generic WebSocket target adapter."""

    name = "websocket"
    version = "1.0.0"
    transport = "websocket"

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        decoder: ProviderProtocolDecoder | None = None,
        encoder: ProviderProtocolEncoder | None = None,
    ) -> None:
        super().__init__(sample_rate=sample_rate)
        self._decoder = decoder or JsonProviderProtocolDecoder()
        self._encoder = encoder or RawPcmEncoder()

    def build_connection(
        self, endpoint_config: dict[str, Any], *, sample_rate: int | None = None
    ) -> WebSocketTransport:
        config = self.connection_config(endpoint_config, sample_rate=sample_rate)
        return WebSocketTransport(
            decoder=self._decoder,
            encoder=self._encoder,
            capabilities=self.capabilities(endpoint_config),
        )
