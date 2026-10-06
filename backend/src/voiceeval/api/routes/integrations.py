"""Integration provider + account configuration API."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import SessionDep, require_user_dep
from voiceeval.schemas.integrations import (
    CredentialFieldRead,
    IntegrationAccountCreate,
    IntegrationAccountRead,
    IntegrationProviderRead,
)
from voiceeval.services.connectors import build_catalog
from voiceeval.services.integrations import IntegrationService

router = APIRouter(
    prefix="/integrations", tags=["integrations"], dependencies=[require_user_dep]
)


@router.get("/connectors")
async def list_connectors() -> dict:
    """Connector catalog: which connection kinds each provider supports + specs."""
    return build_catalog()


@router.get("/providers", response_model=list[IntegrationProviderRead])
async def list_providers(session: SessionDep) -> list[IntegrationProviderRead]:
    service = IntegrationService(session)
    providers = await service.list_providers()
    return [
        IntegrationProviderRead(
            id=provider.id,
            slug=provider.slug,
            display_name=provider.display_name,
            credentials=[
                CredentialFieldRead(
                    key=field.key,
                    label=field.label,
                    secret=field.secret,
                    required=field.required,
                )
                for field in spec
            ],
        )
        for provider, spec in providers
    ]


@router.post("/accounts", response_model=IntegrationAccountRead, status_code=201)
async def create_account(
    payload: IntegrationAccountCreate, session: SessionDep
) -> IntegrationAccountRead:
    service = IntegrationService(session)
    account = await service.create_account(
        provider_id=payload.provider_id,
        name=payload.name,
        config=payload.config,
        secrets=payload.secrets,
    )
    await session.commit()
    return IntegrationAccountRead.model_validate(account)


@router.get("/accounts", response_model=list[IntegrationAccountRead])
async def list_accounts(session: SessionDep) -> list[IntegrationAccountRead]:
    service = IntegrationService(session)
    return [
        IntegrationAccountRead.model_validate(account)
        for account in await service.list_accounts()
    ]
