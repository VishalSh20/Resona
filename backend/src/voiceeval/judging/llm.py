"""Seams the judge uses to reach models.

The judge never instantiates a provider directly:

* :func:`get_judge_llm` — the generation model (extraction, ReAct, adjudication,
  verification, audio annotation, ASR re-listen). Routed through the shared
  ``voiceeval.llm`` seam so OpenRouter/OpenAI/Anthropic are interchangeable.
* :func:`get_judge_decision_model` — Jev via the Decisions API.

Both are process-wide singletons that tests can replace.
"""

from __future__ import annotations

from voiceeval.core.config import get_settings
from voiceeval.llm.base import BaseGenerationModel, DecisionModel
from voiceeval.llm.jev import get_decision_model
from voiceeval.llm.providers import get_generation_model


def get_judge_llm() -> BaseGenerationModel:
    return get_generation_model()


def get_judge_decision_model() -> DecisionModel:
    return get_decision_model()


def judge_model_id() -> str | None:
    settings = get_settings()
    return settings.judge_llm_model or settings.openrouter_model


def adjudicator_model_id() -> str | None:
    settings = get_settings()
    return settings.adjudicator_model or judge_model_id()


def verifier_model_id() -> str | None:
    settings = get_settings()
    return settings.verifier_model or judge_model_id()


def audio_model_id() -> str | None:
    settings = get_settings()
    return settings.audio_model or judge_model_id()


__all__ = [
    "adjudicator_model_id",
    "audio_model_id",
    "get_judge_decision_model",
    "get_judge_llm",
    "judge_model_id",
    "verifier_model_id",
]
