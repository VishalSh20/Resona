"""Explicit state-machine transition functions.

Status mutation is never arbitrary: each domain entity exposes the exact set of
legal transitions from the design documents. Attempting anything else raises
:class:`InvalidStateTransitionError`.

The maps below mirror ``05-state-machines-validation.md``. Where the source
documents conflict (notably the evaluator ``rejected`` status, which appears in
``02-domain-schema.md`` but not in the state-machine diagram), both pieces of
information are preserved and the decision documented in ``docs/decisions/``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.domain.enums import (
    AttemptStatus,
    AttemptTerminalStatus,
    CallRunStatus,
    RunStatus,
)

_StatusT = TypeVar("_StatusT", bound=StrEnum)

# DRAFT -> READY -> QUEUED -> RUNNING -> (PARTIAL | COMPLETED); any non-terminal
# may be CANCELLED. PARTIAL may resume back to RUNNING.
RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.DRAFT: frozenset({RunStatus.READY, RunStatus.CANCELLED}),
    RunStatus.READY: frozenset({RunStatus.QUEUED, RunStatus.CANCELLED}),
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {RunStatus.PARTIAL, RunStatus.COMPLETED, RunStatus.CANCELLED}
    ),
    RunStatus.PARTIAL: frozenset(
        {RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.CANCELLED}
    ),
}

# QUEUED -> RUNNING -> COMPLETED; exceptional terminals INFRASTRUCTURE_FAILED /
# CANCELLED from either non-terminal state.
CALL_RUN_TRANSITIONS: dict[CallRunStatus, frozenset[CallRunStatus]] = {
    CallRunStatus.QUEUED: frozenset(
        {
            CallRunStatus.RUNNING,
            CallRunStatus.INFRASTRUCTURE_FAILED,
            CallRunStatus.CANCELLED,
        }
    ),
    CallRunStatus.RUNNING: frozenset(
        {
            CallRunStatus.COMPLETED,
            CallRunStatus.INFRASTRUCTURE_FAILED,
            CallRunStatus.CANCELLED,
        }
    ),
}

# QUEUED -> STARTING -> CONNECTING -> RUNNING -> TERMINATING -> TERMINAL. Any
# pre-terminal state may jump straight to TERMINAL (e.g. cancellation before the
# connection is established). Reaching TERMINAL requires a terminal class.
ATTEMPT_TRANSITIONS: dict[AttemptStatus, frozenset[AttemptStatus]] = {
    AttemptStatus.QUEUED: frozenset(
        {AttemptStatus.STARTING, AttemptStatus.TERMINAL}
    ),
    AttemptStatus.STARTING: frozenset(
        {AttemptStatus.CONNECTING, AttemptStatus.TERMINAL}
    ),
    AttemptStatus.CONNECTING: frozenset(
        {AttemptStatus.RUNNING, AttemptStatus.TERMINAL}
    ),
    AttemptStatus.RUNNING: frozenset(
        {AttemptStatus.TERMINATING, AttemptStatus.TERMINAL}
    ),
    AttemptStatus.TERMINATING: frozenset({AttemptStatus.TERMINAL}),
}

TERMINAL_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.CANCELLED,
    CallRunStatus.COMPLETED,
    CallRunStatus.INFRASTRUCTURE_FAILED,
    CallRunStatus.CANCELLED,
    AttemptStatus.TERMINAL,
}


def _transition(
    current: _StatusT,
    target: _StatusT,
    allowed: dict[_StatusT, frozenset[_StatusT]],
    entity: str,
) -> _StatusT:
    if current not in allowed:
        raise InvalidStateTransitionError(
            f"{entity} status '{current.value}' is terminal and cannot change"
        )
    if target not in allowed[current]:
        raise InvalidStateTransitionError(
            f"cannot transition {entity} from '{current.value}' to '{target.value}'"
        )
    return target


def transition_run(current: RunStatus, target: RunStatus) -> RunStatus:
    return _transition(current, target, RUN_TRANSITIONS, "run")


def transition_call_run(
    current: CallRunStatus, target: CallRunStatus
) -> CallRunStatus:
    return _transition(current, target, CALL_RUN_TRANSITIONS, "call run")


def reopen_call_run_for_retry(current: CallRunStatus) -> CallRunStatus:
    """Reopen an infrastructure-failed run so a retry can attach a new attempt.

    A retry never creates another CallRun (statistical sample); it reuses the
    logical run and adds a physical attempt. Only ``INFRASTRUCTURE_FAILED`` may
    be reopened — every other terminal run (completed/cancelled) stays terminal.
    """
    if current is not CallRunStatus.INFRASTRUCTURE_FAILED:
        raise InvalidStateTransitionError(
            f"call run status '{current.value}' cannot be reopened for retry"
        )
    return CallRunStatus.RUNNING


def transition_call_attempt(
    current: AttemptStatus,
    target: AttemptStatus,
    terminal_status: AttemptTerminalStatus | None = None,
) -> tuple[AttemptStatus, AttemptTerminalStatus | None]:
    """Transition an attempt lifecycle state.

    Reaching ``TERMINAL`` requires an explicit terminal class. Non-terminal
    targets must not carry a terminal class.
    """
    _transition(current, target, ATTEMPT_TRANSITIONS, "call attempt")
    if target is AttemptStatus.TERMINAL:
        if terminal_status is None:
            raise InvalidStateTransitionError(
                "attempt terminal transition requires a terminal status"
            )
        return target, terminal_status
    return target, None
