"""Sarvam TTS resilience: streaming → REST sentence-chunked → alternate (§9.3).

Reported Sarvam issues (intermittent unrecoverable streaming errors, WAV header
problems) mean the streaming path cannot be the only one. This adapter tries the
streaming provider first, then a REST (sentence-chunked) provider, then an
alternate provider for the same language. A failed provider is reported through
``on_error`` so the caller can emit ``caller.tts_error`` and retry once.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
from typing import Protocol

from voiceeval.runtime.providers.base import SynthesisRequest, TTSProvider

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")

ErrorHook = Callable[[str, Exception], None]


class SupportsSynthesize(Protocol):
    name: str

    def synthesize(self, request: SynthesisRequest) -> AsyncIterator: ...


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text or "") if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


class SentenceChunkedTTS:
    """Wraps a REST-only provider by synthesizing one sentence at a time."""

    def __init__(self, provider: TTSProvider) -> None:
        self._provider = provider
        self.name = f"{provider.name}_sentences"

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator:
        for sentence in _split_sentences(request.text):
            sentence_request = SynthesisRequest(
                text=sentence,
                language=request.language,
                voice=request.voice,
                sample_rate=request.sample_rate,
                channels=request.channels,
            )
            async for chunk in self._provider.synthesize(sentence_request):
                yield chunk


class FallbackTTSProvider:
    def __init__(
        self,
        primary: TTSProvider,
        *,
        rest: TTSProvider | None = None,
        alternate: TTSProvider | None = None,
        on_error: ErrorHook | None = None,
    ) -> None:
        self.name = "sarvam_fallback"
        self._primary = primary
        self._rest = SentenceChunkedTTS(rest) if rest is not None else None
        self._alternate = alternate
        self._on_error = on_error

    async def synthesize(self, request: SynthesisRequest) -> AsyncIterator:
        providers = [self._primary, self._rest, self._alternate]
        last_error: Exception | None = None
        for provider in providers:
            if provider is None:
                continue
            try:
                async for chunk in provider.synthesize(request):
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - deliberate provider fallback
                last_error = exc
                if self._on_error is not None:
                    self._on_error(provider.name, exc)
        if last_error is not None:
            raise last_error


__all__ = ["FallbackTTSProvider", "SentenceChunkedTTS"]
