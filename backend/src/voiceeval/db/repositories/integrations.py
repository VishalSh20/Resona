"""Integration provider/account/secret persistence.

Providers and accounts are the "where/how we authenticate" layer that an
``AgentTarget`` is attached to. Secrets are encrypted at rest (see
``voiceeval.services.secrets``); this repository stores and retrieves the
encrypted values by ``(account, key)``.
"""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository


class IntegrationRepository(Repository):
    async def get_provider(self, provider_id: str) -> domain.IntegrationProvider:
        return await self._get(
            domain.IntegrationProvider, provider_id, name="integration provider"
        )

    async def get_provider_by_slug(self, slug: str) -> domain.IntegrationProvider:
        result = await self._session.execute(
            select(domain.IntegrationProvider).where(
                domain.IntegrationProvider.slug == slug
            )
        )
        provider = result.scalar_one_or_none()
        if provider is None:
            raise ResourceNotFoundError(f"integration provider '{slug}' not found")
        return provider

    async def list_providers(self) -> list[domain.IntegrationProvider]:
        result = await self._session.execute(
            select(domain.IntegrationProvider).order_by(
                domain.IntegrationProvider.slug
            )
        )
        return list(result.scalars().all())

    async def create_account(
        self,
        provider_id: str,
        name: str,
        *,
        config: dict | None = None,
        status: str = "active",
    ) -> domain.IntegrationAccount:
        account = domain.IntegrationAccount(
            id=new_id(EntityKind.INTEGRATION_ACCOUNT),
            provider_id=provider_id,
            name=name,
            config=config or {},
            status=status,
        )
        self._session.add(account)
        await self._session.flush()
        return account

    async def list_accounts(self) -> list[domain.IntegrationAccount]:
        result = await self._session.execute(select(domain.IntegrationAccount))
        return list(result.scalars().all())

    async def get_account(self, account_id: str) -> domain.IntegrationAccount:
        return await self._get(
            domain.IntegrationAccount, account_id, name="integration account"
        )

    async def get_transport_type(self, transport_type_id: str) -> domain.TransportType:
        return await self._get(
            domain.TransportType, transport_type_id, name="transport type"
        )

    async def get_transport_type_by_slug(self, slug: str) -> domain.TransportType | None:
        result = await self._session.execute(
            select(domain.TransportType).where(domain.TransportType.slug == slug)
        )
        return result.scalar_one_or_none()

    async def ensure_transport_type(
        self, slug: str, display_name: str, category: str
    ) -> domain.TransportType:
        existing = await self.get_transport_type_by_slug(slug)
        if existing is not None:
            return existing
        transport_type = domain.TransportType(
            id=new_id(EntityKind.TRANSPORT_TYPE),
            slug=slug,
            display_name=display_name,
            category=category,
            capabilities=None,
        )
        self._session.add(transport_type)
        await self._session.flush()
        return transport_type

    async def upsert_endpoint(
        self,
        *,
        agent_target_revision_id: str,
        transport_type_id: str,
        connection_config: dict,
    ) -> domain.AgentEndpoint:
        result = await self._session.execute(
            select(domain.AgentEndpoint).where(
                domain.AgentEndpoint.agent_target_revision_id
                == agent_target_revision_id,
                domain.AgentEndpoint.transport_type_id == transport_type_id,
            )
        )
        endpoint = result.scalar_one_or_none()
        if endpoint is None:
            endpoint = domain.AgentEndpoint(
                id=new_id(EntityKind.AGENT_ENDPOINT),
                agent_target_revision_id=agent_target_revision_id,
                transport_type_id=transport_type_id,
                connection_config=connection_config,
            )
            self._session.add(endpoint)
        else:
            endpoint.connection_config = connection_config
        await self._session.flush()
        return endpoint

    async def list_endpoints_for_revision(
        self, agent_target_revision_id: str
    ) -> list[domain.AgentEndpoint]:
        result = await self._session.execute(
            select(domain.AgentEndpoint).where(
                domain.AgentEndpoint.agent_target_revision_id
                == agent_target_revision_id
            )
        )
        return list(result.scalars().all())

    async def get_secret(self, account_id: str, key: str) -> domain.IntegrationSecret:
        result = await self._session.execute(
            select(domain.IntegrationSecret).where(
                domain.IntegrationSecret.integration_account_id == account_id,
                domain.IntegrationSecret.key == key,
            )
        )
        secret = result.scalar_one_or_none()
        if secret is None:
            raise ResourceNotFoundError(
                f"secret '{key}' not found for integration account '{account_id}'"
            )
        return secret

    async def store_secret(
        self, account_id: str, key: str, encrypted_value: str
    ) -> domain.IntegrationSecret:
        result = await self._session.execute(
            select(domain.IntegrationSecret).where(
                domain.IntegrationSecret.integration_account_id == account_id,
                domain.IntegrationSecret.key == key,
            )
        )
        secret = result.scalar_one_or_none()
        if secret is None:
            secret = domain.IntegrationSecret(
                id=new_id(EntityKind.INTEGRATION_SECRET),
                integration_account_id=account_id,
                key=key,
                encrypted_value=encrypted_value,
            )
            self._session.add(secret)
        else:
            secret.encrypted_value = encrypted_value
        await self._session.flush()
        return secret

    async def create_connection_session(
        self,
        *,
        endpoint_id: str,
        revision_id: str,
        status: str = "connecting",
        provider_session_id: str | None = None,
        runtime_config: dict | None = None,
        ephemeral_data: dict | None = None,
    ) -> domain.ConnectionSession:
        """Record one runtime connection to an endpoint/revision."""
        now = utc_now()
        connection = domain.ConnectionSession(
            id=new_id(EntityKind.CONNECTION_SESSION),
            endpoint_id=endpoint_id,
            revision_id=revision_id,
            status=status,
            provider_session_id=provider_session_id,
            runtime_config=runtime_config or {},
            ephemeral_data=ephemeral_data or {},
            started_at=now,
            connected_at=now if status == "connected" else None,
        )
        self._session.add(connection)
        await self._session.flush()
        return connection

    async def update_connection_session(
        self,
        connection_id: str,
        *,
        status: str,
        provider_session_id: str | None = None,
        error_message: str | None = None,
    ) -> domain.ConnectionSession:
        connection = await self._get(
            domain.ConnectionSession, connection_id, name="connection session"
        )
        connection.status = status
        if provider_session_id is not None:
            connection.provider_session_id = provider_session_id
        if error_message is not None:
            connection.error_message = error_message
        if status == "connected":
            connection.connected_at = utc_now()
        if status in {"terminated", "failed"}:
            connection.ended_at = utc_now()
        await self._session.flush()
        return connection
