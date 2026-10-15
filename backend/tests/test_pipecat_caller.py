"""Pipecat caller: frame serialization, prompt, context resolution and queue SQL."""

from __future__ import annotations

import base64
import json
import struct
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    InputAudioRawFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
)
from sqlalchemy.dialects import postgresql

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.pipecat_caller import context as context_module
from voiceeval.runtime.pipecat_caller.context import load_caller_context, resolve_protocol
from voiceeval.runtime.pipecat_caller.queue import pending_attempts_statement
from voiceeval.runtime.pipecat_caller.serializer import VoiceEvalFrameSerializer
from voiceeval.runtime.pipecat_caller.settings import PipecatCallerSettings
from voiceeval.runtime.scenario import parse_scenario

SCENARIO = {
    "motive": {"objective": "Get help with my locked account"},
    "facts": [{"id": "account_id", "value": "AC-1234"}],
    "language": {"primary": "hi-IN", "secondary": "en-IN"},
}

SCENARIO_DICT = parse_scenario(SCENARIO)
PERSONA = PersonaProfile(
    version="persona.v1", traits=("friendly", "patient"), primary_language="hi-IN"
)


def _settings(**overrides) -> PipecatCallerSettings:
    return PipecatCallerSettings(_env_file=None, **overrides)


# ---------------------------------------------------------------- serializer


async def test_serialize_output_audio_is_raw_pcm():
    serializer = VoiceEvalFrameSerializer(sample_rate=16_000)
    pcm = struct.pack("<4h", 1, 2, 3, 4)
    payload = await serializer.serialize(
        OutputAudioRawFrame(audio=pcm, sample_rate=16_000, num_channels=1)
    )
    assert payload == pcm


async def test_serialize_control_message_is_json():
    serializer = VoiceEvalFrameSerializer(sample_rate=16_000)
    payload = await serializer.serialize(
        OutputTransportMessageFrame(message={"type": "caller.turn.end"})
    )
    assert json.loads(payload) == {"type": "caller.turn.end"}


async def test_deserialize_decodes_base64_agent_audio():
    serializer = VoiceEvalFrameSerializer(sample_rate=16_000)
    pcm = struct.pack("<3h", 5, 6, 7)
    message = json.dumps(
        {
            "type": "agent.audio",
            "payload": {"data": base64.b64encode(pcm).decode("ascii")},
        }
    )
    frame = await serializer.deserialize(message)
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.audio == pcm
    assert frame.sample_rate == 16_000


async def test_deserialize_binary_is_raw_pcm():
    serializer = VoiceEvalFrameSerializer(sample_rate=16_000)
    frame = await serializer.deserialize(b"\x01\x00\x02\x00")
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.audio == b"\x01\x00\x02\x00"


async def test_deserialize_ignores_non_audio_and_garbage():
    serializer = VoiceEvalFrameSerializer(sample_rate=16_000)
    assert await serializer.deserialize(json.dumps({"type": "turn.start"})) is None
    assert await serializer.deserialize("not-json") is None


# ------------------------------------------------------------------ context


def _bundle(transport: str, adapter_name: str | None = None, **endpoint) -> SimpleNamespace:
    target_link = {
        "transport": transport,
        "endpoint_config": {"url": "ws://target/target", **endpoint},
    }
    if adapter_name is not None:
        target_link["adapter_name"] = adapter_name
    return SimpleNamespace(
        target_link=target_link,
        scenario=SCENARIO_DICT,
        persona=PERSONA,
    )


async def test_load_caller_context_extracts_websocket_target(monkeypatch):
    async def _loader(session, attempt_id):
        return _bundle("websocket", adapter_name="fake", headers={"X-Auth": "token"})

    monkeypatch.setattr(context_module, "load_attempt_context", _loader)
    context = await load_caller_context(None, "att_1", _settings())
    assert context.target_ws_url == "ws://target/target"
    assert context.target_headers == {"X-Auth": "token"}
    assert context.in_sample_rate == 16_000
    # A generic websocket adapter speaks the voiceeval protocol by default.
    assert context.target_protocol == "voiceeval"
    assert "account_id" in context.script.scenario
    assert "friendly" in context.script.persona


async def test_load_caller_context_rejects_non_websocket_transport(monkeypatch):
    async def _loader(session, attempt_id):
        return _bundle("sip")

    monkeypatch.setattr(context_module, "load_attempt_context", _loader)
    with pytest.raises(ValidationError):
        await load_caller_context(None, "att_1", _settings())


def test_resolve_protocol_precedence():
    settings = _settings(protocol="protobuf")
    # An explicit target choice always wins.
    assert resolve_protocol({"adapter_name": "fake"}, {"protocol": "protobuf"}, settings) == "protobuf"
    # A voiceeval adapter implies the voiceeval protocol.
    assert resolve_protocol({"adapter_name": "websocket"}, {}, settings) == "voiceeval"
    # Otherwise the configured default applies (a real Pipecat agent).
    assert resolve_protocol({}, {}, settings) == "protobuf"


# ---------------------------------------------------------------- transport


def test_serializer_is_selected_by_protocol():
    from pipecat.serializers.protobuf import ProtobufFrameSerializer

    from voiceeval.runtime.pipecat_caller.transport import serializer_for

    assert isinstance(
        serializer_for("voiceeval", sample_rate=16_000), VoiceEvalFrameSerializer
    )
    assert isinstance(
        serializer_for("protobuf", sample_rate=16_000), ProtobufFrameSerializer
    )


# -------------------------------------------------------------------- queue


def test_pending_attempts_statement_locks_and_filters_transport():
    sql = str(
        pending_attempts_statement(4, ("websocket", "fake")).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FOR UPDATE OF call_attempt SKIP LOCKED" in sql
    assert "target_snapshot" in sql and "->>" in sql
    assert "LIMIT" in sql
