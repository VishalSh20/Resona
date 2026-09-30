"""FloorTracker — who holds the conversational floor, in tens of milliseconds.

Fuses target VAD, interim transcript, end-of-turn probability and caller playout
position into the floor state (§8.1) and keeps per-turn stats. It also provides
the non-speech / music / hold classifier hook used on SIP (§4.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voiceeval.core.clocks import monotonic_ms as default_monotonic_ms


class FloorState(StrEnum):
    SILENCE = "SILENCE"
    TARGET_SPEAKING = "TARGET_SPEAKING"
    CALLER_SPEAKING = "CALLER_SPEAKING"
    OVERLAP = "OVERLAP"
    TARGET_PAUSED = "TARGET_PAUSED"
    CALLER_PLANNING = "CALLER_PLANNING"


class FloorEventKind(StrEnum):
    FLOOR_TAKEN = "floor.taken"
    FLOOR_YIELDED = "floor.yielded"
    OVERLAP_START = "overlap.start"
    OVERLAP_END = "overlap.end"


@dataclass(frozen=True)
class FloorEvent:
    kind: FloorEventKind
    at_ms: int
    state: FloorState
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TargetTurnStats:
    """Per-turn target stats used by the analyzer and interruption planner."""

    words: int = 0
    speech_ms: int = 0
    pauses: int = 0
    end_of_turn_probability: float = 0.0

    def reset(self) -> None:
        self.words = 0
        self.speech_ms = 0
        self.pauses = 0
        self.end_of_turn_probability = 0.0


class FloorTracker:
    """Deterministic floor tracker; call the ``note_*`` methods as signals arrive."""

    def __init__(
        self,
        *,
        clock=default_monotonic_ms,
        paused_after_ms: int = 400,
    ) -> None:
        self._clock = clock
        self._paused_after_ms = paused_after_ms
        self._state = FloorState.SILENCE
        self._target_speaking = False
        self._caller_speaking = False
        self._target_last_speech_ms: int | None = None
        self._target_speech_started_ms: int | None = None
        self._in_overlap = False
        self._in_target_pause = False
        self.turn = TargetTurnStats()

    @property
    def state(self) -> FloorState:
        return self._state

    @property
    def target_speaking(self) -> bool:
        return self._target_speaking

    @property
    def caller_speaking(self) -> bool:
        return self._caller_speaking

    # ------------------------------------------------------------------ inputs
    def note_target_vad(self, active: bool, *, at_ms: int | None = None) -> list[FloorEvent]:
        now = at_ms if at_ms is not None else self._clock()
        events: list[FloorEvent] = []
        if active and not self._target_speaking:
            self._target_speech_started_ms = now
            self._in_target_pause = False
        if not active and self._target_speaking:
            self._target_last_speech_ms = now
        self._target_speaking = active
        events.extend(self._recompute(now))
        return events

    def note_caller_playout(self, active: bool, *, at_ms: int | None = None) -> list[FloorEvent]:
        now = at_ms if at_ms is not None else self._clock()
        self._caller_speaking = active
        return self._recompute(now)

    def note_target_transcript(self, text: str | None = None, *, is_final: bool = False) -> None:
        if text:
            self.turn.words = max(self.turn.words, len(text.split()))
        if is_final:
            self._finalize_turn()

    def note_end_of_turn_probability(self, probability: float) -> None:
        self.turn.end_of_turn_probability = probability

    def mark_caller_planning(self) -> FloorState:
        if not self._target_speaking and not self._caller_speaking:
            self._state = FloorState.CALLER_PLANNING
        return self._state

    def note_non_speech(self, is_hold_or_prompt: bool) -> None:
        """Hold music / IVR menus keep VAD 'speaking'; they must not count as turns."""
        if is_hold_or_prompt:
            self._target_speaking = False
            self.turn.reset()
            self._state = FloorState.SILENCE

    # ----------------------------------------------------------------- internal
    def _finalize_turn(self) -> None:
        if self._target_speech_started_ms is not None:
            end = self._target_last_speech_ms or self._clock()
            self.turn.speech_ms = max(0, end - self._target_speech_started_ms)
        self._target_speech_started_ms = None

    def silence_ms(self, at_ms: int | None = None) -> int:
        if self._target_speaking or self._caller_speaking:
            return 0
        now = at_ms if at_ms is not None else self._clock()
        anchor = self._target_last_speech_ms
        if anchor is None:
            return now
        return max(0, now - anchor)

    def _recompute(self, now: int) -> list[FloorEvent]:
        events: list[FloorEvent] = []
        previous = self._state

        if self._target_speaking and self._caller_speaking:
            new = FloorState.OVERLAP
        elif self._target_speaking:
            new = FloorState.TARGET_SPEAKING
        elif self._caller_speaking:
            new = FloorState.CALLER_SPEAKING
        elif (
            self._target_last_speech_ms is not None
            and self.turn.end_of_turn_probability < 0.5
            and now - self._target_last_speech_ms <= self._paused_after_ms
        ):
            new = FloorState.TARGET_PAUSED
        else:
            new = FloorState.SILENCE

        if new == FloorState.OVERLAP and not self._in_overlap:
            self._in_overlap = True
            events.append(FloorEvent(FloorEventKind.OVERLAP_START, now, new))
        elif new != FloorState.OVERLAP and self._in_overlap:
            self._in_overlap = False
            events.append(FloorEvent(FloorEventKind.OVERLAP_END, now, new))

        if previous != FloorState.CALLER_SPEAKING and new == FloorState.CALLER_SPEAKING:
            events.append(FloorEvent(FloorEventKind.FLOOR_TAKEN, now, new))
        if previous == FloorState.CALLER_SPEAKING and new == FloorState.TARGET_SPEAKING:
            events.append(FloorEvent(FloorEventKind.FLOOR_YIELDED, now, new))

        self._state = new
        return events


__all__ = [
    "FloorEvent",
    "FloorEventKind",
    "FloorState",
    "FloorTracker",
    "TargetTurnStats",
]
