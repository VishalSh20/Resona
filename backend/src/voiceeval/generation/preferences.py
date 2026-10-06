"""Workflow A — ``get_simulation_preferences``.

Given a Simulation description plus the available metrics and personalities,
decide which metrics and personalities are useful enough to include in the
Simulation's evaluation space.

Node flow:

    intent                 → LLM
    metric selection       → LLM (reasons about each metric's usefulness)
    personality selection  → LLM
    final constraints      → deterministic

This workflow is fully LLM-driven; deterministic code only validates that the
final selection is a subset of the available sets (no invented values).
"""

from __future__ import annotations

import logging

from voiceeval.core.errors import ValidationError
from voiceeval.generation.deterministic import unique, validate_preferences
from voiceeval.generation.errors import GenerationError
from voiceeval.generation.models import (
    EvaluationIntent,
    MetricSelection,
    PersonalitySelection,
    SimulationPreferences,
)
from voiceeval.generation.registries import (
    MetricReasoningRegistry,
    PersonalityRegistry,
    get_metric_reasoning_registry,
    get_personality_registry,
)
from voiceeval.llm import BaseGenerationModel, get_generation_model

logger = logging.getLogger("voiceeval.generation.preferences")


class SimulationPreferencesWorkflow:
    def __init__(
        self,
        *,
        generation: BaseGenerationModel | None = None,
        metric_registry: MetricReasoningRegistry | None = None,
        personality_registry: PersonalityRegistry | None = None,
    ) -> None:
        self._generation = generation or get_generation_model()
        self._metrics = metric_registry or get_metric_reasoning_registry()
        self._personalities = personality_registry or get_personality_registry()

    async def run(
        self,
        *,
        description: str,
        available_metrics: list[str],
        available_personalities: list[str],
    ) -> SimulationPreferences:
        metrics = self._normalize_metrics(available_metrics)
        personalities = self._normalize_personalities(available_personalities)

        intent = await self._analyze_intent(description)

        metric_selections = await self._select_metrics(description, intent, metrics)
        personality_selections = await self._select_personalities(
            description, intent, personalities
        )

        selected_metrics = [s.metric for s in metric_selections]
        selected_personalities = [s.personality for s in personality_selections]

        validation = validate_preferences(
            metrics=selected_metrics,
            personalities=selected_personalities,
            available_metrics=metrics,
            available_personalities=personalities,
        )
        if not validation.passed:
            raise GenerationError(
                "preference selection failed validation: "
                + "; ".join(validation.errors)
            )

        return SimulationPreferences(
            metrics=selected_metrics, personalities=selected_personalities
        )

    # -- normalize (deterministic) ------------------------------------------- #
    def _normalize_metrics(self, available_metrics: list[str]) -> list[str]:
        metrics = unique(available_metrics)
        unknown = [m for m in metrics if not self._metrics.has(m)]
        if unknown:
            raise ValidationError(f"unknown metric keys: {', '.join(unknown)}")
        return metrics

    def _normalize_personalities(self, available_personalities: list[str]) -> list[str]:
        personalities = unique(available_personalities)
        keys = set(self._personalities.keys())
        unknown = [p for p in personalities if p not in keys]
        if unknown:
            raise ValidationError(f"unknown personality keys: {', '.join(unknown)}")
        return personalities

    # -- intent (LLM) -------------------------------------------------------- #
    async def _analyze_intent(self, description: str) -> EvaluationIntent:
        system = (
            "You analyze a voice-agent evaluation simulation and extract its "
            "evaluation intent. Return only structured JSON."
        )
        user = (
            "Simulation description:\n"
            f"{description}\n\n"
            "Extract objectives, behavioral requirements, failure modes, task "
            "characteristics, language requirements, caller stressors, knowledge "
            "dependence, temporal sensitivity, and any ambiguity flags."
        )
        try:
            return await self._generation.structured(
                EvaluationIntent, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"intent analysis failed: {exc}") from exc

    # -- metric selection (LLM, with reasoning) ------------------------------ #
    async def _select_metrics(
        self, description: str, intent: EvaluationIntent, metrics: list[str]
    ) -> list[MetricSelection]:
        catalog = [
            {
                "key": key,
                "family": self._metrics.get(key).family,
                "measurement_type": self._metrics.get(key).measurement_type,
                "relevant_behaviors": sorted(self._metrics.get(key).relevant_behaviors),
                "relevant_caller_traits": sorted(
                    self._metrics.get(key).relevant_caller_traits
                ),
                "evidence_sources": sorted(self._metrics.get(key).evidence_sources),
            }
            for key in metrics
        ]
        system = (
            "You are a metric-selection analyst for a voice-agent evaluation. "
            "Reason about which metrics are genuinely useful for evaluating the "
            "target agent, and select them. For each selected metric, give a "
            "short reason. Return only structured JSON."
        )
        user = (
            "Simulation description:\n"
            f"{description}\n\n"
            f"Evaluation intent: {intent.model_dump_json()}\n\n"
            f"Available metrics: {catalog}\n\n"
            "Select the metrics that are useful for this simulation. For each, "
            "explain briefly why it matters. Exclude metrics that are not useful."
        )
        try:
            return await self._generation.structured_many(
                MetricSelection, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"metric selection failed: {exc}") from exc

    # -- personality selection (LLM) ----------------------------------------- #
    async def _select_personalities(
        self,
        description: str,
        intent: EvaluationIntent,
        personalities: list[str],
    ) -> list[PersonalitySelection]:
        catalog = [
            {
                "key": key,
                "behavioral_axes": sorted(self._personalities.get(key).behavioral_axes),
                "pressure_signals": sorted(self._personalities.get(key).pressure_signals),
            }
            for key in personalities
        ]
        system = (
            "You select caller personalities for a voice-agent evaluation. "
            "Return only structured JSON."
        )
        user = (
            "Simulation description:\n"
            f"{description}\n\n"
            f"Evaluation intent: {intent.model_dump_json()}\n\n"
            f"Available personalities: {catalog}\n\n"
            "Select the personalities that are useful for this simulation, with "
            "a short reason for each."
        )
        try:
            return await self._generation.structured_many(
                PersonalitySelection, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"personality selection failed: {exc}") from exc


__all__ = ["SimulationPreferencesWorkflow"]
