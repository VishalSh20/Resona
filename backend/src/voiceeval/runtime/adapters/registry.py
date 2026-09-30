"""Explicit, versioned target-adapter registry.

The registry is the source of truth for which target adapters exist and which
versions are supported. Target revision creation uses it to reject unknown
adapters before any call is attempted; the runner uses it to instantiate the
adapter named by the execution manifest. Unknown adapter -> validation error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.adapters.base import TargetAdapter

AdapterFactory = Callable[[], TargetAdapter]


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    version: str


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], AdapterFactory] = {}

    def register(
        self, name: str, version: str, factory: AdapterFactory | None = None
    ) -> None:
        if factory is None:
            raise ValidationError(
                f"adapter '{name}' version '{version}' requires a factory"
            )
        self._adapters[(name, version)] = factory

    def get(self, name: str, version: str) -> AdapterInfo | None:
        if (name, version) in self._adapters:
            return AdapterInfo(name=name, version=version)
        return None

    def ensure_exists(self, name: str, version: str) -> AdapterInfo:
        info = self.get(name, version)
        if info is None:
            raise ValidationError(
                f"unknown target adapter '{name}' version '{version}'"
            )
        return info

    def create(self, name: str, version: str) -> TargetAdapter:
        """Instantiate a registered adapter, rejecting unknown adapters."""
        self.ensure_exists(name, version)
        return self._adapters[(name, version)]()

    def known_names(self) -> set[str]:
        return {name for name, _ in self._adapters}


def _build_default_registry() -> AdapterRegistry:
    # Imported here so the registry module has no import-time dependency on the
    # concrete adapters (keeps the services layer importable in isolation).
    from voiceeval.runtime.adapters.fake import FakeTargetAdapter
    from voiceeval.runtime.adapters.websocket import WebSocketAdapter

    registry = AdapterRegistry()
    # v1 known adapters. The deterministic fake target lets the runtime exercise
    # an end-to-end call without a real provider; the generic websocket adapter
    # is the v1 transport target. WebRTC remains an interface-only contract and
    # is intentionally not registered.
    registry.register("fake", "1.0.0", FakeTargetAdapter)
    registry.register("websocket", "1.0.0", WebSocketAdapter)
    return registry


_registry = _build_default_registry()


def get_adapter_registry() -> AdapterRegistry:
    return _registry
