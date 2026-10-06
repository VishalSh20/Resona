"""Call-run operations that mutate execution state.

Reads live in ``results.py``; the retry operation belongs here because it
mutates a run and enqueues a fresh physical attempt.
"""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import (
    IdempotencyKeyDep,
    SessionDep,
    require_user_dep,
)
from voiceeval.schemas.results import CallRunRead
from voiceeval.services.idempotency import IdempotencyService
from voiceeval.services.plans import PlanService
from voiceeval.services.results import ResultService
from voiceeval.workers.enqueue import enqueue_execution_attempt

router = APIRouter(
    prefix="/call-runs", tags=["call-runs"], dependencies=[require_user_dep]
)


@router.post("/{run_id}/retry", response_model=CallRunRead)
async def retry_call_run(
    run_id: str,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> CallRunRead:
    """Retry an infrastructure-failed logical run (adds an attempt, not a run)."""
    await IdempotencyService(session).reserve(idempotency_key, "run:retry")
    await PlanService(session).retry_run(
        run_id, enqueue_attempt=enqueue_execution_attempt
    )
    run = await ResultService(session).get_run(run_id)
    await session.commit()
    return CallRunRead.model_validate(run)
