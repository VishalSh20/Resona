"""Caller TTS component.

Wraps a :class:`TTSProvider` and, as it streams audio, emits the canonical caller
media/speech/audible events with an explicitly assigned media timestamp. The
component never guesses clocks: the media timestamp advances by the synthesized
frame duration, while the runner monotonic clock is stamped by the event builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.events import (
    CanonicalEvent,
    CanonicalEventBuilder,
    EventSource,
    EventType,
)
from voiceeval.runtime.media.audio import Resampler
from voiceeval.runtime.media.recorder import MediaRecorder
from voiceeval.runtime.providers.base import SynthesisRequest, TTSProvider


@dataclass
class SpeechResult:
    events: list[CanonicalEvent] = field(default_factory=list)
    chunks: list[AudioChunk] = field(default_factory=list)
    text: str = ""
    language: str = "en-IN"


class TTS:
    """Streams caller speech and records the canonical events it produces."""

    def __init__(
        self,
        provider: TTSProvider,
        builder: CanonicalEventBuilder,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        recorder: MediaRecorder | None = None,
    ) -> None:
        self._provider = provider
        self._builder = builder
        self._sample_rate = sample_rate
        self._channels = channels
        self._recorder = recorder

    async def speak(
        self,
        text: str,
        *,
        language: str = "en-IN",
        voice: str | None = None,
        turn_id: str | None = None,
    ) -> SpeechResult:
        result = SpeechResult(text=text, language=language)
        request = SynthesisRequest(
            text=text,
            language=language,
            voice=voice,
            sample_rate=self._sample_rate,
            channels=self._channels,
        )

        result.events.append(
            self._builder.build(
                EventType.CALLER_MEDIA_START,
                source=EventSource.CALLER,
                payload={"text": text, "language": language},
                turn_id=turn_id,
            )
        )
        media_timestamp = 0
        audible_open = False

        async for chunk in self._provider.synthesize(request):
            if chunk.sample_rate != self._sample_rate:
                chunk = Resampler.resample(chunk, self._sample_rate)
            if self._recorder is not None:
                self._recorder.append(chunk)
            result.chunks.append(chunk)

            result.events.append(
                self._builder.build(
                    EventType.CALLER_MEDIA_CHUNK,
                    source=EventSource.CALLER,
                    payload={
                        "bytes": len(chunk.data),
                        "sample_rate": chunk.sample_rate,
                        "channels": chunk.channels,
                    },
                    media_timestamp=media_timestamp,
                    turn_id=turn_id,
                )
            )
            media_timestamp += chunk.duration_ms or 0

            if not audible_open:
                audible_open = True
                result.events.append(
                    self._builder.build(
                        EventType.CALLER_AUDIBLE_START,
                        source=EventSource.DERIVED,
                        payload={"text": text},
                        media_timestamp=0,
                        turn_id=turn_id,
                    )
                )

        if audible_open:
            result.events.append(
                self._builder.build(
                    EventType.CALLER_AUDIBLE_END,
                    source=EventSource.DERIVED,
                    payload={"text": text},
                    media_timestamp=media_timestamp,
                    turn_id=turn_id,
                )
            )

        result.events.append(
            self._builder.build(
                EventType.CALLER_MEDIA_END,
                source=EventSource.CALLER,
                payload={"duration_ms": media_timestamp},
                media_timestamp=media_timestamp,
                turn_id=turn_id,
            )
        )
        return result
