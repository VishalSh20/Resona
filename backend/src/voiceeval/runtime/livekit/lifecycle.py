"""Macro call lifecycle state machine (migration doc §4.4).

```
INIT → DISPATCHED → REGISTERED → DIALING/CONNECTING → RINGING ─▶ ANSWERED
                                                                   │
                         ┌─────────────── IVR_NAVIGATION ◀─────────┤ (optional)
                         │                                         │
                         └──────────────▶ CONVERSING ◀─────────────┘
                                              │
                                  CLOSING (goodbye) → ENDED
```

Every failure exit is reachable from any non-terminal state. Each phase has its
own timeout; the conversation stall and wall-clock timeouts map to the last two
phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ConnectionState(StrEnum):
    INIT = "INIT"
    DISPATCHED = "DISPATCHED"
    REGISTERED = "REGISTERED"
    DIALING = "DIALING"
    CONNECTING = "CONNECTING"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    IVR_NAVIGATION = "IVR_NAVIGATION"
    CONVERSING = "CONVERSING"
    CLOSING = "CLOSING"
    ENDED = "ENDED"
    # failure exits
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    REJECTED = "REJECTED"
    VOICEMAIL = "VOICEMAIL"
    TARGET_SILENT = "TARGET_SILENT"
    TRANSPORT_LOST = "TRANSPORT_LOST"
    TARGET_HUNG_UP = "TARGET_HUNG_UP"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


#: Failure exits (non-goodbye terminals).
FAILURE_STATES: frozenset[ConnectionState] = frozenset(
    {
        ConnectionState.NO_ANSWER,
        ConnectionState.BUSY,
        ConnectionState.REJECTED,
        ConnectionState.VOICEMAIL,
        ConnectionState.TARGET_SILENT,
        ConnectionState.TRANSPORT_LOST,
        ConnectionState.TARGET_HUNG_UP,
        ConnectionState.TIMEOUT,
        ConnectionState.CANCELLED,
        ConnectionState.INTERNAL_ERROR,
    }
)

#: Any terminal state (goodbye or failure).
TERMINAL_STATES: frozenset[ConnectionState] = FAILURE_STATES | frozenset(
    {ConnectionState.ENDED}
)

#: Happy-path transitions. Failure exits are allowed from any non-terminal state.
_ALLOWED: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.INIT: frozenset({ConnectionState.DISPATCHED}),
    ConnectionState.DISPATCHED: frozenset({ConnectionState.REGISTERED}),
    ConnectionState.REGISTERED: frozenset(
        {ConnectionState.DIALING, ConnectionState.CONNECTING}
    ),
    ConnectionState.DIALING: frozenset(
        {ConnectionState.RINGING, ConnectionState.CONNECTING, ConnectionState.ANSWERED}
    ),
    ConnectionState.CONNECTING: frozenset(
        {ConnectionState.RINGING, ConnectionState.ANSWERED, ConnectionState.CONVERSING}
    ),
    ConnectionState.RINGING: frozenset(
        {ConnectionState.ANSWERED, ConnectionState.VOICEMAIL}
    ),
    ConnectionState.ANSWERED: frozenset({ConnectionState.CONVERSING}),
    ConnectionState.IVR_NAVIGATION: frozenset(
        {ConnectionState.CONVERSING, ConnectionState.CLOSING}
    ),
    ConnectionState.CONVERSING: frozenset(
        {ConnectionState.IVR_NAVIGATION, ConnectionState.CLOSING}
    ),
    ConnectionState.CLOSING: frozenset({ConnectionState.ENDED}),
    ConnectionState.ENDED: frozenset(),
}


class InvalidTransitionError(ValueError):
    def __init__(self, current: ConnectionState, target: ConnectionState) -> None:
        super().__init__(f"invalid lifecycle transition {current} → {target}")
        self.current = current
        self.target = target


@dataclass(frozen=True)
class LifecycleTimeouts:
    """Per-phase timeouts in milliseconds (§4.4)."""

    dispatch_ms: int = 15_000
    register_ms: int = 15_000
    dial_ms: int = 30_000
    ring_ms: int = 45_000
    first_audio_ms: int = 15_000
    conversation_stall_ms: int = 10_000
    wall_clock_ms: int = 180_000

    def for_state(self, state: ConnectionState) -> int | None:
        return {
            ConnectionState.DISPATCHED: self.dispatch_ms,
            ConnectionState.REGISTERED: self.register_ms,
            ConnectionState.DIALING: self.dial_ms,
            ConnectionState.RINGING: self.ring_ms,
            ConnectionState.ANSWERED: self.first_audio_ms,
            ConnectionState.CONVERSING: self.conversation_stall_ms,
        }.get(state)


@dataclass
class LifecycleMachine:
    """Tracks and validates the macro lifecycle with phase timestamps."""

    state: ConnectionState = ConnectionState.INIT
    timeouts: LifecycleTimeouts = field(default_factory=LifecycleTimeouts)
    history: list[ConnectionState] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(self.state)

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def failed(self) -> bool:
        return self.state in FAILURE_STATES

    def can_transition(self, target: ConnectionState) -> bool:
        if self.state in TERMINAL_STATES:
            return False
        if target in FAILURE_STATES:
            return True
        return target in _ALLOWED.get(self.state, frozenset())

    def transition(self, target: ConnectionState) -> ConnectionState:
        if not self.can_transition(target):
            raise InvalidTransitionError(self.state, target)
        self.state = target
        self.history.append(target)
        return self.state

    def fail(self, target: ConnectionState) -> ConnectionState:
        if target not in FAILURE_STATES:
            raise InvalidTransitionError(self.state, target)
        return self.transition(target)

    def timeout_ms(self) -> int | None:
        return self.timeouts.for_state(self.state)


__all__ = [
    "ConnectionState",
    "FAILURE_STATES",
    "InvalidTransitionError",
    "LifecycleMachine",
    "LifecycleTimeouts",
    "TERMINAL_STATES",
]
