"""Canonical runtime events and their deterministic construction.

A canonical event is the normalized envelope described in
``03-runtime-event-schema.md``. The builder owns sequence assignment and clock
stamping so every producer (adapters, caller, media) emits well-formed events
with a strictly increasing sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from voiceeval.core.clocks import monotonic_ms as default_monotonic_ms
from voiceeval.core.clocks import utc_now, wall_clock_iso
from voiceeval.core.ids import EntityKind, new_id


class EventType(StrEnum):
    # connection
    CONNECTION_REQUESTED = "connection.requested"
    CONNECTION_WS_OPEN = "connection.ws.open"
    CONNECTION_WS_MESSAGE = "connection.ws.message"
    CONNECTION_WS_ERROR = "connection.ws.error"
    CONNECTION_WS_CLOSE = "connection.ws.close"
    CONNECTION_READY = "connection.ready"
    CONNECTION_ERROR = "connection.error"
    CONNECTION_CLOSED = "connection.closed"

    # caller media / speech / audible
    CALLER_MEDIA_START = "caller.media.start"
    CALLER_MEDIA_CHUNK = "caller.media.chunk"
    CALLER_MEDIA_END = "caller.media.end"
    CALLER_SPEECH_START = "caller.speech.start"
    CALLER_SPEECH_END = "caller.speech.end"
    CALLER_AUDIBLE_START = "caller.audible.start"
    CALLER_AUDIBLE_END = "caller.audible.end"

    # agent media / speech / audible
    AGENT_MEDIA_START = "agent.media.start"
    AGENT_MEDIA_CHUNK = "agent.media.chunk"
    AGENT_MEDIA_END = "agent.media.end"
    AGENT_SPEECH_START = "agent.speech.start"
    AGENT_SPEECH_END = "agent.speech.end"
    AGENT_AUDIBLE_START = "agent.audible.start"
    AGENT_AUDIBLE_END = "agent.audible.end"

    # text
    AGENT_TEXT_FIRST = "agent.text.first"
    AGENT_TEXT_DELTA = "agent.text.delta"
    AGENT_TEXT_FINAL = "agent.text.final"

    # turns
    TURN_START = "turn.start"
    TURN_END = "turn.end"
    TURN_INTERRUPTED = "turn.interrupted"
    TURN_OVERLAPPED = "turn.overlapped"

    # language
    CALLER_LANGUAGE_DETECTED = "caller.language.detected"
    CALLER_CODE_SWITCH_DETECTED = "caller.code_switch.detected"
    AGENT_LANGUAGE_DETECTED = "agent.language.detected"
    AGENT_CODE_SWITCH_DETECTED = "agent.code_switch.detected"

    # tools
    TOOL_CALL_START = "tool.call.start"
    TOOL_CALL_ARGS = "tool.call.args"
    TOOL_CALL_RESULT = "tool.call.result"
    TOOL_CALL_END = "tool.call.end"

    # caller decisions
    CALLER_STATE_INITIALIZED = "caller.state.initialized"
    CALLER_STATE_MUTATED = "caller.state.mutated"
    CALLER_ACTION_SELECTED = "caller.action.selected"
    CALLER_UTTERANCE_REALIZED = "caller.utterance.realized"
    CALLER_INTERRUPTION_SCHEDULED = "caller.interruption.scheduled"
    CALLER_RECOVERY_USED = "caller.recovery.used"
    CALLER_ASSERTION_UPDATED = "caller.assertion.updated"
    CALLER_FALSE_INTERRUPTION = "caller.false_interruption"
    CALLER_TTS_ERROR = "caller.tts_error"
    CALLER_TERMINAL = "caller.terminal"

    # target perception (LiveKit caller migration). These deliberately do NOT use
    # the ``caller.`` prefix: ``EventMaterializer.materialize`` turns every
    # ``caller.``-prefixed event into a state transition, so high-frequency and
    # purely informational events must live under other prefixes.
    TARGET_SPEECH_START = "target.speech.start"
    TARGET_SPEECH_END = "target.speech.end"
    TARGET_TRANSCRIPT_INTERIM = "target.transcript.interim"
    TARGET_TRANSCRIPT_FINAL = "target.transcript.final"

    # floor / interruption (see migration doc §8)
    FLOOR_TAKEN = "floor.taken"
    FLOOR_YIELDED = "floor.yielded"
    OVERLAP_START = "overlap.start"
    OVERLAP_END = "overlap.end"
    BARGE_IN_ATTEMPTED = "barge_in.attempted"
    BARGE_IN_SUCCEEDED = "barge_in.succeeded"
    BARGE_IN_IGNORED = "barge_in.ignored"

    # explainability + metrics (kept out of the ``caller.`` prefix on purpose)
    DECISION_RECORDED = "decision.recorded"
    METRIC_RECORDED = "metric.recorded"

    # Runner-reported lifecycle transitions (the LiveKit job has no adapter
    # lifecycle hook, so it reports connecting/running as canonical events).
    ATTEMPT_LIFECYCLE = "attempt.lifecycle"

    ATTEMPT_TERMINAL = "attempt.terminal"


class EventSource(StrEnum):
    PROVIDER_RAW = "provider_raw"
    PROVIDER_NORMALIZED = "provider_normalized"
    RUNTIME = "runtime"
    DERIVED = "derived"
    CALLER = "caller"
    METRIC = "metric"
    #: Our own transcription of the target's audio (not the provider's captions).
    INDEPENDENT_ASR = "independent_asr"


@dataclass
class CanonicalEvent:
    event_id: str
    call_attempt_id: str
    sequence: int
    type: str
    source: str
    monotonic_ms: int
    wall_clock: datetime
    media_timestamp: int | None = None
    turn_id: str | None = None
    provider_event_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_envelope(self) -> dict[str, Any]:
        """Serialize to the runner->backend ``runtime.event`` envelope."""
        return {
            "event_id": self.event_id,
            "call_attempt_id": self.call_attempt_id,
            "sequence": self.sequence,
            "type": self.type,
            "source": self.source,
            "monotonic_ms": self.monotonic_ms,
            "wall_clock": wall_clock_iso_of(self.wall_clock),
            "media_timestamp": self.media_timestamp,
            "turn_id": self.turn_id,
            "provider_event_id": self.provider_event_id,
            "payload": self.payload,
        }


def wall_clock_iso_of(value: datetime) -> str:
    return value.isoformat()


class CanonicalEventBuilder:
    """Assigns a strictly increasing sequence and clock stamps to events."""

    def __init__(
        self,
        call_attempt_id: str,
        *,
        monotonic_clock=default_monotonic_ms,
        wall_clock=utc_now,
    ) -> None:
        self._call_attempt_id = call_attempt_id
        self._monotonic = monotonic_clock
        self._wall_clock = wall_clock
        self._sequence = 0

    @property
    def sequence(self) -> int:
        return self._sequence

    def build(
        self,
        event_type: str,
        *,
        source: str,
        payload: dict[str, Any] | None = None,
        monotonic_ms: int | None = None,
        media_timestamp: int | None = None,
        turn_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> CanonicalEvent:
        self._sequence += 1
        return CanonicalEvent(
            event_id=new_id(EntityKind.EVENT),
            call_attempt_id=self._call_attempt_id,
            sequence=self._sequence,
            type=str(event_type),
            source=str(source),
            monotonic_ms=(
                monotonic_ms if monotonic_ms is not None else self._monotonic()
            ),
            wall_clock=self._wall_clock(),
            media_timestamp=media_timestamp,
            turn_id=turn_id,
            provider_event_id=provider_event_id,
            payload=payload or {},
        )
