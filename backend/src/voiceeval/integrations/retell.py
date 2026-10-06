"""Retell provider adapter.

Retell is a two-level import: retrieve the agent, then retrieve the response
engine it points to (``retell-llm`` or ``conversation-flow``). The agent
response alone may not carry the prompt/tools/workflow.
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
    normalize_variables_config,
)
from voiceeval.integrations.http import get_json, post_json
from voiceeval.db.models.domain import IntegrationAccount

BASE_URL = "https://api.retellai.com"
API_KEY_SECRET = "api_key"


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
        name=str(agent.get("agent_name") or agent["agent_id"]),
        agent_url=None,
    )


def _pick(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None


def map_revision(
    agent: dict[str, Any], response_engine: dict[str, Any] | None
) -> ProviderRevision:
    engine = response_engine or {}

    first_message = _pick(engine, "begin_message", "first_message")

    llm_config: dict[str, Any] = {}
    for key in ("model", "model_temperature"):
        if key in engine and engine[key] is not None:
            llm_config[key] = engine[key]

    tts_config: dict[str, Any] = {}
    for key in ("voice_id", "voice_model", "voice_speed", "voice_temperature"):
        if key in engine and engine[key] is not None:
            tts_config[key] = engine[key]

    stt_config: dict[str, Any] = {}
    if isinstance(engine.get("stt"), dict):
        stt_config = engine["stt"]
    elif "stt_config" in engine:
        stt_config = engine["stt_config"]

    turn_config: dict[str, Any] = {}
    for key in ("responsiveness", "interruption_sensitivity"):
        if key in engine and engine[key] is not None:
            turn_config[key] = engine[key]

    conversation_config: dict[str, Any] = {}
    for key in ("conversation_settings",):
        if key in engine and engine[key] is not None:
            conversation_config[key] = engine[key]

    tools_config = engine.get("tools") or []
    knowledge_config = {"knowledge_base_ids": engine.get("knowledge_base_ids") or []}
    workflow_config = {
        "states": engine.get("states") or engine.get("nodes"),
        "transitions": engine.get("transitions"),
    }
    variables_config = normalize_variables_config(engine.get("dynamic_variables"))

    canonical = CanonicalAgentRevision(
        first_message=first_message,
        llm_config=llm_config or None,
        stt_config=stt_config or None,
        tts_config=tts_config or None,
        turn_config=turn_config or None,
        conversation_config=conversation_config or None,
        tools_config=tools_config or None,
        variables_config=variables_config or None,
        knowledge_config=knowledge_config or None,
        workflow_config=workflow_config or None,
    )

    raw = {"agent": agent, "response_engine": engine}

    return ProviderRevision(
        provider_revision_id=str(agent.get("version")) if agent.get("version") else None,
        provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
        raw_config=raw,
        canonical_config=canonical,
        revision_label=str(agent.get("version")) if agent.get("version") else None,
        description=_pick(agent, "version_description"),
        source_updated_at=_parse_ts(agent.get("updated_at")),
    )


class RetellAdapter(BaseAgentProviderAdapter):
    provider_slug = "retell"

    CREDENTIAL_SPEC = (
        CredentialField(key="api_key", label="API Key"),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def _headers(self, account: IntegrationAccount, secrets: SecretResolver) -> dict[str, str]:
        api_key = await secrets.resolve(account.id, API_KEY_SECRET)
        return {"Authorization": f"Bearer {api_key}"}

    async def retrieve_agent(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent_id: str,
        *,
        version: str | None = None,
    ) -> dict[str, Any]:
        headers = await self._headers(account, secrets)
        params = {"version": version} if version else None
        return await get_json(
            f"{BASE_URL}/get-agent/{agent_id}", headers=headers, params=params
        )

    async def retrieve_response_engine(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        response_engine: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not response_engine:
            return None
        headers = await self._headers(account, secrets)
        kind = response_engine.get("type")
        if kind == "retell-llm":
            llm_id = response_engine.get("llm_id")
            return await get_json(f"{BASE_URL}/get-retell-llm/{llm_id}", headers=headers)
        if kind == "conversation-flow":
            flow_id = response_engine.get("flow_id")
            return await get_json(
                f"{BASE_URL}/get-conversation-flow/{flow_id}", headers=headers
            )
        return None

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        # A secret resolution failure is the authoritative "connection invalid".
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
        engine = await self.retrieve_response_engine(
            account, secrets, agent.get("response_engine")
        )
        return map_revision(agent, engine)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        # Retell exposes an agent-version listing endpoint; version identifiers
        # surface through ``agent.version`` on the per-version retrieval.
        headers = await self._headers(account, secrets)
        data = await get_json(
            f"{BASE_URL}/list-agent-versions",
            headers=headers,
            params={"agent_id": external_agent_id},
        )
        summaries: list[ProviderRevisionSummary] = []
        for item in data.get("versions", []):
            summaries.append(
                ProviderRevisionSummary(
                    provider_revision_id=str(item.get("version")) if item.get("version") else None,
                    label=str(item.get("version")) if item.get("version") else None,
                    description=item.get("description"),
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
            account, secrets, external_agent_id, version=provider_revision_id
        )
        engine = await self.retrieve_response_engine(
            account, secrets, agent.get("response_engine")
        )
        return map_revision(agent, engine)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """A Retell agent is reached over a per-call web call (WHIP).

        ``POST /v3/create-web-call`` mints the browser token and call id at
        connect time (see ``start_connection``); the gateway uses WHIP signaling
        (SDP offer + ICE trickle), which is the ``whip`` target link.
        """
        return [
            ProviderEndpoint(
                transport="whip",
                connection_config={"provider": "retell", "call_setup": "per_call"},
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
        if transport != "whip":
            return None
        headers = await self._headers(account, secrets)
        payload: dict[str, Any] = {"agent_id": agent.external_agent_id}
        version = revision.provider_revision_id
        if version:
            payload["agent_version"] = version
        data = await post_json(
            f"{BASE_URL}/v3/create-web-call", headers=headers, json=payload
        )
        call_id = data.get("call_id")
        access_token = data.get("access_token")
        if not call_id or not access_token:
            raise ConnectionFailedError(
                "retell did not return a call_id and access_token for the web call"
            )
        return StartedConnection(
            endpoint_config={
                "provider": "retell",
                "call_id": call_id,
                "access_token": access_token,
                "ice_servers": data.get("ice_servers") or [],
                "identity": "client",
                "base_url": BASE_URL,
            },
            provider_session_id=call_id,
        )
