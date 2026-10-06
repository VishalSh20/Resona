"""Workflow B — ``get_evaluations`` (the core workflow).

Instantiates a Simulation into concrete ``RunEvaluatorDraft`` scenarios. It is a
structured planning pipeline, not a free-running agent:

    validate → analyze space → generate 2N profiles → dedupe/filter →
    Jev-score → diversity-aware select N → (fan-out) generate scenarios →
    select best scenario → metric candidates → Jev metric selection →
    mandatory metrics → judge prompt → validate → bounded repair.

Deterministic code owns membership/coverage/correctness; the LLM owns semantic
generation; Jev owns bounded selection. Fan-out over selected profiles uses
``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
import logging

from voiceeval.core.config import get_settings
from voiceeval.core.errors import ValidationError
from voiceeval.generation.deterministic import (
    canonical_personality,
    enforce_metric_policy,
    greedy_diverse_selection,
    validate_profile,
    validate_run_evaluator,
)
from voiceeval.generation.errors import GenerationError
from voiceeval.generation.models import (
    CallerProfile,
    EvaluationSpaceAnalysis,
    JudgePromptSpec,
    RunEvaluatorDraft,
    ScenarioCandidate,
    SimulationInput,
    SimulationWorkflowSpec,
)
from voiceeval.generation.registries import (
    BackgroundRegistry,
    MetricReasoningRegistry,
    PersonalityRegistry,
    get_background_registry,
    get_metric_reasoning_registry,
    get_personality_registry,
)
from voiceeval.llm import (
    BaseGenerationModel,
    DecisionModel,
    DecisionQuestion,
    get_decision_model,
    get_generation_model,
)

logger = logging.getLogger("voiceeval.generation.evaluations")

_JEV_SCORE_CRITERIA = ["low diagnostic value", "medium diagnostic value", "high diagnostic value"]
_JEV_INCLUDE_THRESHOLD = 0.5


class EvaluationsWorkflow:
    def __init__(
        self,
        *,
        generation: BaseGenerationModel | None = None,
        decision: DecisionModel | None = None,
        metric_registry: MetricReasoningRegistry | None = None,
        personality_registry: PersonalityRegistry | None = None,
        background_registry: BackgroundRegistry | None = None,
    ) -> None:
        self._generation = generation or get_generation_model()
        self._decision = decision or get_decision_model()
        self._metrics = metric_registry or get_metric_reasoning_registry()
        self._personalities = personality_registry or get_personality_registry()
        self._backgrounds = background_registry or get_background_registry()
        self._settings = get_settings()

    async def run(
        self,
        *,
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
    ) -> list[RunEvaluatorDraft]:
        self._validate_simulation(simulation)
        n = simulation.evaluator_count

        analysis = await self._analyze_evaluation_space(simulation, workflow_spec)

        candidates = await self._generate_profile_candidates(
            simulation, workflow_spec, analysis, target=2 * n
        )
        candidates = self._deduplicate_and_filter(candidates, simulation)
        if len(candidates) < n:
            candidates = await self._generate_profile_candidates(
                simulation, workflow_spec, analysis, target=2 * n
            )
            candidates = self._deduplicate_and_filter(candidates, simulation)

        scores = await self._score_profiles(candidates, simulation, analysis)
        selected = greedy_diverse_selection(
            candidates,
            n,
            lambda p: scores.get(_profile_key(p), 0.0),
            diversity_weight=0.5,
        )

        drafts = await asyncio.gather(
            *[
                self._plan_evaluator(profile, simulation, workflow_spec, analysis)
                for profile in selected
            ]
        )
        return list(drafts)

    # -- deterministic validation ------------------------------------------- #
    def _validate_simulation(self, simulation: SimulationInput) -> None:
        if not simulation.metric_set:
            raise ValidationError("simulation.metric_set must not be empty")
        if not simulation.personalities:
            raise ValidationError("simulation.personalities must not be empty")
        if not simulation.languages:
            raise ValidationError("simulation.languages must not be empty")
        if not simulation.backgrounds:
            raise ValidationError("simulation.backgrounds must not be empty")
        unknown_metrics = [m for m in simulation.metric_set if not self._metrics.has(m)]
        if unknown_metrics:
            raise ValidationError(
                f"unknown metric keys in simulation.metric_set: {', '.join(unknown_metrics)}"
            )

    # -- semantic analysis (LLM) --------------------------------------------- #
    async def _analyze_evaluation_space(
        self, simulation: SimulationInput, workflow_spec: SimulationWorkflowSpec
    ) -> EvaluationSpaceAnalysis:
        system = (
            "You analyze a voice-agent evaluation space. Return only structured JSON."
        )
        user = (
            "Simulation:\n"
            f"{simulation.model_dump_json()}\n\n"
            "Detailed simulation workflow:\n"
            f"{workflow_spec.model_dump_json()}\n\n"
            "Extract core behaviors, stress conditions, language requirements, "
            "knowledge dependencies, important interaction patterns, and target "
            "failure modes."
        )
        try:
            return await self._generation.structured(
                EvaluationSpaceAnalysis, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"evaluation space analysis failed: {exc}") from exc

    # -- profile candidate generation (LLM) ---------------------------------- #
    async def _generate_profile_candidates(
        self,
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
        analysis: EvaluationSpaceAnalysis,
        *,
        target: int,
    ) -> list[CallerProfile]:
        system = (
            "You design synthetic caller profiles for a voice-agent evaluation. "
            "Return only structured JSON."
        )
        user = (
            "Design exactly "
            f"{target} diverse caller profiles.\n\n"
            "Simulation:\n"
            f"{simulation.model_dump_json()}\n\n"
            "Workflow:\n"
            f"{workflow_spec.model_dump_json()}\n\n"
            "Analysis:\n"
            f"{analysis.model_dump_json()}\n\n"
            "Maximize diagnostic coverage across these axes:\n"
            "- language (monolingual, bilingual, code-switching, regional-dominant)\n"
            "- background (spread across the allowed backgrounds)\n"
            "- personality (spread across the allowed personalities; combine traits "
            "when they create a stronger test)\n"
            "- high-risk / diagnostically interesting combinations\n\n"
            "Every value MUST come from the allowed sets. Preserve major/minor "
            "language semantics (major is the dominant language). Do not repeat "
            "near-identical profiles."
        )
        try:
            return await self._generation.structured_many(
                CallerProfile, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"profile generation failed: {exc}") from exc

    # -- dedup + filter (deterministic) -------------------------------------- #
    def _deduplicate_and_filter(
        self, candidates: list[CallerProfile], simulation: SimulationInput
    ) -> list[CallerProfile]:
        seen: set[tuple] = set()
        kept: list[CallerProfile] = []
        for profile in candidates:
            profile.personality = canonical_personality(profile.personality)
            validation = validate_profile(profile, simulation)
            if not validation.passed:
                continue
            key = _profile_key(profile)
            if key in seen:
                continue
            seen.add(key)
            kept.append(profile)
        return kept

    # -- Jev scoring --------------------------------------------------------- #
    async def _score_profiles(
        self,
        candidates: list[CallerProfile],
        simulation: SimulationInput,
        analysis: EvaluationSpaceAnalysis,
    ) -> dict[tuple, float]:
        if not candidates:
            return {}
        questions = {
            f"profile_{i}": DecisionQuestion(
                type="score",
                instructions=(
                    "How diagnostically valuable is this caller profile for the "
                    f"simulation? Profile: {profile.model_dump_json()}"
                ),
                criteria=_JEV_SCORE_CRITERIA,
            )
            for i, profile in enumerate(candidates)
        }
        state = {
            "simulation": simulation.model_dump(),
            "analysis": analysis.model_dump(),
        }
        try:
            answers = await self._decision.decide(state=state, questions=questions)
        except Exception as exc:
            logger.warning("Jev profile scoring failed, using neutral scores: %s", exc)
            return {_profile_key(p): 1.0 for p in candidates}

        return {
            _profile_key(profile): float(answers[f"profile_{i}"].value)
            for i, profile in enumerate(candidates)
        }

    # -- per-profile planning (fan-out) -------------------------------------- #
    async def _plan_evaluator(
        self,
        profile: CallerProfile,
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
        analysis: EvaluationSpaceAnalysis,
    ) -> RunEvaluatorDraft:
        scenarios = await self._generate_scenarios(
            profile, simulation, workflow_spec, analysis
        )
        best = self._select_best_scenario(scenarios, simulation)

        metric_candidates = self._build_metric_candidates(best, simulation)
        contextual = await self._select_metrics(
            best, simulation, metric_candidates
        )
        final_metrics = enforce_metric_policy(
            selected=contextual,
            simulation=simulation,
            mandatory_metrics=self._settings.generation_mandatory_metrics,
            minimum=self._settings.generation_min_metrics_per_evaluator,
            maximum=self._settings.generation_max_metrics_per_evaluator,
        )

        judge_spec = await self._generate_judge_prompt(
            best, final_metrics, simulation, workflow_spec
        )

        draft = RunEvaluatorDraft(
            scenario=best.render(),
            expected_output_prompt=judge_spec.render(),
            metrics=final_metrics,
            languages={
                "major": profile.major_language,
                "minor": profile.minor_language,
            },
            background=profile.background,
            personality=canonical_personality(profile.personality),
            rationale=profile.rationale,
        )

        for attempt in range(self._settings.generation_max_repair_attempts + 1):
            validation = validate_run_evaluator(draft, simulation)
            if validation.passed:
                return draft
            if attempt < self._settings.generation_max_repair_attempts:
                draft = await self._repair(
                    draft, validation, simulation, workflow_spec, analysis
                )
            else:
                raise GenerationError(
                    "evaluator failed validation after repair: "
                    + "; ".join(validation.errors)
                )
        return draft  # pragma: no cover - unreachable

    async def _generate_scenarios(
        self,
        profile: CallerProfile,
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
        analysis: EvaluationSpaceAnalysis,
        *,
        repair_hint: str | None = None,
    ) -> list[ScenarioCandidate]:
        system = (
            "You write realistic caller-agent scenarios for a voice-agent "
            "evaluation. Return only structured JSON."
        )
        hint = f"\n\nFix these issues from the previous attempt: {repair_hint}" if repair_hint else ""
        user = (
            f"Write {self._settings.generation_scenarios_per_profile} realistic "
            "scenarios for this caller profile.\n\n"
            "Simulation:\n"
            f"{simulation.model_dump_json()}\n\n"
            "Workflow:\n"
            f"{workflow_spec.model_dump_json()}\n\n"
            "Caller profile:\n"
            f"{profile.model_dump_json()}\n\n"
            "Analysis:\n"
            f"{analysis.model_dump_json()}\n\n"
            "Each scenario must be a realistic interaction, not a metric "
            "checklist. For each scenario, include metric_opportunities: for every "
            "metric the scenario can actually measure, give a measurability "
            "(primary/secondary/incidental/not_measurable), the observable "
            "behavior, and evidence sources."
            f"{hint}"
        )
        try:
            scenarios = await self._generation.structured_many(
                ScenarioCandidate, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"scenario generation failed: {exc}") from exc
        if not scenarios:
            raise GenerationError("scenario generation produced no scenarios")
        return scenarios

    def _select_best_scenario(
        self, scenarios: list[ScenarioCandidate], simulation: SimulationInput
    ) -> ScenarioCandidate:
        if not scenarios:
            raise GenerationError("no scenario candidates to select from")
        return max(scenarios, key=lambda s: _score_scenario(s, simulation))

    def _build_metric_candidates(
        self, scenario: ScenarioCandidate, simulation: SimulationInput
    ) -> list[str]:
        available = set(simulation.metric_set)
        candidates: list[str] = []
        for opportunity in scenario.metric_opportunities:
            if opportunity.metric not in available:
                continue
            if opportunity.measurability in {"primary", "secondary"}:
                if opportunity.metric not in candidates:
                    candidates.append(opportunity.metric)
        return candidates

    async def _select_metrics(
        self,
        scenario: ScenarioCandidate,
        simulation: SimulationInput,
        candidates: list[str],
    ) -> list[str]:
        if not candidates:
            return []
        questions = {
            f"metric_{metric}": DecisionQuestion(
                type="noul",
                instructions=(
                    f"Should metric '{metric}' be measured for this scenario? "
                    f"Scenario: {scenario.title}. Observable behaviors: "
                    + ", ".join(
                        o.observable_behavior
                        for o in scenario.metric_opportunities
                        if o.metric == metric
                    )
                ),
                criteria={
                    "true": "The scenario can meaningfully measure this metric.",
                    "false": "The scenario cannot meaningfully measure this metric.",
                },
            )
            for metric in candidates
        }
        state = {"scenario": scenario.model_dump(), "simulation": simulation.model_dump()}
        try:
            answers = await self._decision.decide(state=state, questions=questions)
        except Exception as exc:
            logger.warning("Jev metric selection failed, keeping candidates: %s", exc)
            return candidates

        return [
            metric
            for metric in candidates
            if answers[f"metric_{metric}"].value >= _JEV_INCLUDE_THRESHOLD
        ] or candidates

    async def _generate_judge_prompt(
        self,
        scenario: ScenarioCandidate,
        metrics: list[str],
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
    ) -> JudgePromptSpec:
        metric_defs = [
            {
                "key": key,
                "family": self._metrics.get(key).family,
                "relevant_behaviors": sorted(self._metrics.get(key).relevant_behaviors),
            }
            for key in metrics
        ]
        system = (
            "You write the judge-facing expected-output prompt for a voice-agent "
            "evaluation. Return only structured JSON."
        )
        user = (
            "Simulation:\n"
            f"{simulation.model_dump_json()}\n\n"
            "Workflow:\n"
            f"{workflow_spec.model_dump_json()}\n\n"
            "Selected scenario:\n"
            f"{scenario.model_dump_json()}\n\n"
            f"Selected metrics: {metric_defs}\n\n"
            "Produce the judge specification: objective, expected agent behavior, "
            "per-metric expectations (what to evaluate, pass condition, failure "
            "condition, evidence), evidence requirements, prohibited assumptions, "
            "and the outcome definition. Use the canonical metric meanings above; "
            "do not invent new metric semantics."
        )
        try:
            return await self._generation.structured(
                JudgePromptSpec, system=system, user=user
            )
        except Exception as exc:
            raise GenerationError(f"judge prompt generation failed: {exc}") from exc

    async def _repair(
        self,
        draft: RunEvaluatorDraft,
        validation,
        simulation: SimulationInput,
        workflow_spec: SimulationWorkflowSpec,
        analysis: EvaluationSpaceAnalysis,
    ) -> RunEvaluatorDraft:
        profile = CallerProfile(
            major_language=draft.languages["major"] or "",
            minor_language=draft.languages.get("minor"),
            background=draft.background,
            personality=draft.personality,
        )
        scenarios = await self._generate_scenarios(
            profile,
            simulation,
            workflow_spec,
            analysis,
            repair_hint="; ".join(validation.errors),
        )
        best = self._select_best_scenario(scenarios, simulation)
        judge_spec = await self._generate_judge_prompt(
            best, draft.metrics, simulation, workflow_spec
        )
        return RunEvaluatorDraft(
            scenario=best.render(),
            expected_output_prompt=judge_spec.render(),
            metrics=draft.metrics,
            languages=draft.languages,
            background=draft.background,
            personality=draft.personality,
            rationale=draft.rationale,
        )


def _profile_key(profile: CallerProfile) -> tuple:
    return (
        profile.major_language,
        profile.minor_language,
        profile.background,
        tuple(profile.personality),
    )


def _score_scenario(scenario: ScenarioCandidate, simulation: SimulationInput) -> float:
    available = set(simulation.metric_set)
    primary = 0
    secondary = 0
    distinct: set[str] = set()
    for opportunity in scenario.metric_opportunities:
        if opportunity.metric not in available:
            continue
        if opportunity.measurability == "primary":
            primary += 1
            distinct.add(opportunity.metric)
        elif opportunity.measurability == "secondary":
            secondary += 1
            distinct.add(opportunity.metric)
    richness = sum(
        1
        for field in (
            scenario.context,
            scenario.caller_instructions,
            scenario.underlying_problem,
            scenario.conversation_goal,
            scenario.communication_behavior,
        )
        if field
    )
    return 3 * primary + 1 * secondary + 2 * len(distinct) + 0.5 * richness


__all__ = ["EvaluationsWorkflow"]
