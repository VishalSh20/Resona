"""TargetLink: the transport-specific connection to the agent under evaluation.

A ``TargetLink`` is the caller migration's replacement for the old
``runtime.adapters.TargetAdapter`` transport role. The caller brain is identical
across transports; every connectivity difference is confined to a link
implementation (see ``docs/V2-changes/caller-migration-to-livekit.md`` §4.2).

The contract is deliberately small: ``connect`` · ``incoming_audio`` ·
``send_audio`` · ``send_dtmf`` · ``events`` · ``close`` · ``capabilities``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from voiceeval.runtime.connections import AudioChunk, CloseReason, RawAgentEvent


@dataclass(frozen=True)
class TargetLinkCapabilities:
    """What a transport can do — drives planner and session decisions."""

    codec: str
    sample_rate: int
    channels: int = 1
    supports_dtmf: bool = False
    target_speaks_first: bool = True
    #: True when the link provides its own audio into a shared room (BridgeLink
    #: publishes the target audio as a monitor track), rather than the caller
    #: reading the target's track directly.
    provides_monitor_track: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "codec": self.codec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "supports_dtmf": self.supports_dtmf,
            "target_speaks_first": self.target_speaks_first,
            "provides_monitor_track": self.provides_monitor_track,
        }


class TargetLink(ABC):
    """A live connection to the target agent for one attempt."""

    #: Transport slug (``room`` | ``sip`` | ``bridge``).
    transport: str = ""
    #: Version of the link implementation, recorded on the attempt.
    version: str = "1.0.0"

    def __init__(self, *, sample_rate: int = 24_000) -> None:
        self._sample_rate = sample_rate

    def capabilities(self) -> TargetLinkCapabilities:
        """Return the link's capabilities. Static; safe to call before connect."""
        return TargetLinkCapabilities(
            codec="pcm_s16le", sample_rate=self._sample_rate
        )

    @abstractmethod
    async def connect(self) -> None:
        """Establish the transport connection. The only transport-specific step."""

    @abstractmethod
    def incoming_audio(self) -> AsyncIterator[AudioChunk]:
        """Yield audio received from the target."""

    @abstractmethod
    async def send_audio(self, frame: AudioChunk) -> None:
        """Send caller audio to the target."""

    async def send_dtmf(self, digits: str) -> None:
        """Send DTMF digits. Links without DTMF override ``capabilities``."""
        if not self.capabilities().supports_dtmf:
            raise NotImplementedError(
                f"transport '{self.transport}' does not support DTMF"
            )

    async def send_control(self, message: dict[str, Any]) -> None:
        """Send a link-level control message (e.g. ``caller.turn.end``).

        Default is a no-op; protocol-bearing links (BridgeLink) forward it.
        """
        return None

    @abstractmethod
    def events(self) -> AsyncIterator[RawAgentEvent]:
        """Yield provider-native events (passed through as provider_raw/normalized)."""

    @abstractmethod
    async def close(self, reason: CloseReason) -> None:
        """Tear the connection down."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} transport={self.transport!r}>"


__all__ = ["TargetLink", "TargetLinkCapabilities"]
