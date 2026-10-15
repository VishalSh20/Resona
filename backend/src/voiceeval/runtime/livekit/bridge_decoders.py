"""Provider-specific WebSocket protocols for BridgeLink (§4.2, §14.3).

Each provider frames, names and encodes events differently. Rather than branch
inside the bridge, each provider gets a decoder (inbound) and, when its audio
framing differs from raw PCM, an encoder (outbound). Unknown providers fall back
to the generic JSON decoder and raw-PCM encoder.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from voiceeval.runtime.adapters.websocket import (
    Frame,
    JsonProviderProtocolDecoder,
    ProviderProtocolDecoder,
    ProviderProtocolEncoder,
    RawPcmEncoder,
)
from voiceeval.runtime.connections import AudioChunk, RawAgentEvent
from voiceeval.runtime.events import EventSource

#: Reply sent to a provider client-tool call when no tool executor is wired.
#: Returning an error keeps the agent moving instead of stalling on a call the
#: evaluation cannot satisfy.
UNSUPPORTED_TOOL_RESULT = "tool execution is not configured for this evaluation"


class VapiDecoder(ProviderProtocolDecoder):
    """Vapi websocket control protocol (``vapi.websocket``, §4.2/§14.3).

    Vapi does NOT nest message fields under ``payload`` — a control message
    carries its own keys at the top level. Only the assistant's **final**
    transcript is a decision trigger: partials are informational, and
    ``conversation-update`` snapshots are not turns at all. Audio arrives as
    binary websocket frames (handled by the frame decoder).
    """

    def decode(self, frame: Frame) -> list[RawAgentEvent]:
        if frame.kind == "audio":
            data = bytes(frame.payload)
            return [
                RawAgentEvent(
                    type="agent.media.chunk",
                    source=EventSource.PROVIDER_RAW.value,
                    monotonic_ms=frame.media_timestamp or 0,
                    payload={"data": data, "bytes": len(data)},
                    media_timestamp=frame.media_timestamp,
                )
            ]

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        message_type = payload.get("type")

        if message_type == "transcript":
            text = payload.get("transcript")
            if not isinstance(text, str) or not text.strip():
                return []
            # The caller's own transcript is not the trigger; ignore it.
            if payload.get("role") not in (None, "assistant"):
                return []
            if payload.get("transcriptType") == "partial":
                return [
                    RawAgentEvent(
                        type="target.transcript.interim",
                        source=EventSource.PROVIDER_NORMALIZED.value,
                        monotonic_ms=0,
                        payload={"text": text},
                    )
                ]
            # The provider's own caption of the assistant is provenance, NOT the
            # decision trigger: we transcribe the target's audio ourselves so the
            # caller is not at the mercy of the provider's STT (see conversation).
            return [
                RawAgentEvent(
                    type="target.transcript.final",
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload={"text": text, "provider": "vapi"},
                )
            ]

        if message_type == "speech-update":
            if payload.get("role") not in (None, "assistant"):
                return []
            status = payload.get("status")
            if status == "started":
                return [
                    RawAgentEvent(
                        type="agent.speech.start",
                        source=EventSource.PROVIDER_NORMALIZED.value,
                        monotonic_ms=0,
                        payload={},
                    )
                ]
            if status == "stopped":
                return [
                    RawAgentEvent(
                        type="agent.speech.end",
                        source=EventSource.PROVIDER_NORMALIZED.value,
                        monotonic_ms=0,
                        payload={},
                    )
                ]
            return []

        if message_type == "audio":
            # Some Vapi variants deliver audio as base64 inside a JSON control
            # message rather than a binary frame. Accept it defensively; if it is
            # absent we simply drop the message (binary audio is the common path).
            nested = payload.get("payload")
            nested = nested if isinstance(nested, dict) else {}
            encoded = (
                payload.get("audio")
                or payload.get("data")
                or nested.get("audio")
                or nested.get("data")
            )
            if not isinstance(encoded, str):
                return []
            try:
                data = base64.b64decode(encoded)
            except (ValueError, TypeError):
                return []
            if not data:
                return []
            sample_rate = (
                payload.get("sampleRate")
                or payload.get("sample_rate")
                or nested.get("sampleRate")
                or nested.get("sample_rate")
            )
            return [
                RawAgentEvent(
                    type="agent.media.chunk",
                    source=EventSource.PROVIDER_RAW.value,
                    monotonic_ms=0,
                    payload={"data": data, "bytes": len(data), "sample_rate": sample_rate},
                )
            ]

        if message_type == "hang":
            return [
                RawAgentEvent(
                    type="connection.closed",
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload={},
                )
            ]

        # conversation-update / status-update / function-call / etc. are
        # state snapshots, not conversational turns.
        return []


class RetellDecoder(JsonProviderProtocolDecoder):
    _TYPE_ALIASES = {
        **JsonProviderProtocolDecoder._TYPE_ALIASES,
        "audio": "agent.media.chunk",
        "transcript": "agent.text.final",
        "update": "agent.text.delta",
    }


class PipecatDecoder(JsonProviderProtocolDecoder):
    _TYPE_ALIASES = {
        **JsonProviderProtocolDecoder._TYPE_ALIASES,
        "audio": "agent.media.chunk",
        "text": "agent.text.final",
        "transcript": "agent.text.final",
    }


def _event_id(event: dict[str, Any]) -> str | None:
    value = event.get("event_id")
    return str(value) if value is not None else None


def _pcm_rate(fmt: Any) -> int | None:
    if isinstance(fmt, str) and fmt.startswith("pcm_"):
        try:
            return int(fmt.split("_", 1)[1])
        except (ValueError, IndexError):
            return None
    return None


class ElevenLabsDecoder(ProviderProtocolDecoder):
    """ElevenLabs Conversational AI (``wss://api.elevenlabs.io/v1/convai/conversation``).

    Server → client events carry audio as base64 under ``audio_event`` and text
    under ``agent_response_event`` / ``text_response_part``. The negotiation
    metadata names the agent's output sample rate; we track it so decoded audio
    is labelled correctly.
    """

    _CHAT_PART_TYPES = {
        "start": "agent.speech.start",
        "delta": "agent.text.delta",
        "stop": "agent.speech.end",
    }

    def __init__(self, *, sample_rate: int = 16_000) -> None:
        self._output_sample_rate = sample_rate

    def decode(self, frame: Frame) -> list[RawAgentEvent]:
        if frame.kind == "audio":
            return [
                RawAgentEvent(
                    type="agent.media.chunk",
                    source=EventSource.PROVIDER_RAW.value,
                    monotonic_ms=0,
                    payload={
                        "bytes": len(frame.payload),
                        "sample_rate": self._output_sample_rate,
                    },
                    raw=True,
                )
            ]

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        event_type = payload.get("type")

        if event_type == "conversation_initiation_metadata":
            meta = payload.get("conversation_initiation_metadata_event") or {}
            rate = _pcm_rate(meta.get("agent_output_audio_format"))
            if rate:
                self._output_sample_rate = rate
            return []

        if event_type == "audio":
            event = payload.get("audio_event") or {}
            encoded = event.get("audio_base_64")
            if not isinstance(encoded, str):
                return []
            try:
                data = base64.b64decode(encoded)
            except (ValueError, TypeError):
                return []
            return [
                RawAgentEvent(
                    type="agent.media.chunk",
                    source=EventSource.PROVIDER_RAW.value,
                    monotonic_ms=0,
                    payload={
                        "data": data,
                        "bytes": len(data),
                        "sample_rate": self._output_sample_rate,
                    },
                    provider_event_id=_event_id(event),
                    raw=True,
                )
            ]

        if event_type == "agent_response":
            event = payload.get("agent_response_event") or {}
            text = event.get("agent_response")
            if not isinstance(text, str):
                return []
            return [
                RawAgentEvent(
                    type="agent.text.final",
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload={"text": text},
                    provider_event_id=_event_id(event),
                )
            ]

        if event_type == "agent_chat_response_part":
            part = payload.get("text_response_part") or {}
            canonical = self._CHAT_PART_TYPES.get(part.get("type"))
            if canonical is None:
                return []
            text = part.get("text")
            return [
                RawAgentEvent(
                    type=canonical,
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload={"text": text} if isinstance(text, str) and text else {},
                    provider_event_id=_event_id(part),
                )
            ]

        if event_type == "interruption":
            return [
                RawAgentEvent(
                    type="turn.interrupted",
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload=dict(payload.get("interruption_event") or {}),
                )
            ]

        if event_type == "client_tool_call":
            call = payload.get("client_tool_call") or {}
            return [
                RawAgentEvent(
                    type="tool.call.start",
                    source=EventSource.PROVIDER_NORMALIZED.value,
                    monotonic_ms=0,
                    payload={
                        "tool_name": call.get("tool_name"),
                        "arguments": call.get("parameters") or {},
                        "tool_call_id": call.get("tool_call_id"),
                        "status": "pending",
                    },
                    provider_event_id=_event_id(call),
                )
            ]

        return []

    def responses(self, frame: Frame) -> list[str | bytes]:
        payload = frame.payload if isinstance(frame.payload, dict) else {}
        message_type = payload.get("type")
        if message_type == "ping":
            event_id = (payload.get("ping_event") or {}).get("event_id")
            return [json.dumps({"type": "pong", "event_id": event_id})]
        if message_type == "client_tool_call":
            call = payload.get("client_tool_call") or {}
            if call.get("expects_response"):
                return [
                    json.dumps(
                        {
                            "type": "client_tool_result",
                            "tool_call_id": call.get("tool_call_id"),
                            "result": UNSUPPORTED_TOOL_RESULT,
                            "is_error": True,
                        }
                    )
                ]
        return []


class ElevenLabsEncoder(ProviderProtocolEncoder):
    """ElevenLabs expects caller audio as base64 JSON, not raw PCM bytes."""

    def encode_audio(self, chunk: AudioChunk) -> str:
        return json.dumps(
            {"user_audio_chunk": base64.b64encode(chunk.data).decode("ascii")}
        )

    def initial_messages(self) -> list[str | bytes]:
        return [json.dumps({"type": "conversation_initiation_client_data"})]


_DECODERS: dict[str, type[ProviderProtocolDecoder]] = {
    "vapi": VapiDecoder,
    "retell": RetellDecoder,
    "pipecat": PipecatDecoder,
    "elevenlabs": ElevenLabsDecoder,
}

_ENCODERS: dict[str, type[ProviderProtocolEncoder]] = {
    "elevenlabs": ElevenLabsEncoder,
}


def register_provider_decoder(
    provider: str, decoder_cls: type[ProviderProtocolDecoder]
) -> None:
    _DECODERS[provider] = decoder_cls


def register_provider_encoder(
    provider: str, encoder_cls: type[ProviderProtocolEncoder]
) -> None:
    _ENCODERS[provider] = encoder_cls


def decoder_for_provider(provider: str | None) -> ProviderProtocolDecoder:
    if provider and provider in _DECODERS:
        return _DECODERS[provider]()
    return JsonProviderProtocolDecoder()


def encoder_for_provider(provider: str | None) -> ProviderProtocolEncoder:
    cls = _ENCODERS.get(provider) if provider else None
    return cls() if cls is not None else RawPcmEncoder()


__all__ = [
    "ElevenLabsDecoder",
    "ElevenLabsEncoder",
    "PipecatDecoder",
    "RetellDecoder",
    "VapiDecoder",
    "decoder_for_provider",
    "encoder_for_provider",
    "register_provider_decoder",
    "register_provider_encoder",
]
