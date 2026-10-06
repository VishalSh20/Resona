"""Integration provider + account operations.

Captures a provider account (non-secret config + encrypted secrets) so an
``AgentTarget`` can be created against it. The credential requirements come from
the provider adapter's ``credential_spec()``, so the flow stays provider-agnostic.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ValidationError
from voiceeval.db.models import domain
from voiceeval.db.repositories import IntegrationRepository
from voiceeval.integrations.base import CredentialField, SecretResolver
from voiceeval.integrations.registry import get_adapter
from voiceeval.services.secrets import SecretService


class IntegrationService:
    def __init__(
        self, session: AsyncSession, *, secrets: SecretResolver | None = None
    ) -> None:
        self._session = session
        self._integrations = IntegrationRepository(session)
        self._secrets: SecretResolver = secrets or SecretService(session)

    async def list_providers(
        self,
    ) -> list[tuple[domain.IntegrationProvider, list[CredentialField]]]:
        providers = await self._integrations.list_providers()
        result: list[tuple[domain.IntegrationProvider, list[CredentialField]]] = []
        for provider in providers:
            adapter = get_adapter(provider.slug)
            result.append((provider, adapter.credential_spec()))
        return result

    async def create_account(
        self,
        *,
        provider_id: str,
        name: str,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
    ) -> domain.IntegrationAccount:
        config = config or {}
        secrets = secrets or {}
        provider = await self._integrations.get_provider(provider_id)
        adapter = get_adapter(provider.slug)

        for field in adapter.credential_spec():
            if field.secret:
                if field.required and field.key not in secrets:
                    raise ValidationError(
                        f"missing required secret '{field.key}' for provider "
                        f"'{provider.slug}'"
                    )
            elif field.required and field.key not in config:
                raise ValidationError(
                    f"missing required config '{field.key}' for provider "
                    f"'{provider.slug}'"
                )

        account = await self._integrations.create_account(
            provider_id, name, config=config
        )
        for key, value in secrets.items():
            await self._secrets.store(account.id, key, value)

        # Create any provider-side resources and fold the non-secret result into
        # the account config (e.g. a provisioned LiveKit outbound trunk id).
        extra = await adapter.provision_account(account, self._secrets)
        if extra:
            account.config = {**(account.config or {}), **extra}
            await self._session.flush()
        return account

    async def list_accounts(self) -> list[domain.IntegrationAccount]:
        return await self._integrations.list_accounts()
