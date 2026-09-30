"""Target adapter hierarchy.

``TargetAdapter`` is the provider-semantics seam; ``WebSocketAdapter`` is the v1
implemented transport; ``FakeTargetAdapter`` is the deterministic local target;
``WebRTCAdapter`` is an interface and validation contract only.
"""

from voiceeval.runtime.adapters.base import TargetAdapter
from voiceeval.runtime.adapters.fake import (
    FAKE_CAPABILITY_SNAPSHOT,
    FakeScript,
    FakeTargetAdapter,
    FakeTargetServer,
    agent_turn,
    default_script,
    tool_turn,
)
from voiceeval.runtime.adapters.registry import (
    AdapterInfo,
    AdapterRegistry,
    get_adapter_registry,
)
from voiceeval.runtime.adapters.websocket import (
    Frame,
    FrameDecoder,
    JsonProviderProtocolDecoder,
    ProviderProtocolDecoder,
    ProviderProtocolEncoder,
    RawPcmEncoder,
    WebSocketAdapter,
    WebSocketTransport,
)
from voiceeval.runtime.adapters.webrtc import (
    IceServer,
    WebRTCEndpointConfig,
    WebRTCAdapter,
)

__all__ = [
    "AdapterInfo",
    "AdapterRegistry",
    "FAKE_CAPABILITY_SNAPSHOT",
    "FakeScript",
    "FakeTargetAdapter",
    "FakeTargetServer",
    "Frame",
    "FrameDecoder",
    "IceServer",
    "JsonProviderProtocolDecoder",
    "ProviderProtocolDecoder",
    "ProviderProtocolEncoder",
    "RawPcmEncoder",
    "TargetAdapter",
    "WebRTCEndpointConfig",
    "WebRTCAdapter",
    "WebSocketAdapter",
    "WebSocketTransport",
    "agent_turn",
    "default_script",
    "get_adapter_registry",
    "tool_turn",
]
