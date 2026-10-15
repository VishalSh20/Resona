"""Failure taxonomy: infrastructure vs. environment vs. target outcome (§4.5).

The distinction drives retries: only failures that are *not the target's fault*
are retried. This module maps a terminal reason (from the lifecycle machine,
stop conditions, or an exception) to the attempt's persisted terminal status,
failure class, eligibility and degraded flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from voiceeval.domain.enums import AttemptFailureClass, AttemptTerminalStatus


class FailureKind(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    ENVIRONMENT_DEGRADED = "environment_degraded"
    TARGET_OUTCOME = "target_outcome"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class FailureClassification:
    kind: FailureKind
    terminal_status: AttemptTerminalStatus
    failure_class: AttemptFailureClass | None
    eligible: bool
    retryable: bool
    degraded: bool = False
    reason: str = ""


def _infra(reason: str, failure_class: AttemptFailureClass) -> FailureClassification:
    return FailureClassification(
        kind=FailureKind.INFRASTRUCTURE,
        terminal_status=AttemptTerminalStatus.FAILED,
        failure_class=failure_class,
        eligible=False,
        retryable=True,
        reason=reason,
    )


def _target(reason: str) -> FailureClassification:
    return FailureClassification(
        kind=FailureKind.TARGET_OUTCOME,
        terminal_status=AttemptTerminalStatus.COMPLETED,
        failure_class=None,
        eligible=True,
        retryable=False,
        reason=reason,
    )


def _degraded(reason: str) -> FailureClassification:
    return FailureClassification(
        kind=FailureKind.ENVIRONMENT_DEGRADED,
        terminal_status=AttemptTerminalStatus.COMPLETED,
        failure_class=None,
        eligible=True,
        retryable=False,
        degraded=True,
        reason=reason,
    )


_INFRASTRUCTURE: dict[str, AttemptFailureClass] = {
    "DISPATCH_TIMEOUT": AttemptFailureClass.INFRASTRUCTURE,
    "REGISTER_TIMEOUT": AttemptFailureClass.INFRASTRUCTURE,
    "TRUNK_AUTH_FAILURE": AttemptFailureClass.PROVIDER,
    "TRANSPORT_LOST": AttemptFailureClass.TRANSPORT,
    "TTS_FAILURE": AttemptFailureClass.MEDIA,
    "STT_FAILURE": AttemptFailureClass.MEDIA,
    "JOB_CRASH": AttemptFailureClass.RUNNER_CRASH,
    "INTERNAL_ERROR": AttemptFailureClass.INFRASTRUCTURE,
    "CONNECTION_FAILURE": AttemptFailureClass.TRANSPORT,
    "RUNNER_CRASH": AttemptFailureClass.RUNNER_CRASH,
}

_TARGET_OUTCOMES: frozenset[str] = frozenset(
    {
        "NO_ANSWER",
        "BUSY",
        "REJECTED",
        "UNREACHABLE",
        "VOICEMAIL",
        "TARGET_SILENT",
        "TARGET_HUNG_UP",
        "TARGET_ABUSE",
        "RECOVERY_EXHAUSTED",
        "IRRECOVERABLE_OBJECTIVE_FAILURE",
    }
)

#: The caller ran out of turns or looped: the conversation happened, but the
#: caller's own behaviour is the likely cause — the sample must not flow into
#: the target's scores as a valid outcome.
_CALLER_DEGRADED: frozenset[str] = frozenset({"MAX_TURNS", "LOOP"})

_DEGRADED: frozenset[str] = frozenset(
    {"HIGH_PACKET_LOSS", "STT_CONFIDENCE_COLLAPSE", "DEGRADED"}
)

_TIMEOUTS: frozenset[str] = frozenset(
    {"TIMEOUT", "WALL_CLOCK_TIMEOUT", "CONVERSATION_STALL"}
)

_CANCELLED: frozenset[str] = frozenset({"CANCELLED", "PLAN_CANCELLED"})

_SUCCESS: frozenset[str] = frozenset({"NATURAL_SUCCESS", "ENDED"})


def classify_failure(reason: str) -> FailureClassification:
    """Classify a terminal reason into the §4.5 taxonomy.

    Unknown reasons default to an infrastructure failure so an unexplained end
    is retried rather than silently counted as a valid sample.
    """
    key = (reason or "").upper()

    if key in _SUCCESS:
        return FailureClassification(
            kind=FailureKind.SUCCESS,
            terminal_status=AttemptTerminalStatus.COMPLETED,
            failure_class=None,
            eligible=True,
            retryable=False,
            reason=reason,
        )
    if key in _CANCELLED:
        return FailureClassification(
            kind=FailureKind.CANCELLED,
            terminal_status=AttemptTerminalStatus.CANCELLED,
            failure_class=AttemptFailureClass.CANCELLED,
            eligible=False,
            retryable=False,
            reason=reason,
        )
    if key in _TIMEOUTS:
        return FailureClassification(
            kind=FailureKind.TIMEOUT,
            terminal_status=AttemptTerminalStatus.TIMED_OUT,
            failure_class=AttemptFailureClass.TIMEOUT,
            eligible=True,
            retryable=False,
            reason=reason,
        )
    if key in _DEGRADED:
        return _degraded(reason)
    if key in _CALLER_DEGRADED:
        return FailureClassification(
            kind=FailureKind.ENVIRONMENT_DEGRADED,
            terminal_status=AttemptTerminalStatus.COMPLETED,
            failure_class=None,
            eligible=False,
            retryable=False,
            degraded=True,
            reason=reason,
        )
    if key in _TARGET_OUTCOMES:
        return _target(reason)
    if key in _INFRASTRUCTURE:
        return _infra(reason, _INFRASTRUCTURE[key])
    return _infra(reason, AttemptFailureClass.INFRASTRUCTURE)


def terminal_payload(reason: str) -> dict:
    """The ``attempt.terminal`` payload for a terminal reason.

    The control plane persists ``terminal_status``/``failure_class``/``eligible``
    straight from this payload, so a classified reason is what makes a successful
    call count as success rather than defaulting to a failed attempt.
    """
    classification = classify_failure(reason)
    return {
        "terminal_status": classification.terminal_status.value,
        "failure_class": (
            classification.failure_class.value
            if classification.failure_class
            else None
        ),
        "reason": reason,
        "eligible": classification.eligible,
        "degraded": classification.degraded,
    }


__all__ = [
    "FailureClassification",
    "FailureKind",
    "classify_failure",
    "terminal_payload",
]
