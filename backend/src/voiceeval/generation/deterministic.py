"""Deterministic constraints and validation helpers.

The LLM understands semantics; Jev makes bounded decisions; this module owns
hard guarantees: membership checks and validation. None of it calls a model.
"""

from __future__ import annotations

from collections.abc import Iterable

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import Personality
from voiceeval.generation.models import (
    CallerProfile,
    RunEvaluatorDraft,
    SimulationInput,
    ValidationResult,
)
from voiceeval.runtime.caller.traits import trait_composition_errors


def _trait_composition_errors(traits: Iterable[str]) -> list[str]:
    """Composition-rule violations (§7), ignoring traits unknown to the enum."""
    selected: list[Personality] = []
    for trait in traits:
        try:
            selected.append(Personality(str(trait)))
        except ValueError:
            return []  # membership validation reports the unknown trait
    return trait_composition_errors(selected)


def canonical_personality(traits: Iterable[str]) -> list[str]:
    """Return a sorted, deduplicated personality list for stable comparison."""
    return sorted({t for t in traits})


def unique(values: Iterable[str]) -> list[str]:
    return sorted({v for v in values})


def validate_preferences(
    *,
    metrics: list[str],
    personalities: list[str],
    available_metrics: list[str],
    available_personalities: list[str],
) -> ValidationResult:
    errors: list[str] = []
    metric_set = set(available_metrics)
    personality_set = set(available_personalities)
    for metric in metrics:
        if metric not in metric_set:
            errors.append(f"metric '{metric}' is not in available_metrics")
    for personality in personalities:
        if personality not in personality_set:
            errors.append(f"personality '{personality}' is not in available_personalities")
    if len(set(metrics)) != len(metrics):
        errors.append("duplicate metric keys")
    if len(set(personalities)) != len(personalities):
        errors.append("duplicate personality keys")
    return ValidationResult(passed=not errors, errors=errors)


def validate_profile(profile: CallerProfile, simulation: SimulationInput) -> ValidationResult:
    errors: list[str] = []
    languages = [profile.major_language] + (
        [profile.minor_language] if profile.minor_language else []
    )
    if not (1 <= len(languages) <= 2):
        errors.append("a profile must select 1 or 2 languages")
    if profile.minor_language and profile.major_language == profile.minor_language:
        errors.append("major and minor language must differ")
    for lang in languages:
        if lang not in simulation.languages:
            errors.append(f"language '{lang}' is not in simulation.languages")
    for trait in profile.personality:
        if trait not in simulation.personalities:
            errors.append(f"personality '{trait}' is not in simulation.personalities")
    if not profile.personality:
        errors.append("a profile must select at least one personality trait")
    errors.extend(_trait_composition_errors(profile.personality))
    return ValidationResult(passed=not errors, errors=errors)


def validate_run_evaluator(
    draft: RunEvaluatorDraft, simulation: SimulationInput
) -> ValidationResult:
    errors: list[str] = []
    if not draft.scenario.strip():
        errors.append("scenario is empty")
    if not draft.expected_output_prompt.strip():
        errors.append("expected_output_prompt is empty")

    major = draft.languages.get("major")
    minor = draft.languages.get("minor")
    languages = [lang for lang in (major, minor) if lang]
    if not (1 <= len(languages) <= 2):
        errors.append("evaluator must select 1 or 2 languages")
    if major is None:
        errors.append("major language is required")
    if minor is not None and major == minor:
        errors.append("major and minor language must differ")
    for lang in languages:
        if lang not in simulation.languages:
            errors.append(f"language '{lang}' is not in simulation.languages")

    for trait in draft.personality:
        if trait not in simulation.personalities:
            errors.append(f"personality '{trait}' is not in simulation.personalities")
    for metric in draft.metrics:
        if metric not in simulation.metric_set:
            errors.append(f"metric '{metric}' is not in simulation.metric_set")
    if len(set(draft.metrics)) != len(draft.metrics):
        errors.append("duplicate metric keys")

    errors.extend(_trait_composition_errors(draft.personality))

    return ValidationResult(passed=not errors, errors=errors)


__all__ = [
    "canonical_personality",
    "unique",
    "validate_preferences",
    "validate_profile",
    "validate_run_evaluator",
]
