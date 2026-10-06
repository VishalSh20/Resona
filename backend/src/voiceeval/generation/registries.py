"""Machine-readable reasoning registries for evaluator generation.

The LLM must not redefine metric or personality semantics on every call. These
registries are the canonical, reusable metadata the generation workflows reason
over:

* :class:`MetricReasoningRegistry` — what each metric means and when it applies.
* :class:`PersonalityRegistry` — composable caller-trait semantics.

The *keys* of every default catalogue derive from the domain enums
(``Personality``, ``MetricKey`` in :mod:`voiceeval.domain.enums`)
so there is a single source of truth and no string-literal drift. Values are the
domain-schema tokens (uppercase personalities, lowercase metric keys)
so generated evaluators stay within Simulation membership.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import MetricKey, Personality


@dataclass(frozen=True)
class MetricReasoningSpec:
    key: str
    family: str
    measurement_type: Literal["instrumented", "judge", "hybrid"]
    relevant_behaviors: frozenset[str] = frozenset()
    relevant_task_types: frozenset[str] = frozenset()
    relevant_caller_traits: frozenset[str] = frozenset()
    relevant_language_properties: frozenset[str] = frozenset()
    evidence_sources: frozenset[str] = frozenset()
    universal: bool = False
    cost_weight: float = 1.0


@dataclass(frozen=True)
class PersonalitySpec:
    key: str
    behavioral_axes: frozenset[str] = frozenset()
    pressure_signals: frozenset[str] = frozenset()
    metric_affinities: frozenset[str] = frozenset()
    compatible_with: frozenset[str] = frozenset()
    incompatible_with: frozenset[str] = frozenset()


class MetricReasoningRegistry:
    def __init__(self, specs: list[MetricReasoningSpec] | None = None) -> None:
        self._by_key = {s.key: s for s in (specs or [])}

    def register(self, spec: MetricReasoningSpec) -> None:
        self._by_key[spec.key] = spec

    def get(self, key: str) -> MetricReasoningSpec:
        try:
            return self._by_key[key]
        except KeyError:
            raise ValidationError(f"unknown metric '{key}'") from None

    def has(self, key: str) -> bool:
        return key in self._by_key

    def keys(self) -> list[str]:
        return sorted(self._by_key)

    def all(self) -> list[MetricReasoningSpec]:
        return [self._by_key[k] for k in sorted(self._by_key)]


class PersonalityRegistry:
    def __init__(self, specs: list[PersonalitySpec] | None = None) -> None:
        self._by_key = {s.key: s for s in (specs or [])}

    def register(self, spec: PersonalitySpec) -> None:
        self._by_key[spec.key] = spec

    def get(self, key: str) -> PersonalitySpec:
        try:
            return self._by_key[key]
        except KeyError:
            raise ValidationError(f"unknown personality '{key}'") from None

    def keys(self) -> list[str]:
        return sorted(self._by_key)

    def all(self) -> list[PersonalitySpec]:
        return [self._by_key[k] for k in sorted(self._by_key)]


# --------------------------------------------------------------------------- #
# Default metric reasoning catalogue (keys derive from MetricKey)
# --------------------------------------------------------------------------- #

_DEFAULT_METRIC_REASONING: list[MetricReasoningSpec] = [
    MetricReasoningSpec(
        key=MetricKey.TTFA.value,
        family="latency",
        measurement_type="instrumented",
        relevant_behaviors=frozenset({"response_latency"}),
        evidence_sources=frozenset({"event"}),
        universal=True,
        cost_weight=0.5,
    ),
    MetricReasoningSpec(
        key=MetricKey.TTFT.value,
        family="latency",
        measurement_type="instrumented",
        relevant_behaviors=frozenset({"response_latency"}),
        evidence_sources=frozenset({"event"}),
        universal=True,
        cost_weight=0.5,
    ),
    MetricReasoningSpec(
        key=MetricKey.BARGE_IN_LATENCY.value,
        family="latency",
        measurement_type="instrumented",
        relevant_behaviors=frozenset({"interruption_handling", "turn_taking"}),
        relevant_caller_traits=frozenset({Personality.INTERRUPTOR.value, Personality.IMPATIENT.value}),
        evidence_sources=frozenset({"event"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.BARGE_IN_SUCCESS_RATE.value,
        family="latency",
        measurement_type="instrumented",
        relevant_behaviors=frozenset({"interruption_handling", "turn_taking"}),
        relevant_caller_traits=frozenset({Personality.INTERRUPTOR.value, Personality.IMPATIENT.value}),
        evidence_sources=frozenset({"event"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.LANGUAGE_DETECTION_ACCURACY.value,
        family="language",
        measurement_type="instrumented",
        relevant_language_properties=frozenset({"code_switching", "multilingual"}),
        relevant_behaviors=frozenset({"language_detection"}),
        evidence_sources=frozenset({"turn"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.RELEVANCY.value,
        family="conversation",
        measurement_type="judge",
        relevant_behaviors=frozenset({"on_topic_response"}),
        evidence_sources=frozenset({"turn"}),
        universal=True,
    ),
    MetricReasoningSpec(
        key=MetricKey.CONTEXT_RETENTION.value,
        family="conversation",
        measurement_type="judge",
        relevant_behaviors=frozenset({"context_memory"}),
        relevant_task_types=frozenset({"multi_turn", "authentication"}),
        evidence_sources=frozenset({"turn"}),
        universal=True,
    ),
    MetricReasoningSpec(
        key=MetricKey.INSTRUCTION_FOLLOWING.value,
        family="conversation",
        measurement_type="judge",
        relevant_behaviors=frozenset({"policy_compliance"}),
        relevant_task_types=frozenset({"authentication", "procedure"}),
        evidence_sources=frozenset({"turn"}),
        universal=True,
    ),
    MetricReasoningSpec(
        key=MetricKey.EMPATHY.value,
        family="conversation",
        measurement_type="judge",
        relevant_behaviors=frozenset({"emotional_regulation"}),
        relevant_caller_traits=frozenset(
            {Personality.EMOTIONAL.value, Personality.ABUSIVE.value}
        ),
        evidence_sources=frozenset({"turn"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.HALLUCINATION.value,
        family="task",
        measurement_type="judge",
        relevant_behaviors=frozenset({"factual_grounding"}),
        relevant_task_types=frozenset({"knowledge_intensive"}),
        evidence_sources=frozenset({"turn", "tool_call"}),
        universal=True,
    ),
    MetricReasoningSpec(
        key=MetricKey.SEMANTIC_PRESERVATION.value,
        family="language",
        measurement_type="judge",
        relevant_language_properties=frozenset({"code_switching", "multilingual"}),
        relevant_behaviors=frozenset({"semantic_preservation"}),
        evidence_sources=frozenset({"turn"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.LANGUAGE_CONSISTENCY.value,
        family="language",
        measurement_type="judge",
        relevant_language_properties=frozenset({"code_switching", "multilingual"}),
        relevant_behaviors=frozenset({"language_consistency"}),
        evidence_sources=frozenset({"turn"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.REPETITION.value,
        family="conversation",
        measurement_type="hybrid",
        relevant_behaviors=frozenset({"conciseness"}),
        relevant_caller_traits=frozenset(
            {Personality.CONCISE.value, Personality.REPETITIVE.value, Personality.IMPATIENT.value}
        ),
        evidence_sources=frozenset({"turn"}),
    ),
    MetricReasoningSpec(
        key=MetricKey.TASK_COMPLETION.value,
        family="task",
        measurement_type="hybrid",
        relevant_behaviors=frozenset({"goal_resolution"}),
        relevant_task_types=frozenset({"all"}),
        evidence_sources=frozenset({"turn", "tool_call", "state_transition"}),
        universal=True,
    ),
    MetricReasoningSpec(
        key=MetricKey.KB_GROUNDEDNESS.value,
        family="task",
        measurement_type="hybrid",
        relevant_behaviors=frozenset({"knowledge_usage"}),
        relevant_task_types=frozenset({"knowledge_intensive"}),
        evidence_sources=frozenset({"turn", "tool_call"}),
    ),
    # NOTE(later fix): the judge side still scores all language metrics through a
    # single generic ``language_adaptation`` 1-5 field (judges/schema.py), so the
    # per-metric behavior tokens here only drive prompt wording for now. Distinct
    # judge fields per language metric are a follow-up.
    MetricReasoningSpec(
        key=MetricKey.CODE_SWITCHING_ACCURACY.value,
        family="language",
        measurement_type="hybrid",
        relevant_language_properties=frozenset({"code_switching"}),
        relevant_behaviors=frozenset({"code_switching"}),
        evidence_sources=frozenset({"turn"}),
    ),
]


# --------------------------------------------------------------------------- #
# Default personality catalogue (keys derive from Personality)
# --------------------------------------------------------------------------- #

_DEFAULT_PERSONALITIES: list[PersonalitySpec] = [
    PersonalitySpec(
        key=Personality.SUPPORTIVE.value,
        behavioral_axes=frozenset({"cooperation", "patience"}),
        pressure_signals=frozenset({"seeks help", "cooperative"}),
        metric_affinities=frozenset({MetricKey.TASK_COMPLETION.value}),
    ),
    PersonalitySpec(
        key=Personality.CONCISE.value,
        behavioral_axes=frozenset({"verbosity"}),
        pressure_signals=frozenset({"minimal information"}),
        metric_affinities=frozenset({MetricKey.REPETITION.value}),
    ),
    PersonalitySpec(
        key=Personality.VERBOSE.value,
        behavioral_axes=frozenset({"verbosity"}),
        pressure_signals=frozenset({"over-explains", "tangential"}),
        metric_affinities=frozenset({MetricKey.RELEVANCY.value}),
        incompatible_with=frozenset({Personality.CONCISE.value}),
    ),
    PersonalitySpec(
        key=Personality.ABUSIVE.value,
        behavioral_axes=frozenset({"emotional_regulation", "hostility"}),
        pressure_signals=frozenset({"hostile language"}),
        metric_affinities=frozenset({MetricKey.EMPATHY.value}),
        incompatible_with=frozenset({Personality.SUPPORTIVE.value, Personality.COOPERATIVE.value}),
    ),
    PersonalitySpec(
        key=Personality.INTERRUPTOR.value,
        behavioral_axes=frozenset({"turn_taking"}),
        pressure_signals=frozenset({"interrupts agent"}),
        metric_affinities=frozenset({MetricKey.BARGE_IN_LATENCY.value, MetricKey.BARGE_IN_SUCCESS_RATE.value}),
    ),
    PersonalitySpec(
        key=Personality.IMPATIENT.value,
        behavioral_axes=frozenset({"patience", "turn_taking"}),
        pressure_signals=frozenset({"low tolerance for delay"}),
        metric_affinities=frozenset({MetricKey.BARGE_IN_LATENCY.value, MetricKey.REPETITION.value}),
    ),
    PersonalitySpec(
        key=Personality.CONFUSED.value,
        behavioral_axes=frozenset({"comprehension"}),
        pressure_signals=frozenset({"misunderstands instructions"}),
        metric_affinities=frozenset({MetricKey.INSTRUCTION_FOLLOWING.value, MetricKey.CONTEXT_RETENTION.value}),
    ),
    PersonalitySpec(
        key=Personality.SKEPTICAL.value,
        behavioral_axes=frozenset({"trust", "verification"}),
        pressure_signals=frozenset({"challenges claims", "requests evidence"}),
        metric_affinities=frozenset({MetricKey.HALLUCINATION.value, MetricKey.KB_GROUNDEDNESS.value}),
    ),
    PersonalitySpec(
        key=Personality.COOPERATIVE.value,
        behavioral_axes=frozenset({"cooperation"}),
        pressure_signals=frozenset({"follows instructions"}),
        metric_affinities=frozenset({MetricKey.TASK_COMPLETION.value}),
    ),
    PersonalitySpec(
        key=Personality.UNCOOPERATIVE.value,
        behavioral_axes=frozenset({"cooperation"}),
        pressure_signals=frozenset({"resists", "withholds information"}),
        metric_affinities=frozenset({MetricKey.CONTEXT_RETENTION.value, MetricKey.INSTRUCTION_FOLLOWING.value}),
        incompatible_with=frozenset({Personality.COOPERATIVE.value, Personality.SUPPORTIVE.value}),
    ),
    PersonalitySpec(
        key=Personality.HESITANT.value,
        behavioral_axes=frozenset({"decisiveness"}),
        pressure_signals=frozenset({"pauses", "backtracks"}),
        metric_affinities=frozenset({MetricKey.CONTEXT_RETENTION.value}),
    ),
    PersonalitySpec(
        key=Personality.REPETITIVE.value,
        behavioral_axes=frozenset({"perseveration"}),
        pressure_signals=frozenset({"repeats concern"}),
        metric_affinities=frozenset({MetricKey.REPETITION.value}),
    ),
    PersonalitySpec(
        key=Personality.EMOTIONAL.value,
        behavioral_axes=frozenset({"emotional_regulation"}),
        pressure_signals=frozenset({"high emotional intensity"}),
        metric_affinities=frozenset({MetricKey.EMPATHY.value}),
    ),
    PersonalitySpec(
        key=Personality.DEMANDING.value,
        behavioral_axes=frozenset({"assertiveness", "urgency"}),
        pressure_signals=frozenset({"expects immediate action"}),
        metric_affinities=frozenset({MetricKey.TASK_COMPLETION.value, MetricKey.EMPATHY.value}),
    ),
]


def _validate_catalog_sync() -> None:
    """Fail fast if any default catalogue drifts from its domain enum."""
    mismatches: list[str] = []
    if {s.key for s in _DEFAULT_METRIC_REASONING} != {m.value for m in MetricKey}:
        mismatches.append("MetricReasoningSpec keys != MetricKey")
    if {s.key for s in _DEFAULT_PERSONALITIES} != {p.value for p in Personality}:
        mismatches.append("PersonalitySpec keys != Personality")
    if mismatches:
        raise RuntimeError("catalogue/enum drift: " + "; ".join(mismatches))


_validate_catalog_sync()


_default_metric_reasoning: MetricReasoningRegistry | None = None
_default_personalities: PersonalityRegistry | None = None


def get_metric_reasoning_registry() -> MetricReasoningRegistry:
    global _default_metric_reasoning
    if _default_metric_reasoning is None:
        _default_metric_reasoning = MetricReasoningRegistry(_DEFAULT_METRIC_REASONING)
    return _default_metric_reasoning


def get_personality_registry() -> PersonalityRegistry:
    global _default_personalities
    if _default_personalities is None:
        _default_personalities = PersonalityRegistry(_DEFAULT_PERSONALITIES)
    return _default_personalities


def set_personality_registry(registry: PersonalityRegistry | None) -> None:
    global _default_personalities
    _default_personalities = registry


def set_metric_reasoning_registry(registry: MetricReasoningRegistry | None) -> None:
    global _default_metric_reasoning
    _default_metric_reasoning = registry


__all__ = [
    "MetricReasoningRegistry",
    "MetricReasoningSpec",
    "PersonalityRegistry",
    "PersonalitySpec",
    "get_metric_reasoning_registry",
    "get_personality_registry",
    "set_metric_reasoning_registry",
    "set_personality_registry",
]
