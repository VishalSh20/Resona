"""Typed structured-output models for the evaluator-generation workflows.

Every important intermediate artifact the LLM produces is a Pydantic model, so
graph nodes consume typed objects rather than parsing free text. The final
:class:`RunEvaluatorDraft` mirrors the persisted ``run_evaluator`` shape (without
identity columns).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from voiceeval.domain.enums import MetricKey, Personality


class EvaluationIntent(BaseModel):
    objectives: list[str] = Field(default_factory=list)
    behavioral_requirements: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    task_characteristics: list[str] = Field(default_factory=list)
    language_requirements: list[str] = Field(default_factory=list)
    caller_stressors: list[str] = Field(default_factory=list)
    knowledge_dependence: str = "low"
    temporal_sensitivity: str = "low"
    ambiguity_flags: list[str] = Field(default_factory=list)


class MetricSelection(BaseModel):
    metric: MetricKey
    reason: str = ""


class PersonalitySelection(BaseModel):
    personality: Personality
    reason: str = ""


class CallerProfile(BaseModel):
    """One caller profile (languages + personality set) spanning the metrics."""

    major_language: str
    minor_language: str | None = None
    personality: list[Personality] = Field(default_factory=list)
    rationale: str = ""


class SituationSpec(BaseModel):
    """Step 1 output: a pure situation description with no caller identity."""

    situation: str
    why_it_exercises_metrics: list[str] = Field(default_factory=list)
    relevant_agent_context: str = ""


class CallerStory(BaseModel):
    """Step 2 output: caller identity, background, and facts fitted into the situation."""

    caller_name: str = ""
    background: str = ""
    region: str = ""
    facts: list[str] = Field(default_factory=list)
    situation_overview: str = ""


class BehaviorInstructions(BaseModel):
    """Step 3 output: how the caller should behave during the call."""

    tone: str = ""
    opening_style: str = ""
    instructions: list[str] = Field(default_factory=list)
    reaction_triggers: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    fallback_if_stuck: str = ""


class ScenarioCandidate(BaseModel):
    title: str
    context: str = ""
    underlying_problem: str = ""
    conversation_goal: str = ""
    caller_instructions: str = ""
    communication_behavior: str = ""
    behavioral_constraints: list[str] = Field(default_factory=list)

    def render(self) -> str:
        """Render the structured scenario into the persisted ``scenario`` text."""
        blocks: list[str] = []
        if self.context:
            blocks.append(self.context)
        if self.underlying_problem:
            blocks.append(f"Underlying problem: {self.underlying_problem}")
        if self.conversation_goal:
            blocks.append(f"Conversation goal: {self.conversation_goal}")
        if self.caller_instructions:
            blocks.append(f"Caller instructions: {self.caller_instructions}")
        if self.communication_behavior:
            blocks.append(f"Communication behavior: {self.communication_behavior}")
        if self.behavioral_constraints:
            blocks.append(
                "Behavioral constraints:\n- " + "\n- ".join(self.behavioral_constraints)
            )
        return "\n\n".join(blocks)


class MetricExpectation(BaseModel):
    metric: MetricKey
    what_to_evaluate: str = ""
    pass_condition: str = ""
    failure_condition: str = ""
    evidence_to_consider: list[str] = Field(default_factory=list)


class JudgePromptSpec(BaseModel):
    objective: str = ""
    expected_agent_behavior: list[str] = Field(default_factory=list)
    metric_expectations: list[MetricExpectation] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    prohibited_assumptions: list[str] = Field(default_factory=list)
    outcome_definition: str = ""

    def render(self) -> str:
        """Render the judge spec into the persisted ``expected_output_prompt``."""
        blocks: list[str] = []
        if self.objective:
            blocks.append(f"Objective: {self.objective}")
        if self.expected_agent_behavior:
            blocks.append(
                "Expected agent behavior:\n- "
                + "\n- ".join(self.expected_agent_behavior)
            )
        if self.metric_expectations:
            rendered = []
            for exp in self.metric_expectations:
                parts = [f"{exp.metric}:"]
                if exp.what_to_evaluate:
                    parts.append(f"  Evaluate: {exp.what_to_evaluate}")
                if exp.pass_condition:
                    parts.append(f"  Pass: {exp.pass_condition}")
                if exp.failure_condition:
                    parts.append(f"  Fail: {exp.failure_condition}")
                if exp.evidence_to_consider:
                    parts.append(
                        "  Evidence: " + ", ".join(exp.evidence_to_consider)
                    )
                rendered.append("\n".join(parts))
            blocks.append("Metric expectations:\n" + "\n\n".join(rendered))
        if self.evidence_requirements:
            blocks.append(
                "Evidence requirements:\n- " + "\n- ".join(self.evidence_requirements)
            )
        if self.prohibited_assumptions:
            blocks.append(
                "Prohibited assumptions:\n- "
                + "\n- ".join(self.prohibited_assumptions)
            )
        if self.outcome_definition:
            blocks.append(f"Outcome definition: {self.outcome_definition}")
        return "\n\n".join(blocks)


class WorkflowStep(BaseModel):
    step: str
    description: str = ""


class SimulationWorkflowSpec(BaseModel):
    objective: str = ""
    task_flow: list[WorkflowStep] = Field(default_factory=list)
    success_conditions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    knowledge_usage: list[str] = Field(default_factory=list)
    interaction_requirements: list[str] = Field(default_factory=list)


class SimulationInput(BaseModel):
    """The Simulation evaluation space a workflow reasons over."""

    name: str = ""
    description: str = ""
    languages: list[str] = Field(default_factory=list)
    metric_set: list[MetricKey] = Field(default_factory=list)
    personalities: list[Personality] = Field(default_factory=list)
    knowledge_base: dict[str, Any] = Field(default_factory=dict)
    evaluator_count: int = Field(ge=1, le=100)


class SimulationPreferences(BaseModel):
    metrics: list[MetricKey] = Field(default_factory=list)
    personalities: list[Personality] = Field(default_factory=list)


class ValidationResult(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunEvaluatorDraft(BaseModel):
    scenario: str
    expected_output_prompt: str
    metrics: list[MetricKey] = Field(default_factory=list)
    languages: dict[str, str | None] = Field(
        default_factory=lambda: {"major": None, "minor": None}
    )
    personality: list[Personality] = Field(default_factory=list)
    rationale: str = ""
    scenario_config: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "BehaviorInstructions",
    "CallerProfile",
    "CallerStory",
    "EvaluationIntent",
    "JudgePromptSpec",
    "MetricExpectation",
    "MetricSelection",
    "PersonalitySelection",
    "RunEvaluatorDraft",
    "ScenarioCandidate",
    "SimulationInput",
    "SimulationPreferences",
    "SimulationWorkflowSpec",
    "SituationSpec",
    "ValidationResult",
    "WorkflowStep",
]
