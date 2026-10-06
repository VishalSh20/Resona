"""Connector catalog: which connection kinds each provider supports, plus specs.

Served to the frontend so it can render per-provider connection options without
hardcoding. Provider credential fields are read from the integration registry (so
they stay in sync with the adapters); the capability flags and client-supplied
field specs are declared here.
"""

from __future__ import annotations

from typing import Any

from voiceeval.integrations.base import CredentialField
from voiceeval.integrations.registry import get_adapter

#: The connection kinds a client can ask for, and the TargetLink each maps to.
CONNECTION_KINDS: dict[str, dict[str, Any]] = {
    "websocket": {"transport": "bridge", "label": "WebSocket", "media": "websocket-pcm"},
    "webrtc": {
        "transport": "room",
        "label": "WebRTC",
        "media": "webrtc",
        "alternate_transport": "whip",
    },
    "sip": {
        "transport": "sip",
        "label": "SIP trunk (PSTN / SBC)",
        "media": "sip",
        "supports_dtmf": True,
    },
}

#: sip is universal; websocket/webrtc depend on the agent exposing such an endpoint.
UNIVERSAL_KINDS = ["sip"]

#: Per-provider capability + the connection we use automatically.
_PROVIDER_META: dict[str, dict[str, Any]] = {
    "retell": {
        "display_name": "Retell",
        "default_connection": "webrtc",
        "default_transport": "whip",
        "requires_client_config": False,
        "supports": {"websocket": True, "webrtc": True, "sip": True},
    },
    "vapi": {
        "display_name": "Vapi",
        "default_connection": "websocket",
        "default_transport": "bridge",
        "requires_client_config": False,
        "supports": {"websocket": True, "webrtc": True, "sip": True},
    },
    "elevenlabs": {
        "display_name": "ElevenLabs",
        "default_connection": "webrtc",
        "default_transport": "room",
        "requires_client_config": False,
        "supports": {"websocket": True, "webrtc": True, "sip": True},
    },
    "livekit": {
        "display_name": "LiveKit",
        "default_connection": "webrtc",
        "default_transport": "room",
        "requires_client_config": False,
        "supports": {"websocket": False, "webrtc": True, "sip": True},
    },
    "pipecat": {
        "display_name": "Pipecat Cloud",
        "default_connection": "websocket",
        "default_transport": "bridge",
        "requires_client_config": False,
        "supports": {"websocket": True, "webrtc": True, "sip": True},
    },
    "sip": {
        "display_name": "SIP (configured trunk)",
        "default_connection": "sip",
        "default_transport": "sip",
        "requires_client_config": False,
        "supports": {"websocket": False, "webrtc": False, "sip": True},
    },
}

_CUSTOM_META: dict[str, Any] = {
    "display_name": "Custom / other agent",
    "default_connection": None,
    "default_transport": None,
    "requires_client_config": True,
    "supports": {"websocket": True, "webrtc": True, "sip": True},
}

NOTES = [
    "sip is universal: any agent reachable by a number or SIP URI can be dialed via a client-supplied trunk (kind=sip).",
    "websocket/webrtc are only usable for an agent that actually exposes such an endpoint.",
    "Regardless of a provider's default, the client can attach ANY kind to ANY target via POST /targets/{id}/connection.",
    "default_connection = the connection we use automatically for that provider (no client config needed).",
]

CLIENT_CONNECTIONS: list[dict[str, Any]] = [
    {
        "kind": "websocket",
        "label": "WebSocket",
        "transport": "bridge",
        "config": [
            {"key": "url", "label": "WebSocket URL (wss://...)", "type": "string", "required": True},
            {"key": "headers", "label": "Extra headers", "type": "object", "required": False},
            {
                "key": "provider",
                "label": "Protocol",
                "type": "string",
                "required": False,
                "default": "custom",
                "enum": ["custom", "vapi", "retell", "pipecat", "elevenlabs"],
            },
        ],
        "secrets": [
            {"key": "authorization", "label": "Authorization header value", "required": False}
        ],
    },
    {
        "kind": "webrtc",
        "label": "WebRTC",
        "transport": "room",
        "transport_overrides": {
            "room": {
                "config": [
                    {"key": "url", "label": "LiveKit URL (wss://...)", "type": "string", "required": True}
                ],
                "secrets": [
                    {"key": "token", "label": "LiveKit access token", "required": True}
                ],
            },
            "whip": {
                "config": [
                    {"key": "call_id", "label": "Call id", "type": "string", "required": False},
                    {"key": "proxy_url", "label": "WHIP proxy URL", "type": "string", "required": False},
                    {"key": "base_url", "label": "Provider base URL", "type": "string", "required": False},
                    {"key": "ice_servers", "label": "ICE servers", "type": "array", "required": False},
                    {"key": "identity", "label": "Identity", "type": "string", "required": False, "default": "client"},
                ],
                "secrets": [
                    {"key": "access_token", "label": "Access token", "required": True}
                ],
            },
        },
    },
    {
        "kind": "sip",
        "label": "SIP trunk (outbound via your credentials)",
        "transport": "sip",
        "config": [
            {"key": "address", "label": "SIP address (host:port)", "type": "string", "required": True},
            {
                "key": "transport",
                "label": "Transport",
                "type": "string",
                "required": False,
                "enum": ["auto", "udp", "tcp", "tls"],
                "default": "tls",
            },
            {"key": "from_number", "label": "From number / caller ID", "type": "string", "required": False},
            {"key": "to_number", "label": "Destination number (E.164)", "type": "string", "required": False},
            {"key": "sip_uri", "label": "Destination SIP URI", "type": "string", "required": False},
        ],
        "rules": ["to_number or sip_uri is required"],
        "secrets": [
            {"key": "username", "label": "SIP username", "required": False},
            {"key": "password", "label": "SIP password", "required": False},
        ],
    },
]


def _credential(field: CredentialField) -> dict[str, Any]:
    return {
        "key": field.key,
        "label": field.label,
        "secret": field.secret,
        "required": field.required,
    }


def build_catalog() -> dict[str, Any]:
    """The connector catalog (no DB needed — credential specs come from code)."""
    capabilities: list[dict[str, Any]] = []
    agents: list[dict[str, Any]] = []
    for slug, meta in _PROVIDER_META.items():
        capabilities.append({"provider": slug, **meta})
        agents.append(
            {
                "provider": slug,
                "display_name": meta["display_name"],
                "connection_mode": (
                    "account_provisioned" if slug == "sip" else "automatic"
                ),
                "transport": meta["default_transport"],
                "fields": [_credential(f) for f in get_adapter(slug).credential_spec()],
            }
        )
    capabilities.append({"provider": "custom", **_CUSTOM_META})

    return {
        "version": 1,
        "connection_kinds": CONNECTION_KINDS,
        "universal_kinds": UNIVERSAL_KINDS,
        "provider_capabilities": capabilities,
        "notes": NOTES,
        "provider_agents": agents,
        "client_connections": CLIENT_CONNECTIONS,
        "endpoints": {
            "connectors": "GET /api/v1/integrations/connectors",
            "set_connection": "POST /api/v1/targets/{target_id}/connection",
            "create_account": "POST /api/v1/integrations/accounts",
        },
    }


__all__ = ["build_catalog", "CONNECTION_KINDS", "CLIENT_CONNECTIONS"]
