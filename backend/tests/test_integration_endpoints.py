"""Integrations → TargetLink hand-off (Phase 3, §14.3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voiceeval.core.errors import ConnectionFailedError
from voiceeval.integrations.base import (
    ProviderAgentIdentity,
    ProviderEndpoint,
    ProviderRevision,
    provider_endpoint_to_target_link,
    target_link_transport,
)
from voiceeval.integrations.elevenlabs import ElevenLabsAdapter
from voiceeval.integrations.livekit import LiveKitAdapter
from voiceeval.integrations.pipecat import PipecatAdapter
from voiceeval.integrations.retell import RetellAdapter
from voiceeval.integrations.sip import SipAdapter
from voiceeval.integrations.vapi import VapiAdapter
from voiceeval.orchestration.target_link import default_target_link, resolve_target_link


class _NoSecrets:
    async def resolve(self, account_id: str, key: str) -> str:
        return "secret"


def _identity(url=None):
    return ProviderAgentIdentity(external_agent_id="agent1", name="Agent", agent_url=url)


def _revision(raw=None):
    return ProviderRevision(
        provider_revision_id="r1",
        provider_revision_type="AGENT_CONFIGURATION",
        raw_config=raw or {},
        canonical_config=SimpleNamespace(),
    )


def test_transport_mapping():
    assert target_link_transport("webrtc") == "room"
    assert target_link_transport("websocket") == "bridge"
    assert target_link_transport("pstn") == "sip"
    assert target_link_transport("whip") == "whip"
    assert provider_endpoint_to_target_link(ProviderEndpoint("webrtc", {"url": "x"})) == {
        "transport": "room",
        "endpoint_config": {"url": "x"},
    }


async def test_livekit_endpoint_is_a_per_call_room():
    endpoints = await LiveKitAdapter().get_endpoints(
        SimpleNamespace(config={"url": "wss://proj.livekit.cloud"}),
        _NoSecrets(),
        _identity(),
        _revision(),
    )
    assert endpoints[0].transport == "room"
    assert endpoints[0].connection_config["call_setup"] == "per_call"


async def test_livekit_endpoint_needs_no_static_url():
    endpoints = await LiveKitAdapter().get_endpoints(
        SimpleNamespace(config={}), _NoSecrets(), _identity(), _revision()
    )
    assert endpoints[0].transport == "room"


async def test_pipecat_endpoint_is_a_bridge():
    endpoints = await PipecatAdapter().get_endpoints(
        SimpleNamespace(config={}), _NoSecrets(), _identity("wss://pipecat/x"), _revision()
    )
    assert endpoints[0].transport == "bridge"


async def test_vapi_endpoint_is_a_per_call_bridge():
    endpoints = await VapiAdapter().get_endpoints(
        SimpleNamespace(config={}), _NoSecrets(), _identity(), _revision()
    )
    assert endpoints[0].transport == "bridge"
    assert endpoints[0].connection_config["call_setup"] == "per_call"


async def test_retell_endpoint_is_a_per_call_whip():
    endpoints = await RetellAdapter().get_endpoints(
        SimpleNamespace(config={}), _NoSecrets(), _identity(), _revision()
    )
    assert endpoints[0].transport == "whip"
    assert endpoints[0].connection_config["call_setup"] == "per_call"


async def test_retell_start_connection_mints_a_web_call(monkeypatch):
    import voiceeval.integrations.retell as retell_mod

    captured: dict = {}

    async def fake_post(url, *, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return {
            "call_id": "call_1",
            "access_token": "eyJ.retell.token",
            "transport": "gateway",
            "ice_servers": [{"urls": "stun:stun.l.google.com:19302"}],
            "expires_at": 1,
        }

    monkeypatch.setattr(retell_mod, "post_json", fake_post)
    started = await RetellAdapter().start_connection(
        SimpleNamespace(config={}, id="acct1"),
        _NoSecrets(),
        _identity(),
        _revision(),
        transport="whip",
        sample_rate=16000,
    )

    assert started is not None
    assert started.endpoint_config["call_id"] == "call_1"
    assert started.endpoint_config["access_token"] == "eyJ.retell.token"
    assert started.endpoint_config["identity"] == "client"
    assert started.endpoint_config["base_url"] == "https://api.retellai.com"
    assert started.provider_session_id == "call_1"
    assert captured["url"].endswith("/v3/create-web-call")
    assert captured["json"]["agent_id"] == "agent1"


async def test_elevenlabs_endpoint_is_a_per_call_room():
    endpoints = await ElevenLabsAdapter().get_endpoints(
        SimpleNamespace(config={}), _NoSecrets(), _identity(), _revision()
    )
    assert endpoints[0].transport == "room"
    assert endpoints[0].connection_config == {
        "provider": "elevenlabs",
        "call_setup": "per_call",
    }


async def test_vapi_start_connection_mints_websocket_url(monkeypatch):
    import voiceeval.integrations.vapi as vapi_mod

    captured: dict = {}

    async def fake_post(url, *, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return {
            "id": "call_1",
            "transport": {"websocketCallUrl": "wss://api.vapi.ai/call_1/transport"},
        }

    monkeypatch.setattr(vapi_mod, "post_json", fake_post)
    started = await VapiAdapter().start_connection(
        SimpleNamespace(config={}, id="acct1"),
        _NoSecrets(),
        _identity(),
        _revision(),
        transport="bridge",
        sample_rate=16000,
    )

    assert started is not None
    assert started.endpoint_config["url"] == "wss://api.vapi.ai/call_1/transport"
    assert started.provider_session_id == "call_1"
    assert captured["url"].endswith("/call")
    assert captured["json"]["assistantId"] == "agent1"
    assert captured["json"]["assistantVersion"] == "r1"
    assert captured["json"]["transport"]["audioFormat"]["sampleRate"] == 16000


async def test_elevenlabs_start_connection_mints_livekit_token(monkeypatch):
    import voiceeval.integrations.elevenlabs as el_mod

    captured: dict = {}

    async def fake_get(url, *, headers=None, params=None):
        captured["url"] = url
        captured["params"] = params
        return {"token": "eyJ.livekit.jwt"}

    monkeypatch.setattr(el_mod, "get_json", fake_get)
    started = await ElevenLabsAdapter().start_connection(
        SimpleNamespace(config={}, id="acct1"),
        _NoSecrets(),
        _identity(),
        _revision(),
        transport="room",
        sample_rate=16000,
    )

    assert started is not None
    assert started.endpoint_config["token"] == "eyJ.livekit.jwt"
    assert started.endpoint_config["url"] == "wss://livekit.rtc.elevenlabs.io"
    assert started.endpoint_config["room_mode"] == "external"
    assert captured["url"].endswith("/convai/conversation/token")
    assert captured["params"]["agent_id"] == "agent1"
    assert captured["params"]["version_id"] == "r1"


async def test_elevenlabs_start_connection_uses_workspace_livekit_url(monkeypatch):
    import voiceeval.integrations.elevenlabs as el_mod

    async def fake_get(url, *, headers=None, params=None):
        return {"token": "t"}

    monkeypatch.setattr(el_mod, "get_json", fake_get)
    started = await ElevenLabsAdapter().start_connection(
        SimpleNamespace(config={"livekit_url": "wss://acme.livekit.cloud"}, id="acct1"),
        _NoSecrets(),
        _identity(),
        _revision(),
        transport="room",
        sample_rate=16000,
    )
    assert started.endpoint_config["url"] == "wss://acme.livekit.cloud"


async def test_start_connection_is_noop_for_non_bridge():
    assert (
        await VapiAdapter().start_connection(
            SimpleNamespace(config={}, id="acct1"),
            _NoSecrets(),
            _identity(),
            _revision(),
            transport="room",
            sample_rate=16000,
        )
        is None
    )


class _FakeSession:
    def __init__(self, endpoints, transport_types):
        self._endpoints = endpoints
        self._transport_types = transport_types

    async def get(self, model, id_):
        return self._transport_types.get(id_)

    async def execute(self, stmt):
        endpoints = self._endpoints

        class _Scalars:
            def all(self):
                return endpoints

        class _Result:
            def scalars(self):
                return _Scalars()

        return _Result()


async def test_resolve_target_link_prefers_sip_then_room_then_bridge():
    endpoints = [
        SimpleNamespace(
            id="ep_bridge",
            transport_type_id="tt_bridge",
            connection_config={"url": "ws://b"},
        ),
        SimpleNamespace(
            id="ep_room",
            transport_type_id="tt_room",
            connection_config={"url": "ws://r"},
        ),
        SimpleNamespace(
            id="ep_sip",
            transport_type_id="tt_sip",
            connection_config={"to_number": "+1"},
        ),
    ]
    types = {
        "tt_bridge": SimpleNamespace(slug="bridge"),
        "tt_room": SimpleNamespace(slug="room"),
        "tt_sip": SimpleNamespace(slug="sip"),
    }
    link = await resolve_target_link(_FakeSession(endpoints, types), "rev_1")
    assert link["transport"] == "sip"
    assert link["endpoint_config"] == {"to_number": "+1"}
    assert link["endpoint_id"] == "ep_sip"


async def test_resolve_target_link_defaults_to_room_when_unconfigured():
    link = await resolve_target_link(_FakeSession([], {}), "rev_1")
    assert link == default_target_link()


def test_bridge_provider_decoder_selection():
    from voiceeval.runtime.adapters.websocket import JsonProviderProtocolDecoder
    from voiceeval.runtime.livekit.bridge_decoders import (
        VapiDecoder,
        decoder_for_provider,
    )

    assert isinstance(decoder_for_provider("vapi"), VapiDecoder)
    assert isinstance(decoder_for_provider(None), JsonProviderProtocolDecoder)


def test_bridge_link_uses_provider_decoder_and_monitor_track():
    from voiceeval.runtime.livekit.target_links.bridge import BridgeLink

    link = BridgeLink(endpoint_config={"url": "ws://x", "provider": "vapi"})
    assert link.capabilities().provides_monitor_track is True


def test_bridge_link_accepts_room_kwarg():
    from voiceeval.runtime.livekit.target_links.registry import get_target_link_registry

    link = get_target_link_registry().create(
        "bridge", endpoint_config={"url": "ws://x"}, room=object()
    )
    assert link.transport == "bridge"


async def test_sip_endpoint_is_a_static_dial():
    account = SimpleNamespace(
        config={
            "address": "sip.customer.example",
            "from_number": "+15550001111",
            "livekit_trunk_id": "ST_abc",
        }
    )
    endpoints = await SipAdapter().get_endpoints(
        account, _NoSecrets(), _identity(), _revision()
    )
    assert endpoints[0].transport == "sip"
    assert endpoints[0].connection_config["to_number"] == "agent1"
    assert endpoints[0].connection_config["trunk_id"] == "ST_abc"
    # Static: SIP is a revision/account credential, not minted per call.
    assert "call_setup" not in endpoints[0].connection_config


async def test_sip_provision_account_creates_a_livekit_trunk(monkeypatch):
    import voiceeval.integrations.sip as sip_mod

    sink: dict = {}
    monkeypatch.setattr(sip_mod, "_import_api", lambda: _FakeSipApi(sink))
    monkeypatch.setattr(
        sip_mod,
        "get_settings",
        lambda: SimpleNamespace(
            livekit_url="wss://lk", livekit_api_key="k", livekit_api_secret="s"
        ),
    )
    account = SimpleNamespace(
        id="acct1",
        config={
            "address": "sip.customer.example",
            "from_number": "+1555",
            "transport": "tls",
        },
    )
    extra = await SipAdapter().provision_account(account, _NoSecrets())

    assert extra["livekit_trunk_id"] == "ST_new"
    assert sink["created"].address == "sip.customer.example"
    assert sink["created"].numbers == ["+1555"]
    assert sink["created"].transport == 3  # TLS
    assert sink["created"].auth_username == "secret"  # from _NoSecrets


def test_sip_transport_code_mapping():
    from voiceeval.integrations.sip import _transport_code

    assert _transport_code("tls") == 3
    assert _transport_code("TCP") == 2
    assert _transport_code("udp") == 1
    assert _transport_code(None) == 0
    assert _transport_code("bogus") == 0


async def test_sip_provision_account_reuses_an_existing_trunk(monkeypatch):
    import voiceeval.integrations.sip as sip_mod

    sink: dict = {
        "existing": [
            SimpleNamespace(name="resona-sip-acct1", sip_trunk_id="ST_old")
        ]
    }
    monkeypatch.setattr(sip_mod, "_import_api", lambda: _FakeSipApi(sink))
    monkeypatch.setattr(
        sip_mod,
        "get_settings",
        lambda: SimpleNamespace(
            livekit_url="wss://lk", livekit_api_key="k", livekit_api_secret="s"
        ),
    )
    account = SimpleNamespace(id="acct1", config={"address": "sip.customer.example"})
    extra = await SipAdapter().provision_account(account, _NoSecrets())

    assert extra["livekit_trunk_id"] == "ST_old"
    assert "created" not in sink


class _FakeSipApi:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def LiveKitAPI(self, *, url, api_key, api_secret):
        self._sink["url"] = url
        return _FakeSipClient(self._sink)

    def ListSIPOutboundTrunkRequest(self):
        return SimpleNamespace()

    def CreateSIPOutboundTrunkRequest(self, *, trunk):
        return SimpleNamespace(trunk=trunk)

    def SIPOutboundTrunkInfo(self, **kwargs):
        return SimpleNamespace(**kwargs)


class _FakeSipClient:
    def __init__(self, sink: dict) -> None:
        self._sink = sink
        self.sip = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def list_sip_outbound_trunk(self, request):
        return SimpleNamespace(items=list(self._sink.get("existing", [])))

    async def create_sip_outbound_trunk(self, request):
        self._sink["created"] = request.trunk
        return SimpleNamespace(
            sip_trunk_id="ST_new", name=request.trunk.name
        )


class _FakeLiveKitApi:
    """Minimal stand-in for ``livekit.api`` used by LiveKitAdapter.start_connection."""

    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def LiveKitAPI(self, *, url, api_key, api_secret):
        self._sink["url"] = url
        return _FakeLiveKitClient(self._sink)

    def CreateRoomRequest(self, *, name, empty_timeout, max_participants):
        return SimpleNamespace(name=name, empty_timeout=empty_timeout)

    def CreateAgentDispatchRequest(self, *, agent_name, room, deployment=""):
        return SimpleNamespace(agent_name=agent_name, room=room, deployment=deployment)

    def AccessToken(self, api_key, api_secret):
        return _FakeAccessToken(api_key)

    def VideoGrants(self, *, room_join, room):
        return SimpleNamespace(room_join=room_join, room=room)


class _FakeLiveKitClient:
    def __init__(self, sink: dict) -> None:
        self._sink = sink
        self.room = self
        self.agent_dispatch = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def create_room(self, request):
        self._sink["room"] = request.name
        self._sink["empty_timeout"] = request.empty_timeout

    async def create_dispatch(self, request):
        self._sink["dispatch"] = (
            request.agent_name,
            request.room,
            request.deployment,
        )


class _FakeAccessToken:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def with_identity(self, identity):
        return self

    def with_grants(self, grants):
        return self

    def to_jwt(self) -> str:
        return "livekit-jwt"


async def test_livekit_start_connection_creates_room_and_dispatches(monkeypatch):
    import voiceeval.integrations.livekit as lk_mod

    sink: dict = {}
    monkeypatch.setattr(lk_mod, "_import_api", lambda: _FakeLiveKitApi(sink))
    started = await LiveKitAdapter().start_connection(
        SimpleNamespace(config={"url": "wss://target.livekit.cloud"}, id="acct1"),
        _NoSecrets(),
        _identity(),
        _revision(),
        transport="room",
        sample_rate=16000,
    )

    assert sink["url"] == "wss://target.livekit.cloud"
    assert sink["room"].startswith("resona-")
    # We do not pin a deployment because the adapter has no real deployment id
    # from LiveKit; passing an arbitrary revision id (e.g. a Cloud agent id)
    # would fail with "deployment contains reserved character '_'".
    assert sink["dispatch"] == ("agent1", sink["room"], "")
    # External rooms rely on the provider's empty-timeout to self-delete; the
    # timeout sits well above the call wall clock so a live call is never reaped.
    assert sink["empty_timeout"] == 900
    assert started.endpoint_config["token"] == "livekit-jwt"
    assert started.endpoint_config["room_mode"] == "external"
    assert started.provider_session_id == sink["room"]


async def test_livekit_start_connection_without_a_revision_deployment(monkeypatch):
    import dataclasses

    import voiceeval.integrations.livekit as lk_mod

    sink: dict = {}
    monkeypatch.setattr(lk_mod, "_import_api", lambda: _FakeLiveKitApi(sink))
    await LiveKitAdapter().start_connection(
        SimpleNamespace(config={"url": "wss://target.livekit.cloud"}, id="acct1"),
        _NoSecrets(),
        _identity(),
        dataclasses.replace(_revision(), provider_revision_id=None),
        transport="room",
        sample_rate=16000,
    )
    # No deployment pinned for a revision without a provider id.
    assert sink["dispatch"] == ("agent1", sink["room"], "")


async def test_livekit_start_connection_requires_a_project_url():
    with pytest.raises(ConnectionFailedError):
        await LiveKitAdapter().start_connection(
            SimpleNamespace(config={}, id="acct1"),
            _NoSecrets(),
            _identity(),
            _revision(),
            transport="room",
            sample_rate=16000,
        )
