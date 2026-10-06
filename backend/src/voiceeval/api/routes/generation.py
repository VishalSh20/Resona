"""AI evaluator-generation endpoints (the two workflows)."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import SessionDep, require_user_dep
from voiceeval.generation import SimulationPreferencesWorkflow
from voiceeval.schemas.runs import (
    SimulationPreferencesRequest,
    SimulationPreferencesResponse,
)

router = APIRouter(
    prefix="/generation", tags=["generation"], dependencies=[require_user_dep]
)


@router.post(
    "/simulation-preferences", response_model=SimulationPreferencesResponse
)
async def get_simulation_preferences(
    payload: SimulationPreferencesRequest,
    session: SessionDep,
) -> SimulationPreferencesResponse:
    """Workflow A: select useful metrics and personalities for a description."""
    result = await SimulationPreferencesWorkflow().run(
        description=payload.description,
        available_metrics=payload.available_metrics,
        available_personalities=payload.available_personalities,
    )
    return SimulationPreferencesResponse(
        metrics=result.metrics, personalities=result.personalities
    )


__all__ = ["router"]
