"""TargetLink contract, audio conversion and registry (no LiveKit SDK needed)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.livekit.target_links import (
    BridgeLink,
    RoomLink,
    SIP_STATUS_TO_REASON,
    SipLink,
    TargetLinkCapabilities,
    get_target_link_registry,
    set_target_link_registry,
)
from voiceeval.runtime.livekit.target_links import audio as audio_mod


def test_duration_ms_matches_pcm_shape():
    # 16000 Hz, mono, 16-bit -> 32000 bytes per second
    assert audio_mod.duration_ms(32_000, 16_000, 1) == 1000
    assert audio_mod.duration_ms(640, 16_000, 1) == 20


def test_pcm_bytes_to_chunk_sets_metadata():
    chunk = audio_mod.pcm_bytes_to_chunk(b"\x00" * 640, sample_rate=16_000)
    assert chunk.format == "pcm_s16le"
    assert chunk.sample_rate == 16_000
    assert chunk.duration_ms == 20


def test_frame_to_chunk_reads_duck_typed_frame():
    class _Frame:
        data = b"\x00" * 960  # 20ms @ 24kHz mono
        sample_rate = 24_000
        num_channels = 1

    chunk = audio_mod.frame_to_chunk(_Frame())
    assert chunk.sample_rate == 24_000
    assert chunk.duration_ms == 20


def test_registry_resolves_known_transports_without_sdk():
    assert get_target_link_registry().known_names() == {"room", "sip", "bridge", "whip"}
    assert isinstance(get_target_link_registry().create("room"), RoomLink)


def test_registry_rejects_unknown_transport():
    with pytest.raises(ValidationError):
        get_target_link_registry().create("carrier-pigeon")


def test_registry_can_be_overridden_and_restored():
    from voiceeval.runtime.livekit.target_links.registry import TargetLinkRegistry

    sentinel = TargetLinkRegistry()
    sentinel.register("room", lambda **_: RoomLink())
    set_target_link_registry(sentinel)
    try:
        assert sentinel.known_names() == {"room"}
    finally:
        set_target_link_registry(None)
    assert get_target_link_registry().known_names() == {"room", "sip", "bridge", "whip"}


def test_sip_link_requires_a_destination():
    with pytest.raises(ValidationError):
        SipLink(endpoint_config={})


def test_sip_link_capabilities_support_dtmf_and_narrowband():
    link = SipLink(endpoint_config={"to_number": "+15551234567"})
    caps = link.capabilities()
    assert caps.supports_dtmf is True
    assert caps.sample_rate == 8_000


def test_sip_status_mapping_covers_failure_reasons():
    assert SIP_STATUS_TO_REASON["busy"] == "BUSY"
    assert SIP_STATUS_TO_REASON["no_answer"] == "NO_ANSWER"
    assert SIP_STATUS_TO_REASON["declined"] == "REJECTED"


def test_sip_link_uses_the_passed_caller_room_name():
    link = SipLink(
        endpoint_config={"to_number": "+15551234567"},
        room=SimpleNamespace(name="attempt-abc"),
    )
    assert link._room_name() == "attempt-abc"


def test_sip_link_requires_a_room_name():
    link = SipLink(endpoint_config={"to_number": "+15551234567"})
    with pytest.raises(ValidationError):
        link._room_name()


def test_sip_link_client_kwargs_prefer_explicit_config():
    link = SipLink(
        endpoint_config={
            "to_number": "+15551234567",
            "url": "wss://explicit.livekit",
            "api_key": "k",
            "api_secret": "s",
        }
    )
    kwargs = link._client_kwargs()
    assert kwargs["url"] == "wss://explicit.livekit"
    assert kwargs["api_key"] == "k"


def test_room_link_external_mode_ignores_the_caller_room():
    passed = object()
    link = RoomLink(endpoint_config={"room_mode": "external"}, room=passed)
    assert link._external is True
    assert link._room is None
    assert link._owns_room is True


def test_room_link_caller_mode_reuses_the_passed_room():
    passed = object()
    link = RoomLink(endpoint_config={}, room=passed)
    assert link._external is False
    assert link._room is passed
    assert link._owns_room is False


def test_room_link_caller_mode_without_room_owns_one():
    link = RoomLink(endpoint_config={})
    assert link._owns_room is True


def test_bridge_link_publishes_a_monitor_track():
    link = BridgeLink(endpoint_config={"url": "ws://localhost:9999/target"})
    caps = link.capabilities()
    assert isinstance(caps, TargetLinkCapabilities)
    assert caps.provides_monitor_track is True
