"""Run and RunEvaluator API (v0.4): read runs and manage generated evaluators."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import (
    IdempotencyKeyDep,
    SessionDep,
    require_user_dep,
)
from voiceeval.schemas.runs import (
    GenerateEvaluationsRequest,
    GenerateEvaluationsResponse,
    RunEvaluatorRead,
    RunEvaluatorUpdate,
    RunRead,
)
from voiceeval.services.idempotency import IdempotencyService, hash_request
from voiceeval.services.runs import RunService

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[require_user_dep])


@router.get("/{run_id}", response_model=RunRead)
async def get_run(run_id: str, session: SessionDep) -> RunRead:
    service = RunService(session)
    return RunRead.model_validate(await service.get_run(run_id))


@router.get("/{run_id}/evaluators", response_model=list[RunEvaluatorRead])
async def list_evaluators(run_id: str, session: SessionDep) -> list[RunEvaluatorRead]:
    service = RunService(session)
    return [
        RunEvaluatorRead.model_validate(e)
        for e in await service.list_evaluators(run_id)
    ]


@router.get("/{run_id}/evaluators/{evaluator_id}", response_model=RunEvaluatorRead)
async def get_evaluator(
    run_id: str, evaluator_id: str, session: SessionDep
) -> RunEvaluatorRead:
    service = RunService(session)
    return RunEvaluatorRead.model_validate(
        await service.get_evaluator(run_id, evaluator_id)
    )


@router.post(
    "/{run_id}/evaluators/generate",
    response_model=GenerateEvaluationsResponse,
    status_code=201,
)
async def generate_evaluators(
    run_id: str,
    payload: GenerateEvaluationsRequest,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> GenerateEvaluationsResponse:
    await IdempotencyService(session).reserve(
        idempotency_key,
        "run:generate-evaluators",
        request_hash=hash_request(payload.model_dump(mode="json")),
    )
    service = RunService(session)
    evaluators = await service.generate_evaluators(run_id, payload.workflow_spec)
    await session.commit()
    return GenerateEvaluationsResponse(
        run_id=run_id,
        count=len(evaluators),
        evaluators=[RunEvaluatorRead.model_validate(e) for e in evaluators],
    )


@router.post("/{run_id}/ready", response_model=RunRead)
async def mark_run_ready(run_id: str, session: SessionDep) -> RunRead:
    """Freeze a run's evaluator set: transition it from editable to ``ready``."""
    service = RunService(session)
    run = await service.mark_ready(run_id)
    await session.commit()
    return RunRead.model_validate(run)


@router.post("/{run_id}/start", response_model=RunRead)
async def start_run(run_id: str, session: SessionDep) -> RunRead:
    """Queue a ready run for execution (expanded into call runs by the worker)."""
    service = RunService(session)
    run = await service.start_run(run_id)
    await session.commit()
    return RunRead.model_validate(run)


@router.patch("/{run_id}/evaluators/{evaluator_id}", response_model=RunEvaluatorRead)
async def update_evaluator(
    run_id: str,
    evaluator_id: str,
    payload: RunEvaluatorUpdate,
    session: SessionDep,
) -> RunEvaluatorRead:
    service = RunService(session)
    evaluator = await service.update_evaluator(
        run_id,
        evaluator_id,
        scenario=payload.scenario,
        scenario_config=payload.scenario_config,
        expected_output_prompt=payload.expected_output_prompt,
        metrics=payload.metrics,
        languages=payload.languages,
        personality=payload.personality,
    )
    await session.commit()
    return RunEvaluatorRead.model_validate(evaluator)


__all__ = ["router"]
