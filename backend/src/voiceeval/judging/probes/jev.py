"""Jev probe runner (spec §4).

Chains dependent decisions across requests, retries transport failures with
backoff, and — when a fallback is supplied — routes a single failed decision to
the LLM adjudicator (``resolver: llm_fallback``) instead of failing the metric.
Records the resolved model snapshot id from every call for provenance.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from voiceeval.llm.base import DecisionAnswer, DecisionModel, DecisionQuestion, LLMError

logger = logging.getLogger("voiceeval.judging.jev")


@dataclass
class ProbeAnswer:
    qid: str
    type: str
    value: Any
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    model: str | None = None
    resolver: str = "jev"
    raw: dict | None = None

    def as_decision(self) -> DecisionAnswer:
        return DecisionAnswer(
            type=self.type,
            value=self.value,
            confidence=self.confidence,
            probabilities=self.probabilities,
        )


FallbackFn = Callable[[str, dict[str, Any], DecisionQuestion], Awaitable[ProbeAnswer]]


class JevRunner:
    def __init__(
        self,
        model: DecisionModel,
        *,
        max_retries: int = 3,
        backoff_s: float = 0.4,
        fallback: FallbackFn | None = None,
    ) -> None:
        self._model = model
        self._max_retries = max(1, max_retries)
        self._backoff_s = backoff_s
        self._fallback = fallback

    async def run(
        self,
        state: dict[str, Any],
        questions: dict[str, DecisionQuestion],
    ) -> dict[str, ProbeAnswer]:
        if not questions:
            return {}

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                answers, model_id = await self._call(state, questions)
                return {
                    qid: _to_probe_answer(qid, answer, model_id)
                    for qid, answer in answers.items()
                }
            except LLMError as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._backoff_s * (2**attempt))

        if self._fallback is not None:
            logger.info("routing %d probe(s) to LLM fallback", len(questions))
            return {
                qid: await self._fallback(qid, state, question)
                for qid, question in questions.items()
            }
        raise LLMError(f"Jev probe failed after {self._max_retries} attempts: {last_error}")

    async def run_single(
        self, state: dict[str, Any], qid: str, question: DecisionQuestion
    ) -> ProbeAnswer:
        results = await self.run(state, {qid: question})
        return results[qid]

    async def _call(
        self, state: dict[str, Any], questions: dict[str, DecisionQuestion]
    ) -> tuple[dict[str, DecisionAnswer], str | None]:
        if hasattr(self._model, "decide_batch"):
            response = await self._model.decide_batch(  # type: ignore[attr-defined]
                state=state, questions=questions
            )
            return response.answers, response.model
        answers = await self._model.decide(state=state, questions=questions)
        return answers, None


def _to_probe_answer(qid: str, answer: DecisionAnswer, model_id: str | None) -> ProbeAnswer:
    return ProbeAnswer(
        qid=qid,
        type=answer.type,
        value=answer.value,
        confidence=answer.confidence,
        probabilities=answer.probabilities,
        model=model_id,
        resolver="jev",
    )


@dataclass
class ProbeBatch:
    """A named set of questions sharing one state (one decision unit)."""

    state: dict[str, Any]
    questions: dict[str, DecisionQuestion] = field(default_factory=dict)

    def add(self, qid: str, question: DecisionQuestion) -> None:
        self.questions[qid] = question


__all__ = ["FallbackFn", "JevRunner", "ProbeAnswer", "ProbeBatch"]
