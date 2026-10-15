"""WHIP target link: construction, capabilities, registry (no live WebRTC)."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.livekit.target_links import WhipLink, get_target_link_registry
from voiceeval.runtime.livekit.target_links.whip import (
    WEBRTC_RATE,
    caller_audio_track_class,
)


def test_whip_link_capabilities():
    link = WhipLink(endpoint_config={"call_id": "c1", "access_token": "t"})
    caps = link.capabilities()
    assert caps.codec == "pcm_s16le"
    assert caps.sample_rate == 24_000
    assert caps.supports_dtmf is False
    assert caps.provides_monitor_track is False


def test_whip_transport_is_registered_and_creatable():
    assert "whip" in get_target_link_registry().known_names()
    link = get_target_link_registry().create(
        "whip", endpoint_config={"call_id": "c1", "access_token": "t"}, room=object()
    )
    assert link.transport == "whip"


def test_whip_proxy_url_is_built_from_the_call_id():
    link = WhipLink(
        endpoint_config={"call_id": "c1", "base_url": "https://api.retellai.com"}
    )
    assert link._proxy_url() == "https://api.retellai.com/webrtc-proxy/c1"


def test_whip_proxy_url_prefers_an_explicit_url():
    link = WhipLink(endpoint_config={"proxy_url": "https://x/webrtc-proxy/abc"})
    assert link._proxy_url() == "https://x/webrtc-proxy/abc"


async def test_whip_connect_requires_call_and_token():
    link = WhipLink(endpoint_config={})
    with pytest.raises(ValidationError):
        await link.connect()


async def test_caller_track_emits_silence_when_idle():
    track = caller_audio_track_class()(WEBRTC_RATE, 1)
    frame = await track.recv()
    assert frame.sample_rate == WEBRTC_RATE
    assert frame.samples == WEBRTC_RATE * 20 // 1000


async def test_caller_track_resamples_pushed_audio_to_48k():
    track = caller_audio_track_class()(WEBRTC_RATE, 1)
    # 100 ms of 24 kHz mono s16le.
    track.push(AudioChunk(data=b"\x10\x00" * 2400, sample_rate=24_000))
    # Drain a few frames; the resampler may need priming, so accept the first
    # non-20ms-silence frame at the right rate.
    for _ in range(6):
        frame = await track.recv()
        if frame.sample_rate != WEBRTC_RATE:
            continue
        assert frame.samples == WEBRTC_RATE * 20 // 1000
        return
    raise AssertionError("caller track never produced a frame at the wire rate")
