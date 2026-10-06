"""Simulation and Run configuration API (v0.4)."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import (
    IdempotencyKeyDep,
    SessionDep,
    require_user_dep,
)
from voiceeval.schemas.runs import RunCreate, RunRead
from voiceeval.schemas.simulations import (
    SimulationCreate,
    SimulationCreatedRead,
    SimulationRead,
)
from voiceeval.services.idempotency import IdempotencyService, hash_request
from voiceeval.services.runs import RunService
from voiceeval.services.simulations import SimulationService

router = APIRouter(
    prefix="/simulations", tags=["simulations"], dependencies=[require_user_dep]
)


@router.post("", response_model=SimulationCreatedRead, status_code=201)
async def create_simulation(
    payload: SimulationCreate,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> SimulationCreatedRead:
    await IdempotencyService(session).reserve(
        idempotency_key,
        "simulation:create",
        request_hash=hash_request(payload.model_dump(mode="json")),
    )
    simulation = await SimulationService(session).create_simulation(
        name=payload.name,
        description=payload.description,
        agent_target_id=payload.agent_target_id,
        languages=payload.languages,
        call_ambience=payload.call_ambience,
        metric_set=payload.metric_set,
        personalities=payload.personalities,
        knowledge_base=payload.knowledge_base,
        evaluator_count=payload.evaluator_count,
    )
    run = await RunService(session).create_run(
        simulation.id, payload.target_revision_id
    )
    await session.commit()
    return SimulationCreatedRead(
        simulation=SimulationRead.model_validate(simulation),
        run=RunRead.model_validate(run),
    )


@router.get("", response_model=list[SimulationRead])
async def list_simulations(session: SessionDep) -> list[SimulationRead]:
    service = SimulationService(session)
    return [
        SimulationRead.model_validate(s) for s in await service.list_simulations()
    ]


@router.get("/{simulation_id}", response_model=SimulationRead)
async def get_simulation(simulation_id: str, session: SessionDep) -> SimulationRead:
    service = SimulationService(session)
    return SimulationRead.model_validate(await service.get_simulation(simulation_id))


@router.post(
    "/{simulation_id}/runs", response_model=RunRead, status_code=201
)
async def create_run(
    simulation_id: str,
    payload: RunCreate,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> RunRead:
    await IdempotencyService(session).reserve(
        idempotency_key,
        "run:create",
        request_hash=hash_request(
            {"simulation_id": simulation_id, **payload.model_dump(mode="json")}
        ),
    )
    service = RunService(session)
    run = await service.create_run(simulation_id, payload.target_revision_id)
    await session.commit()
    return RunRead.model_validate(run)


@router.get("/{simulation_id}/runs", response_model=list[RunRead])
async def list_runs(simulation_id: str, session: SessionDep) -> list[RunRead]:
    service = RunService(session)
    return [RunRead.model_validate(r) for r in await service.list_runs(simulation_id)]


__all__ = ["router"]
