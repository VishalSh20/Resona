"""LiveKit Cloud provider adapter.

LiveKit does not expose the agent's semantic prompt/LLM/STT/TTS configuration
through a provider API; its agent identity is the dispatch name, and deployment
versions are runtime/deployment revisions. This adapter therefore produces
``provider_revision_type = DEPLOYMENT`` and does not fabricate semantic config.
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import get_settings
from voiceeval.core.errors import ConnectionFailedError, DependencyUnavailableError
from voiceeval.core.ids import new_plain_ulid
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
    StartedConnection,
)
from voiceeval.db.models.domain import IntegrationAccount

API_KEY_SECRET = "api_key"
API_SECRET_SECRET = "api_secret"


class LiveKitAdapter(BaseAgentProviderAdapter):
    provider_slug = "livekit"

    CREDENTIAL_SPEC = (
        CredentialField(key="api_key", label="API Key"),
        CredentialField(key="api_secret", label="API Secret"),
        CredentialField(key="url", label="LiveKit URL", secret=False),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def _require_credentials(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        await secrets.resolve(account.id, API_KEY_SECRET)
        await secrets.resolve(account.id, API_SECRET_SECRET)

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        await self._require_credentials(account, secrets)
        url = (account.config or {}).get("url")
        if not url:
            raise ConnectionFailedError(
                "livekit account is missing its project url in config"
            )
        if not isinstance(url, str) or not url.startswith(("ws://", "wss://", "http://", "https://")):
            raise ConnectionFailedError(
                "livekit account url must be a valid LiveKit URL (e.g. wss://...livekit.cloud)"
            )

    async def validate_agent_reference(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return self._identity(account, external_agent_id)

    async def get_agent_identity(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return self._identity(account, external_agent_id)

    @staticmethod
    def _identity(account: IntegrationAccount, external_agent_id: str) -> ProviderAgentIdentity:
        return ProviderAgentIdentity(
            external_agent_id=external_agent_id,
            name=external_agent_id,
            agent_url=None,
        )

    def _deployment_revision(
        self, account: IntegrationAccount, external_agent_id: str, deployment_id: str | None
    ) -> ProviderRevision:
        raw: dict[str, Any] = {
            "agent_name": external_agent_id,
            "account_config": account.config or {},
        }
        if deployment_id:
            raw["deployment_id"] = deployment_id
        return ProviderRevision(
            provider_revision_id=deployment_id,
            provider_revision_type=PROVIDER_REVISION_TYPE_DEPLOYMENT,
            raw_config=raw,
            canonical_config=CanonicalAgentRevision(),
            revision_label=deployment_id,
        )

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision:
        return self._deployment_revision(account, external_agent_id, None)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        # LiveKit Cloud deployment-version listing requires a control-plane call
        # not yet wired; no semantic configuration is available either way.
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
        return self._deployment_revision(account, external_agent_id, provider_revision_id)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """A LiveKit agent is reached as a per-call room participant (§4.2).

        The LiveKit dispatcher creates the room and issues the dispatch; the
        caller worker joins that room via ``ctx.job.room``. No per-call room
        minting happens inside ``start_connection``.
        """
        return [
            ProviderEndpoint(
                transport="room",
                connection_config={"provider": "livekit"},
            )
        ]

    async def start_connection(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
        *,
        transport: str,
        sample_rate: int,
    ) -> StartedConnection | None:
        if transport != "room":
            return None
        config = account.config or {}
        url = config.get("url")
        if not url:
            raise ConnectionFailedError(
                "livekit account is missing its project url"
            )
        api_key = await secrets.resolve(account.id, API_KEY_SECRET)
        api_secret = await secrets.resolve(account.id, API_SECRET_SECRET)
        api = _import_api()
        settings = get_settings()

        room_name = f"resona-{new_plain_ulid()}"
        try:
            async with api.LiveKitAPI(
                url=url, api_key=api_key, api_secret=api_secret
            ) as client:
                await client.room.create_room(
                    api.CreateRoomRequest(
                        name=room_name,
                        empty_timeout=settings.livekit_target_room_empty_timeout_s,
                        max_participants=4,
                    )
                )
                await client.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(
                        agent_name=agent.external_agent_id,
                        room=room_name,
                    )
                )
        except Exception as exc:
            raise ConnectionFailedError(
                f"failed to prepare livekit target room: {exc}"
            ) from exc

        token = (
            api.AccessToken(api_key, api_secret)
            .with_identity("resona-caller")
            .with_grants(api.VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )
        return StartedConnection(
            endpoint_config={
                "url": url,
                "token": token,
                "provider": "livekit",
                "room_mode": "external",
            },
            provider_session_id=room_name,
        )


def _import_api() -> Any:
    try:
        from livekit import api  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        raise DependencyUnavailableError(
            "livekit-api is not installed; the 'livekit' target is unavailable"
        ) from exc
    return api
