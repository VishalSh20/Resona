"""Caller media engine.

Audio helpers used by the runner and caller: an :class:`AudioSource` contract, a
sample-rate :class:`Resampler`, an energy-based :class:`VAD`, and the
:class:`TTS` component that turns caller text into audio while emitting the
canonical ``caller.media.*`` / ``caller.speech.*`` / ``caller.audible.*`` events.

All three clock domains are distinct and preserved: the runner monotonic clock,
the media/RTP timestamp carried by the audio, and the wall clock. None is
assumed to equal another.
"""

from __future__ import annotations

import array
import math
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from voiceeval.runtime.connections import AudioChunk

SAMPLE_WIDTH_BYTES = 2  # s16le
_SILENCE_THRESHOLD = 0.01


def pcm_to_wav(pcm: bytes, *, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap raw little-endian 16-bit PCM in a minimal RIFF/WAVE container.

    Used to make recorded captures directly playable; the header is the
    canonical 44-byte ``fmt ``/``data`` layout.
    """
    byte_rate = sample_rate * channels * SAMPLE_WIDTH_BYTES
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack(
        "<IHHIIHH",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        channels * SAMPLE_WIDTH_BYTES,
        SAMPLE_WIDTH_BYTES * 8,
    )
    header += b"data" + struct.pack("<I", len(pcm))
    return header + pcm


@runtime_checkable
class AudioSource(Protocol):
    """A pull-based source of caller audio frames."""

    def read(self, num_frames: int) -> AsyncIterator[AudioChunk]: ...


def _pcm_samples(data: bytes) -> array.array:
    samples = array.array("h")
    usable = len(data) - (len(data) % SAMPLE_WIDTH_BYTES)
    samples.frombytes(data[:usable])
    return samples


def _rms(samples: array.array) -> float:
    if not samples:
        return 0.0
    peak = max(1, 32767)
    total = sum((sample / peak) ** 2 for sample in samples)
    return math.sqrt(total / len(samples))


class Resampler:
    """Linear-interpolation PCM s16le resampler (mono)."""

    @staticmethod
    def resample(chunk: AudioChunk, target_rate: int) -> AudioChunk:
        if chunk.sample_rate == target_rate or len(chunk) == 0:
            return chunk
        samples = _pcm_samples(chunk.data)
        if len(samples) == 0:
            return AudioChunk(
                data=b"",
                sample_rate=target_rate,
                channels=chunk.channels,
                format=chunk.format,
            )
        ratio = target_rate / chunk.sample_rate
        out_count = max(1, int(len(samples) * ratio))
        resampled = array.array("h", bytes(out_count * SAMPLE_WIDTH_BYTES))
        for i in range(out_count):
            position = i / ratio
            left = int(position)
            right = min(left + 1, len(samples) - 1)
            frac = position - left
            value = samples[left] * (1 - frac) + samples[right] * frac
            resampled[i] = int(max(-32768, min(32767, value)))
        return AudioChunk(
            data=resampled.tobytes(),
            sample_rate=target_rate,
            channels=chunk.channels,
            format=chunk.format,
            duration_ms=int(len(resampled) * 1000 / target_rate),
        )


@dataclass(frozen=True)
class VadEvent:
    kind: str  # "speech_start" | "speech_end"
    monotonic_ms: int


class VAD:
    """Energy-based voice activity detector with hangover.

    Deterministic and threshold-driven, so the same audio always produces the
    same speech boundaries. It is intentionally simple; a model-based VAD can be
    swapped in behind the same interface.
    """

    def __init__(
        self,
        *,
        threshold: float = _SILENCE_THRESHOLD,
        hangover_frames: int = 5,
        frame_ms: int = 20,
    ) -> None:
        self._threshold = threshold
        self._hangover_frames = hangover_frames
        self._frame_ms = frame_ms
        self._speaking = False
        self._silence_run = 0
        self._elapsed_ms = 0

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def push(self, chunk: AudioChunk) -> VadEvent | None:
        rms = _rms(_pcm_samples(chunk.data))
        duration = chunk.duration_ms or self._frame_ms
        self._elapsed_ms += duration
        voiced = rms >= self._threshold

        if voiced:
            self._silence_run = 0
            if not self._speaking:
                self._speaking = True
                return VadEvent("speech_start", self._elapsed_ms)
            return None

        if self._speaking:
            self._silence_run += 1
            if self._silence_run >= self._hangover_frames:
                self._speaking = False
                return VadEvent("speech_end", self._elapsed_ms)
        return None
