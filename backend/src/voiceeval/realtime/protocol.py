"""Runner control WebSocket message schemas.

The runner channel is telemetry/control, never the audio path. Messages are JSON
text frames. Inbound (runner -> backend) messages are the three types below;
outbound (backend -> runner) control messages are built by the helper functions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from voiceeval.core.clocks import wall_clock_iso
from voiceeval.core.errors import ValidationError

EventSource = Literal[
    "provider_raw",
    "provider_normalized",
    "runtime",
    "derived",
    "caller",
    "metric",
]


class RunnerRegister(BaseModel):
    type: Literal["runner.register"]
    attempt_id: str
    runner_id: str
    runner_version: str


class RunnerHeartbeat(BaseModel):
    type: Literal["runner.heartbeat"]
    attempt_id: str
    monotonic_ms: int


class RuntimeEventEnvelope(BaseModel):
    """Canonical runtime event envelope (03-runtime-event-schema.md)."""

    event_id: str
    call_attempt_id: str
    sequence: int
    type: str
    source: EventSource
    monotonic_ms: int
    wall_clock: datetime
    media_timestamp: int | None = None
    turn_id: str | None = None
    provider_event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RuntimeEventMessage(BaseModel):
    type: Literal["runtime.event"]
    event: RuntimeEventEnvelope


RunnerMessage = RunnerRegister | RunnerHeartbeat | RuntimeEventMessage

_MESSAGE_PARSERS: dict[str, type[BaseModel]] = {
    "runner.register": RunnerRegister,
    "runner.heartbeat": RunnerHeartbeat,
    "runtime.event": RuntimeEventMessage,
}


def parse_runner_message(raw: dict[str, Any]) -> RunnerMessage:
    """Parse an inbound runner message, rejecting unknown message types."""
    msg_type = raw.get("type")
    parser = _MESSAGE_PARSERS.get(msg_type)
    if parser is None:
        raise ValidationError(f"unknown runner message type '{msg_type}'")
    return parser.model_validate(raw)


def build_heartbeat_ack() -> dict[str, str]:
    return {"type": "runner.heartbeat_ack", "server_time": wall_clock_iso()}


def build_event_ack(sequence: int) -> dict[str, Any]:
    """Acknowledge a stored runtime event so the runner can drop it from its
    bounded replay buffer (§10 caution 2)."""
    return {"type": "runner.event_ack", "sequence": sequence}


def build_cancel(reason: str) -> dict[str, str]:
    return {"type": "attempt.cancel", "reason": reason}


def build_terminate(reason: str) -> dict[str, str]:
    return {"type": "attempt.terminate", "reason": reason}
