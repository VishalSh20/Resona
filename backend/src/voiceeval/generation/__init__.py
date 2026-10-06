"""AI evaluator-generation workflows.

Two workflows produce the evaluators that were previously authored by hand:

* :class:`SimulationPreferencesWorkflow` — select useful metrics/personalities.
* :class:`EvaluationsWorkflow` — instantiate a Simulation into concrete
  RunEvaluator drafts.

Workflow B uses a three-step LLM pipeline per evaluator (situation, caller
story, behaviour instructions) and keeps the simulation's full metric set.
The LLM provider abstraction lives in :mod:`voiceeval.llm`.
"""

from voiceeval.generation.errors import GenerationError, GenerationValidationError
from voiceeval.generation.evaluations import EvaluationsWorkflow
from voiceeval.generation.models import (
    BehaviorInstructions,
    CallerProfile,
    CallerStory,
    EvaluationIntent,
    JudgePromptSpec,
    MetricExpectation,
    MetricSelection,
    PersonalitySelection,
    RunEvaluatorDraft,
    ScenarioCandidate,
    SimulationInput,
    SimulationPreferences,
    SimulationWorkflowSpec,
    SituationSpec,
    ValidationResult,
    WorkflowStep,
)
from voiceeval.generation.preferences import SimulationPreferencesWorkflow
from voiceeval.generation.registries import (
    MetricReasoningRegistry,
    MetricReasoningSpec,
    PersonalityRegistry,
    PersonalitySpec,
    get_metric_reasoning_registry,
    get_personality_registry,
)

__all__ = [
    "BehaviorInstructions",
    "CallerProfile",
    "CallerStory",
    "EvaluationIntent",
    "EvaluationsWorkflow",
    "GenerationError",
    "GenerationValidationError",
    "JudgePromptSpec",
    "MetricExpectation",
    "MetricReasoningRegistry",
    "MetricReasoningSpec",
    "MetricSelection",
    "PersonalityRegistry",
    "PersonalitySelection",
    "PersonalitySpec",
    "RunEvaluatorDraft",
    "ScenarioCandidate",
    "SimulationInput",
    "SimulationPreferences",
    "SimulationPreferencesWorkflow",
    "SimulationWorkflowSpec",
    "SituationSpec",
    "ValidationResult",
    "WorkflowStep",
    "get_metric_reasoning_registry",
    "get_personality_registry",
]
