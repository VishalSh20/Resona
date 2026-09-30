"""Retry classification and deterministic run-seed derivation.

The orchestrator never conflates an infrastructure failure (retryable — a
physical attempt may be re-run against the same logical ``CallRun``) with a
semantic failure (a valid evaluation outcome that must be recorded, not hidden
behind a retry).
"""

from __future__ import annotations

import hashlib
import json

from voiceeval.domain.enums import AttemptTerminalStatus

# Failure classes that justify re-running a physical attempt: runner crash,
# connection setup failure, transient provider failure and generic
# infrastructure failure. Everything else (media, timeout, malformed stream,
# cancellation) is terminal for the logical run.
RETRYABLE_FAILURE_CLASSES = frozenset(
    {"infrastructure", "provider", "transport", "runner_crash"}
)

# Orchestration action returned by ``resolve_attempt_termination``.
ACTION_COMPLETED = "completed"
ACTION_INFRASTRUCTURE_FAILED = "infrastructure_failed"
ACTION_CANCELLED = "cancelled"
ACTION_RETRY = "retry"


def resolve_attempt_termination(
    terminal_status: str,
    failure_class: str | None,
    attempt_no: int,
    max_attempts: int,
) -> str:
    """Decide what happens to a logical run after an attempt terminates.

    Returns one of the ``ACTION_*`` constants:
      * ``retry`` — spawn another attempt on the same run (infrastructure failure
        with the retry budget remaining).
      * ``infrastructure_failed`` — infrastructure failure with the budget
        exhausted.
      * ``completed`` — the run is a finished statistical sample, regardless of
        whether the call succeeded (COMPLETED), timed out, or failed semantically.
      * ``cancelled`` — the run was cancelled.
    """
    status = AttemptTerminalStatus(terminal_status)
    if status is AttemptTerminalStatus.CANCELLED:
        return ACTION_CANCELLED
    if status is AttemptTerminalStatus.COMPLETED:
        return ACTION_COMPLETED
    if status is AttemptTerminalStatus.TIMED_OUT:
        # A wall-clock timeout is a semantic outcome: the call reached a
        # meaningful conversation, so it is a valid sample, not an infra retry.
        return ACTION_COMPLETED
    # status is FAILED: distinguish infrastructure from semantic failure.
    if failure_class in RETRYABLE_FAILURE_CLASSES:
        if attempt_no < max_attempts:
            return ACTION_RETRY
        return ACTION_INFRASTRUCTURE_FAILED
    # Any other failure (semantic, media, malformed stream) is a valid outcome.
    return ACTION_COMPLETED


def derive_run_seed(
    run_id: str, run_evaluator_id: str, repetition_no: int
) -> str:
    """Derive a deterministic run seed from run/evaluator/repetition identity.

    The same run + evaluator + repetition always yields the same seed, so
    reproducing a single logical call run does not change its randomness.
    """
    payload = json.dumps(
        [run_id, run_evaluator_id, repetition_no],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
