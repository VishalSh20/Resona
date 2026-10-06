"""ASR guard (spec §5.5).

When the agent seems to mishear a low-confidence caller turn, re-listen to the
clean caller clip with an audio-capable model and re-run the probe on the
corrected snippet. When the audio differs from the ASR text the failure is
attributed to ASR (``caveat: asr_error``) and the probe is not penalized.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from voiceeval.core.config import get_settings

ReListenFn = Callable[[str, int | None, int | None], Awaitable[str | None]]


class ASRGuard:
    def __init__(self, re_listen: ReListenFn | None = None, *, threshold: float | None = None) -> None:
        self._re_listen = re_listen
        self._threshold = threshold if threshold is not None else get_settings().asr_conf_tau

    def should_trigger(self, asr_confidence: float | None) -> bool:
        return asr_confidence is not None and asr_confidence < self._threshold

    async def correct(self, text: str, start_ms: int | None, end_ms: int | None) -> tuple[str, bool]:
        """Return ``(corrected_text, is_asr_error)``."""
        if self._re_listen is None:
            return text, False
        corrected = await self._re_listen(text, start_ms, end_ms)
        if corrected is None or corrected.strip() == text.strip():
            return text, False
        return corrected, True


__all__ = ["ASRGuard", "ReListenFn"]
