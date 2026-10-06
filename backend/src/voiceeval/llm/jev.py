"""Jev decision model via the OpenRouter Decisions API.

Jev (``typesafe/jev-1.13``) is a System One decision model: it takes an
application ``state`` object plus a map of typed ``questions`` and returns typed
answers with calibrated probabilities — no prose to parse. It is the bounded
decisioning half of the evaluator-generation architecture; the LLM does semantic
generation, Jev makes the selection decisions.

Reference: https://openrouter.ai/docs/guides/community/jev
"""

from __future__ import annotations

from typing import Any

import httpx

from voiceeval.core.config import get_settings
from voiceeval.core.errors import DependencyUnavailableError
from voiceeval.llm.base import (
    DecisionAnswer,
    DecisionModel,
    DecisionQuestion,
    DecisionResponse,
    LLMError,
)


class JevDecisionModel:
    """Thin HTTP client for the OpenRouter Decisions API (Jev)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openrouter_api_key
        self._base_url = (base_url or settings.jev_base_url).rstrip("/")
        self._model = model or settings.jev_model
        self._timeout_s = timeout_s

    async def decide(
        self, *, state: dict[str, Any], questions: dict[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        response = await self.decide_batch(state=state, questions=questions)
        return response.answers

    async def decide_batch(
        self, *, state: dict[str, Any], questions: dict[str, DecisionQuestion]
    ) -> DecisionResponse:
        """Full Decisions-API response, including resolved model + cost."""
        if not self._api_key:
            raise DependencyUnavailableError(
                "OPENROUTER_API_KEY is not configured; Jev decisions cannot run"
            )

        payload: dict[str, Any] = {
            "model": self._model,
            "state": state,
            "questions": {
                key: {
                    "type": q.type,
                    "instructions": q.instructions,
                    "criteria": q.criteria,
                }
                for key, q in questions.items()
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(
                    self._base_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Jev decision request failed: {exc}") from exc

        try:
            answers = body["answers"]
        except (KeyError, TypeError) as exc:
            raise LLMError("unexpected Jev response shape") from exc

        missing = [key for key in questions if key not in answers]
        if missing:
            raise LLMError(f"Jev response missing answers for {missing}")

        usage = body.get("usage") or {}
        return DecisionResponse(
            answers={key: _parse_answer(answers[key]) for key in questions},
            model=body.get("model"),
            cost=usage.get("cost"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            raw=body,
        )


def _parse_answer(raw: dict[str, Any]) -> DecisionAnswer:
    qtype = raw.get("type")
    if qtype == "noul":
        return DecisionAnswer(
            type="noul", value=float(raw.get("noul", 0.0)), confidence=None
        )
    if qtype == "choice":
        return DecisionAnswer(
            type="choice",
            value=raw.get("choice"),
            confidence=raw.get("confidence"),
            probabilities=raw.get("probabilities"),
        )
    if qtype == "score":
        return DecisionAnswer(
            type="score",
            value=float(raw.get("score", 0.0)),
            confidence=raw.get("confidence"),
            probabilities=raw.get("probabilities"),
        )
    raise LLMError(f"unknown Jev answer type: {qtype!r}")


_decision_model: DecisionModel | None = None


def get_decision_model() -> DecisionModel:
    global _decision_model
    if _decision_model is None:
        _decision_model = JevDecisionModel()
    return _decision_model


def set_decision_model(model: DecisionModel | None) -> None:
    global _decision_model
    _decision_model = model


__all__ = [
    "JevDecisionModel",
    "get_decision_model",
    "set_decision_model",
]
