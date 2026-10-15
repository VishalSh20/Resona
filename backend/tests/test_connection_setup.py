"""Tests for the runtime connection-starter seam (per-call bridge endpoints)."""

from __future__ import annotations

from types import SimpleNamespace

from voiceeval.integrations.base import StartedConnection
from voiceeval.runtime.livekit.connection_setup import prepare_target_link


class _FakeTargetRepo:
    def __init__(self, session) -> None:
        pass

    async def get_target(self, target_id: str):
        return SimpleNamespace(
            external_agent_id="agent1",
            name="Agent",
            agent_url=None,
            integration_account_id="acct1",
            provider_id="prov1",
        )


class _FakeIntegrationRepo:
    def __init__(self, session) -> None:
        pass

    async def get_account(self, account_id: str):
        return SimpleNamespace(id=account_id, config={})

    async def get_provider(self, provider_id: str):
        return SimpleNamespace(slug="vapi")


def _revision():
    return SimpleNamespace(
        provider_revision_id="r1",
        provider_revision_type="AGENT_CONFIGURATION",
        source_config={},
        source_branch_id=None,
        revision_label="r1",
    )


async def test_prepare_passthrough_for_static_bridge():
    prepared = await prepare_target_link(
        object(),
        {
            "transport": "bridge",
            "endpoint_config": {"url": "ws://x", "provider": "custom"},
            "endpoint_id": "ep_1",
        },
        SimpleNamespace(target_snapshot={}),
        None,
    )
    assert prepared.transport == "bridge"
    assert prepared.endpoint_config == {"url": "ws://x", "provider": "custom"}
    assert prepared.provider_session_id is None
    assert prepared.endpoint_id == "ep_1"


async def test_prepare_passthrough_does_not_touch_db_for_room():
    # No session/repo fakes installed: a room link must not hit the DB at all.
    prepared = await prepare_target_link(
        object(),
        {"transport": "room", "endpoint_config": {"url": "wss://room"}},
        SimpleNamespace(target_snapshot={}),
        None,
    )
    assert prepared.transport == "room"
    assert prepared.endpoint_config == {"url": "wss://room"}


async def test_prepare_mints_per_call_url(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    class _FakeAdapter:
        async def start_connection(
            self, account, secrets, agent, revision, *, transport, sample_rate
        ):
            assert transport == "bridge"
            assert sample_rate == 16000
            assert agent.external_agent_id == "agent1"
            return StartedConnection(
                endpoint_config={"url": "wss://minted", "provider": "vapi"},
                provider_session_id="sess1",
            )

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "get_adapter", lambda slug: _FakeAdapter())

    prepared = await prepare_target_link(
        object(),
        {
            "transport": "bridge",
            "endpoint_config": {"provider": "vapi", "call_setup": "per_call"},
            "endpoint_id": "ep_2",
        },
        SimpleNamespace(target_snapshot={"agent_target_id": "t1"}),
        _revision(),
    )
    assert prepared.endpoint_config["url"] == "wss://minted"
    assert prepared.endpoint_config["provider"] == "vapi"
    assert prepared.provider_session_id == "sess1"
    assert prepared.endpoint_id == "ep_2"


async def test_prepare_mints_per_call_room(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    class _FakeAdapter:
        async def start_connection(
            self, account, secrets, agent, revision, *, transport, sample_rate
        ):
            assert transport == "room"
            return StartedConnection(
                endpoint_config={
                    "url": "wss://livekit",
                    "token": "jwt-token",
                    "room_mode": "external",
                },
                provider_session_id="room-1",
            )

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "get_adapter", lambda slug: _FakeAdapter())

    prepared = await prepare_target_link(
        object(),
        {
            "transport": "room",
            "endpoint_config": {"provider": "elevenlabs", "call_setup": "per_call"},
            "endpoint_id": "ep_3",
        },
        SimpleNamespace(target_snapshot={"agent_target_id": "t1"}),
        _revision(),
    )
    assert prepared.transport == "room"
    assert prepared.endpoint_config["token"] == "jwt-token"
    assert prepared.endpoint_config["room_mode"] == "external"
    assert prepared.provider_session_id == "room-1"
    assert prepared.endpoint_id == "ep_3"


async def test_prepare_mints_per_call_whip(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    class _FakeAdapter:
        async def start_connection(
            self, account, secrets, agent, revision, *, transport, sample_rate
        ):
            assert transport == "whip"
            return StartedConnection(
                endpoint_config={
                    "call_id": "call_9",
                    "access_token": "tok",
                    "ice_servers": [],
                },
                provider_session_id="call_9",
            )

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "get_adapter", lambda slug: _FakeAdapter())

    prepared = await prepare_target_link(
        object(),
        {
            "transport": "whip",
            "endpoint_config": {"provider": "retell", "call_setup": "per_call"},
            "endpoint_id": "ep_4",
        },
        SimpleNamespace(target_snapshot={"agent_target_id": "t1"}),
        _revision(),
    )
    assert prepared.transport == "whip"
    assert prepared.endpoint_config["call_id"] == "call_9"
    assert prepared.provider_session_id == "call_9"
    assert prepared.endpoint_id == "ep_4"


# --- client-supplied connections --------------------------------------------


class _FakeSecrets:
    _VALUES = {
        "conn_authorization": "Bearer tok",
        "conn_token": "jwt-room",
        "conn_username": "u",
        "conn_password": "p",
        "conn_access_token": "whip-tok",
    }

    def __init__(self, session) -> None:
        pass

    async def resolve(self, account_id: str, key: str) -> str:
        from voiceeval.core.errors import ResourceNotFoundError

        if key in self._VALUES:
            return self._VALUES[key]
        raise ResourceNotFoundError(key)


def _client_link(transport: str, config: dict) -> dict:
    return {
        "transport": transport,
        "endpoint_config": {**config, "client_supplied": True},
        "endpoint_id": "ep_c",
    }


async def test_client_websocket_connection_adds_auth_header(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "SecretService", _FakeSecrets)

    prepared = await prepare_target_link(
        object(), _client_link("bridge", {"url": "wss://agent"}), SimpleNamespace(target_snapshot={"agent_target_id": "t1"}), _revision()
    )
    assert prepared.transport == "bridge"
    assert prepared.endpoint_config["url"] == "wss://agent"
    assert prepared.endpoint_config["headers"]["Authorization"] == "Bearer tok"
    assert prepared.endpoint_config["provider"] == "custom"
    assert "client_supplied" not in prepared.endpoint_config


async def test_client_webrtc_room_connection_adds_token(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "SecretService", _FakeSecrets)

    prepared = await prepare_target_link(
        object(), _client_link("room", {"url": "wss://lk"}), SimpleNamespace(target_snapshot={"agent_target_id": "t1"}), _revision()
    )
    assert prepared.transport == "room"
    assert prepared.endpoint_config["token"] == "jwt-room"
    assert prepared.endpoint_config["room_mode"] == "external"


async def test_client_sip_connection_provisions_a_trunk(monkeypatch):
    import voiceeval.runtime.livekit.connection_setup as cs

    monkeypatch.setattr(cs, "TargetRepository", _FakeTargetRepo)
    monkeypatch.setattr(cs, "IntegrationRepository", _FakeIntegrationRepo)
    monkeypatch.setattr(cs, "SecretService", _FakeSecrets)

    async def fake_trunk(**kwargs):
        assert kwargs["address"] == "sip.carrier.example:5061"
        assert kwargs["username"] == "u"
        return "ST_client"

    monkeypatch.setattr(cs, "ensure_outbound_trunk", fake_trunk)

    prepared = await prepare_target_link(
        object(),
        _client_link("sip", {"address": "sip.carrier.example:5061", "to_number": "+9199", "transport": "tls"}),
        SimpleNamespace(target_snapshot={"agent_target_id": "t1"}),
        _revision(),
    )
    assert prepared.transport == "sip"
    assert prepared.endpoint_config["trunk_id"] == "ST_client"


def test_connection_validation():
    import pytest

    from voiceeval.core.errors import ValidationError
    from voiceeval.services.targets import TargetService

    with pytest.raises(ValidationError):
        TargetService._validate_connection("bridge", {})
    with pytest.raises(ValidationError):
        TargetService._validate_connection("sip", {"address": "x"})
    TargetService._validate_connection("sip", {"address": "x", "to_number": "+1"})
    TargetService._validate_connection("room", {"url": "wss://x"})


def test_client_connection_kinds_map_to_transports():
    from voiceeval.integrations.base import CLIENT_CONNECTION_KINDS

    assert CLIENT_CONNECTION_KINDS == {
        "websocket": "bridge",
        "webrtc": "room",
        "sip": "sip",
    }


def test_connector_catalog():
    from voiceeval.services.connectors import build_catalog

    catalog = build_catalog()
    providers = {p["provider"]: p for p in catalog["provider_capabilities"]}
    assert set(providers) == {
        "retell",
        "vapi",
        "elevenlabs",
        "livekit",
        "pipecat",
        "sip",
        "custom",
    }
    assert providers["sip"]["supports"] == {
        "websocket": False,
        "webrtc": False,
        "sip": True,
    }
    assert providers["custom"]["requires_client_config"] is True
    assert providers["retell"]["default_transport"] == "whip"
    assert catalog["universal_kinds"] == ["sip"]
    assert {c["kind"] for c in catalog["client_connections"]} == {
        "websocket",
        "webrtc",
        "sip",
    }
    # credential fields come from the adapters
    agents = {a["provider"]: a for a in catalog["provider_agents"]}
    assert [f["key"] for f in agents["sip"]["fields"]][0] == "address"
    assert agents["elevenlabs"]["fields"][1]["key"] == "livekit_url"
