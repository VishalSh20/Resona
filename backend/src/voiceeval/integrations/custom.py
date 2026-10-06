"""Generic/custom WebSocket provider adapter.

A "custom" agent is any agent reachable over a raw WebSocket endpoint the user
supplies (``wss://...``). There is no provider API to introspect: the agent's
identity is simply its name, and the reachable endpoint is the user-supplied
URL carried by the manual target's ``agent_url`` and attached as a
client-supplied websocket link via ``POST /targets/{id}/connection``
(kind=``websocket``, transport=``bridge``).

This adapter exists so a "custom" integration account can be provisioned with
no required credentials and targets can be created against it, mirroring the
``custom`` capability already described by the connector catalog.
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
from voiceeval.db.models.domain import IntegrationAccount

#: Provider name sent in the websocket bridge so the runtime picks the generic
#: JSON decoding path (``provider == "custom"``).
PROTOCOL_CUSTOM = "custom"


class CustomAdapter(BaseAgentProviderAdapter):
    """No-op adapter for user-supplied (generic) WebSocket agents.

    Because there is no provider control plane, ``provision_account`` and
    ``start_connection`` do nothing: the connection is entirely client-supplied.
    The generic JSON websocket protocol is selected by the ``provider=custom``
    endpoint config and decoded by ``JsonProviderProtocolDecoder``.
    """

    provider_slug = "custom"

    def credential_spec(self) -> list[CredentialField]:
        return []

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        # No provider-side requirements; validation happens on the connection
        # endpoint (which requires a ``url`` for the bridge).
        return None

    async def validate_agent_reference(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return ProviderAgentIdentity(external_agent_id=external_agent_id, name=external_agent_id)

    async def get_agent_identity(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return ProviderAgentIdentity(external_agent_id=external_agent_id, name=external_agent_id)

    def _revision(self, provider_revision_id: str | None) -> ProviderRevision:
        return ProviderRevision(
            provider_revision_id=provider_revision_id,
            provider_revision_type=PROVIDER_REVISION_TYPE_DEPLOYMENT,
            raw_config={"provider": PROTOCOL_CUSTOM},
            canonical_config=CanonicalAgentRevision(),
            revision_label=provider_revision_id,
        )

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision:
        return self._revision(None)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        return []

    async def get_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> ProviderRevision:
        return self._revision(provider_revision_id)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """A static websocket bridge from the user-supplied agent URL.

        Custom agents authored through the client-supplied connection path carry
        their own ``url`` in the attached bridge; this fallback covers a custom
        agent whose endpoint only lives on the target (``agent.agent_url``).
        """
        config: dict[str, Any] = {"provider": PROTOCOL_CUSTOM}
        if agent.agent_url:
            config["url"] = agent.agent_url
        return [ProviderEndpoint(transport="bridge", connection_config=config)]


__all__ = ["CustomAdapter", "PROTOCOL_CUSTOM"]