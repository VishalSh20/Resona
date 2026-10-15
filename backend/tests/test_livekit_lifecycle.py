"""Lifecycle machine, failure classifier and event mapper (§4.4, §4.5, §10)."""

from __future__ import annotations

import pytest

from voiceeval.domain.enums import AttemptFailureClass, AttemptTerminalStatus
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.livekit.event_mapping import SessionEventMapper, SessionSignal
from voiceeval.runtime.livekit.failure import FailureKind, classify_failure
from voiceeval.runtime.livekit.lifecycle import (
    ConnectionState,
    InvalidTransitionError,
    LifecycleMachine,
    LifecycleTimeouts,
)


def test_lifecycle_happy_path():
    machine = LifecycleMachine()
    for state in (
        ConnectionState.DISPATCHED,
        ConnectionState.REGISTERED,
        ConnectionState.DIALING,
        ConnectionState.RINGING,
        ConnectionState.ANSWERED,
        ConnectionState.CONVERSING,
        ConnectionState.CLOSING,
        ConnectionState.ENDED,
    ):
        machine.transition(state)
    assert machine.terminal
    assert not machine.failed
    assert machine.history[0] == ConnectionState.INIT


def test_lifecycle_rejects_invalid_transition():
    machine = LifecycleMachine()
    with pytest.raises(InvalidTransitionError):
        machine.transition(ConnectionState.ANSWERED)


def test_lifecycle_failure_exit_allowed_from_any_non_terminal():
    machine = LifecycleMachine()
    machine.transition(ConnectionState.DISPATCHED)
    machine.fail(ConnectionState.BUSY)
    assert machine.failed and machine.terminal


def test_lifecycle_timeouts_per_phase():
    timeouts = LifecycleTimeouts(dispatch_ms=1, ring_ms=2, conversation_stall_ms=3)
    assert timeouts.for_state(ConnectionState.DISPATCHED) == 1
    assert timeouts.for_state(ConnectionState.RINGING) == 2
    assert timeouts.for_state(ConnectionState.CONVERSING) == 3
    assert timeouts.for_state(ConnectionState.ENDED) is None


@pytest.mark.parametrize(
    "reason,kind,retryable,terminal",
    [
        ("DISPATCH_TIMEOUT", FailureKind.INFRASTRUCTURE, True, AttemptTerminalStatus.FAILED),
        ("TRANSPORT_LOST", FailureKind.INFRASTRUCTURE, True, AttemptTerminalStatus.FAILED),
        ("NO_ANSWER", FailureKind.TARGET_OUTCOME, False, AttemptTerminalStatus.COMPLETED),
        ("BUSY", FailureKind.TARGET_OUTCOME, False, AttemptTerminalStatus.COMPLETED),
        ("CONVERSATION_STALL", FailureKind.TIMEOUT, False, AttemptTerminalStatus.TIMED_OUT),
        ("NATURAL_SUCCESS", FailureKind.SUCCESS, False, AttemptTerminalStatus.COMPLETED),
        ("CANCELLED", FailureKind.CANCELLED, False, AttemptTerminalStatus.CANCELLED),
    ],
)
def test_classify_failure(reason, kind, retryable, terminal):
    result = classify_failure(reason)
    assert result.kind == kind
    assert result.retryable == retryable
    assert result.terminal_status == terminal


def test_classify_degraded_is_completed_and_flagged():
    result = classify_failure("HIGH_PACKET_LOSS")
    assert result.kind == FailureKind.ENVIRONMENT_DEGRADED
    assert result.degraded is True
    assert result.eligible is True
    assert result.failure_class is None


def test_classify_unknown_defaults_to_retryable_infrastructure():
    result = classify_failure("something-weird")
    assert result.kind == FailureKind.INFRASTRUCTURE
    assert result.retryable is True


def test_event_mapper_maps_signals_to_canonical_events():
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 100)
    mapper = SessionEventMapper(builder)
    event = mapper.emit(SessionSignal.TARGET_SPEECH_START, payload={"x": 1})
    assert event.type == EventType.TARGET_SPEECH_START
    assert event.source == EventSource.PROVIDER_NORMALIZED
    assert event.sequence == 1
    assert mapper.emit(SessionSignal.FLOOR_TAKEN).sequence == 2


def test_high_frequency_signals_avoid_the_caller_prefix():
    # Otherwise EventMaterializer would materialize them as state transitions.
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 0)
    mapper = SessionEventMapper(builder)
    for signal in (
        SessionSignal.TARGET_SPEECH_START,
        SessionSignal.FLOOR_TAKEN,
        SessionSignal.OVERLAP_START,
        SessionSignal.BARGE_IN_ATTEMPTED,
        SessionSignal.DECISION_RECORDED,
        SessionSignal.METRIC_RECORDED,
    ):
        assert not str(mapper.emit(signal).type).startswith("caller.")


def test_terminal_signal_maps_to_attempt_terminal():
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 0)
    mapper = SessionEventMapper(builder)
    event = mapper.emit(
        SessionSignal.TERMINAL, payload={"terminal_status": "completed"}
    )
    assert event.type == EventType.ATTEMPT_TERMINAL
    assert event.source == EventSource.RUNTIME
