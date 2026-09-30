"""Stop-condition tests: precedence and terminal mapping."""

from __future__ import annotations

from voiceeval.domain.enums import AttemptFailureClass, AttemptTerminalStatus
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.stop_conditions import StopConditionEngine, StopReason


class Clock:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def _engine(clock, **overrides):
    kwargs = dict(
        stall_ms=10_000,
        wall_clock_timeout_ms=180_000,
        max_wall_clock_timeout_ms=300_000,
        clock=clock,
    )
    kwargs.update(overrides)
    return StopConditionEngine(**kwargs)


def _builder(clock):
    return CanonicalEventBuilder("att_1", monotonic_clock=clock)


def test_natural_success_stops_with_completed_and_eligible():
    clock = Clock()
    engine = _engine(clock)
    builder = _builder(clock)
    event = builder.build(
        EventType.CALLER_TERMINAL,
        source=EventSource.CALLER,
        payload={"reason": "NATURAL_SUCCESS"},
    )
    decision = engine.observe(event)
    assert decision is not None
    assert decision.reason is StopReason.NATURAL_SUCCESS
    assert decision.terminal_status is AttemptTerminalStatus.COMPLETED
    assert decision.eligible is True
    assert decision.evidence_event_id == event.event_id


def test_natural_success_wins_over_stall():
    clock = Clock()
    engine = _engine(clock, stall_ms=1000)
    builder = _builder(clock)
    engine.observe(
        builder.build(
            EventType.CALLER_TERMINAL, source=EventSource.CALLER, payload={"reason": "NATURAL_SUCCESS"}
        )
    )
    clock.now = 5_000  # a stall would also be true
    assert engine.check_timeouts().reason is StopReason.NATURAL_SUCCESS


def test_recovery_exhausted_is_semantic_failure():
    clock = Clock()
    engine = _engine(clock)
    event = _builder(clock).build(
        EventType.CALLER_RECOVERY_USED,
        source=EventSource.CALLER,
        payload={"recovery_count": 2, "max_attempts": 2, "exhausted": True},
    )
    decision = engine.observe(event)
    assert decision.reason is StopReason.RECOVERY_EXHAUSTED
    assert decision.terminal_status is AttemptTerminalStatus.FAILED
    assert decision.failure_class is None
    assert decision.eligible is True


def test_partial_recovery_does_not_stop():
    clock = Clock()
    engine = _engine(clock)
    event = _builder(clock).build(
        EventType.CALLER_RECOVERY_USED,
        source=EventSource.CALLER,
        payload={"recovery_count": 1, "max_attempts": 2, "exhausted": False},
    )
    assert engine.observe(event) is None


def test_connection_error_is_retryable_transport_failure():
    clock = Clock()
    engine = _engine(clock)
    event = _builder(clock).build(EventType.CONNECTION_ERROR, source=EventSource.RUNTIME, payload={})
    decision = engine.observe(event)
    assert decision.reason is StopReason.CONNECTION_FAILURE
    assert decision.failure_class is AttemptFailureClass.TRANSPORT
    assert decision.eligible is False


def test_stall_timeout_maps_to_timed_out():
    clock = Clock()
    engine = _engine(clock, stall_ms=1000)
    clock.now = 1000
    decision = engine.check_timeouts()
    assert decision.reason is StopReason.CONVERSATION_STALL
    assert decision.terminal_status is AttemptTerminalStatus.TIMED_OUT


def test_wall_clock_timeout_when_recent_events():
    clock = Clock()
    engine = _engine(clock, stall_ms=10_000, wall_clock_timeout_ms=5_000)
    builder = _builder(clock)
    clock.now = 5_000
    engine.observe(
        builder.build(EventType.AGENT_TEXT_FINAL, source=EventSource.PROVIDER_NORMALIZED, payload={})
    )
    decision = engine.check_timeouts()
    assert decision.reason is StopReason.WALL_CLOCK_TIMEOUT
    assert decision.terminal_status is AttemptTerminalStatus.TIMED_OUT


def test_wall_clock_is_capped_by_max():
    engine = _engine(Clock(), wall_clock_timeout_ms=999_999, max_wall_clock_timeout_ms=300_000)
    assert engine.wall_clock_timeout_ms == 300_000


def test_remaining_stall_ms_counts_down():
    clock = Clock()
    engine = _engine(clock, stall_ms=1000)
    assert engine.remaining_stall_ms() == 1000
    clock.now = 400
    assert engine.remaining_stall_ms() == 600


def test_decision_is_sticky():
    clock = Clock()
    engine = _engine(clock)
    builder = _builder(clock)
    first = engine.observe(
        builder.build(
            EventType.CALLER_TERMINAL, source=EventSource.CALLER, payload={"reason": "NATURAL_SUCCESS"}
        )
    )
    second = engine.observe(
        builder.build(EventType.CONNECTION_ERROR, source=EventSource.RUNTIME, payload={})
    )
    assert second is first


def test_forced_failure_decision():
    engine = _engine(Clock())
    decision = engine.fail(reason=StopReason.CANCELLED, detail={"control": "attempt.cancel"})
    assert decision.terminal_status is AttemptTerminalStatus.CANCELLED
    assert decision.detail == {"control": "attempt.cancel"}
