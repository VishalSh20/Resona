"""Frame serializer bridging Pipecat frames to the voiceeval websocket protocol.

The generic target speaks a JSON control protocol carrying base64 PCM audio
(``{"type": "agent.audio", "payload": {"data": ...}}``) and expects raw PCM for
inbound audio. This serializer is the Pipecat counterpart of
:class:`voiceeval.runtime.adapters.websocket.RawPcmEncoder` /
``JsonProviderProtocolDecoder``.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

_AGENT_AUDIO_TYPE = "agent.audio"


class VoiceEvalFrameSerializer(FrameSerializer):
    """Serialize/deserialize frames for the generic websocket target."""

    def __init__(
        self, *, sample_rate: int, num_channels: int = 1, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._sample_rate = sample_rate
        self._num_channels = num_channels

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        if isinstance(
            frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)
        ):
            return json.dumps(frame.message)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, (bytes, bytearray)):
            return self._audio_frame(bytes(data))

        text = data.strip() if isinstance(data, str) else ""
        if not text:
            return None
        try:
            message = json.loads(text)
        except (ValueError, TypeError):
            return None
        if not isinstance(message, dict) or message.get("type") != _AGENT_AUDIO_TYPE:
            return None
        encoded = (message.get("payload") or {}).get("data")
        if not isinstance(encoded, str):
            return None
        try:
            audio = base64.b64decode(encoded)
        except (ValueError, TypeError):
            return None
        return self._audio_frame(audio)

    def _audio_frame(self, audio: bytes) -> InputAudioRawFrame:
        return InputAudioRawFrame(
            audio=audio,
            sample_rate=self._sample_rate,
            num_channels=self._num_channels,
        )


__all__ = ["VoiceEvalFrameSerializer"]
