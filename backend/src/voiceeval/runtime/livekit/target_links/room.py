"""RoomLink — target reached as a LiveKit room participant (WebRTC).

Two shapes, per migration doc §4.2:
* same project — the target participates in the caller's room;
* external LiveKit server — the caller opens a second ``rtc.Room`` connection to
  the target's URL with a supplied token.

LiveKit is imported lazily so the module loads without the SDK.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from voiceeval.core.errors import DependencyUnavailableError, ValidationError
from voiceeval.runtime.connections import AudioChunk, CloseReason, RawAgentEvent
from voiceeval.runtime.livekit.target_links.audio import chunk_to_frame, frame_to_chunk
from voiceeval.runtime.livekit.target_links.base import (
    TargetLink,
    TargetLinkCapabilities,
)

logger = logging.getLogger("voiceeval.livekit.roomlink")


def _import_rtc() -> Any:
    try:
        from livekit import rtc  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional SDK
        raise DependencyUnavailableError(
            "livekit SDK is not installed; the 'room' target link is unavailable"
        ) from exc
    return rtc


class RoomLink(TargetLink):
    transport = "room"

    def __init__(
        self,
        *,
        endpoint_config: dict[str, Any] | None = None,
        sample_rate: int = 24_000,
        room: Any | None = None,
    ) -> None:
        super().__init__(sample_rate=sample_rate)
        self._config = dict(endpoint_config or {})
        # ``room_mode: "external"`` reaches a provider-owned LiveKit room (a
        # platform target); the caller's own room (``ctx.room``) is not used.
        # Otherwise the target participates in the caller's room (``ctx.room``).
        self._external = str(self._config.get("room_mode") or "caller") == "external"
        if self._external:
            self._room: Any | None = None
        else:
            self._room = room
        self._owns_room = self._room is None
        self._source: Any | None = None
        self._audio: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self._events: asyncio.Queue[RawAgentEvent] = asyncio.Queue()
        self._connected = False

    def capabilities(self) -> TargetLinkCapabilities:
        return TargetLinkCapabilities(
            codec=str(self._config.get("codec", "pcm_s16le")),
            sample_rate=int(self._config.get("sample_rate", self._sample_rate)),
            channels=int(self._config.get("channels", 1)),
            supports_dtmf=False,
            target_speaks_first=bool(self._config.get("target_speaks_first", True)),
            provides_monitor_track=False,
        )

    async def connect(self) -> None:
        rtc = _import_rtc()
        url = self._config.get("url")
        token = self._config.get("token")
        if self._room is None:
            self._room = rtc.Room()
        room = self._room
        assert room is not None

        @room.on("track_subscribed")
        def _on_track(track: Any, *_args: Any) -> None:
            logger.info("room=%s track_subscribed kind=%s args=%s", getattr(room, "name", None), getattr(track, "kind", None), [getattr(a, "identity", a) for a in _args])
            if getattr(track, "kind", None) == rtc.TrackKind.KIND_AUDIO:
                asyncio.ensure_future(self._consume_track(track))

        @room.on("track_subscription_failed")
        def _on_sub_failed(*args: Any) -> None:
            logger.warning("room=%s track_subscription_failed args=%s", getattr(room, "name", None), args)

        @room.on("track_unsubscribed")
        def _on_unsub(*args: Any) -> None:
            logger.warning("room=%s track_unsubscribed args=%s", getattr(room, "name", None), args)

        @room.on("participant_connected")
        def _on_join(participant: Any, *_args: Any) -> None:
            logger.info("room=%s participant_connected identity=%s", getattr(room, "name", None), getattr(participant, "identity", None))

        @room.on("participant_disconnected")
        def _on_leave(participant: Any, *_args: Any) -> None:
            logger.info("room=%s participant_disconnected identity=%s", getattr(room, "name", None), getattr(participant, "identity", None))
            self._events.put_nowait(
                RawAgentEvent(
                    type="target.participant.left",
                    source="provider_raw",
                    monotonic_ms=0,
                    payload={"identity": getattr(participant, "identity", None)},
                )
            )

        # A room we created (external provider room, or no caller room supplied)
        # must be connected before publishing; a reused caller room is already
        # connected by the framework.
        if self._owns_room:
            if not url or not token:
                raise ValidationError(
                    "room target link requires 'url' and 'token' in endpoint_config"
                )
            await room.connect(url, token)

        logger.info(
            "room=%s local_identity=%s remote_participants=%s",
            getattr(room, "name", None),
            getattr(room.local_participant, "identity", None),
            [getattr(p, "identity", None) for p in room.remote_participants.values()],
        )
        for _p in room.remote_participants.values():
            logger.info(
                "room=%s remote participant %s track_publications=%s",
                getattr(room, "name", None),
                getattr(_p, "identity", None),
                {
                    sid: {
                        "kind": getattr(pub, "kind", None),
                        "source": getattr(pub, "source", None),
                        "subscribed": getattr(pub, "subscribed", None),
                        "name": getattr(pub, "name", None),
                    }
                    for sid, pub in getattr(_p, "track_publications", {}).items()
                },
            )

        if self._config.get("publish_caller_audio", True):
            self._source = rtc.AudioSource(
                self.capabilities().sample_rate, self.capabilities().channels
            )
            track = rtc.LocalAudioTrack.create_audio_track("caller", self._source)
            options = rtc.TrackPublishOptions()
            options.source = rtc.TrackSource.SOURCE_MICROPHONE
            await room.local_participant.publish_track(track, options)
            logger.info("room=%s published caller audio track", getattr(room, "name", None))

        # The framework connects this room before our handlers attach, so a
        # target that joined earlier has already been auto-subscribed and its
        # ``track_subscribed`` edge is gone. Pick up any audio already present.
        for _p in room.remote_participants.values():
            for pub in getattr(_p, "track_publications", {}).values():
                if getattr(pub, "kind", None) != rtc.TrackKind.KIND_AUDIO:
                    continue
                existing = getattr(pub, "track", None)
                if existing is not None:
                    logger.info(
                        "room=%s consuming pre-subscribed audio track %s from %s",
                        getattr(room, "name", None),
                        getattr(pub, "sid", None),
                        getattr(_p, "identity", None),
                    )
                    asyncio.ensure_future(self._consume_track(existing))
                elif hasattr(pub, "set_subscribed"):
                    logger.info(
                        "room=%s subscribing to un-subscribed audio track %s from %s",
                        getattr(room, "name", None),
                        getattr(pub, "sid", None),
                        getattr(_p, "identity", None),
                    )
                    pub.set_subscribed(True)

        if self._config.get("diagnostic_poll", True):
            asyncio.ensure_future(self._diagnostic_poll())

        self._connected = True
        self._events.put_nowait(
            RawAgentEvent(
                type="connection.ready",
                source="provider_raw",
                monotonic_ms=0,
                payload={"room": getattr(room, "name", None)},
            )
        )

    async def _diagnostic_poll(self) -> None:
        room = self._room
        for i in range(20):
            if not self._connected or room is None:
                return
            snapshot: dict[str, Any] = {}
            for ident, p in room.remote_participants.items():
                snapshot[ident] = {
                    getattr(pub, "sid", sid): {
                        "kind": getattr(pub, "kind", None),
                        "source": getattr(pub, "source", None),
                        "subscribed": getattr(pub, "subscribed", None),
                        "has_track": getattr(pub, "track", None) is not None,
                    }
                    for sid, pub in getattr(p, "track_publications", {}).items()
                }
            logger.info("diagnostic poll #%d room=%s remote=%s", i, getattr(room, "name", None), snapshot)
            await asyncio.sleep(1)

    async def _consume_track(self, track: Any) -> None:
        stream = _import_rtc().AudioStream(
            track,
            sample_rate=self.capabilities().sample_rate,
            num_channels=self.capabilities().channels,
        )
        async for event in stream:
            self._audio.put_nowait(frame_to_chunk(event.frame))

    async def incoming_audio(self) -> AsyncIterator[AudioChunk]:
        while self._connected:
            yield await self._audio.get()

    async def send_audio(self, frame: AudioChunk) -> None:
        if self._source is None:
            return
        await self._source.capture_frame(chunk_to_frame(frame))

    def events(self) -> AsyncIterator[RawAgentEvent]:
        async def _gen() -> AsyncIterator[RawAgentEvent]:
            while self._connected:
                yield await self._events.get()

        return _gen()

    async def close(self, reason: CloseReason) -> None:
        self._connected = False
        if self._room is not None and self._owns_room:
            await self._room.disconnect()


__all__ = ["RoomLink"]
