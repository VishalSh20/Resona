"""Agent target configuration API (create / discover / import / sync)."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import (
    IdempotencyKeyDep,
    SessionDep,
    require_user_dep,
)
from voiceeval.schemas.targets import (
    PreviewAgentIdentity,
    PreviewRevision,
    RevisionDiscoveryCandidate,
    RevisionDiscoveryResponse,
    RevisionImportRequest,
    TargetCreate,
    TargetConnectionUpsert,
    TargetCreatedRead,
    TargetPreviewRequest,
    TargetPreviewResponse,
    TargetRead,
    TargetRevisionRead,
)
from voiceeval.services.idempotency import IdempotencyService, hash_request
from voiceeval.services.targets import TargetService

router = APIRouter(
    prefix="/targets", tags=["targets"], dependencies=[require_user_dep]
)


@router.post("", response_model=TargetCreatedRead, status_code=201)
async def create_target(
    payload: TargetCreate, session: SessionDep
) -> TargetCreatedRead:
    service = TargetService(session)
    target, revision = await service.create_target(
        provider_id=payload.provider_id,
        integration_account_id=payload.integration_account_id,
        name=payload.name,
        external_agent_id=payload.external_agent_id,
        agent_url=payload.agent_url,
        description=payload.description,
        first_message=payload.first_message,
        llm_config=payload.llm_config,
        stt_config=payload.stt_config,
        tts_config=payload.tts_config,
        turn_config=payload.turn_config,
        conversation_config=payload.conversation_config,
        tools_config=payload.tools_config,
        variables_config=payload.variables_config,
        knowledge_config=payload.knowledge_config,
        workflow_config=payload.workflow_config,
        handoffs_config=payload.handoffs_config,
        guardrails_config=payload.guardrails_config,
    )
    await session.commit()
    return TargetCreatedRead(
        target=TargetRead.model_validate(target),
        revision=TargetRevisionRead.model_validate(revision),
    )


@router.post("/preview", response_model=TargetPreviewResponse)
async def preview_target(
    payload: TargetPreviewRequest, session: SessionDep
) -> TargetPreviewResponse:
    service = TargetService(session)
    identity, revision = await service.preview_target(
        provider_id=payload.provider_id,
        external_agent_id=payload.external_agent_id,
        config=payload.config,
        secrets=payload.secrets,
    )
    canonical = revision.canonical_config
    return TargetPreviewResponse(
        identity=PreviewAgentIdentity(
            external_agent_id=identity.external_agent_id,
            name=identity.name,
            agent_url=identity.agent_url,
        ),
        revision=PreviewRevision(
            provider_revision_id=revision.provider_revision_id,
            provider_revision_type=revision.provider_revision_type,
            revision_label=revision.revision_label,
            description=revision.description,
            first_message=canonical.first_message,
            canonical_config=canonical.as_dict(),
            source_updated_at=revision.source_updated_at,
        ),
    )


@router.get("", response_model=list[TargetRead])
async def list_targets(session: SessionDep) -> list[TargetRead]:
    service = TargetService(session)
    return [TargetRead.model_validate(t) for t in await service.list_targets()]


@router.get("/{target_id}", response_model=TargetRead)
async def get_target(target_id: str, session: SessionDep) -> TargetRead:
    service = TargetService(session)
    return TargetRead.model_validate(await service.get_target(target_id))


@router.post(
    "/{target_id}/revisions/discover", response_model=RevisionDiscoveryResponse
)
async def discover_revisions(
    target_id: str, session: SessionDep
) -> RevisionDiscoveryResponse:
    service = TargetService(session)
    candidates = await service.discover_revisions(target_id)
    return RevisionDiscoveryResponse(
        agent_target_id=target_id,
        candidates=[
            RevisionDiscoveryCandidate(
                provider_revision_id=summary.provider_revision_id,
                branch_id=summary.branch_id,
                label=summary.label,
                description=summary.description,
                already_imported=already,
            )
            for summary, already in candidates
        ],
    )


@router.post(
    "/{target_id}/revisions", response_model=TargetRevisionRead, status_code=201
)
async def import_revision(
    target_id: str,
    payload: RevisionImportRequest,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> TargetRevisionRead:
    await IdempotencyService(session).reserve(
        idempotency_key,
        "target:revision",
        request_hash=hash_request(
            {"target_id": target_id, **payload.model_dump(mode="json")}
        ),
    )
    service = TargetService(session)
    revision = await service.import_revision(
        target_id,
        payload.provider_revision_id,
        branch_id=payload.branch_id,
    )
    await session.commit()
    return TargetRevisionRead.model_validate(revision)


@router.post("/{target_id}/sync", response_model=TargetRevisionRead)
async def sync_target(
    target_id: str, session: SessionDep
) -> TargetRevisionRead:
    service = TargetService(session)
    revision = await service.sync_target(target_id)
    await session.commit()
    return TargetRevisionRead.model_validate(revision)


@router.get("/{target_id}/revisions", response_model=list[TargetRevisionRead])
async def list_revisions(
    target_id: str, session: SessionDep
) -> list[TargetRevisionRead]:
    service = TargetService(session)
    return [
        TargetRevisionRead.model_validate(r)
        for r in await service.list_revisions(target_id)
    ]


@router.get("/{target_id}/revisions/{revision_id}", response_model=TargetRevisionRead)
async def get_revision(
    target_id: str, revision_id: str, session: SessionDep
) -> TargetRevisionRead:
    service = TargetService(session)
    return TargetRevisionRead.model_validate(await service.get_revision(revision_id))


@router.post(
    "/{target_id}/connection", response_model=TargetRevisionRead, status_code=201
)
async def set_target_connection(
    target_id: str, payload: TargetConnectionUpsert, session: SessionDep
) -> TargetRevisionRead:
    """Client-supplied connection: how to reach the agent (websocket/webrtc/sip)."""
    service = TargetService(session)
    revision = await service.set_connection(
        target_id,
        kind=payload.kind,
        transport=payload.transport,
        config=payload.config,
        secrets=payload.secrets,
        revision_id=payload.revision_id,
    )
    await session.commit()
    return TargetRevisionRead.model_validate(revision)
