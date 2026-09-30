"""Provider contracts for caller speech synthesis and recognition.

Keeping TTS/ASR behind protocols means the caller loop never couples to a
vendor-specific API. A provider is a pure transport of *audio* and *text*; it
knows nothing about scenario state, turns or evaluation semantics.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from voiceeval.runtime.connections import AudioChunk


@dataclass(frozen=True)
class SynthesisRequest:
    """A unit of caller speech to synthesize.

    ``language`` is a BCP-47-ish tag (e.g. ``hi-IN``); ``voice`` selects a
    provider voice and may be ``None`` to use the provider default.
    """

    text: str
    language: str = "en-IN"
    voice: str | None = None
    sample_rate: int = 16000
    channels: int = 1


@dataclass(frozen=True)
class Transcript:
    """A recognition result.

    ``source`` records provenance so a caller-side recognition is never confused
    with a provider target transcript (see the provenance distinction in the
    runtime schema).
    """

    text: str
    is_final: bool = True
    language: str | None = None
    confidence: float | None = None
    source: str = "independent_asr"


@runtime_checkable
class TTSProvider(Protocol):
    name: str

    def synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]: ...


@runtime_checkable
class ASRProvider(Protocol):
    name: str

    def transcribe(
        self, audio: Iterable[AudioChunk], *, language: str | None = None
    ) -> AsyncIterator[Transcript]: ...
