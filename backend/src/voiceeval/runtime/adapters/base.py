"""Target adapter contract.

An adapter is the single place where *provider semantics* live: how to validate
an endpoint configuration, what capabilities the target exposes, how to build a
transport connection, and how a provider-level observation maps onto a canonical
event. Transport (framing/IO), provider semantics (this layer) and evaluation
semantics (the caller/metric layer) stay strictly separate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.connections import (
    AgentConnection,
    CapabilitySnapshot,
    ConnectionConfig,
    RawAgentEvent,
)
from voiceeval.runtime.events import CanonicalEvent, CanonicalEventBuilder, EventSource


class TargetAdapter(ABC):
    """Base class for every target adapter. Subclasses are versioned."""

    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    transport: ClassVar[str] = ""

    def __init__(self, *, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate

    # -- configuration --------------------------------------------------------

    def validate_config(self, endpoint_config: dict[str, Any]) -> None:
        """Reject an endpoint configuration the adapter cannot execute.

        The base contract requires a URL; adapters add provider-specific rules.
        Raw secrets are never accepted here (they are resolved at dispatch time).
        """
        url = endpoint_config.get("url")
        if not url or not isinstance(url, str):
            raise ValidationError(
                f"adapter '{self.name}' requires a string 'url' in endpoint_config"
            )

    def capabilities(self, endpoint_config: dict[str, Any]) -> CapabilitySnapshot:
        """Return the target's declared capability snapshot."""
        return CapabilitySnapshot.from_dict(
            endpoint_config.get("capability_snapshot") or {}
        )

    # -- execution ------------------------------------------------------------

    def connection_config(
        self, endpoint_config: dict[str, Any], *, sample_rate: int | None = None
    ) -> ConnectionConfig:
        headers = endpoint_config.get("headers")
        if headers is not None and not isinstance(headers, dict):
            raise ValidationError("endpoint_config.headers must be an object")
        return ConnectionConfig(
            url=str(endpoint_config["url"]),
            headers={str(k): str(v) for k, v in (headers or {}).items()},
            sample_rate=sample_rate or self._sample_rate,
            channels=int(endpoint_config.get("channels", 1)),
            timeout_s=float(endpoint_config.get("timeout_s", 10.0)),
            options=dict(endpoint_config.get("options") or {}),
        )

    @abstractmethod
    def build_connection(
        self, endpoint_config: dict[str, Any], *, sample_rate: int | None = None
    ) -> AgentConnection:
        """Construct (but do not connect) a transport connection."""

    def to_canonical(
        self, raw: RawAgentEvent, builder: CanonicalEventBuilder
    ) -> list[CanonicalEvent]:
        """Map a provider observation into the canonical event vocabulary.

        The default mapping passes the provider's normalized event type through
        unchanged; adapters override this to translate provider-specific names.
        When the provider does not carry a monotonic timestamp, the builder
        stamps arrival time so latency metrics retain a runner-monotonic basis.
        """
        return [
            builder.build(
                raw.type,
                source=raw.source,
                payload=raw.payload,
                monotonic_ms=raw.monotonic_ms or None,
                media_timestamp=raw.media_timestamp,
                turn_id=raw.turn_id,
                provider_event_id=raw.provider_event_id,
            )
        ]

    def raw_source(self) -> str:
        return EventSource.PROVIDER_NORMALIZED.value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name}@{self.version}>"
