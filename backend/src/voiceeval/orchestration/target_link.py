"""Resolve a persisted ``AgentEndpoint`` into the manifest's ``target_link``.

This is the bridge from the provider-integration layer (``integrations/`` +
``agent_endpoint`` rows) to the runtime TargetLink the caller connects with
(§14.3 — the hand-off the design doc calls the main blocker for real targets).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.repositories import IntegrationRepository
from voiceeval.integrations.base import (
    ProviderEndpoint,
    provider_endpoint_to_target_link,
    target_link_transport,
)

#: Preference order when a revision exposes several transports.
TARGET_LINK_PREFERENCE = ("sip", "room", "whip", "bridge")


def default_target_link() -> dict[str, Any]:
    """The fallback when no endpoint is configured (a LiveKit room target)."""
    return {"transport": "room", "endpoint_config": {}}


async def resolve_target_link(
    session: AsyncSession, revision_id: str
) -> dict[str, Any]:
    """Resolve the preferred TargetLink for an agent target revision.

    The resolved link carries the ``agent_endpoint`` id (when one exists) so the
    runner can attribute a runtime connection session back to it.
    """
    repo = IntegrationRepository(session)
    endpoints = await repo.list_endpoints_for_revision(revision_id)
    resolved: list[tuple[str, dict[str, Any], str]] = []
    for endpoint in endpoints:
        transport_type = await repo.get_transport_type(endpoint.transport_type_id)
        resolved.append(
            (
                transport_type.slug,
                dict(endpoint.connection_config or {}),
                endpoint.id,
            )
        )

    for preferred in TARGET_LINK_PREFERENCE:
        for slug, config, endpoint_id in resolved:
            if target_link_transport(slug) == preferred:
                return {
                    "transport": preferred,
                    "endpoint_config": config,
                    "endpoint_id": endpoint_id,
                }

    if resolved:
        slug, config, endpoint_id = resolved[0]
        link = provider_endpoint_to_target_link(ProviderEndpoint(slug, config))
        link["endpoint_id"] = endpoint_id
        return link
    return default_target_link()


__all__ = ["TARGET_LINK_PREFERENCE", "default_target_link", "resolve_target_link"]
