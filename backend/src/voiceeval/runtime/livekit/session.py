"""AgentSession assembly for the caller (migration doc §5, §6.4, §9).

LiveKit supplies the audio pipeline (VAD, STT, TTS, playout, interruption
mechanics). We take over "when to reply and what to say" in
:mod:`voiceeval.runtime.livekit.runtime`.

The LiveKit SDK is imported lazily. Exact plugin parameter names change across
1.x releases — confirm them against the pinned version in the phase-0 spike
(§14.0). Sarvam models default to ``bulbul:v3`` (TTS) and ``saaras:v4`` (STT) with
the sample rates from §9.3.
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import get_settings

CALLER_SAMPLE_RATE_WEbrtc = 24_000
CALLER_SAMPLE_RATE_NARROWBAND = 8_000


def _require_agents() -> Any:
    from voiceeval.core.errors import DependencyUnavailableError

    try:
        import livekit.agents as agents  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        raise DependencyUnavailableError(
            "livekit-agents is not installed; the LiveKit caller runtime is unavailable"
        ) from exc
    return agents


def load_silero_vad() -> Any:
    """Load the Silero VAD once per worker process at prewarm (§5, §11)."""
    try:
        from livekit.plugins import silero  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        from voiceeval.core.errors import DependencyUnavailableError

        raise DependencyUnavailableError(
            "livekit-plugins-silero is not installed"
        ) from exc
    return silero.VAD.load()


def build_sarvam_tts(
    *,
    model: str = "bulbul:v3",
    speaker: str = "shubh",
    target_language: str = "en-IN",
    sample_rate: int = CALLER_SAMPLE_RATE_WEbrtc,
    api_key: str | None = None,
) -> Any:
    try:
        from livekit.plugins import sarvam  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        from voiceeval.core.errors import DependencyUnavailableError

        raise DependencyUnavailableError(
            "livekit-plugins-sarvam is not installed"
        ) from exc
    settings = get_settings()
    # NOTE: confirm exact parameter names against the pinned plugin version.
    return sarvam.TTS(
        model=model,
        speaker=speaker,
        target_language_code=target_language,
        speech_sample_rate=sample_rate,
        api_key=api_key or settings.sarvam_api_key,
    )


def build_sarvam_stt(
    *,
    model: str = "saaras:v4",
    language: str = "unknown",
    api_key: str | None = None,
) -> Any:
    try:
        from livekit.plugins import sarvam  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        from voiceeval.core.errors import DependencyUnavailableError

        raise DependencyUnavailableError(
            "livekit-plugins-sarvam is not installed"
        ) from exc
    settings = get_settings()
    return sarvam.STT(
        model=model, language=language, api_key=api_key or settings.sarvam_api_key
    )


def build_agent_session(
    *,
    vad: Any | None = None,
    stt: Any | None = None,
    tts: Any | None = None,
    turn_detection: Any | None = None,
    llm: Any | None = None,
    sample_rate: int = CALLER_SAMPLE_RATE_WEbrtc,
) -> Any:
    """Construct an ``AgentSession`` wired to Silero VAD + Sarvam STT/TTS.

    ``llm`` is a small model used only for the bounded Analyze/Realize calls; it
    never owns state or action selection (§6.3). Interruption/endpointing defaults
    are left to the session builder; the caller's planner drives timing.
    """
    agents = _require_agents()
    kwargs: dict[str, Any] = {
        "vad": vad or load_silero_vad(),
        "stt": stt or build_sarvam_stt(),
        "tts": tts or build_sarvam_tts(sample_rate=sample_rate),
    }
    if llm is not None:
        kwargs["llm"] = llm
    if turn_detection is not None:
        kwargs["turn_detection"] = turn_detection
    return agents.AgentSession(**kwargs)


__all__ = [
    "CALLER_SAMPLE_RATE_NARROWBAND",
    "CALLER_SAMPLE_RATE_WEbrtc",
    "build_agent_session",
    "build_sarvam_stt",
    "build_sarvam_tts",
    "load_silero_vad",
]
