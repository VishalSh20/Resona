"""Evaluation trigger.

The seam between orchestration (an attempt/run finished) and the evaluation
workers (metrics, judges, aggregation). The default implementation enqueues ARQ
jobs; it is best-effort, so losing an evaluation enqueue never fails the state
change that produced it. Tests can install a no-op or recording trigger.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger("voiceeval.evaluation.trigger")


@runtime_checkable
class EvaluationTrigger(Protocol):
    async def on_attempt_terminal(
        self, attempt_id: str, *, eligible: bool, call_run_id: str | None, run_id: str | None
    ) -> None: ...

    async def on_run_completed(self, run_id: str) -> None: ...


class NoOpEvaluationTrigger:
    async def on_attempt_terminal(
        self, attempt_id: str, *, eligible: bool, call_run_id: str | None, run_id: str | None
    ) -> None:
        return None

    async def on_run_completed(self, run_id: str) -> None:
        return None


class ArqEvaluationTrigger:
    """Enqueue evaluation work on the ARQ queues (best-effort)."""

    async def on_attempt_terminal(
        self, attempt_id: str, *, eligible: bool, call_run_id: str | None, run_id: str | None
    ) -> None:
        if not eligible or call_run_id is None:
            return
        # The Voice-Agent Judge computes every metric for the call run in one
        # stage, so the attempt hands straight off to judging.
        try:
            from voiceeval.workers.enqueue import enqueue_judges

            await enqueue_judges(call_run_id)
        except Exception as exc:  # pragma: no cover - depends on live Redis
            logger.warning(
                "failed to enqueue judges for call run %s: %s",
                call_run_id,
                exc,
            )

    async def on_run_completed(self, run_id: str) -> None:
        try:
            from voiceeval.workers.enqueue import enqueue_aggregation

            await enqueue_aggregation(run_id)
        except Exception as exc:  # pragma: no cover - depends on live Redis
            logger.warning("failed to enqueue aggregation for run %s: %s", run_id, exc)


_trigger: EvaluationTrigger | None = None


def get_evaluation_trigger() -> EvaluationTrigger:
    global _trigger
    if _trigger is None:
        _trigger = ArqEvaluationTrigger()
    return _trigger


def set_evaluation_trigger(trigger: EvaluationTrigger | None) -> None:
    global _trigger
    _trigger = trigger


__all__ = [
    "ArqEvaluationTrigger",
    "EvaluationTrigger",
    "NoOpEvaluationTrigger",
    "get_evaluation_trigger",
    "set_evaluation_trigger",
]
