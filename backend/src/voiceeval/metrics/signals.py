"""Deterministic-metric signal extraction.

Metrics are computed from observed truth: the append-only runtime-event log, the
materialized turns and tool calls, and the media artifacts. :class:`AttemptSignals`
turns those heterogeneous records into a small queryable timeline so metric
implementations never reach into ORM objects or raw provider payloads.

Every derived boundary (e.g. an audibility edge synthesized from media activity)
is flagged, and clock domains are recorded in the measurement basis, so the
provenance of a latency number stays explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.runtime.events import EventType

CLOCK_RUNNER_MONOTONIC = "runner_monotonic"


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


@dataclass(frozen=True)
class TimelineEvent:
    type: str
    monotonic_ms: int
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str | None = None
    source: str | None = None
    media_timestamp: int | None = None
    turn_id: str | None = None


@dataclass(frozen=True)
class TurnView:
    turn_id: str | None
    speaker: str
    sequence_no: int | None
    start_ms: int | None
    end_ms: int | None
    reference_text: str | None
    observed_text: str | None
    transcript_source: str | None

    @property
    def duration_ms(self) -> int | None:
        if self.start_ms is None or self.end_ms is None:
            return None
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class ToolCallView:
    call_id: str | None
    ordinal: int | None
    tool_name: str
    arguments: dict[str, Any] | None
    result: dict[str, Any] | None
    status: str | None
    start_ms: int | None
    end_ms: int | None


@dataclass(frozen=True)
class MediaView:
    media_id: str | None
    track: str
    representation: str
    duration_ms: int | None
    sample_rate: int | None
    sha256: str | None


def _timeline_event(event: Any) -> TimelineEvent:
    return TimelineEvent(
        type=str(_attr(event, "type", "event_type", default="")),
        monotonic_ms=int(_attr(event, "monotonic_ms", default=0) or 0),
        payload=dict(_attr(event, "payload", default={}) or {}),
        event_id=_attr(event, "event_id", "id"),
        source=_attr(event, "source"),
        media_timestamp=_attr(event, "media_timestamp"),
        turn_id=_attr(event, "turn_id"),
    )


def _turn_view(turn: Any) -> TurnView:
    return TurnView(
        turn_id=_attr(turn, "turn_id", "id"),
        speaker=str(_attr(turn, "speaker", default="")),
        sequence_no=_attr(turn, "sequence_no"),
        start_ms=_attr(turn, "start_ms"),
        end_ms=_attr(turn, "end_ms"),
        reference_text=_attr(turn, "reference_text"),
        observed_text=_attr(turn, "observed_text"),
        transcript_source=_attr(turn, "transcript_source"),
    )


def _tool_view(tool: Any) -> ToolCallView:
    return ToolCallView(
        call_id=_attr(tool, "call_id", "id"),
        ordinal=_attr(tool, "ordinal"),
        tool_name=str(_attr(tool, "tool_name", default="")),
        arguments=dict(_attr(tool, "arguments", default={}) or {}) or None,
        result=dict(_attr(tool, "result", default={}) or {}) or None,
        status=_attr(tool, "status"),
        start_ms=_attr(tool, "start_ms"),
        end_ms=_attr(tool, "end_ms"),
    )


def _media_view(media: Any) -> MediaView:
    return MediaView(
        media_id=_attr(media, "media_id", "id"),
        track=str(_attr(media, "track", default="")),
        representation=str(_attr(media, "representation", default="")),
        duration_ms=_attr(media, "duration_ms"),
        sample_rate=_attr(media, "sample_rate"),
        sha256=_attr(media, "sha256"),
    )


def _chunk_duration_ms(event: TimelineEvent) -> int:
    payload = event.payload or {}
    explicit = payload.get("duration_ms")
    if explicit is not None:
        return int(explicit)
    bytes_ = payload.get("bytes")
    sample_rate = int(payload.get("sample_rate") or 16000)
    channels = int(payload.get("channels") or 1)
    if bytes_:
        samples = int(bytes_) / (2 * max(1, channels))
        return int(samples * 1000 / max(1, sample_rate))
    return 0


@dataclass
class AttemptSignals:
    """A queryable view over one attempt's observed truth."""

    events: list[TimelineEvent] = field(default_factory=list)
    turns: list[TurnView] = field(default_factory=list)
    tool_calls: list[ToolCallView] = field(default_factory=list)
    media: list[MediaView] = field(default_factory=list)

    @classmethod
    def from_records(
        cls,
        *,
        events: list[Any] | None = None,
        turns: list[Any] | None = None,
        tool_calls: list[Any] | None = None,
        media: list[Any] | None = None,
    ) -> "AttemptSignals":
        timeline = [_timeline_event(e) for e in (events or [])]
        # Stable sort by monotonic time; equal timestamps keep ingestion order.
        timeline.sort(key=lambda e: e.monotonic_ms)
        return cls(
            events=timeline,
            turns=[_turn_view(t) for t in (turns or [])],
            tool_calls=[_tool_view(t) for t in (tool_calls or [])],
            media=[_media_view(m) for m in (media or [])],
        )

    # -- raw event access -----------------------------------------------------

    def by_type(self, event_type: str | EventType) -> list[TimelineEvent]:
        name = str(event_type)
        return [event for event in self.events if event.type == name]

    def first(self, event_type: str | EventType) -> TimelineEvent | None:
        found = self.by_type(event_type)
        return found[0] if found else None

    def last(self, event_type: str | EventType) -> TimelineEvent | None:
        found = self.by_type(event_type)
        return found[-1] if found else None

    def first_at_or_after(
        self, event_type: str | EventType, monotonic_ms: int
    ) -> TimelineEvent | None:
        for event in self.by_type(event_type):
            if event.monotonic_ms >= monotonic_ms:
                return event
        return None

    def last_at_or_before(
        self, event_type: str | EventType, monotonic_ms: int
    ) -> TimelineEvent | None:
        found = [
            event
            for event in self.by_type(event_type)
            if event.monotonic_ms <= monotonic_ms
        ]
        return found[-1] if found else None

    def span_ms(self) -> int | None:
        if len(self.events) < 2:
            return None
        return self.events[-1].monotonic_ms - self.events[0].monotonic_ms

    # -- derived audibility boundaries ---------------------------------------

    def caller_audible_end_points(self) -> list[tuple[int, bool]]:
        """Caller audible-end times as ``(monotonic_ms, derived)`` pairs."""
        explicit = [
            (event.monotonic_ms, False)
            for event in self.by_type(EventType.CALLER_AUDIBLE_END)
        ]
        if explicit:
            return explicit
        chunks = self.by_type(EventType.CALLER_MEDIA_CHUNK)
        if chunks:
            return [
                (chunk.monotonic_ms + _chunk_duration_ms(chunk), True)
                for chunk in chunks
            ]
        return [
            (event.monotonic_ms, True)
            for event in self.by_type(EventType.CALLER_MEDIA_END)
        ]

    def caller_audible_end_ms(self) -> tuple[int, bool] | None:
        points = self.caller_audible_end_points()
        return points[-1] if points else None

    def agent_audible_windows(self) -> list[tuple[int, int, bool]]:
        """Agent audibility windows as ``(start_ms, end_ms, derived)``.

        Explicit ``agent.audible.start``/``agent.audible.end`` events are used
        when present. Otherwise windows are derived from the agent's declared
        speech boundaries, falling back to media activity grouped by turn (the
        configured audio-activity detector's job in production).
        """
        starts = self.by_type(EventType.AGENT_AUDIBLE_START)
        ends = self.by_type(EventType.AGENT_AUDIBLE_END)
        if starts and ends:
            return [
                (start.monotonic_ms, end.monotonic_ms, False)
                for start, end in zip(starts, ends)
            ]
        if starts:
            # Onset observed; end unknown. A degenerate window still supports
            # onset-based metrics (TTFA) but never an interruption measurement.
            return [(start.monotonic_ms, start.monotonic_ms, False) for start in starts]

        speech_starts = self.by_type(EventType.AGENT_SPEECH_START)
        speech_ends = self.by_type(EventType.AGENT_SPEECH_END)
        if speech_starts and speech_ends:
            return [
                (start.monotonic_ms, end.monotonic_ms, True)
                for start, end in zip(speech_starts, speech_ends)
            ]

        chunks = self.by_type(EventType.AGENT_MEDIA_CHUNK)
        if chunks:
            grouped: dict[str, list[TimelineEvent]] = {}
            for chunk in chunks:
                grouped.setdefault(chunk.turn_id or "__all__", []).append(chunk)
            windows: list[tuple[int, int, bool]] = []
            for group in grouped.values():
                start = min(chunk.monotonic_ms for chunk in group)
                end = max(
                    chunk.monotonic_ms + _chunk_duration_ms(chunk) for chunk in group
                )
                windows.append((start, end, True))
            windows.sort()
            return windows
        return []

    def agent_audible_start_ms(self) -> tuple[int, bool] | None:
        windows = self.agent_audible_windows()
        return (windows[0][0], windows[0][2]) if windows else None

    def agent_audible_end_ms(self) -> tuple[int, bool] | None:
        windows = self.agent_audible_windows()
        return (windows[-1][1], windows[-1][2]) if windows else None

    def caller_speech_start_times(self) -> list[int]:
        """All caller speech onsets, explicit or derived from media activity."""
        explicit = [event.monotonic_ms for event in self.by_type(EventType.CALLER_SPEECH_START)]
        if explicit:
            return explicit
        audible = [event.monotonic_ms for event in self.by_type(EventType.CALLER_AUDIBLE_START)]
        if audible:
            return audible
        return [event.monotonic_ms for event in self.by_type(EventType.CALLER_MEDIA_CHUNK)]

    def caller_speech_start_ms(self) -> tuple[int, bool] | None:
        event = self.first(EventType.CALLER_SPEECH_START)
        if event is not None:
            return event.monotonic_ms, False
        audible = self.first(EventType.CALLER_AUDIBLE_START)
        if audible is not None:
            return audible.monotonic_ms, True
        chunk = self.first(EventType.CALLER_MEDIA_CHUNK)
        if chunk is not None:
            return chunk.monotonic_ms, True
        return None

    def agent_text_first_ms(self) -> int | None:
        event = self.first(EventType.AGENT_TEXT_FIRST)
        return event.monotonic_ms if event else None

    # -- transcripts / provenance --------------------------------------------

    def caller_reference_texts(self) -> list[str]:
        return [
            turn.reference_text
            for turn in self.turns
            if turn.speaker == "caller" and turn.reference_text
        ]

    def transcript_texts(self, source: str) -> list[str]:
        return [
            turn.observed_text
            for turn in self.turns
            if turn.transcript_source == source and turn.observed_text
        ]

    def provider_target_input_texts(self) -> list[str]:
        return self.transcript_texts("provider_target_input")

    def provider_target_output_texts(self) -> list[str]:
        return self.transcript_texts("provider_target_output")

    def independent_asr_texts(self) -> list[str]:
        return self.transcript_texts("independent_asr")

    def observed_agent_texts(self) -> list[str]:
        texts = [
            turn.observed_text
            for turn in self.turns
            if turn.speaker == "agent" and turn.observed_text
        ]
        for event in self.by_type(EventType.AGENT_TEXT_FINAL):
            text = (event.payload or {}).get("text")
            if text:
                texts.append(str(text))
        return texts

    def agent_assertions(self) -> list[str]:
        assertions: list[str] = []
        for event in self.by_type(EventType.AGENT_TEXT_FINAL):
            for assertion in (event.payload or {}).get("assertions") or []:
                assertions.append(str(assertion))
        return assertions

    def caller_terminal_payload(self) -> dict[str, Any] | None:
        event = self.last(EventType.CALLER_TERMINAL)
        return dict(event.payload) if event else None

    def turn_durations_ms(self) -> list[int]:
        durations = [
            duration
            for duration in (turn.duration_ms for turn in self.turns)
            if duration is not None
        ]
        if durations:
            return durations
        # Fall back to pairing turn.start/turn.end events by turn id when the
        # materialized turn has not been closed yet.
        starts = {
            event.turn_id: event.monotonic_ms
            for event in self.by_type(EventType.TURN_START)
            if event.turn_id
        }
        ends = {
            event.turn_id: event.monotonic_ms
            for event in self.by_type(EventType.TURN_END)
            if event.turn_id
        }
        return [
            ends[turn_id] - start
            for turn_id, start in starts.items()
            if turn_id in ends and ends[turn_id] >= start
        ]
