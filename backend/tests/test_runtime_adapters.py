"""Target adapter tests: registry, framers/decoders, transport, WebRTC contract."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ConnectionFailedError, ValidationError
from voiceeval.runtime.adapters import (
    FakeTargetAdapter,
    FakeTargetServer,
    FrameDecoder,
    JsonProviderProtocolDecoder,
    WebSocketAdapter,
    WebRTCAdapter,
    agent_turn,
    default_script,
    get_adapter_registry,
)
from voiceeval.runtime.adapters.websocket import Frame
from voiceeval.runtime.connections import (
    AudioChunk,
    CloseReason,
    ConnectionConfig,
)
from voiceeval.runtime.events import CanonicalEventBuilder, EventType


# --- registry ----------------------------------------------------------------


def test_registry_creates_registered_adapter():
    adapter = get_adapter_registry().create("fake", "1.0.0")
    assert isinstance(adapter, FakeTargetAdapter)
    assert adapter.name == "fake"


def test_registry_rejects_unknown_adapter():
    with pytest.raises(ValidationError):
        get_adapter_registry().create("nope", "9.9.9")


def test_registry_keeps_info_lookup():
    info = get_adapter_registry().get("websocket", "1.0.0")
    assert info is not None and info.name == "websocket"


# --- config validation -------------------------------------------------------


def test_websocket_adapter_requires_url():
    with pytest.raises(ValidationError):
        WebSocketAdapter().validate_config({})


def test_websocket_adapter_rejects_non_object_headers():
    adapter = WebSocketAdapter()
    adapter.validate_config({"url": "ws://x"})
    with pytest.raises(ValidationError):
        adapter.connection_config({"url": "ws://x", "headers": "bad"})


def test_connection_config_carries_transport_settings():
    config = WebSocketAdapter(sample_rate=8000).connection_config(
        {"url": "ws://x", "channels": 2, "timeout_s": 3.5, "options": {"k": "v"}}
    )
    assert config.url == "ws://x"
    assert config.sample_rate == 8000
    assert config.channels == 2
    assert config.timeout_s == 3.5
    assert config.options == {"k": "v"}


# --- framing -----------------------------------------------------------------


def test_frame_decoder_splits_binary_into_multiple_frames():
    decoder = FrameDecoder(audio_frame_bytes=4)
    frames = decoder.decode(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09")
    assert [f.kind for f in frames] == ["audio", "audio", "audio"]
    assert frames[0].payload == b"\x01\x02\x03\x04"
    assert frames[-1].payload == b"\x09"


def test_frame_decoder_separates_explicit_frames_array():
    decoder = FrameDecoder()
    frames = decoder.decode('{"frames": [{"type": "a"}, {"type": "b"}]}')
    assert len(frames) == 2
    assert frames[0].payload == {"type": "a"}


def test_frame_decoder_plain_json_is_one_control_frame():
    frames = FrameDecoder().decode('{"type": "turn.start"}')
    assert len(frames) == 1 and frames[0].kind == "control"


def test_frame_decoder_empty_text_yields_nothing():
    assert FrameDecoder().decode("   ") == []


# --- protocol decoding -------------------------------------------------------


def test_decoder_maps_control_frame_to_observation():
    events = JsonProviderProtocolDecoder().decode(
        Frame(kind="control", payload={"type": "turn.start", "turn_id": "t1"})
    )
    assert len(events) == 1
    assert events[0].type == "turn.start"
    assert events[0].turn_id == "t1"


def test_decoder_translates_media_alias_and_counts_bytes():
    events = JsonProviderProtocolDecoder().decode(
        Frame(
            kind="control",
            payload={"type": "agent.audio", "payload": {"data": "AAAA"}},
        )
    )
    assert events[0].type == EventType.AGENT_MEDIA_CHUNK.value
    assert events[0].payload["bytes"] == 3
    assert events[0].payload["data"] == b"\x00\x00\x00"


def test_decoder_audio_frame_is_provider_raw():
    events = JsonProviderProtocolDecoder().decode(
        Frame(kind="audio", payload=b"\x00" * 8)
    )
    assert events[0].type == EventType.AGENT_MEDIA_CHUNK.value
    assert events[0].source == "provider_raw"
    assert events[0].payload["bytes"] == 8
    assert events[0].payload["data"] == b"\x00" * 8


def test_decoder_ignores_frames_without_type():
    assert JsonProviderProtocolDecoder().decode(Frame(kind="control", payload={})) == []


def test_to_canonical_assigns_increasing_sequence():
    adapter = FakeTargetAdapter()
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 0)
    raw = JsonProviderProtocolDecoder().decode(
        Frame(kind="control", payload={"type": "turn.start"})
    )[0]
    first = adapter.to_canonical(raw, builder)[0]
    second = adapter.to_canonical(raw, builder)[0]
    assert (first.sequence, second.sequence) == (1, 2)


# --- WebRTC contract ---------------------------------------------------------


def _webrtc_config(**overrides):
    config = {
        "signaling": {"url": "https://signal.example", "method": "POST"},
        "ice_servers": [{"urls": ["stun:stun.example"]}],
        "codecs": ["opus"],
        "audio_tracks": ["caller"],
    }
    config.update(overrides)
    return config


def test_webrtc_validation_accepts_well_formed_config():
    WebRTCAdapter().validate_config(_webrtc_config())


@pytest.mark.parametrize(
    "patch",
    [
        {"ice_servers": []},
        {"codecs": []},
        {"audio_tracks": []},
        {"signaling": {"url": "https://x", "method": "TRACE"}},
    ],
)
def test_webrtc_validation_rejects_incomplete_config(patch):
    with pytest.raises(ValidationError):
        WebRTCAdapter().validate_config(_webrtc_config(**patch))


def test_webrtc_execution_is_refused_not_faked():
    with pytest.raises(ConnectionFailedError):
        WebRTCAdapter().build_connection(_webrtc_config())


# --- fake target over the real transport -------------------------------------


async def test_fake_target_round_trip_over_websocket():
    server = await FakeTargetServer().start()
    try:
        adapter = FakeTargetAdapter()
        connection = adapter.build_connection({"url": server.url})
        await connection.connect(ConnectionConfig(url=server.url))

        receiver = connection.receive().__aiter__()
        greeting = await receiver.__anext__()
        assert greeting.type == "turn.start"

        await connection.send_audio(
            AudioChunk(data=b"\x00\x01" * 160, sample_rate=16000, duration_ms=20)
        )
        await connection.send_control({"type": "caller.turn.end", "turn_id": "turn_c1"})

        # Read up to (and including) the first scripted batch, which the server
        # only emits after it has consumed the caller's audio and turn boundary.
        seen_batch = False
        for _ in range(32):
            event = await receiver.__anext__()
            if event.turn_id == "turn_agent_1":
                seen_batch = True
                break
        assert seen_batch
        assert server.received_audio_bytes == len(b"\x00\x01" * 160)
        assert server.caller_turns_seen == 1

        await connection.close(CloseReason.CALLER_ENDED)
    finally:
        await server.stop()


def test_default_script_has_greeting_and_batches():
    script = default_script()
    assert script.greeting and len(script.batches) == 3
    assert agent_turn("t", text="hi")
