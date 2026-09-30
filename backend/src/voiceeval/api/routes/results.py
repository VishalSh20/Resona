"""Results, forensics and media API (v0.4).

Read-only surfaces over evaluation truth. They reconstruct runs, call runs,
attempts, conversation materialization, metric results with evidence, aggregates,
the composite score and forensic bundles without ever exposing SQLAlchemy models.
Event collections are paginated because they can be large.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from voiceeval.api.dependencies import SessionDep, require_user_dep
from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.schemas.results import (
    AggregateRead,
    CallAttemptRead,
    CallRunRead,
    CompositeRead,
    ConversationRead,
    EvidenceRead,
    ForensicsRead,
    JudgeExecutionRead,
    ManifestRead,
    MediaArtifactRead,
    MediaUrlRead,
    MetricResultRead,
    PaginatedEvents,
    RunResultsRead,
)
from voiceeval.services.results import ResultService
from voiceeval.storage import get_object_store, verify_media_key

# Authenticated read surfaces over evaluation truth.
router = APIRouter(tags=["results"], dependencies=[require_user_dep])

# The media-blob endpoint is deliberately unauthenticated by bearer token: it is
# fetched by browsers/players via a short-lived, HMAC-signed URL, so its
# authorisation is the signature and expiry, not a session. It must stay outside
# the authenticated router.
blob_router = APIRouter(tags=["results"])


@router.get("/runs/{run_id}/results", response_model=RunResultsRead)
async def run_results(run_id: str, session: SessionDep) -> RunResultsRead:
    return RunResultsRead.model_validate(
        await ResultService(session).run_results(run_id)
    )


@router.get(
    "/runs/{run_id}/evaluators/{run_evaluator_id}/results",
    response_model=RunResultsRead,
)
async def evaluator_results(
    run_id: str, run_evaluator_id: str, session: SessionDep
) -> RunResultsRead:
    return RunResultsRead.model_validate(
        await ResultService(session).evaluator_results(run_id, run_evaluator_id)
    )


@router.get("/runs/{run_id}/aggregates", response_model=list[AggregateRead])
async def run_aggregates(run_id: str, session: SessionDep) -> list[AggregateRead]:
    rows = await ResultService(session).list_aggregates(run_id)
    return [AggregateRead.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/composite", response_model=CompositeRead)
async def run_composite(run_id: str, session: SessionDep) -> CompositeRead:
    composite = await ResultService(session).get_composite(run_id)
    if composite is None:
        raise ResourceNotFoundError(f"run '{run_id}' has no composite score yet")
    return CompositeRead.model_validate(composite)


@router.get("/call-runs/{call_run_id}", response_model=CallRunRead)
async def get_call_run(call_run_id: str, session: SessionDep) -> CallRunRead:
    return CallRunRead.model_validate(await ResultService(session).get_run(call_run_id))


@router.get("/runs/{run_id}/call-runs", response_model=list[CallRunRead])
async def list_run_call_runs(
    run_id: str, session: SessionDep
) -> list[CallRunRead]:
    rows = await ResultService(session).list_runs(run_id)
    return [CallRunRead.model_validate(row) for row in rows]


@router.get("/call-runs/{call_run_id}/attempts", response_model=list[CallAttemptRead])
async def list_call_run_attempts(
    call_run_id: str, session: SessionDep
) -> list[CallAttemptRead]:
    rows = await ResultService(session).list_attempts(call_run_id)
    return [CallAttemptRead.model_validate(row) for row in rows]


@router.get("/runs/{run_id}/manifest", response_model=ManifestRead)
async def get_run_manifest(run_id: str, session: SessionDep) -> ManifestRead:
    return ManifestRead.model_validate(await ResultService(session).get_manifest(run_id))


@router.get("/call-runs/{call_run_id}/forensics", response_model=ForensicsRead)
async def get_forensics(call_run_id: str, session: SessionDep) -> ForensicsRead:
    from voiceeval.services.results import ForensicsService

    return ForensicsRead.model_validate(
        await ForensicsService(session).reconstruct(call_run_id)
    )


@router.get("/call-attempts/{attempt_id}", response_model=CallAttemptRead)
async def get_call_attempt(attempt_id: str, session: SessionDep) -> CallAttemptRead:
    return CallAttemptRead.model_validate(
        await ResultService(session).get_attempt(attempt_id)
    )


@router.get("/call-attempts/{attempt_id}/events", response_model=PaginatedEvents)
async def list_attempt_events(
    attempt_id: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    source: Annotated[str | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
    from_ms: Annotated[int | None, Query(ge=0)] = None,
    to_ms: Annotated[int | None, Query(ge=0)] = None,
) -> PaginatedEvents:
    payload = await ResultService(session).list_events(
        attempt_id,
        limit=limit,
        offset=offset,
        source=source,
        event_type=type,
        from_ms=from_ms,
        to_ms=to_ms,
    )
    return PaginatedEvents.model_validate(payload)


@router.get(
    "/call-attempts/{attempt_id}/conversation", response_model=ConversationRead
)
async def get_attempt_conversation(
    attempt_id: str, session: SessionDep
) -> ConversationRead:
    return ConversationRead.model_validate(
        await ResultService(session).get_conversation(attempt_id)
    )


@router.get(
    "/call-attempts/{attempt_id}/media", response_model=list[MediaArtifactRead]
)
async def list_attempt_media(
    attempt_id: str, session: SessionDep
) -> list[MediaArtifactRead]:
    rows = await ResultService(session).list_media(attempt_id)
    return [MediaArtifactRead.model_validate(row) for row in rows]


@router.get("/metric-results/{metric_result_id}", response_model=MetricResultRead)
async def get_metric_result(
    metric_result_id: str, session: SessionDep
) -> MetricResultRead:
    return MetricResultRead.model_validate(
        await ResultService(session).get_metric_result(metric_result_id)
    )


@router.get(
    "/metric-results/{metric_result_id}/evidence", response_model=list[EvidenceRead]
)
async def get_metric_result_evidence(
    metric_result_id: str, session: SessionDep
) -> list[EvidenceRead]:
    rows = await ResultService(session).list_evidence(metric_result_id)
    return [EvidenceRead.model_validate(row) for row in rows]


@router.get(
    "/judge-executions/{judge_execution_id}", response_model=JudgeExecutionRead
)
async def get_judge_execution(
    judge_execution_id: str, session: SessionDep
) -> JudgeExecutionRead:
    """Return a judge execution and its full §9 result document."""
    return JudgeExecutionRead.model_validate(
        await ResultService(session).get_judge_execution(judge_execution_id)
    )


@router.get("/media/{media_artifact_id}/url", response_model=MediaUrlRead)
async def get_media_url(
    media_artifact_id: str,
    session: SessionDep,
    expires_in: Annotated[int, Query(ge=1, le=3600)] = 300,
) -> MediaUrlRead:
    return MediaUrlRead.model_validate(
        await ResultService(session).media_url(
            media_artifact_id, expires_in_seconds=expires_in
        )
    )


@blob_router.get("/media/blob")
async def get_media_blob(key: str, exp: int, sig: str) -> Response:
    """Serve a locally-stored media object for a valid short-lived URL."""
    verify_media_key(key, expires_at=exp, signature=sig)
    data = get_object_store().get(key)
    return Response(content=data, media_type="application/octet-stream")


__all__ = ["blob_router", "router"]
