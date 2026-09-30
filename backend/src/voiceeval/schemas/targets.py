"""Agent target request/response contracts (V1).

``AgentTarget`` is the stable provider-side agent identity (``external_agent_id``,
``name``, optional ``agent_url``). ``AgentTargetRevision`` holds only
version/revision-specific configuration. Provider revision import is driven
entirely by ``provider_revision_id`` (+ optional ``branch_id``); the adapter is
the source of truth for the normalized configuration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourceKind = Literal["IMPORTED", "MANUAL"]
ProviderRevisionType = Literal["AGENT_CONFIGURATION", "DEPLOYMENT"]


class TargetCreate(BaseModel):
    """Create a target and its initial revision.

    Provider-backed: supply ``external_agent_id``; the adapter retrieves and
    normalizes the current revision. Manual/custom: omit ``external_agent_id``
    and supply the known configuration directly (``source_kind`` = MANUAL).
    """

    name: str | None = None
    provider_id: str
    integration_account_id: str
    external_agent_id: str | None = None
    agent_url: str | None = None
    description: str | None = None
    first_message: str | None = None
    llm_config: dict[str, Any] = Field(default_factory=dict)
    stt_config: dict[str, Any] = Field(default_factory=dict)
    tts_config: dict[str, Any] = Field(default_factory=dict)
    turn_config: dict[str, Any] = Field(default_factory=dict)
    conversation_config: dict[str, Any] = Field(default_factory=dict)
    tools_config: dict[str, Any] = Field(default_factory=dict)
    variables_config: dict[str, Any] = Field(default_factory=dict)
    knowledge_config: dict[str, Any] = Field(default_factory=dict)
    workflow_config: dict[str, Any] = Field(default_factory=dict)
    handoffs_config: dict[str, Any] = Field(default_factory=dict)
    guardrails_config: dict[str, Any] = Field(default_factory=dict)


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_id: str
    integration_account_id: str
    external_agent_id: str | None = None
    name: str
    agent_url: str | None = None


class TargetRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_target_id: str
    revision_no: int
    provider_revision_id: str | None = None
    provider_revision_type: ProviderRevisionType | None = None
    revision_label: str | None = None
    source_branch_id: str | None = None
    description: str | None = None
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
    canonical_config: dict[str, Any]
    source_config: dict[str, Any]
    source_updated_at: datetime | None = None
    config_hash: str
    source_kind: str
    created_at: datetime | None = None


class TargetCreatedRead(BaseModel):
    """Result of creating a target: the asset plus its initial revision."""

    target: TargetRead
    revision: TargetRevisionRead


class RevisionImportRequest(BaseModel):
    """Select a provider revision to import (the adapter fetches + normalizes)."""

    provider_revision_id: str
    branch_id: str | None = None


class RevisionDiscoveryCandidate(BaseModel):
    provider_revision_id: str | None
    branch_id: str | None = None
    label: str | None = None
    description: str | None = None
    already_imported: bool = False


class RevisionDiscoveryResponse(BaseModel):
    agent_target_id: str
    candidates: list[RevisionDiscoveryCandidate]


class TargetPreviewRequest(BaseModel):
    provider_id: str
    external_agent_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class PreviewAgentIdentity(BaseModel):
    external_agent_id: str
    name: str
    agent_url: str | None = None


class PreviewRevision(BaseModel):
    provider_revision_id: str | None = None
    provider_revision_type: ProviderRevisionType | None = None
    revision_label: str | None = None
    description: str | None = None
    first_message: str | None = None
    canonical_config: dict[str, Any]
    source_updated_at: datetime | None = None


class TargetPreviewResponse(BaseModel):
    identity: PreviewAgentIdentity
    revision: PreviewRevision


ConnectionKind = Literal["websocket", "webrtc", "sip"]
ConnectionTransport = Literal["bridge", "room", "whip", "sip"]


class TargetConnectionUpsert(BaseModel):
    """Client-supplied connection: *how* to reach the agent under test.

    - ``websocket`` → ``bridge``:  ``config.url`` (+ optional ``headers``);
      secret ``authorization`` (added as an ``Authorization`` header).
    - ``webrtc`` → ``room`` (LiveKit): ``config.url`` + secret ``token``.
      Set ``transport="whip"`` for a WHIP endpoint instead: ``config`` carries
      ``call_id``/``base_url``/``ice_servers`` and secret ``access_token``.
    - ``sip`` → ``sip`` (outbound trunk): ``config.address`` (+ ``from_number``,
      ``transport`` tls|tcp|udp) and the destination ``config.to_number`` /
      ``sip_uri``; secrets ``username``/``password``.

    Non-secret ``config`` is frozen into the manifest; ``secrets`` are encrypted
    and only resolved at connect time.
    """

    kind: ConnectionKind
    transport: ConnectionTransport | None = None
    revision_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)

