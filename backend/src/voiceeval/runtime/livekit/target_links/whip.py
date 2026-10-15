"""WhipLink — outbound WebRTC (WHIP) to a provider's signaling gateway.

Some platforms (Retell web calls) carry audio over a WHIP-style signaling proxy
rather than a LiveKit room: create the call, POST an SDP offer to the gateway's
session endpoint, trickle ICE candidates, and exchange Opus media over a raw
WebRTC peer connection. This link speaks that protocol with ``aiortc`` and
presents the usual :class:`TargetLink` audio boundary (PCM s16le chunks in/out).

``aiortc``/``av`` are imported lazily so this module and the registry import
cleanly without the optional dependency installed.
"""

from __future__ import annotations

import asyncio
import fractions
from collections.abc import AsyncIterator
from typing import Any

import httpx

from voiceeval.core.errors import DependencyUnavailableError, ValidationError
from voiceeval.runtime.connections import AudioChunk, CloseReason, RawAgentEvent
from voiceeval.runtime.livekit.target_links.audio import duration_ms
from voiceeval.runtime.livekit.target_links.base import (
    TargetLink,
    TargetLinkCapabilities,
)

#: Retell hosts the WHIP signaling proxy at ``<host>/webrtc-proxy/<call_id>``.
DEFAULT_BASE_URL = "https://api.retellai.com"
DEFAULT_IDENTITY = "client"
FRAME_MS = 20
#: Opus runs at 48 kHz; the caller's PCM is resampled to this for the wire.
WEBRTC_RATE = 48_000


def _import_aiortc() -> tuple[Any, ...]:
    try:
        import av
        from aiortc import (
            RTCConfiguration,
            RTCIceServer,
            RTCPeerConnection,
            RTCSessionDescription,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise DependencyUnavailableError(
            "aiortc/av are not installed; the 'whip' target link is unavailable"
        ) from exc
    return av, RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription


def caller_audio_track_class() -> type:
    """Build the aiortc audio track class on demand (aiortc is optional)."""
    try:
        import av
        from aiortc.mediastreams import MediaStreamTrack
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise DependencyUnavailableError(
            "aiortc/av are not installed; the 'whip' target link is unavailable"
        ) from exc

    class CallerAudioTrack(MediaStreamTrack):
        """Feeds PCM ``AudioChunk``s to WebRTC as 20 ms Opus frames.

        When the caller is silent the queue drains and ``recv`` emits silence so
        the RTP stream stays continuous.
        """

        kind = "audio"

        def __init__(self, rate: int = WEBRTC_RATE, channels: int = 1) -> None:
            super().__init__()
            self._rate = rate
            self._channels = channels
            self._samples_per_frame = rate * FRAME_MS // 1000
            self._queue: asyncio.Queue[AudioChunk] = asyncio.Queue()
            self._buffer = bytearray()
            self._resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
            self._pts = 0

        def push(self, chunk: AudioChunk) -> None:
            self._queue.put_nowait(chunk)

        def _resample(self, chunk: AudioChunk) -> bytes:
            samples = len(chunk.data) // (2 * chunk.channels)
            if samples <= 0:
                return b""
            frame = av.AudioFrame(
                format="s16",
                layout="mono" if chunk.channels == 1 else "stereo",
                samples=samples,
            )
            frame.sample_rate = chunk.sample_rate
            frame.planes[0].update(chunk.data)
            return b"".join(bytes(f.planes[0]) for f in (self._resampler.resample(frame) or []))

        async def _next_pcm(self, nbytes: int) -> bytes:
            while len(self._buffer) < nbytes:
                try:
                    chunk = await asyncio.wait_for(
                        self._queue.get(), timeout=FRAME_MS / 1000
                    )
                except asyncio.TimeoutError:
                    break
                self._buffer.extend(self._resample(chunk))
            data = bytes(self._buffer[:nbytes])
            del self._buffer[:nbytes]
            if len(data) < nbytes:
                data += b"\x00" * (nbytes - len(data))
            return data

        async def recv(self) -> Any:
            data = await self._next_pcm(self._samples_per_frame * 2)
            frame = av.AudioFrame(
                format="s16", layout="mono", samples=self._samples_per_frame
            )
            frame.sample_rate = self._rate
            frame.planes[0].update(data)
            frame.pts = self._pts
            frame.time_base = fractions.Fraction(1, self._rate)
            self._pts += self._samples_per_frame
            return frame

    return CallerAudioTrack


class _WhipSignaling:
    """The WHIP-style HTTP signaling used by Retell's gateway proxy."""

    def __init__(self, proxy_url: str, access_token: str, identity: str) -> None:
        self._base = proxy_url.rstrip("/") + "/v1/webrtc/sessions"
        self._token = access_token
        self._identity = identity

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def create(self, sdp: str) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self._base,
                headers=self._headers("application/json"),
                json={"identity": self._identity, "sdp": sdp},
            )
            response.raise_for_status()
            data = response.json()
        return str(data["session_id"]), str(data["sdp"])

    async def add_candidate(self, session_id: str, candidate: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.patch(
                f"{self._base}/{session_id}",
                headers=self._headers("application/json"),
                json={"candidate": candidate},
            )

    async def close(self, session_id: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.delete(
                f"{self._base}/{session_id}", headers=self._headers()
            )


class WhipLink(TargetLink):
    transport = "whip"

    def __init__(
        self,
        *,
        endpoint_config: dict[str, Any] | None = None,
        sample_rate: int = 24_000,
        room: Any | None = None,
    ) -> None:
        super().__init__(sample_rate=sample_rate)
        self._config = dict(endpoint_config or {})
        self._rate = int(self._config.get("sample_rate", sample_rate))
        self._audio: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self._events: asyncio.Queue[RawAgentEvent] = asyncio.Queue()
        self._connected = False
        self._pc: Any | None = None
        self._track: Any | None = None
        self._signaling: _WhipSignaling | None = None
        self._session_id: str | None = None
        self._pending_candidates: list[dict[str, Any]] = []
        self._tasks: list[asyncio.Task[None]] = []

    def capabilities(self) -> TargetLinkCapabilities:
        return TargetLinkCapabilities(
            codec="pcm_s16le",
            sample_rate=self._rate,
            channels=1,
            supports_dtmf=False,
            target_speaks_first=bool(self._config.get("target_speaks_first", True)),
            provides_monitor_track=False,
        )

    def _proxy_url(self) -> str | None:
        explicit = self._config.get("proxy_url")
        if explicit:
            return str(explicit)
        call_id = self._config.get("call_id")
        if not call_id:
            return None
        base = str(self._config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        return f"{base}/webrtc-proxy/{call_id}"

    async def connect(self) -> None:
        (
            av,
            RTCConfiguration,
            RTCIceServer,
            RTCPeerConnection,
            RTCSessionDescription,
        ) = _import_aiortc()

        proxy_url = self._proxy_url()
        access_token = self._config.get("access_token")
        if not proxy_url or not access_token:
            raise ValidationError(
                "whip target link requires 'call_id' (or 'proxy_url') and 'access_token'"
            )

        ice_servers = [
            RTCIceServer(
                urls=server.get("urls"),
                username=server.get("username"),
                credential=server.get("credential"),
            )
            for server in (self._config.get("ice_servers") or [])
            if isinstance(server, dict) and server.get("urls")
        ]
        pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        self._pc = pc
        signaling = _WhipSignaling(
            proxy_url, str(access_token), str(self._config.get("identity") or DEFAULT_IDENTITY)
        )
        self._signaling = signaling

        @pc.on("track")
        def _on_track(remote: Any) -> None:
            if getattr(remote, "kind", None) == "audio":
                self._tasks.append(asyncio.ensure_future(self._consume(remote, av)))

        @pc.on("icecandidate")
        def _on_candidate(candidate: Any) -> None:
            if candidate is None:
                return
            payload = {
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex,
            }
            if self._session_id is None:
                self._pending_candidates.append(payload)
            else:
                self._tasks.append(
                    asyncio.ensure_future(signaling.add_candidate(self._session_id, payload))
                )

        @pc.on("connectionstatechange")
        def _on_state() -> None:
            if pc.connectionState in {"failed", "closed"}:
                self._events.put_nowait(
                    RawAgentEvent(
                        type="target.participant.left",
                        source="provider_raw",
                        monotonic_ms=0,
                        payload={"state": pc.connectionState},
                    )
                )

        if self._config.get("publish_caller_audio", True):
            self._track = caller_audio_track_class()(WEBRTC_RATE, 1)
            pc.addTrack(self._track)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        session_id, answer_sdp = await signaling.create(pc.localDescription.sdp)
        self._session_id = session_id
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

        pending, self._pending_candidates = self._pending_candidates, []
        for payload in pending:
            self._tasks.append(asyncio.ensure_future(signaling.add_candidate(session_id, payload)))

        self._connected = True
        self._events.put_nowait(
            RawAgentEvent(
                type="connection.ready",
                source="provider_raw",
                monotonic_ms=0,
                payload={"session_id": session_id},
            )
        )

    async def _consume(self, track: Any, av: Any) -> None:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=self._rate)
        try:
            while self._connected:
                frame = await track.recv()
                for out in resampler.resample(frame) or []:
                    data = bytes(out.planes[0])
                    self._audio.put_nowait(
                        AudioChunk(
                            data=data,
                            sample_rate=self._rate,
                            channels=1,
                            format="pcm_s16le",
                            duration_ms=duration_ms(len(data), self._rate, 1),
                        )
                    )
        except Exception:  # pragma: no cover - transport teardown races
            pass

    async def incoming_audio(self) -> AsyncIterator[AudioChunk]:
        while self._connected:
            yield await self._audio.get()

    async def send_audio(self, frame: AudioChunk) -> None:
        if self._track is not None:
            self._track.push(frame)

    def events(self) -> AsyncIterator[RawAgentEvent]:
        async def _gen() -> AsyncIterator[RawAgentEvent]:
            while self._connected:
                yield await self._events.get()

        return _gen()

    async def close(self, reason: CloseReason) -> None:
        self._connected = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        if self._session_id and self._signaling is not None:
            try:
                await self._signaling.close(self._session_id)
            except Exception:
                pass
        if self._pc is not None:
            await self._pc.close()
            self._pc = None


__all__ = ["WhipLink", "caller_audio_track_class", "DEFAULT_BASE_URL"]
