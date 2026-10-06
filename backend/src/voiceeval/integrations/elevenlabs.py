"""ElevenLabs provider adapter.

ElevenLabs separates ``agent_id`` / ``version_id`` / ``branch_id`` and supports
retrieving an agent at an exact version or branch, so the adapter maps directly
onto the revision schema with no secondary request.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from voiceeval.core.errors import ConnectionFailedError
from voiceeval.integrations.base import (
    PROVIDER_REVISION_TYPE_CONFIGURATION,
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
from voiceeval.integrations.http import get_json
from voiceeval.db.models.domain import IntegrationAccount

BASE_URL = "https://api.elevenlabs.io/v1"
API_KEY_SECRET = "api_key"

#: ElevenLabs Conversational AI WebRTC is a LiveKit room; the workspace may
#: override this via the non-secret ``livekit_url`` account field.
DEFAULT_LIVEKIT_URL = "wss://livekit.rtc.elevenlabs.io"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def map_identity(agent: dict[str, Any]) -> ProviderAgentIdentity:
    return ProviderAgentIdentity(
        external_agent_id=str(agent["agent_id"]),
        name=str(agent.get("name") or agent["agent_id"]),
        agent_url=None,
    )


def map_revision(agent: dict[str, Any]) -> ProviderRevision:
    conv = agent.get("conversation_config") if isinstance(agent.get("conversation_config"), dict) else {}

    stt_config = conv.get("asr")
    tts_config = conv.get("tts")
    turn_config = conv.get("turn") or conv.get("vad")
    conversation_config = conv.get("conversation")

    procedures = agent.get("procedures")
    workflow_config = {"workflow": agent.get("workflow"), "procedures": procedures}
    tools_config = procedures or None

    canonical = CanonicalAgentRevision(
        first_message=None,
        stt_config=stt_config,
        tts_config=tts_config,
        turn_config=turn_config,
        conversation_config=conversation_config,
        workflow_config=workflow_config,
        tools_config=tools_config,
    )

    return ProviderRevision(
        provider_revision_id=agent.get("version_id"),
        provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
        raw_config=dict(agent),
        canonical_config=canonical,
        branch_id=agent.get("branch_id"),
        revision_label=agent.get("version_id"),
        source_updated_at=_parse_ts(agent.get("updated_at")),
    )


class ElevenLabsAdapter(BaseAgentProviderAdapter):
    provider_slug = "elevenlabs"

    CREDENTIAL_SPEC = (
        CredentialField(key="api_key", label="API Key"),
        CredentialField(
            key="livekit_url",
            label="LiveKit URL",
            secret=False,
            required=False,
        ),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def _headers(self, account: IntegrationAccount, secrets: SecretResolver) -> dict[str, str]:
        api_key = await secrets.resolve(account.id, API_KEY_SECRET)
        return {"xi-api-key": api_key}

    async def retrieve_agent(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent_id: str,
        *,
        version_id: str | None = None,
        branch_id: str | None = None,
    ) -> dict[str, Any]:
        headers = await self._headers(account, secrets)
        params: dict[str, str] = {}
        if version_id:
            params["version_id"] = version_id
        if branch_id:
            params["branch_id"] = branch_id
        return await get_json(
            f"{BASE_URL}/convai/agents/{agent_id}", headers=headers, params=params
        )

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        await secrets.resolve(account.id, API_KEY_SECRET)

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
        summaries: list[ProviderRevisionSummary] = []
        if agent.get("version_id"):
            summaries.append(
                ProviderRevisionSummary(
                    provider_revision_id=agent.get("version_id"),
                    branch_id=agent.get("branch_id"),
                    label=agent.get("version_id"),
                )
            )
        return summaries

    async def get_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> ProviderRevision:
        agent = await self.retrieve_agent(
            account,
            secrets,
            external_agent_id,
            version_id=provider_revision_id,
            branch_id=branch_id,
        )
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
        """ElevenLabs Conversational AI is reached over a per-call LiveKit room.

        WebRTC is the primary transport; the conversation token is minted at
        connect time by ``start_connection`` (``GET /convai/conversation/token``),
        so there is no stable endpoint to persist.
        """
        return [
            ProviderEndpoint(
                transport="room",
                connection_config={"provider": "elevenlabs", "call_setup": "per_call"},
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
        headers = await self._headers(account, secrets)
        params: dict[str, str] = {"agent_id": agent.external_agent_id}
        if revision.provider_revision_id:
            params["version_id"] = revision.provider_revision_id
        if revision.branch_id:
            params["branch_id"] = revision.branch_id
        data = await get_json(
            f"{BASE_URL}/convai/conversation/token",
            headers=headers,
            params=params,
        )
        token = data.get("token")
        if not token:
            raise ConnectionFailedError(
                "elevenlabs did not return a conversation token"
            )
        url = (account.config or {}).get("livekit_url") or DEFAULT_LIVEKIT_URL
        return StartedConnection(
            endpoint_config={
                "url": url,
                "token": token,
                "provider": "elevenlabs",
                "room_mode": "external",
            },
            provider_session_id=revision.provider_revision_id,
        )
