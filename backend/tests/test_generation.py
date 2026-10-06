"""Tests for the evaluator-generation workflows and deterministic helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from voiceeval.generation.deterministic import (
    canonical_personality,
    validate_preferences,
    validate_profile,
    validate_run_evaluator,
)
from voiceeval.generation.evaluations import EvaluationsWorkflow
from voiceeval.generation.models import (
    CallerProfile,
    RunEvaluatorDraft,
    SimulationInput,
    SimulationWorkflowSpec,
)
from voiceeval.generation.preferences import SimulationPreferencesWorkflow
from voiceeval.llm import StaticGenerationModel


def _simulation() -> SimulationInput:
    return SimulationInput(
        name="Credit Card Support",
        description="Handle blocked card requests with authentication.",
        languages=["hi", "en"],
        metric_set=["task_completion", "context_retention", "hallucination", "empathy"],
        personalities=["IMPATIENT", "INTERRUPTOR", "SUPPORTIVE", "SKEPTICAL"],
        knowledge_base={},
        evaluator_count=2,
    )


# --------------------------------------------------------------------------- #
# Deterministic helpers
# --------------------------------------------------------------------------- #

def test_canonical_personality_sorts_and_dedupes():
    assert canonical_personality(["INTERRUPTOR", "IMPATIENT", "INTERRUPTOR"]) == [
        "IMPATIENT",
        "INTERRUPTOR",
    ]


def test_validate_preferences_rejects_unknown_and_duplicates():
    result = validate_preferences(
        metrics=["task_completion", "task_completion"],
        personalities=["IMPATIENT"],
        available_metrics=["task_completion"],
        available_personalities=["IMPATIENT"],
    )
    assert not result.passed
    assert any("duplicate" in e for e in result.errors)


def test_run_evaluator_draft_rejects_unknown_metric():
    with pytest.raises(PydanticValidationError):
        RunEvaluatorDraft(
            scenario="scenario text",
            expected_output_prompt="judge prompt",
            metrics=["task_completion", "not_a_metric"],
            personality=["IMPATIENT"],
        )


def test_validate_run_evaluator_enforces_subset_membership():
    sim = _simulation()
    # "ttfa" is a valid MetricKey but not in this Simulation's metric_set.
    draft = RunEvaluatorDraft(
        scenario="scenario text",
        expected_output_prompt="judge prompt",
        metrics=["task_completion", "ttfa"],
        languages={"major": "hi", "minor": "en"},
        personality=["IMPATIENT"],
    )
    result = validate_run_evaluator(draft, sim)
    assert not result.passed
    assert any("ttfa" in e for e in result.errors)


def test_validate_run_evaluator_requires_major_language():
    sim = _simulation()
    draft = RunEvaluatorDraft(
        scenario="scenario text",
        expected_output_prompt="judge prompt",
        metrics=["task_completion"],
        languages={"major": None, "minor": None},
        personality=["IMPATIENT"],
    )
    result = validate_run_evaluator(draft, sim)
    assert not result.passed
    assert any("major language" in e for e in result.errors)


def test_validate_profile_requires_non_empty_personality():
    sim = _simulation()
    profile = CallerProfile(
        major_language="hi", personality=[]
    )
    assert not validate_profile(profile, sim).passed


# --------------------------------------------------------------------------- #
# Workflow A
# --------------------------------------------------------------------------- #

async def test_preferences_workflow_selects_via_llm():
    generation = StaticGenerationModel(
        [
            '{"objectives":["resolve"],"behavioral_requirements":["handle frustration"],'
            '"failure_modes":[],"task_characteristics":[],"language_requirements":["hi"],'
            '"caller_stressors":["impatience"],"knowledge_dependence":"high",'
            '"temporal_sensitivity":"low","ambiguity_flags":[]}',
            '{"items": ['
            '{"metric":"task_completion","reason":"goal resolution"},'
            '{"metric":"hallucination","reason":"grounding"},'
            '{"metric":"empathy","reason":"emotional callers"}'
            "]}",
            '{"items": ['
            '{"personality":"IMPATIENT","reason":"pressure"},'
            '{"personality":"INTERRUPTOR","reason":"turn-taking"}'
            "]}",
        ]
    )

    workflow = SimulationPreferencesWorkflow(generation=generation)
    result = await workflow.run(
        description="Handle blocked cards with frustrated callers.",
        available_metrics=["task_completion", "empathy", "hallucination", "ttfa"],
        available_personalities=["IMPATIENT", "SUPPORTIVE", "INTERRUPTOR", "VERBOSE"],
    )

    assert set(result.metrics) == {"task_completion", "hallucination", "empathy"}
    assert set(result.personalities) == {"IMPATIENT", "INTERRUPTOR"}


# --------------------------------------------------------------------------- #
# Workflow B
# --------------------------------------------------------------------------- #

def _profile_response():
    return {
        "items": [
            {
                "major_language": "hi",
                "minor_language": "en",
                "personality": ["IMPATIENT", "INTERRUPTOR"],
                "rationale": "bilingual impatient interrupter",
            },
            {
                "major_language": "en",
                "minor_language": None,
                "personality": ["SKEPTICAL"],
                "rationale": "skeptical verifier",
            },
        ]
    }


def _situation_response():
    return {
        "situation": "A customer's credit card is blocked while travelling abroad.",
        "why_it_exercises_metrics": ["task_completion", "context_retention"],
        "relevant_agent_context": "Banking support agent can unblock cards after authentication.",
    }


def _caller_story_response():
    return {
        "caller_name": "Rahul Sharma",
        "background": "Frequent traveller currently in Singapore.",
        "region": "Mumbai, India (currently in Singapore)",
        "facts": ["Card ending 4821 was blocked", "Last transaction declined at hotel"],
        "situation_overview": "Rahul calls from Singapore because his card was blocked.",
    }


def _behaviour_response():
    return {
        "tone": "frustrated and urgent",
        "opening_style": "Demand immediate unblocking",
        "instructions": ["Interrupt if agent asks for irrelevant details", "Ask for supervisor if stalled"],
        "reaction_triggers": ["If asked to hold, express urgency"],
        "constraints": ["Do not reveal OTP"],
        "fallback_if_stuck": "Repeat the last request firmly.",
    }


def _judge_response():
    return {
        "objective": "assess handling",
        "expected_agent_behavior": ["authenticate", "resolve"],
        "metric_expectations": [
            {
                "metric": "task_completion",
                "what_to_evaluate": "goal resolved",
                "pass_condition": "resolved",
                "failure_condition": "unresolved",
                "evidence_to_consider": ["turn"],
            },
            {
                "metric": "context_retention",
                "what_to_evaluate": "remembers provided info",
                "pass_condition": "kept",
                "failure_condition": "forgot",
                "evidence_to_consider": ["turn"],
            },
            {
                "metric": "hallucination",
                "what_to_evaluate": "factual grounding",
                "pass_condition": "grounded",
                "failure_condition": "invented",
                "evidence_to_consider": ["turn"],
            },
            {
                "metric": "empathy",
                "what_to_evaluate": "tone",
                "pass_condition": "empathetic",
                "failure_condition": "cold",
                "evidence_to_consider": ["turn"],
            },
        ],
        "evidence_requirements": ["turns"],
        "prohibited_assumptions": ["invented facts"],
        "outcome_definition": "task resolved",
    }


def _generation_fn(request):
    system = request.system
    if "caller-profile designer" in system:
        return _profile_response()
    if "pure situation" in system:
        return _situation_response()
    if "caller identity" in system:
        return _caller_story_response()
    if "behaviour instructions" in system or "behavior instructions" in system:
        return _behaviour_response()
    if "downstream judge" in system:
        return _judge_response()
    raise AssertionError(f"unexpected system prompt: {system}")


async def test_evaluations_workflow_generates_valid_evaluators():
    generation = StaticGenerationModel(_generation_fn)
    workflow = EvaluationsWorkflow(generation=generation)

    sim = _simulation()
    spec = SimulationWorkflowSpec(
        objective="Verify blocked-card handling and authentication.",
        task_flow=[],
        success_conditions=["card unblocked after authentication"],
        constraints=["must authenticate before acting"],
    )

    drafts = await workflow.run(simulation=sim, workflow_spec=spec)

    assert len(drafts) == sim.evaluator_count
    for draft in drafts:
        result = validate_run_evaluator(draft, sim)
        assert result.passed, result.errors
        assert set(draft.metrics) == set(sim.metric_set)
        assert set(draft.personality) <= set(sim.personalities)
        assert "# Situation_Overview" in draft.scenario
        assert "# Facts" in draft.scenario
        assert "# Behavioural_Instructions" in draft.scenario
        assert draft.scenario_config
        assert draft.scenario_config["schema_version"] == "evaluator.v1"
        assert draft.scenario_config["persona"]["name"] == "Rahul Sharma"
        assert draft.scenario_config["persona"]["region"]
