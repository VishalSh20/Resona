"""BridgeLink — a WebSocket / provider-protocol audio target.

The adapter speaks the target's protocol, converts codec and sample rate, and
exposes audio in/out to the session (migration doc §4.2). It reuses the existing
``runtime.adapters.websocket`` transport for the wire protocol. For a BridgeLink
target the room still exists: the job publishes the target's audio into the room
as a monitor track; metrics are computed in-process at the audio boundary.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from voiceeval.runtime.adapters.websocket import WebSocketAdapter
from voiceeval.runtime.connections import AudioChunk, CloseReason, RawAgentEvent
from voiceeval.runtime.livekit.target_links.audio import pcm_bytes_to_chunk
from voiceeval.runtime.livekit.target_links.base import (
    TargetLink,
    TargetLinkCapabilities,
)


def _payload_bytes(payload: dict[str, Any]) -> bytes | None:
    for key in ("data", "audio", "pcm", "bytes"):
        value = payload.get(key)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
    return None


class BridgeLink(TargetLink):
    transport = "bridge"

    def __init__(
        self,
        *,
        endpoint_config: dict[str, Any] | None = None,
        sample_rate: int = 16_000,
        decoder: Any | None = None,
        encoder: Any | None = None,
        room: Any | None = None,
    ) -> None:
        super().__init__(sample_rate=sample_rate)
        self._config = dict(endpoint_config or {})
        # ``room`` is accepted for uniform link construction (the job passes the
        # caller's room to every link). Bridge audio is carried by the socket, so
        # the room is only the monitor/demux plane and is not used here.
        self._room = room
        provider = self._config.get("provider")
        if decoder is None or encoder is None:
            from voiceeval.runtime.livekit.bridge_decoders import (
                decoder_for_provider,
                encoder_for_provider,
            )

            if decoder is None:
                decoder = decoder_for_provider(provider)
            if encoder is None:
                encoder = encoder_for_provider(provider)
        self._adapter = WebSocketAdapter(
            sample_rate=sample_rate, decoder=decoder, encoder=encoder
        )
        self._connection: Any | None = None
        self._pump: asyncio.Task[None] | None = None
        self._audio: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self._events: asyncio.Queue[RawAgentEvent] = asyncio.Queue()
        self._connected = False

    def capabilities(self) -> TargetLinkCapabilities:
        snapshot = self._config.get("capability_snapshot") or {}
        return TargetLinkCapabilities(
            codec=str(snapshot.get("codec", self._config.get("codec", "pcm_s16le"))),
            sample_rate=int(snapshot.get("sample_rate", self._config.get("sample_rate", self._sample_rate))),
            channels=int(self._config.get("channels", 1)),
            supports_dtmf=False,
            target_speaks_first=bool(self._config.get("target_speaks_first", True)),
            provides_monitor_track=True,
        )

    async def connect(self) -> None:
        config = self._adapter.connection_config(self._config)
        self._connection = self._adapter.build_connection(self._config)
        await self._connection.connect(config)
        self._connected = True
        self._pump = asyncio.create_task(self._demux())

    async def _demux(self) -> None:
        assert self._connection is not None
        try:
            async for raw in self._connection.receive():
                data = _payload_bytes(raw.payload or {})
                if raw.type.endswith("media.chunk") and data is not None:
                    self._audio.put_nowait(
                        pcm_bytes_to_chunk(
                            data,
                            sample_rate=int(
                                (raw.payload or {}).get(
                                    "sample_rate", self.capabilities().sample_rate
                                )
                            ),
                            channels=self.capabilities().channels,
                        )
                    )
                else:
                    self._events.put_nowait(raw)
        finally:
            self._connected = False

    async def incoming_audio(self) -> AsyncIterator[AudioChunk]:
        while self._connected:
            yield await self._audio.get()

    async def send_audio(self, frame: AudioChunk) -> None:
        if self._connection is not None:
            await self._connection.send_audio(frame)

    async def send_control(self, message: dict[str, Any]) -> None:
        if self._connection is not None and hasattr(self._connection, "send_control"):
            await self._connection.send_control(message)

    def events(self) -> AsyncIterator[RawAgentEvent]:
        async def _gen() -> AsyncIterator[RawAgentEvent]:
            while self._connected:
                yield await self._events.get()

        return _gen()

    async def close(self, reason: CloseReason) -> None:
        self._connected = False
        if self._pump is not None:
            self._pump.cancel()
        if self._connection is not None:
            await self._connection.close(reason)


__all__ = ["BridgeLink"]
