"""Explicit state-machine transition tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.domain.enums import (
    AttemptStatus,
    AttemptTerminalStatus,
    CallRunStatus,
    RunStatus,
)
from voiceeval.domain.state_machines import (
    transition_call_attempt,
    transition_call_run,
    transition_run,
)


def test_run_happy_path():
    chain = [
        RunStatus.DRAFT,
        RunStatus.READY,
        RunStatus.QUEUED,
        RunStatus.RUNNING,
        RunStatus.COMPLETED,
    ]
    current = chain[0]
    for target in chain[1:]:
        current = transition_run(current, target)
    assert current is RunStatus.COMPLETED


def test_run_can_cancel_any_nonterminal():
    for state in (
        RunStatus.DRAFT,
        RunStatus.READY,
        RunStatus.QUEUED,
        RunStatus.RUNNING,
        RunStatus.PARTIAL,
    ):
        transition_run(state, RunStatus.CANCELLED)


def test_run_partial_can_resume():
    assert transition_run(RunStatus.PARTIAL, RunStatus.RUNNING) is RunStatus.RUNNING


def test_run_invalid_transition_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition_run(RunStatus.DRAFT, RunStatus.RUNNING)


def test_run_terminal_is_immutable():
    with pytest.raises(InvalidStateTransitionError):
        transition_run(RunStatus.COMPLETED, RunStatus.RUNNING)


def test_call_run_happy_path():
    assert transition_call_run(CallRunStatus.QUEUED, CallRunStatus.RUNNING) is CallRunStatus.RUNNING
    assert transition_call_run(CallRunStatus.RUNNING, CallRunStatus.COMPLETED) is CallRunStatus.COMPLETED


def test_call_run_infrastructure_failed_from_queued():
    transition_call_run(CallRunStatus.QUEUED, CallRunStatus.INFRASTRUCTURE_FAILED)


def test_call_run_terminal_immutable():
    with pytest.raises(InvalidStateTransitionError):
        transition_call_run(CallRunStatus.COMPLETED, CallRunStatus.RUNNING)


def test_attempt_happy_path():
    chain = [
        AttemptStatus.QUEUED,
        AttemptStatus.STARTING,
        AttemptStatus.CONNECTING,
        AttemptStatus.RUNNING,
        AttemptStatus.TERMINATING,
    ]
    current = chain[0]
    for target in chain[1:]:
        current, terminal = transition_call_attempt(current, target)
        assert terminal is None
    current, terminal = transition_call_attempt(
        current, AttemptStatus.TERMINAL, terminal_status=AttemptTerminalStatus.COMPLETED
    )
    assert current is AttemptStatus.TERMINAL
    assert terminal is AttemptTerminalStatus.COMPLETED


def test_attempt_terminal_requires_terminal_status():
    with pytest.raises(InvalidStateTransitionError):
        transition_call_attempt(AttemptStatus.RUNNING, AttemptStatus.TERMINAL)


def test_attempt_can_cancel_before_connecting():
    for state in (AttemptStatus.QUEUED, AttemptStatus.STARTING, AttemptStatus.CONNECTING):
        _, terminal = transition_call_attempt(
            state, AttemptStatus.TERMINAL, terminal_status=AttemptTerminalStatus.CANCELLED
        )
        assert terminal is AttemptTerminalStatus.CANCELLED
