"""Build the Pipecat websocket client transport for one target connection.

Two wire protocols are supported: Pipecat's native protobuf framing (what a real
Pipecat agent serves) and the voiceeval raw-PCM/JSON protocol (the fake target).
"""

from __future__ import annotations

from typing import Any

from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.client import (
    WebsocketClientParams,
    WebsocketClientTransport,
)

from voiceeval.runtime.pipecat_caller.serializer import VoiceEvalFrameSerializer

VOICE_EVAL_PROTOCOL = "voiceeval"


def serializer_for(protocol: str, *, sample_rate: int) -> FrameSerializer:
    if protocol == VOICE_EVAL_PROTOCOL:
        return VoiceEvalFrameSerializer(sample_rate=sample_rate)
    return ProtobufFrameSerializer()


def build_websocket_transport(
    *,
    url: str,
    sample_rate: int,
    headers: dict[str, str] | None = None,
    protocol: str = "protobuf",
) -> Any:
    """A websocket transport framing audio in the target's wire protocol."""
    params = WebsocketClientParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_sample_rate=sample_rate,
        audio_out_sample_rate=sample_rate,
        add_wav_header=False,
        additional_headers=headers or None,
        serializer=serializer_for(protocol, sample_rate=sample_rate),
    )
    return WebsocketClientTransport(url, params=params)


__all__ = ["VOICE_EVAL_PROTOCOL", "build_websocket_transport", "serializer_for"]
