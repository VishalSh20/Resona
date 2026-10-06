"""Provider adapter contract and provider-neutral envelopes.

The application/service layer knows only this module. Provider-specific API
knowledge (HTTP calls and field mapping) lives entirely inside each adapter,
which returns provider-neutral ``ProviderRevision`` / ``ProviderAgentIdentity``
objects. Credentials are resolved through a ``SecretResolver``, never embedded
in the envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from voiceeval.db.models.domain import IntegrationAccount

PROVIDER_REVISION_TYPE_CONFIGURATION = "AGENT_CONFIGURATION"
PROVIDER_REVISION_TYPE_DEPLOYMENT = "DEPLOYMENT"


def normalize_variables_config(value: Any) -> dict[str, Any] | None:
    """Normalize a provider's dynamic-variable payload into a name-keyed dict.

    Providers expose variables in different shapes: a list of names, a list of
    ``{name, ...}`` objects, or an already name-keyed object. The canonical form
    is ``{name: metadata}``, where ``metadata`` is the provider's per-variable
    object or ``{}`` when only the name is known. Returns ``None`` when empty.
    """
    if not value:
        return None
    if isinstance(value, dict):
        return {str(name): meta for name, meta in value.items()}
    if isinstance(value, (list, tuple)):
        normalized: dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if name is not None:
                    normalized[str(name)] = {k: v for k, v in item.items() if k != "name"}
            elif item is not None:
                normalized[str(item)] = {}
        return normalized or None
    return None


class SecretResolver(Protocol):
    """Resolves an encrypted credential for an account by key."""

    async def resolve(self, account_id: str, key: str) -> str: ...


@dataclass(frozen=True)
class CredentialField:
    """One credential/config field a provider account requires.

    ``secret`` fields are stored encrypted in ``integration_secret``; non-secret
    fields are stored in ``integration_account.config``.
    """

    key: str
    label: str
    secret: bool = True
    required: bool = True


@dataclass(frozen=True)
class ProviderAgentIdentity:
    external_agent_id: str
    name: str
    agent_url: str | None = None


@dataclass(frozen=True)
class CanonicalAgentRevision:
    """Provider-normalized semantic agent configuration."""

    first_message: str | None = None
    llm_config: dict[str, Any] | None = None
    stt_config: dict[str, Any] | None = None
    tts_config: dict[str, Any] | None = None
    turn_config: dict[str, Any] | None = None
    conversation_config: dict[str, Any] | None = None
    tools_config: dict[str, Any] | None = None
    variables_config: dict[str, Any] | None = None
    knowledge_config: dict[str, Any] | None = None
    workflow_config: dict[str, Any] | None = None
    handoffs_config: dict[str, Any] | None = None
    guardrails_config: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "first_message": self.first_message,
            "llm_config": self.llm_config,
            "stt_config": self.stt_config,
            "tts_config": self.tts_config,
            "turn_config": self.turn_config,
            "conversation_config": self.conversation_config,
            "tools_config": self.tools_config,
            "variables_config": self.variables_config,
            "knowledge_config": self.knowledge_config,
            "workflow_config": self.workflow_config,
            "handoffs_config": self.handoffs_config,
            "guardrails_config": self.guardrails_config,
        }


@dataclass(frozen=True)
class ProviderRevision:
    """Provider-neutral revision snapshot.

    ``raw_config`` preserves the provider response verbatim (becomes
    ``source_config``); ``canonical_config`` is the normalized representation
    consumed by the rest of the platform.
    """

    provider_revision_id: str | None
    provider_revision_type: str
    raw_config: dict[str, Any]
    canonical_config: CanonicalAgentRevision
    branch_id: str | None = None
    revision_label: str | None = None
    description: str | None = None
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRevisionSummary:
    provider_revision_id: str | None
    branch_id: str | None = None
    label: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ProviderEndpoint:
    transport: str
    connection_config: dict[str, Any]


@dataclass(frozen=True)
class StartedConnection:
    """The result of a per-call connection setup.

    Some providers do not expose a stable endpoint on the agent/revision; the
    URL is minted per call by an authenticated provider API request (Vapi
    ``POST /call`` → ``websocketCallUrl``, ElevenLabs ``get-signed-url`` →
    ``signed_url``). ``endpoint_config`` is merged over the frozen config before
    the TargetLink is built; ``provider_session_id`` is the provider's handle for
    the call and ``ephemeral`` carries short-lived values that must not be frozen.
    """

    endpoint_config: dict[str, Any]
    provider_session_id: str | None = None
    ephemeral: dict[str, Any] = field(default_factory=dict)


#: Canonical TargetLink transports (see caller-migration-to-livekit.md §4.2).
TARGET_LINK_ROOM = "room"
TARGET_LINK_SIP = "sip"
TARGET_LINK_BRIDGE = "bridge"
TARGET_LINK_WHIP = "whip"

#: Provider transport vocabulary → TargetLink transport.
_PROVIDER_TO_TARGET_LINK: dict[str, str] = {
    "webrtc": TARGET_LINK_ROOM,  # a LiveKit/WebRTC participant
    "room": TARGET_LINK_ROOM,
    "websocket": TARGET_LINK_BRIDGE,
    "ws": TARGET_LINK_BRIDGE,
    "bridge": TARGET_LINK_BRIDGE,
    "whip": TARGET_LINK_WHIP,
    "sip": TARGET_LINK_SIP,
    "pstn": TARGET_LINK_SIP,
}

#: Client-facing connection kinds → canonical TargetLink transport. A client can
#: say *how* to reach an agent: a websocket, webrtc (``transport`` picks
#: ``room``/``whip``), or a SIP trunk (outbound via their credentials).
CLIENT_CONNECTION_KINDS: dict[str, str] = {
    "websocket": TARGET_LINK_BRIDGE,
    "webrtc": TARGET_LINK_ROOM,
    "sip": TARGET_LINK_SIP,
}


def provider_endpoint_to_target_link(endpoint: ProviderEndpoint) -> dict[str, Any]:
    """Convert a provider endpoint into the manifest's ``target_link`` shape."""
    transport = _PROVIDER_TO_TARGET_LINK.get(endpoint.transport, endpoint.transport)
    return {
        "transport": transport,
        "endpoint_config": dict(endpoint.connection_config or {}),
    }


def target_link_transport(transport: str) -> str:
    """Normalize a transport slug to a TargetLink transport."""
    return _PROVIDER_TO_TARGET_LINK.get(transport, transport)


class AgentProviderAdapter(Protocol):
    provider_slug: str

    def credential_spec(self) -> list[CredentialField]: ...

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None: ...

    async def provision_account(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> dict[str, Any]: ...

    async def validate_agent_reference(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity: ...

    async def get_agent_identity(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity: ...

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision: ...

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]: ...

    async def get_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> ProviderRevision: ...

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision: ...

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]: ...

    async def start_connection(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
        *,
        transport: str,
        sample_rate: int,
    ) -> StartedConnection | None: ...


class BaseAgentProviderAdapter:
    """Default adapter behaviour: static endpoints, no per-call setup.

    Adapters whose endpoint is fixed (or supplied by config) inherit this and
    return ``None`` from :meth:`start_connection`, which tells the runtime seam
    to connect with the frozen ``endpoint_config`` unchanged.
    """

    provider_slug: str = ""

    async def provision_account(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> dict[str, Any]:
        """Create provider-side resources an account needs at setup time.

        Returns extra **non-secret** config to merge into
        ``IntegrationAccount.config`` (e.g. a provisioned trunk id). Default
        does nothing.
        """
        return {}

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
        return None
