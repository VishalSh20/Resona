"""Pipecat Cloud provider adapter.

Pipecat Cloud has a control-plane API describing deployments, but deployment
metadata is not the application's semantic prompt/LLM/TTS configuration. The
adapter imports what is exposed and does not fabricate the rest.
"""

from __future__ import annotations

from typing import Any

from voiceeval.integrations.base import (
    PROVIDER_REVISION_TYPE_DEPLOYMENT,
    BaseAgentProviderAdapter,
    CanonicalAgentRevision,
    CredentialField,
    ProviderAgentIdentity,
    ProviderEndpoint,
    ProviderRevision,
    ProviderRevisionSummary,
    SecretResolver,
)
from voiceeval.integrations.http import get_json
from voiceeval.db.models.domain import IntegrationAccount

BASE_URL = "https://api.pipecat.daily.co/v1"
API_TOKEN_SECRET = "api_token"


def map_identity(agent: dict[str, Any]) -> ProviderAgentIdentity:
    return ProviderAgentIdentity(
        external_agent_id=str(agent.get("name") or agent.get("agentName")),
        name=str(agent.get("name") or agent.get("agentName")),
        agent_url=agent.get("endpoint"),
    )


def map_revision(agent: dict[str, Any]) -> ProviderRevision:
    deployment_id = agent.get("activeDeploymentId") or agent.get("deploymentId")
    raw: dict[str, Any] = dict(agent)
    return ProviderRevision(
        provider_revision_id=deployment_id,
        provider_revision_type=PROVIDER_REVISION_TYPE_DEPLOYMENT,
        raw_config=raw,
        canonical_config=CanonicalAgentRevision(),
        revision_label=deployment_id,
    )


class PipecatAdapter(BaseAgentProviderAdapter):
    provider_slug = "pipecat"

    CREDENTIAL_SPEC = (
        CredentialField(key="api_token", label="API Token"),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def _headers(self, account: IntegrationAccount, secrets: SecretResolver) -> dict[str, str]:
        token = await secrets.resolve(account.id, API_TOKEN_SECRET)
        return {"Authorization": f"Bearer {token}"}

    async def retrieve_agent(
        self, account: IntegrationAccount, secrets: SecretResolver, agent_name: str
    ) -> dict[str, Any]:
        headers = await self._headers(account, secrets)
        return await get_json(f"{BASE_URL}/agents/{agent_name}", headers=headers)

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        await secrets.resolve(account.id, API_TOKEN_SECRET)

    async def validate_agent_reference(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return await self.get_agent_identity(account, secrets, external_agent_id)

    async def get_agent_identity(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        agent = await self.retrieve_agent(account, secrets, external_agent_id)
        return map_identity(agent)

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision:
        agent = await self.retrieve_agent(account, secrets, external_agent_id)
        return map_revision(agent)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        agent = await self.retrieve_agent(account, secrets, external_agent_id)
        deployment_id = agent.get("activeDeploymentId") or agent.get("deploymentId")
        if not deployment_id:
            return []
        return [
            ProviderRevisionSummary(
                provider_revision_id=deployment_id,
                label=deployment_id,
            )
        ]

    async def get_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> ProviderRevision:
        agent = await self.retrieve_agent(account, secrets, external_agent_id)
        return map_revision(agent)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """Pipecat exposes a signaling endpoint → protocol bridge (§4.2)."""
        url = agent.agent_url or (revision.raw_config or {}).get("endpoint")
        if not url:
            return []
        return [
            ProviderEndpoint(
                transport="bridge",
                connection_config={"url": url, "provider": "pipecat"},
            )
        ]
