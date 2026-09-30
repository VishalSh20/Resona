"""Validation worker job (v0.4).

Runs the deterministic Simulation-membership validators over a ``RunEvaluator``
and persists a ``ValidationReport``. It runs outside the API request lifecycle.
"""

from __future__ import annotations

from voiceeval.core.clocks import utc_now
from voiceeval.core.ids import new_plain_ulid
from voiceeval.db.models import domain
from voiceeval.db.models.support import Job
from voiceeval.db.repositories import (
    RunEvaluatorRepository,
    SimulationRepository,
    RunRepository,
)
from voiceeval.db.session import get_session_factory
from voiceeval.generation.deterministic import validate_run_evaluator
from voiceeval.generation.models import RunEvaluatorDraft, SimulationInput
from voiceeval.domain.enums import ValidationStatus


def _simulation_input(simulation: domain.Simulation) -> SimulationInput:
    return SimulationInput(
        name=simulation.name,
        description=simulation.description or "",
        languages=simulation.languages,
        metric_set=simulation.metric_set,
        personalities=simulation.personalities,
        knowledge_base=simulation.knowledge_base,
        evaluator_count=simulation.evaluator_count,
    )


async def validate_run_evaluator(ctx: dict, run_evaluator_id: str, job_id: str) -> str:
    factory = get_session_factory()
    async with factory() as session:
        evaluator = await RunEvaluatorRepository(session).get_evaluator(run_evaluator_id)
        run = await RunRepository(session).get_run(evaluator.run_id)
        simulation = await SimulationRepository(session).get_simulation(run.simulation_id)

        draft = RunEvaluatorDraft(
            scenario=evaluator.scenario,
            expected_output_prompt=evaluator.expected_output_prompt,
            metrics=evaluator.metrics,
            languages=evaluator.languages,
            personality=evaluator.personality,
        )
        outcome = validate_run_evaluator(draft, _simulation_input(simulation))

        report = domain.ValidationReport(
            id=new_plain_ulid(),
            run_evaluator_id=evaluator.id,
            validator_version="deterministic.v1",
            status=(
                ValidationStatus.PASSED.value
                if outcome.passed
                else ValidationStatus.FAILED.value
            ),
            blocking_error_count=len(outcome.errors),
            warning_count=len(outcome.warnings),
            checks=[{"key": "deterministic", "errors": outcome.errors, "warnings": outcome.warnings}],
        )
        session.add(report)

        job = await session.get(Job, job_id)
        if job is not None:
            job.status = "completed"
            job.finished_at = utc_now()

        await session.commit()
        return report.status


__all__ = ["validate_run_evaluator"]
