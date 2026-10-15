"""SipLink — outbound SIP call to a phone number or SIP URI.

Per migration doc §4.3: dispatch the caller first, dial second (so the target's
greeting is not played into an empty room); watch the SIP participant call
status and map it to a terminal reason. Media is carried by the room, so the
audio plane reuses :class:`RoomLink`; this link adds the SIP control plane and
DTMF.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voiceeval.core.config import get_settings
from voiceeval.core.errors import DependencyUnavailableError, ValidationError
from voiceeval.runtime.connections import AudioChunk, CloseReason, RawAgentEvent

#: SIP call-status values → attempt terminal reasons (§4.3 / §4.4).
SIP_STATUS_TO_REASON: dict[str, str] = {
    "active": "ANSWERED",
    "ringing": "RINGING",
    "dialing": "DIALING",
    "busy": "BUSY",
    "no_answer": "NO_ANSWER",
    "declined": "REJECTED",
    "unreachable": "UNREACHABLE",
    "failed": "TRANSPORT_LOST",
}


def _import_api() -> Any:
    try:
        from livekit import api  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional SDK
        raise DependencyUnavailableError(
            "livekit-api is not installed; the 'sip' target link is unavailable"
        ) from exc
    return api


class SipLink:
    """Outbound SIP connector.

    Composes a room-backed media plane (created by the job) with an outbound SIP
    dial. Kept separate from :class:`RoomLink` because the dial lifecycle and
    DTMF surface differ.
    """

    transport = "sip"
    version = "1.0.0"

    def __init__(
        self,
        *,
        endpoint_config: dict[str, Any] | None = None,
        sample_rate: int = 8_000,
        room: Any | None = None,
    ) -> None:
        from voiceeval.runtime.livekit.target_links.room import RoomLink

        self._config = dict(endpoint_config or {})
        if not self._config.get("to_number") and not self._config.get("sip_uri"):
            raise ValidationError(
                "sip target link requires 'to_number' or 'sip_uri' in endpoint_config"
            )
        self._sample_rate = sample_rate
        self._room_link = RoomLink(
            endpoint_config=self._config, sample_rate=sample_rate, room=room
        )
        self._sip_participant_identity: str | None = None
        self._status: str = "created"

    def capabilities(self) -> Any:
        caps = self._room_link.capabilities()
        return type(caps)(
            codec="pcm_s16le",
            sample_rate=self._sample_rate,  # narrowband SIP
            channels=1,
            supports_dtmf=True,
            target_speaks_first=bool(self._config.get("target_speaks_first", True)),
            provides_monitor_track=False,
        )

    async def connect(self) -> None:
        api = _import_api()
        client = api.LiveKitAPI(**self._client_kwargs())
        try:
            participant = await client.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=self._room_name(),
                    sip_trunk_id=self._config.get("trunk_id")
                    or self._config.get("sip_outbound_trunk_id"),
                    sip_call_to=self._config.get("to_number")
                    or self._config.get("sip_uri"),
                    sip_number=self._config.get("from_number"),
                    participant_identity=self._config.get("identity", "sip-target"),
                    wait_until_answered=bool(
                        self._config.get("wait_until_answered", True)
                    ),
                )
            )
        finally:
            await client.aclose()
        self._sip_participant_identity = getattr(participant, "participant_identity", None)
        self._status = "active"
        # Join the room so the media plane is live (caller is dispatched first).
        await self._room_link.connect()

    def _room_name(self) -> str:
        """The caller's room name (the SIP participant joins it)."""
        name = self._config.get("room_name") or getattr(
            getattr(self._room_link, "_room", None), "name", None
        )
        if not name:
            raise ValidationError(
                "sip target link requires the caller room to be known"
            )
        return str(name)

    def _client_kwargs(self) -> dict[str, Any]:
        # SIP dials on *our* LiveKit project (the caller's room lives there);
        # fall back to the deployment settings when endpoint config omits them.
        settings = get_settings()
        return {
            "url": self._config.get("url") or settings.livekit_url,
            "api_key": self._config.get("api_key") or settings.livekit_api_key,
            "api_secret": self._config.get("api_secret") or settings.livekit_api_secret,
        }

    @property
    def status(self) -> str:
        return self._status

    def terminal_reason_for_status(self, sip_status: str) -> str | None:
        return SIP_STATUS_TO_REASON.get(sip_status)

    def incoming_audio(self) -> AsyncIterator[AudioChunk]:
        return self._room_link.incoming_audio()

    async def send_audio(self, frame: AudioChunk) -> None:
        await self._room_link.send_audio(frame)

    async def send_dtmf(self, digits: str) -> None:
        room = getattr(self._room_link, "_room", None)
        if room is None:
            raise DependencyUnavailableError("sip link is not connected")
        for digit in digits:
            await room.local_participant.publish_dtmf(digit=digit)

    def events(self) -> AsyncIterator[RawAgentEvent]:
        return self._room_link.events()

    async def close(self, reason: CloseReason) -> None:
        await self._room_link.close(reason)


__all__ = ["SipLink", "SIP_STATUS_TO_REASON"]
