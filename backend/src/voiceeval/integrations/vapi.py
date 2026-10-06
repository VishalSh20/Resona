"""Vapi provider adapter.

Assistant configuration is largely available from the assistant resource
itself. ``transportConfigurations`` is preserved in ``source_config`` only; the
transport/endpoint layer is handled separately.
"""

from __future__ import annotations

import re
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

BASE_URL = "https://api.vapi.ai"
API_KEY_SECRET = "api_key"

_VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_variables(*texts: str | None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _VARIABLE_RE.findall(text):
            if match not in seen:
                seen.add(match)
                names.append(match)
    return names


def _messages_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def _system_message(messages: Any) -> str | None:
    if not isinstance(messages, list):
        return None
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            content = message.get("content")
            if isinstance(content, str):
                return content
    return None


def map_identity(assistant: dict[str, Any]) -> ProviderAgentIdentity:
    return ProviderAgentIdentity(
        external_agent_id=str(assistant["id"]),
        name=str(assistant.get("name") or assistant["id"]),
        agent_url=None,
    )


def map_revision(assistant: dict[str, Any]) -> ProviderRevision:
    model = assistant.get("model") if isinstance(assistant.get("model"), dict) else {}
    messages = model.get("messages")
    llm_config = {k: v for k, v in model.items() if k != "tools"} or None
    tools_config = model.get("tools") or None

    system_message = _system_message(messages)

    conversation_fields = (
        "endCallPhrases",
        "endCall",
        "voicemail",
        "maxDurationSeconds",
        "maxDuration",
        "backgroundSound",
        "silenceTimeoutSeconds",
        "startSpeakingPlan",
        "stopSpeakingPlan",
    )
    conversation_config = {
        key: assistant[key]
        for key in conversation_fields
        if assistant.get(key) is not None
    } or None

    variables_config = normalize_variables_config(
        _extract_variables(
            assistant.get("firstMessage"),
            _messages_text(messages),
        )
    )

    canonical = CanonicalAgentRevision(
        first_message=assistant.get("firstMessage"),
        llm_config=llm_config,
        stt_config=assistant.get("transcriber"),
        tts_config=assistant.get("voice"),
        conversation_config=conversation_config,
        tools_config=tools_config,
        variables_config=variables_config,
    )

    return ProviderRevision(
        provider_revision_id=assistant.get("latestVersion"),
        provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
        raw_config=dict(assistant),
        canonical_config=canonical,
        revision_label=assistant.get("latestVersion"),
        description=system_message,
        source_updated_at=_parse_ts(assistant.get("updatedAt")),
    )


class VapiAdapter(BaseAgentProviderAdapter):
    provider_slug = "vapi"

    CREDENTIAL_SPEC = (
        CredentialField(key="api_key", label="API Key"),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def _headers(self, account: IntegrationAccount, secrets: SecretResolver) -> dict[str, str]:
        api_key = await secrets.resolve(account.id, API_KEY_SECRET)
        return {"Authorization": f"Bearer {api_key}"}

    async def retrieve_assistant(
        self, account: IntegrationAccount, secrets: SecretResolver, assistant_id: str
    ) -> dict[str, Any]:
        headers = await self._headers(account, secrets)
        return await get_json(f"{BASE_URL}/assistant/{assistant_id}", headers=headers)

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
        assistant = await self.retrieve_assistant(account, secrets, external_agent_id)
        return map_identity(assistant)

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision:
        assistant = await self.retrieve_assistant(account, secrets, external_agent_id)
        return map_revision(assistant)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        assistant = await self.retrieve_assistant(account, secrets, external_agent_id)
        version = assistant.get("latestVersion")
        if not version:
            return []
        return [
            ProviderRevisionSummary(
                provider_revision_id=version,
                label=version,
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
        # Vapi does not expose arbitrary historical versions through the base
        # assistant resource; the current assistant object is returned and the
        # caller must preserve the selected provider version for runtime.
        assistant = await self.retrieve_assistant(account, secrets, external_agent_id)
        return map_revision(assistant)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """A Vapi assistant is reached over a per-call websocket (§4.2).

        The URL is minted at connect time by ``start_connection`` (``POST /call``
        returns ``transport.websocketCallUrl``); there is no stable endpoint to
        persist.
        """
        return [
            ProviderEndpoint(
                transport="bridge",
                connection_config={"provider": "vapi", "call_setup": "per_call"},
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
        if transport != "bridge":
            return None
        headers = await self._headers(account, secrets)
        payload: dict[str, Any] = {
            "assistantId": agent.external_agent_id,
            "transport": {
                "provider": "vapi.websocket",
                "audioFormat": {
                    "format": "pcm_s16le",
                    "container": "raw",
                    "sampleRate": sample_rate,
                },
            },
        }
        version = revision.provider_revision_id or revision.revision_label
        if version:
            payload["assistantVersion"] = version
        data = await post_json(f"{BASE_URL}/call", headers=headers, json=payload)
        url = (data.get("transport") or {}).get("websocketCallUrl")
        if not url:
            raise ConnectionFailedError(
                "vapi did not return a transport.websocketCallUrl for the call"
            )
        return StartedConnection(
            endpoint_config={
                "url": url,
                "provider": "vapi",
                "sample_rate": sample_rate,
            },
            provider_session_id=data.get("id"),
        )
