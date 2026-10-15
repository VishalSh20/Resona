"""TargetLink registry — resolves a transport slug to a link implementation.

Mirrors ``runtime.adapters.registry``: registration is factory-based so a link
can pick up per-attempt ``endpoint_config`` and credentials at construction time
rather than at import. Factories import their LiveKit-dependent modules lazily,
so the registry imports cleanly without the SDK installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.livekit.target_links.base import TargetLink


@dataclass(frozen=True)
class TargetLinkInfo:
    name: str
    factory: Callable[..., TargetLink]


class TargetLinkRegistry:
    def __init__(self) -> None:
        self._links: dict[str, Callable[..., TargetLink]] = {}

    def register(self, name: str, factory: Callable[..., TargetLink]) -> None:
        if not callable(factory):
            raise ValidationError(
                f"target link '{name}' factory must be callable"
            )
        self._links[name] = factory

    def get(self, name: str) -> Callable[..., TargetLink]:
        try:
            return self._links[name]
        except KeyError as exc:
            raise ValidationError(
                f"unknown target link '{name}'; known: {sorted(self._links)}"
            ) from exc

    def ensure_exists(self, name: str) -> None:
        self.get(name)

    def create(self, name: str, **kwargs: Any) -> TargetLink:
        return self.get(name)(**kwargs)

    def known_names(self) -> set[str]:
        return set(self._links)


def _build_default_registry() -> TargetLinkRegistry:
    registry = TargetLinkRegistry()

    def _room(**kwargs: Any) -> TargetLink:
        from voiceeval.runtime.livekit.target_links.room import RoomLink

        return RoomLink(**kwargs)

    def _sip(**kwargs: Any) -> TargetLink:
        from voiceeval.runtime.livekit.target_links.sip import SipLink

        return SipLink(**kwargs)

    def _bridge(**kwargs: Any) -> TargetLink:
        from voiceeval.runtime.livekit.target_links.bridge import BridgeLink

        return BridgeLink(**kwargs)

    def _whip(**kwargs: Any) -> TargetLink:
        from voiceeval.runtime.livekit.target_links.whip import WhipLink

        return WhipLink(**kwargs)

    registry.register("room", _room)
    registry.register("sip", _sip)
    registry.register("bridge", _bridge)
    registry.register("whip", _whip)
    return registry


_registry: TargetLinkRegistry | None = None


def get_target_link_registry() -> TargetLinkRegistry:
    global _registry
    if _registry is None:
        _registry = _build_default_registry()
    return _registry


def set_target_link_registry(registry: TargetLinkRegistry | None) -> None:
    global _registry
    _registry = registry


__all__ = [
    "TargetLinkInfo",
    "TargetLinkRegistry",
    "get_target_link_registry",
    "set_target_link_registry",
]
