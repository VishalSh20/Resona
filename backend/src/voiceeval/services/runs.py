"""Run and RunEvaluator domain operations (v0.4), wired to the generator."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import (
    InvalidStateTransitionError,
    ResourceNotFoundError,
    ValidationError,
)
from voiceeval.db.models import domain
from voiceeval.db.repositories import (
    RunEvaluatorRepository,
    RunRepository,
    SimulationRepository,
    TargetRepository,
)
from voiceeval.domain.enums import RunStatus
from voiceeval.generation.deterministic import validate_run_evaluator
from voiceeval.generation.errors import GenerationError
from voiceeval.generation.evaluations import EvaluationsWorkflow
from voiceeval.generation.models import (
    RunEvaluatorDraft,
    SimulationInput,
    SimulationWorkflowSpec,
)

_EDITABLE_STATUSES = {RunStatus.DRAFT.value, RunStatus.READY.value}


def _simulation_to_input(simulation: domain.Simulation) -> SimulationInput:
    return SimulationInput(
        name=simulation.name,
        description=simulation.description or "",
        languages=simulation.languages,
        metric_set=simulation.metric_set,
        personalities=simulation.personalities,
        knowledge_base=simulation.knowledge_base,
        evaluator_count=simulation.evaluator_count,
    )


class RunService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        workflow: EvaluationsWorkflow | None = None,
    ) -> None:
        self._session = session
        self._runs = RunRepository(session)
        self._evaluators = RunEvaluatorRepository(session)
        self._simulations = SimulationRepository(session)
        self._targets = TargetRepository(session)
        self._workflow = workflow

    async def create_run(
        self, simulation_id: str, target_revision_id: str
    ) -> domain.Run:
        simulation = await self._simulations.get_simulation(simulation_id)
        revision = await self._targets.get_revision(target_revision_id)
        if revision.agent_target_id != simulation.agent_target_id:
            raise ValidationError(
                "target revision does not belong to the simulation's agent"
            )
        existing_runs = await self._runs.list_runs(simulation_id)
        run = await self._runs.create_run(
            simulation_id=simulation_id,
            target_revision_id=target_revision_id,
            evaluator_count=simulation.evaluator_count,
        )
        # Runs after the first inherit a copy of the first run's evaluators; in
        # those runs only personality may be changed.
        if existing_runs:
            source = await self._evaluators.list_evaluators(existing_runs[0].id)
            if source:
                await self._evaluators.create_many(
                    run.id,
                    [
                        {
                            "scenario": e.scenario,
                            "expected_output_prompt": e.expected_output_prompt,
                            "metrics": e.metrics,
                            "languages": e.languages,
                            "personality": e.personality,
                        }
                        for e in source
                    ],
                )
        return run

    async def _is_first_run(self, run: domain.Run) -> bool:
        runs = await self._runs.list_runs(run.simulation_id)
        return bool(runs) and runs[0].id == run.id

    async def get_run(self, run_id: str) -> domain.Run:
        return await self._runs.get_run(run_id)

    async def list_runs(self, simulation_id: str) -> list[domain.Run]:
        await self._simulations.get_simulation(simulation_id)
        return await self._runs.list_runs(simulation_id)

    async def list_evaluators(self, run_id: str) -> list[domain.RunEvaluator]:
        await self._runs.get_run(run_id)
        return await self._evaluators.list_evaluators(run_id)

    async def get_evaluator(self, run_id: str, evaluator_id: str) -> domain.RunEvaluator:
        await self._runs.get_run(run_id)
        evaluator = await self._evaluators.get_evaluator(evaluator_id)
        if evaluator.run_id != run_id:
            raise ResourceNotFoundError(
                f"run evaluator '{evaluator_id}' does not belong to run '{run_id}'"
            )
        return evaluator

    async def generate_evaluators(
        self,
        run_id: str,
        workflow_spec: SimulationWorkflowSpec,
    ) -> list[domain.RunEvaluator]:
        run = await self._runs.get_run(run_id)
        if run.status not in _EDITABLE_STATUSES:
            raise InvalidStateTransitionError(
                f"run '{run_id}' is '{run.status}'; evaluators can only be "
                "generated while the run is editable"
            )
        if not await self._is_first_run(run):
            raise ValidationError(
                "evaluators can only be generated on the first run of a simulation"
            )
        simulation = await self._simulations.get_simulation(run.simulation_id)

        workflow = self._workflow or EvaluationsWorkflow()
        drafts = await workflow.run(
            simulation=_simulation_to_input(simulation),
            workflow_spec=workflow_spec,
        )
        if not drafts:
            raise GenerationError("generation produced no evaluators")

        payloads = [
            {
                "scenario": d.scenario,
                "expected_output_prompt": d.expected_output_prompt,
                "metrics": d.metrics,
                "languages": d.languages,
                "personality": d.personality,
                "scenario_config": d.scenario_config,
            }
            for d in drafts
        ]
        return await self._evaluators.create_many(run_id, payloads)

    async def update_evaluator(
        self,
        run_id: str,
        evaluator_id: str,
        *,
        scenario: str | None = None,
        scenario_config: dict[str, Any] | None = None,
        expected_output_prompt: str | None = None,
        metrics: list[str] | None = None,
        languages: dict[str, str | None] | None = None,
        personality: list[str] | None = None,
    ) -> domain.RunEvaluator:
        run = await self._runs.get_run(run_id)
        if run.status not in _EDITABLE_STATUSES:
            raise InvalidStateTransitionError(
                f"run '{run_id}' is '{run.status}'; evaluators can only be "
                "edited while the run is editable"
            )
        evaluator = await self._evaluators.get_evaluator(evaluator_id)
        if evaluator.run_id != run_id:
            raise ResourceNotFoundError(
                f"run evaluator '{evaluator_id}' does not belong to run '{run_id}'"
            )
        if not await self._is_first_run(run):
            if (
                scenario is not None
                or expected_output_prompt is not None
                or metrics is not None
                or languages is not None
            ):
                raise ValidationError(
                    "only personality can be edited on a run other than the first"
                )

        simulation = await self._simulations.get_simulation(run.simulation_id)
        merged = RunEvaluatorDraft(
            scenario=scenario if scenario is not None else evaluator.scenario,
            expected_output_prompt=(
                expected_output_prompt
                if expected_output_prompt is not None
                else evaluator.expected_output_prompt
            ),
            metrics=metrics if metrics is not None else evaluator.metrics,
            languages=languages if languages is not None else evaluator.languages,
            personality=(
                personality if personality is not None else evaluator.personality
            ),
        )
        validation = validate_run_evaluator(merged, _simulation_to_input(simulation))
        if not validation.passed:
            raise ValidationError(
                "evaluator update violates simulation constraints: "
                + "; ".join(validation.errors)
            )

        return await self._evaluators.update_evaluator(
            evaluator,
            scenario=scenario,
            scenario_config=scenario_config,
            expected_output_prompt=expected_output_prompt,
            metrics=metrics,
            languages=languages,
            personality=personality,
        )

    async def mark_ready(self, run_id: str) -> domain.Run:
        run = await self._runs.get_run(run_id)
        evaluators = await self._evaluators.list_evaluators(run_id)
        if not evaluators:
            raise ValidationError(
                f"run '{run_id}' has no evaluators; generate evaluators before "
                "marking it ready"
            )
        return await self._runs.transition_run(run, RunStatus.READY)

    async def start_run(self, run_id: str) -> domain.Run:
        """Queue a ready run for execution (expansion + dispatch happen in workers)."""
        run = await self._runs.get_run(run_id)
        if run.status not in {RunStatus.READY.value, RunStatus.QUEUED.value}:
            raise InvalidStateTransitionError(
                f"run '{run_id}' is '{run.status}'; only a ready run can be started"
            )
        evaluators = await self._evaluators.list_evaluators(run_id)
        if not evaluators:
            raise ValidationError(f"run '{run_id}' has no evaluators to execute")
        if run.status == RunStatus.READY.value:
            run = await self._runs.transition_run(run, RunStatus.QUEUED)

        from voiceeval.workers.enqueue import enqueue_execution_run

        await enqueue_execution_run(run.id)
        return run


__all__ = ["RunService"]
