"""LiveKit caller runtime.

Implements the caller migration (``docs/V2-changes/caller-migration-to-livekit.md``):
one room + one job process per attempt, with the caller brain reused unchanged
and a thin behavior layer we own.
"""

from __future__ import annotations

from voiceeval.runtime.livekit.target_links.base import TargetLink, TargetLinkCapabilities
from voiceeval.runtime.livekit.target_links.registry import (
    TargetLinkRegistry,
    get_target_link_registry,
)

__all__ = [
    "TargetLink",
    "TargetLinkCapabilities",
    "TargetLinkRegistry",
    "get_target_link_registry",
]
