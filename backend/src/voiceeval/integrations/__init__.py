"""Provider integration adapters (data-sync only).

These adapters fetch and normalize provider agent/revision configuration. They
are deliberately separate from ``voiceeval.runtime.adapters`` (the transport/
communication layer). The service layer depends only on ``base`` and
``registry``, never on a concrete provider adapter.
"""

from voiceeval.integrations import base, registry
from voiceeval.integrations.base import (
    AgentProviderAdapter,
    CanonicalAgentRevision,
    ProviderAgentIdentity,
    ProviderEndpoint,
    ProviderRevision,
    ProviderRevisionSummary,
    SecretResolver,
)

__all__ = [
    "AgentProviderAdapter",
    "CanonicalAgentRevision",
    "ProviderAgentIdentity",
    "ProviderEndpoint",
    "ProviderRevision",
    "ProviderRevisionSummary",
    "SecretResolver",
    "base",
    "registry",
]
