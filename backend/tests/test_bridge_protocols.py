"""ElevenLabs bridge protocol: encoder framing, decoder mapping, transport round-trip."""

from __future__ import annotations

import asyncio
import base64
import json

from websockets.asyncio.server import serve

from voiceeval.runtime.adapters.websocket import (
    Frame,
    ProviderProtocolEncoder,
    RawPcmEncoder,
    WebSocketAdapter,
)
from voiceeval.runtime.connections import AudioChunk, CloseReason, ConnectionConfig
from voiceeval.runtime.livekit.bridge_decoders import (
    ElevenLabsDecoder,
    ElevenLabsEncoder,
    decoder_for_provider,
    encoder_for_provider,
)
from voiceeval.runtime.livekit.target_links.bridge import BridgeLink

# --- encoder -----------------------------------------------------------------


def test_elevenlabs_encoder_frames_audio_as_base64_json():
    payload = ElevenLabsEncoder().encode_audio(
        AudioChunk(data=b"\x01\x02\x03", sample_rate=16000)
    )
    assert isinstance(payload, str)
    assert base64.b64decode(json.loads(payload)["user_audio_chunk"]) == b"\x01\x02\x03"


def test_elevenlabs_encoder_sends_initiation_message():
    messages = ElevenLabsEncoder().initial_messages()
    assert json.loads(messages[0])["type"] == "conversation_initiation_client_data"


def test_encoder_for_provider_registry():
    assert isinstance(encoder_for_provider("elevenlabs"), ElevenLabsEncoder)
    assert isinstance(encoder_for_provider("vapi"), RawPcmEncoder)
    assert isinstance(encoder_for_provider(None), RawPcmEncoder)
    assert isinstance(encoder_for_provider("vapi"), ProviderProtocolEncoder)


# --- decoder -----------------------------------------------------------------


def test_decoder_for_provider_knows_elevenlabs():
    assert isinstance(decoder_for_provider("elevenlabs"), ElevenLabsDecoder)


def test_elevenlabs_decoder_maps_audio_event_to_media_chunk():
    data = b"\x00\x01" * 10
    events = ElevenLabsDecoder().decode(
        Frame(
            kind="control",
            payload={
                "type": "audio",
                "audio_event": {
                    "audio_base_64": base64.b64encode(data).decode(),
                    "event_id": 1,
                },
            },
        )
    )
    assert len(events) == 1
    assert events[0].type == "agent.media.chunk"
    assert events[0].source == "provider_raw"
    assert events[0].payload["data"] == data
    assert events[0].payload["bytes"] == len(data)


def test_elevenlabs_decoder_tracks_negotiated_output_sample_rate():
    decoder = ElevenLabsDecoder()
    decoder.decode(
        Frame(
            kind="control",
            payload={
                "type": "conversation_initiation_metadata",
                "conversation_initiation_metadata_event": {
                    "agent_output_audio_format": "pcm_22050"
                },
            },
        )
    )
    events = decoder.decode(
        Frame(
            kind="control",
            payload={
                "type": "audio",
                "audio_event": {"audio_base_64": base64.b64encode(b"\x00\x00").decode()},
            },
        )
    )
    assert events[0].payload["sample_rate"] == 22050


def test_elevenlabs_decoder_maps_agent_response_and_chat_parts():
    decoder = ElevenLabsDecoder()
    response = decoder.decode(
        Frame(
            kind="control",
            payload={
                "type": "agent_response",
                "agent_response_event": {"agent_response": "hello", "event_id": 5},
            },
        )
    )[0]
    assert response.type == "agent.text.final"
    assert response.payload["text"] == "hello"

    part = decoder.decode(
        Frame(
            kind="control",
            payload={
                "type": "agent_chat_response_part",
                "text_response_part": {"type": "delta", "text": "wor", "event_id": 6},
            },
        )
    )[0]
    assert part.type == "agent.text.delta"
    assert part.payload["text"] == "wor"


def test_elevenlabs_decoder_answers_ping_with_pong():
    decoder = ElevenLabsDecoder()
    frame = Frame(
        kind="control",
        payload={"type": "ping", "ping_event": {"event_id": 42, "ping_ms": 0}},
    )
    assert decoder.decode(frame) == []
    replies = decoder.responses(frame)
    assert json.loads(replies[0]) == {"type": "pong", "event_id": 42}


def test_elevenlabs_decoder_ignores_non_canonical_events():
    decoder = ElevenLabsDecoder()
    for message_type in ("vad_score", "user_transcript", "feedback"):
        assert decoder.decode(Frame(kind="control", payload={"type": message_type})) == []


# --- transport round-trip over a real websocket ------------------------------


async def _eventually(predicate, *, timeout: float = 5.0) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return predicate()


async def test_elevenlabs_bridge_round_trip_over_websocket():
    incoming: list[dict] = []
    audio_sent = b"\x10\x20" * 40

    async def handler(ws):
        await ws.send(json.dumps({"type": "ping", "ping_event": {"event_id": 7, "ping_ms": 0}}))
        async for raw in ws:
            try:
                message = json.loads(raw)
            except (ValueError, TypeError):
                continue
            incoming.append(message)
            if "user_audio_chunk" in message:
                await ws.send(
                    json.dumps(
                        {
                            "type": "audio",
                            "audio_event": {
                                "audio_base_64": base64.b64encode(b"\xaa\xbb").decode(),
                                "event_id": 1,
                            },
                        }
                    )
                )

    server = await serve(handler, "127.0.0.1", 0, max_size=None)
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}/"
    connection = WebSocketAdapter(
        sample_rate=16000, decoder=ElevenLabsDecoder(), encoder=ElevenLabsEncoder()
    ).build_connection({"url": url})
    events = []
    try:
        await connection.connect(ConnectionConfig(url=url))

        async def reader():
            async for event in connection.receive():
                events.append(event)
                if event.type == "agent.media.chunk":
                    return

        task = asyncio.create_task(reader())
        await connection.send_audio(AudioChunk(data=audio_sent, sample_rate=16000))
        await asyncio.wait_for(task, timeout=5)
        await _eventually(lambda: any(m.get("type") == "pong" for m in incoming))

        # The encoder framed the init message and base64 audio, not raw bytes.
        assert any(
            m.get("type") == "conversation_initiation_client_data" for m in incoming
        )
        audio_messages = [m for m in incoming if "user_audio_chunk" in m]
        assert audio_messages
        assert base64.b64decode(audio_messages[0]["user_audio_chunk"]) == audio_sent

        # The transport replied to the server's ping.
        assert any(m.get("type") == "pong" and m.get("event_id") == 7 for m in incoming)

        # The decoder surfaced the agent audio as a canonical media chunk.
        chunk = next(e for e in events if e.type == "agent.media.chunk")
        assert chunk.payload["data"] == b"\xaa\xbb"
    finally:
        await connection.close(CloseReason.RUNNER_SHUTDOWN)
        server.close()
        await server.wait_closed()


# --- client tool calls -------------------------------------------------------


def test_elevenlabs_decoder_maps_client_tool_call_and_replies():
    decoder = ElevenLabsDecoder()
    frame = Frame(
        kind="control",
        payload={
            "type": "client_tool_call",
            "client_tool_call": {
                "tool_call_id": "tc1",
                "tool_name": "lookup",
                "expects_response": True,
                "parameters": {"id": "42"},
            },
        },
    )
    events = decoder.decode(frame)
    assert events[0].type == "tool.call.start"
    assert events[0].payload["tool_name"] == "lookup"
    assert events[0].payload["tool_call_id"] == "tc1"
    assert events[0].payload["arguments"] == {"id": "42"}

    reply = json.loads(decoder.responses(frame)[0])
    assert reply["type"] == "client_tool_result"
    assert reply["tool_call_id"] == "tc1"
    assert reply["is_error"] is True


def test_elevenlabs_decoder_skips_reply_when_tool_expects_no_response():
    frame = Frame(
        kind="control",
        payload={
            "type": "client_tool_call",
            "client_tool_call": {"tool_call_id": "tc2", "expects_response": False},
        },
    )
    assert ElevenLabsDecoder().responses(frame) == []


# --- binary (Vapi-style) audio through BridgeLink ----------------------------


async def test_bridge_link_delivers_binary_audio_for_vapi():
    async def handler(ws):
        await ws.send(b"\x01\x02\x03\x04")

    server = await serve(handler, "127.0.0.1", 0, max_size=None)
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}/"
    link = BridgeLink(endpoint_config={"url": url, "provider": "vapi"}, sample_rate=16000)
    try:
        await link.connect()

        async def first_chunk():
            async for chunk in link.incoming_audio():
                return chunk

        chunk = await asyncio.wait_for(first_chunk(), timeout=5)
        assert chunk.data == b"\x01\x02\x03\x04"
    finally:
        await link.close(CloseReason.RUNNER_SHUTDOWN)
        server.close()
        await server.wait_closed()
