"""Mapping of LiveKit session signals to canonical runtime events (§10).

The runner WebSocket protocol and the ingestion/materialization path are
unchanged; only the producer changes. This mapper is that producer's adapter
from framework signal names to the canonical :class:`EventType` envelope.

High-frequency signals (floor, target, metrics, decisions) deliberately map to
non-``caller.`` prefixes so ``EventMaterializer`` does not turn them into state
transitions (§10 caution 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from voiceeval.runtime.events import (
    CanonicalEvent,
    CanonicalEventBuilder,
    EventSource,
    EventType,
)


class SessionSignal(StrEnum):
    # perception
    TARGET_SPEECH_START = "target_speech_start"
    TARGET_SPEECH_END = "target_speech_end"
    TARGET_TRANSCRIPT_INTERIM = "target_transcript_interim"
    TARGET_TRANSCRIPT_FINAL = "target_transcript_final"
    # turns
    CALLER_TURN_START = "caller_turn_start"
    CALLER_TURN_END = "caller_turn_end"
    TURN_INTERRUPTED = "turn_interrupted"
    TURN_OVERLAPPED = "turn_overlapped"
    # floor / interruption
    FLOOR_TAKEN = "floor_taken"
    FLOOR_YIELDED = "floor_yielded"
    OVERLAP_START = "overlap_start"
    OVERLAP_END = "overlap_end"
    BARGE_IN_ATTEMPTED = "barge_in_attempted"
    BARGE_IN_SUCCEEDED = "barge_in_succeeded"
    BARGE_IN_IGNORED = "barge_in_ignored"
    FALSE_INTERRUPTION = "false_interruption"
    # state / decisions / metrics
    STATE_MUTATED = "state_mutated"
    DECISION_RECORDED = "decision_recorded"
    METRIC_RECORDED = "metric_recorded"
    # provider-native passthrough
    PROVIDER_RAW = "provider_raw"
    PROVIDER_NORMALIZED = "provider_normalized"
    # terminal
    TERMINAL = "terminal"


#: signal → (canonical event type, event source)
SIGNAL_MAP: dict[SessionSignal, tuple[EventType, EventSource]] = {
    SessionSignal.TARGET_SPEECH_START: (
        EventType.TARGET_SPEECH_START,
        EventSource.PROVIDER_NORMALIZED,
    ),
    SessionSignal.TARGET_SPEECH_END: (
        EventType.TARGET_SPEECH_END,
        EventSource.PROVIDER_NORMALIZED,
    ),
    SessionSignal.TARGET_TRANSCRIPT_INTERIM: (
        EventType.TARGET_TRANSCRIPT_INTERIM,
        EventSource.PROVIDER_NORMALIZED,
    ),
    SessionSignal.TARGET_TRANSCRIPT_FINAL: (
        EventType.TARGET_TRANSCRIPT_FINAL,
        EventSource.PROVIDER_NORMALIZED,
    ),
    SessionSignal.CALLER_TURN_START: (EventType.TURN_START, EventSource.CALLER),
    SessionSignal.CALLER_TURN_END: (EventType.TURN_END, EventSource.CALLER),
    SessionSignal.TURN_INTERRUPTED: (EventType.TURN_INTERRUPTED, EventSource.CALLER),
    SessionSignal.TURN_OVERLAPPED: (EventType.TURN_OVERLAPPED, EventSource.CALLER),
    SessionSignal.FLOOR_TAKEN: (EventType.FLOOR_TAKEN, EventSource.DERIVED),
    SessionSignal.FLOOR_YIELDED: (EventType.FLOOR_YIELDED, EventSource.DERIVED),
    SessionSignal.OVERLAP_START: (EventType.OVERLAP_START, EventSource.DERIVED),
    SessionSignal.OVERLAP_END: (EventType.OVERLAP_END, EventSource.DERIVED),
    SessionSignal.BARGE_IN_ATTEMPTED: (EventType.BARGE_IN_ATTEMPTED, EventSource.DERIVED),
    SessionSignal.BARGE_IN_SUCCEEDED: (EventType.BARGE_IN_SUCCEEDED, EventSource.DERIVED),
    SessionSignal.BARGE_IN_IGNORED: (EventType.BARGE_IN_IGNORED, EventSource.DERIVED),
    SessionSignal.FALSE_INTERRUPTION: (
        EventType.CALLER_FALSE_INTERRUPTION,
        EventSource.DERIVED,
    ),
    SessionSignal.STATE_MUTATED: (EventType.CALLER_STATE_MUTATED, EventSource.CALLER),
    SessionSignal.DECISION_RECORDED: (EventType.DECISION_RECORDED, EventSource.DERIVED),
    SessionSignal.METRIC_RECORDED: (EventType.METRIC_RECORDED, EventSource.METRIC),
    SessionSignal.PROVIDER_RAW: (EventType.CONNECTION_WS_MESSAGE, EventSource.PROVIDER_RAW),
    SessionSignal.PROVIDER_NORMALIZED: (
        EventType.CONNECTION_WS_MESSAGE,
        EventSource.PROVIDER_NORMALIZED,
    ),
    SessionSignal.TERMINAL: (EventType.ATTEMPT_TERMINAL, EventSource.RUNTIME),
}


@dataclass
class SessionEventMapper:
    """Turns framework signals into canonical events via a shared builder."""

    builder: CanonicalEventBuilder
    _emitted: int = field(default=0, init=False)

    @property
    def emitted(self) -> int:
        return self._emitted

    def emit(
        self,
        signal: SessionSignal,
        *,
        payload: dict | None = None,
        monotonic_ms: int | None = None,
        media_timestamp: int | None = None,
        turn_id: str | None = None,
        provider_event_id: str | None = None,
    ) -> CanonicalEvent:
        event_type, source = SIGNAL_MAP[signal]
        event = self.builder.build(
            event_type,
            source=source,
            payload=payload,
            monotonic_ms=monotonic_ms,
            media_timestamp=media_timestamp,
            turn_id=turn_id,
            provider_event_id=provider_event_id,
        )
        self._emitted += 1
        return event


__all__ = ["SIGNAL_MAP", "SessionEventMapper", "SessionSignal"]
