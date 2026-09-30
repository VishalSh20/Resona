"""Stop-condition evaluation.

After every normalized event the engine is asked whether the call should stop.
Conditions are evaluated with an explicit precedence so a stronger signal (e.g.
natural success) always wins over a weaker one (e.g. a stall) that may be true at
the same time. The triggering evidence event is retained on the decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from voiceeval.core.clocks import monotonic_ms as default_monotonic_ms
from voiceeval.domain.enums import AttemptFailureClass, AttemptTerminalStatus
from voiceeval.runtime.events import CanonicalEvent, EventType


class StopReason(StrEnum):
    NATURAL_SUCCESS = "NATURAL_SUCCESS"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"
    IRRECOVERABLE_OBJECTIVE_FAILURE = "IRRECOVERABLE_OBJECTIVE_FAILURE"
    CONVERSATION_STALL = "CONVERSATION_STALL"
    WALL_CLOCK_TIMEOUT = "WALL_CLOCK_TIMEOUT"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    # Not part of the documented evaluation precedence: driven by an explicit
    # control command (plan cancellation) rather than by conversation state.
    CANCELLED = "CANCELLED"


# Strongest first. When several signals are present the earliest wins.
STOP_PRECEDENCE: tuple[StopReason, ...] = (
    StopReason.NATURAL_SUCCESS,
    StopReason.RECOVERY_EXHAUSTED,
    StopReason.IRRECOVERABLE_OBJECTIVE_FAILURE,
    StopReason.CONVERSATION_STALL,
    StopReason.WALL_CLOCK_TIMEOUT,
    StopReason.CONNECTION_FAILURE,
)

# How each reason maps onto the attempt terminal contract.
_TERMINAL_MAP: dict[StopReason, tuple[AttemptTerminalStatus, AttemptFailureClass | None, bool]] = {
    StopReason.NATURAL_SUCCESS: (
        AttemptTerminalStatus.COMPLETED,
        None,
        True,
    ),
    StopReason.IRRECOVERABLE_OBJECTIVE_FAILURE: (
        AttemptTerminalStatus.FAILED,
        None,
        True,
    ),
    StopReason.RECOVERY_EXHAUSTED: (
        AttemptTerminalStatus.FAILED,
        None,
        True,
    ),
    StopReason.CONVERSATION_STALL: (
        AttemptTerminalStatus.TIMED_OUT,
        AttemptFailureClass.TIMEOUT,
        False,
    ),
    StopReason.WALL_CLOCK_TIMEOUT: (
        AttemptTerminalStatus.TIMED_OUT,
        AttemptFailureClass.TIMEOUT,
        False,
    ),
    StopReason.CONNECTION_FAILURE: (
        AttemptTerminalStatus.FAILED,
        AttemptFailureClass.TRANSPORT,
        False,
    ),
    StopReason.CANCELLED: (
        AttemptTerminalStatus.CANCELLED,
        AttemptFailureClass.CANCELLED,
        False,
    ),
}

_CONNECTION_FAILURE_TYPES = {
    EventType.CONNECTION_ERROR.value,
    EventType.CONNECTION_WS_ERROR.value,
}


@dataclass(frozen=True)
class StopDecision:
    reason: StopReason
    terminal_status: AttemptTerminalStatus
    failure_class: AttemptFailureClass | None
    eligible: bool
    evidence_event_id: str | None
    monotonic_ms: int
    detail: dict = field(default_factory=dict)

    def as_payload(self) -> dict:
        return {
            "reason": self.reason.value,
            "terminal_status": self.terminal_status.value,
            "failure_class": self.failure_class.value if self.failure_class else None,
            "eligible": self.eligible,
            "evidence_event_id": self.evidence_event_id,
            "monotonic_ms": self.monotonic_ms,
            **self.detail,
        }


class StopConditionEngine:
    def __init__(
        self,
        *,
        stall_ms: int = 10_000,
        wall_clock_timeout_ms: int = 180_000,
        max_wall_clock_timeout_ms: int = 300_000,
        clock: Callable[[], int] = default_monotonic_ms,
    ) -> None:
        self._stall_ms = stall_ms
        self._wall_clock_timeout_ms = min(
            wall_clock_timeout_ms, max_wall_clock_timeout_ms
        )
        self._max_wall_clock_timeout_ms = max_wall_clock_timeout_ms
        self._clock = clock
        self._started_ms = self._clock()
        self._last_event_ms = self._started_ms
        self._pending: dict[StopReason, StopDecision] = {}
        self._decided: StopDecision | None = None

    @property
    def decided(self) -> StopDecision | None:
        return self._decided

    @property
    def stall_ms(self) -> int:
        return self._stall_ms

    @property
    def wall_clock_timeout_ms(self) -> int:
        return self._wall_clock_timeout_ms

    def remaining_stall_ms(self) -> int:
        elapsed = self._clock() - self._last_event_ms
        return max(0, self._stall_ms - elapsed)

    def observe(self, event: CanonicalEvent) -> StopDecision | None:
        """Record an event and return a decision if a condition now holds."""
        self._last_event_ms = max(self._last_event_ms, event.monotonic_ms)

        if event.type == EventType.CALLER_TERMINAL.value:
            reason_value = (event.payload or {}).get("reason")
            reason = (
                StopReason.RECOVERY_EXHAUSTED
                if reason_value == StopReason.RECOVERY_EXHAUSTED.value
                else StopReason.NATURAL_SUCCESS
                if reason_value == StopReason.NATURAL_SUCCESS.value
                else StopReason.IRRECOVERABLE_OBJECTIVE_FAILURE
            )
            self._record(reason, event, {"caller_reason": reason_value})
        elif event.type == EventType.CALLER_RECOVERY_USED.value:
            if (event.payload or {}).get("exhausted"):
                self._record(
                    StopReason.RECOVERY_EXHAUSTED,
                    event,
                    {"recovery_count": (event.payload or {}).get("recovery_count")},
                )
        elif event.type in _CONNECTION_FAILURE_TYPES:
            self._record(StopReason.CONNECTION_FAILURE, event, {})

        return self._resolve()

    def fail(self, *, reason: StopReason, detail: dict | None = None) -> StopDecision:
        """Force a terminal decision (e.g. the transport raised)."""
        decision = StopDecision(
            reason=reason,
            terminal_status=_TERMINAL_MAP[reason][0],
            failure_class=_TERMINAL_MAP[reason][1],
            eligible=_TERMINAL_MAP[reason][2],
            evidence_event_id=None,
            monotonic_ms=self._clock(),
            detail=detail or {},
        )
        self._pending[reason] = decision
        return decision

    def check_timeouts(self) -> StopDecision | None:
        """Evaluate the stall and wall-clock conditions."""
        now = self._clock()
        if now - self._last_event_ms >= self._stall_ms:
            self._record(
                StopReason.CONVERSATION_STALL,
                None,
                {"silent_ms": now - self._last_event_ms},
                monotonic_ms=now,
            )
        if now - self._started_ms >= self._wall_clock_timeout_ms:
            self._record(
                StopReason.WALL_CLOCK_TIMEOUT,
                None,
                {"elapsed_ms": now - self._started_ms},
                monotonic_ms=now,
            )
        return self._resolve()

    # -- internals ------------------------------------------------------------

    def _record(
        self,
        reason: StopReason,
        event: CanonicalEvent | None,
        detail: dict,
        *,
        monotonic_ms: int | None = None,
    ) -> None:
        terminal_status, failure_class, eligible = _TERMINAL_MAP[reason]
        self._pending[reason] = StopDecision(
            reason=reason,
            terminal_status=terminal_status,
            failure_class=failure_class,
            eligible=eligible,
            evidence_event_id=event.event_id if event is not None else None,
            monotonic_ms=monotonic_ms if monotonic_ms is not None else (
                event.monotonic_ms if event is not None else self._clock()
            ),
            detail=detail,
        )

    def _resolve(self) -> StopDecision | None:
        if self._decided is not None:
            return self._decided
        for reason in STOP_PRECEDENCE:
            if reason in self._pending:
                self._decided = self._pending[reason]
                return self._decided
        return None
