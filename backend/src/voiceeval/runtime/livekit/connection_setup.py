"""Resolve a frozen ``target_link`` into a concrete, connectable link.

Two things are resolved here at connect time (never frozen into the manifest):

* **per-call providers** — endpoints minted by an authenticated API request
  (Vapi ``POST /call``; ElevenLabs conversation token; a LiveKit project room +
  agent dispatch + caller token). Provider semantics live in the adapter
  (``AgentProviderAdapter.start_connection``).
* **client-supplied connections** — the client told us *how* to reach the agent
  (websocket / webrtc / sip). The non-secret config is frozen; credentials are
  pulled from the account's secrets here, and a SIP trunk is provisioned inline.

Everything else (a static room, a static bridge, a custom URL) passes through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ResourceNotFoundError, ValidationError
from voiceeval.db.models import domain
from voiceeval.db.repositories import IntegrationRepository, TargetRepository
from voiceeval.integrations.base import (
    CanonicalAgentRevision,
    ProviderAgentIdentity,
    ProviderRevision,
)
from voiceeval.integrations.registry import get_adapter
from voiceeval.integrations.sip import ensure_outbound_trunk
from voiceeval.services.secrets import SecretService

#: Secret names looked up (as ``conn_<name>``) for a client-supplied transport.
_CLIENT_SECRET_NAMES = {
    "bridge": ("authorization",),
    "room": ("token",),
    "whip": ("access_token",),
    "sip": ("username", "password"),
}


@dataclass(frozen=True)
class PreparedLink:
    """A ``target_link`` resolved against the tenant that owns the target."""

    transport: str
    endpoint_config: dict[str, Any]
    provider_session_id: str | None = None
    endpoint_id: str | None = None


async def prepare_target_link(
    session: AsyncSession,
    raw_link: dict[str, Any],
    manifest: domain.ExecutionManifest,
    target_revision: domain.AgentTargetRevision | None,
    *,
    sample_rate: int = 16_000,
) -> PreparedLink:
    """Resolve ``raw_link`` into a connectable config (secrets + per-call mints)."""
    transport = str(raw_link.get("transport") or "room")
    config = dict(raw_link.get("endpoint_config") or {})
    endpoint_id = raw_link.get("endpoint_id")

    per_call = config.get("call_setup") == "per_call" and transport in {
        "room",
        "bridge",
        "whip",
    }
    client_supplied = bool(config.get("client_supplied"))
    if not per_call and not client_supplied:
        return PreparedLink(
            transport=transport, endpoint_config=config, endpoint_id=endpoint_id
        )

    if target_revision is None:
        raise ValidationError(
            "dynamic target link requires a target revision on the manifest"
        )
    target_id = (manifest.target_snapshot or {}).get("agent_target_id")
    if not target_id:
        raise ValidationError(
            "dynamic target link requires agent_target_id on the manifest"
        )

    target = await TargetRepository(session).get_target(str(target_id))
    account = await IntegrationRepository(session).get_account(
        target.integration_account_id
    )

    if client_supplied:
        resolved = await _resolve_client_connection(session, config, transport, account)
        return PreparedLink(
            transport=transport, endpoint_config=resolved, endpoint_id=endpoint_id
        )

    provider = await IntegrationRepository(session).get_provider(target.provider_id)
    identity = ProviderAgentIdentity(
        external_agent_id=target.external_agent_id or "",
        name=target.name,
        agent_url=target.agent_url,
    )
    revision = ProviderRevision(
        provider_revision_id=target_revision.provider_revision_id,
        provider_revision_type=target_revision.provider_revision_type or "",
        raw_config=dict(target_revision.source_config or {}),
        canonical_config=CanonicalAgentRevision(),
        branch_id=target_revision.source_branch_id,
        revision_label=target_revision.revision_label,
    )

    adapter = get_adapter(provider.slug)
    started = await adapter.start_connection(
        account,
        SecretService(session),
        identity,
        revision,
        transport=transport,
        sample_rate=sample_rate,
    )
    if started is None:
        return PreparedLink(
            transport=transport, endpoint_config=config, endpoint_id=endpoint_id
        )

    return PreparedLink(
        transport=transport,
        endpoint_config={**config, **started.endpoint_config},
        provider_session_id=started.provider_session_id,
        endpoint_id=endpoint_id,
    )


async def _resolve_client_connection(
    session: AsyncSession,
    config: dict[str, Any],
    transport: str,
    account: domain.IntegrationAccount,
) -> dict[str, Any]:
    """Merge a client-supplied connection's secrets into its frozen config."""
    secrets = SecretService(session)
    out = {key: value for key, value in config.items() if key != "client_supplied"}

    async def secret(name: str) -> str | None:
        try:
            return await secrets.resolve(account.id, f"conn_{name}")
        except ResourceNotFoundError:
            return None

    if transport == "bridge":
        authorization = await secret("authorization")
        if authorization:
            out.setdefault("headers", {})["Authorization"] = authorization
        out.setdefault("provider", "custom")
    elif transport == "room":
        token = await secret("token")
        if token:
            out["token"] = token
        out.setdefault("room_mode", "external")
    elif transport == "whip":
        access_token = await secret("access_token")
        if access_token:
            out["access_token"] = access_token
    elif transport == "sip":
        address = out.get("address")
        if not address:
            raise ValidationError("client sip connection requires an 'address'")
        out["trunk_id"] = await ensure_outbound_trunk(
            name=f"resona-client-sip-{account.id}",
            address=address,
            username=await secret("username"),
            password=await secret("password"),
            from_number=out.get("from_number"),
            transport=out.get("transport") or "auto",
        )
    return out


__all__ = ["PreparedLink", "prepare_target_link"]
