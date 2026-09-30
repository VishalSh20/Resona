"""WebRTC target adapter: interface and validation contract only.

v1 does **not** implement WebRTC media transport. This module defines the shape
that a future implementation must satisfy (signaling, SDP offer/answer, ICE,
codecs, authentication, audio tracks) so that configurations can be modelled and
validated now, while execution fails loudly rather than pretending generic
WebRTC compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.core.errors import ConnectionFailedError, ValidationError
from voiceeval.runtime.adapters.base import TargetAdapter
from voiceeval.runtime.connections import AgentConnection

SUPPORTED_SIGNALING_METHODS = {"POST", "PUT", "WEBSOCKET"}


@dataclass(frozen=True)
class IceServer:
    urls: list[str] = field(default_factory=list)
    username: str | None = None
    credential: str | None = None


@dataclass(frozen=True)
class WebRTCEndpointConfig:
    """The eventual WebRTC endpoint shape."""

    signaling_url: str
    signaling_method: str = "POST"
    ice_servers: list[IceServer] = field(default_factory=list)
    codecs: list[str] = field(default_factory=list)
    audio_tracks: list[str] = field(default_factory=list)
    authentication: dict[str, Any] = field(default_factory=dict)
    supports_offer: bool = True
    supports_answer: bool = False

    @classmethod
    def parse(cls, endpoint_config: dict[str, Any]) -> "WebRTCEndpointConfig":
        signaling = endpoint_config.get("signaling") or {}
        ice = [
            IceServer(
                urls=list(server.get("urls") or []),
                username=server.get("username"),
                credential=server.get("credential"),
            )
            for server in (endpoint_config.get("ice_servers") or [])
            if isinstance(server, dict)
        ]
        return cls(
            signaling_url=str(
                signaling.get("url") or endpoint_config.get("url") or ""
            ),
            signaling_method=str(signaling.get("method", "POST")).upper(),
            ice_servers=ice,
            codecs=list(endpoint_config.get("codecs") or []),
            audio_tracks=list(endpoint_config.get("audio_tracks") or []),
            authentication=dict(endpoint_config.get("authentication") or {}),
            supports_offer=bool(signaling.get("offer", True)),
            supports_answer=bool(signaling.get("answer", False)),
        )


class WebRTCAdapter(TargetAdapter):
    name = "webrtc"
    version = "1.0.0"
    transport = "webrtc"

    def validate_config(self, endpoint_config: dict[str, Any]) -> None:
        parsed = WebRTCEndpointConfig.parse(endpoint_config)
        if not parsed.signaling_url:
            raise ValidationError("webrtc endpoint requires a signaling url")
        if parsed.signaling_method not in SUPPORTED_SIGNALING_METHODS:
            raise ValidationError(
                "webrtc signaling_method must be one of "
                f"{sorted(SUPPORTED_SIGNALING_METHODS)}"
            )
        if not parsed.supports_offer and not parsed.supports_answer:
            raise ValidationError(
                "webrtc endpoint must support SDP offer or answer"
            )
        if not parsed.ice_servers:
            raise ValidationError("webrtc endpoint requires at least one ice server")
        for server in parsed.ice_servers:
            if not server.urls:
                raise ValidationError("webrtc ice server requires at least one url")
        if not parsed.codecs:
            raise ValidationError("webrtc endpoint requires at least one codec")
        if not parsed.audio_tracks:
            raise ValidationError("webrtc endpoint requires at least one audio track")

    def build_connection(
        self, endpoint_config: dict[str, Any], *, sample_rate: int | None = None
    ) -> AgentConnection:
        self.validate_config(endpoint_config)
        raise ConnectionFailedError(
            "WebRTC media transport is not implemented in v1; WebRTC targets "
            "are configuration-validated only and cannot be executed yet"
        )
