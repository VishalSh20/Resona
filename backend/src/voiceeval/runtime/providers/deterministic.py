"""Deterministic in-process speech providers.

These back the local/test runtime: they produce stable, reproducible audio and
transcripts with no network, no credentials and no timing jitter, so the whole
caller loop can be exercised end-to-end. They are *not* used to score anything;
they only stand in for a real provider.
"""

from __future__ import annotations

import math
import struct
from collections.abc import AsyncIterator, Iterable

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.providers.base import SynthesisRequest, Transcript

_TWO_PI = 2.0 * math.pi


def pcm_s16le_tone(
    frequency_hz: float, duration_ms: int, *, sample_rate: int, amplitude: float = 0.2
) -> bytes:
    """Deterministic little-endian 16-bit PCM tone (mono)."""
    sample_count = max(1, int(sample_rate * duration_ms / 1000))
    peak = int(max(0.0, min(1.0, amplitude)) * 32767)
    samples = bytearray()
    for n in range(sample_count):
        value = int(peak * math.sin(_TWO_PI * frequency_hz * n / sample_rate))
        samples += struct.pack("<h", value)
    return bytes(samples)


def pcm_s16le_silence(duration_ms: int, *, sample_rate: int) -> bytes:
    sample_count = max(1, int(sample_rate * duration_ms / 1000))
    return b"\x00\x00" * sample_count


class DeterministicTTS:
    """Synthesizes a fixed-duration tone per word.

    Duration is derived from the text length so different utterances are
    distinguishable while remaining fully reproducible.
    """

    name = "deterministic_tts"

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        chunk_ms: int = 20,
        ms_per_char: int = 12,
        max_duration_ms: int = 4000,
        frequency_hz: float = 220.0,
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_ms
        self._ms_per_char = ms_per_char
        self._max_duration_ms = max_duration_ms
        self._frequency_hz = frequency_hz

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        sample_rate = request.sample_rate or self._sample_rate
        duration_ms = min(
            self._max_duration_ms,
            max(self._chunk_ms, len(request.text) * self._ms_per_char),
        )
        audio = pcm_s16le_tone(
            self._frequency_hz, duration_ms, sample_rate=sample_rate
        )
        # Emit fixed-size frames; a single synthesis is many frames, never one.
        frame_bytes = int(sample_rate * self._chunk_ms / 1000) * 2
        for offset in range(0, len(audio), frame_bytes):
            frame = audio[offset : offset + frame_bytes]
            if not frame:
                continue
            yield AudioChunk(
                data=frame,
                sample_rate=sample_rate,
                channels=request.channels,
                duration_ms=self._chunk_ms,
            )


class DeterministicASR:
    """Recognizes a configured mapping, falling back to an empty final result.

    Caller-side ASR is only a sanity check of the caller's own audio; the
    authoritative transcripts come from the target provider. This implementation
    exists so the media path is exercised deterministically.
    """

    name = "deterministic_asr"

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._mapping = dict(mapping or {})

    async def transcribe(
        self, audio: Iterable[AudioChunk], *, language: str | None = None
    ) -> AsyncIterator[Transcript]:
        total_bytes = sum(len(chunk) for chunk in audio)
        key = str(total_bytes)
        text = self._mapping.get(key, "")
        yield Transcript(
            text=text,
            is_final=True,
            language=language,
            confidence=1.0 if text else None,
        )
