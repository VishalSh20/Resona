"""Provider adapter registry: provider slug -> adapter.

Provider-specific branching never leaks into services: a service resolves an
adapter by ``IntegrationProvider.slug`` and works only against the common
``AgentProviderAdapter`` interface.
"""

from __future__ import annotations

from voiceeval.core.errors import ValidationError
from voiceeval.integrations.base import AgentProviderAdapter
from voiceeval.integrations.custom import CustomAdapter
from voiceeval.integrations.elevenlabs import ElevenLabsAdapter
from voiceeval.integrations.livekit import LiveKitAdapter
from voiceeval.integrations.pipecat import PipecatAdapter
from voiceeval.integrations.retell import RetellAdapter
from voiceeval.integrations.sip import SipAdapter
from voiceeval.integrations.vapi import VapiAdapter


def _build_registry() -> dict[str, AgentProviderAdapter]:
    adapters: list[AgentProviderAdapter] = [
        RetellAdapter(),
        VapiAdapter(),
        ElevenLabsAdapter(),
        LiveKitAdapter(),
        PipecatAdapter(),
        SipAdapter(),
        CustomAdapter(),
    ]
    return {adapter.provider_slug: adapter for adapter in adapters}


_REGISTRY: dict[str, AgentProviderAdapter] = _build_registry()


def get_adapter(provider_slug: str) -> AgentProviderAdapter:
    adapter = _REGISTRY.get(provider_slug)
    if adapter is None:
        raise ValidationError(f"unknown integration provider '{provider_slug}'")
    return adapter


def known_provider_slugs() -> set[str]:
    return set(_REGISTRY)
