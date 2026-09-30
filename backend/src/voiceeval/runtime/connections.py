"""Runtime connection boundary.

Transport, provider semantics and evaluation semantics are kept strictly
separate: ``AgentConnection`` is the transport-level contract a target adapter
implements; decoding provider messages into canonical events is the adapter's
job; evaluation never sees raw provider payloads.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class CloseReason(StrEnum):
    CALLER_ENDED = "CALLER_ENDED"
    NATURAL_SUCCESS = "NATURAL_SUCCESS"
    WALL_CLOCK_TIMEOUT = "WALL_CLOCK_TIMEOUT"
    CONVERSATION_STALL = "CONVERSATION_STALL"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    PLAN_CANCELLED = "PLAN_CANCELLED"
    RUNNER_SHUTDOWN = "RUNNER_SHUTDOWN"


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sample_rate: int
    channels: int = 1
    format: str = "pcm_s16le"
    duration_ms: int | None = None

    def __len__(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class RawAgentEvent:
    """A provider-level observation, before canonical normalization."""

    type: str
    source: str
    monotonic_ms: int
    payload: dict[str, Any] = field(default_factory=dict)
    media_timestamp: int | None = None
    turn_id: str | None = None
    provider_event_id: str | None = None
    raw: bool = False


@dataclass(frozen=True)
class CapabilitySnapshot:
    """The capability map a target exposes (see 02-domain-schema.md)."""

    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "CapabilitySnapshot":
        return cls(values or {})

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass(frozen=True)
class ConnectionConfig:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    sample_rate: int = 16000
    channels: int = 1
    timeout_s: float = 10.0
    options: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AgentConnection(Protocol):
    async def connect(self, config: ConnectionConfig) -> None: ...

    async def send_audio(self, chunk: AudioChunk) -> None: ...

    def receive(self) -> AsyncIterator[RawAgentEvent]: ...

    async def close(self, reason: CloseReason) -> None: ...

    def capabilities(self) -> CapabilitySnapshot: ...
