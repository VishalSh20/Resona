"""Pipecat service construction: Sarvam STT/TTS, OpenRouter LLM, Silero VAD.

The plugin modules are imported lazily so that importing this package stays
cheap. The installed plugins expose the non-deprecated ``Settings`` API, which is
what we use — the sample's ``InputParams``/``params`` path is deprecated since
0.0.105 and is removed in 2.0.0.
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import DependencyUnavailableError
from voiceeval.runtime.pipecat_caller.settings import PipecatCallerSettings


def _require(module: str, extra: str) -> Any:
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - depends on optional extras
        raise DependencyUnavailableError(
            f"the pipecat caller needs the '{extra}' pipecat extra (missing {module})"
        ) from exc


def _pipecat_language(code: str) -> Any | None:
    """Map a BCP-47 tag (``hi-IN``) to a pipecat ``Language``, if it is known."""
    language = _require("pipecat.transcriptions.language", "sarvam")
    try:
        return language.Language(code)
    except ValueError:
        return None


def build_stt(caller: PipecatCallerSettings, core: Settings | None = None) -> Any:
    if not (core or get_settings()).sarvam_api_key:
        raise DependencyUnavailableError("SARVAM_API_KEY is required for the STT stage")
    module = _require("pipecat.services.sarvam.stt", "sarvam")
    settings = module.SarvamSTTService.Settings(
        model=caller.stt_model, language=_pipecat_language(caller.language)
    )
    return module.SarvamSTTService(
        api_key=(core or get_settings()).sarvam_api_key,
        sample_rate=caller.in_sample_rate,
        settings=settings,
    )


def build_tts(caller: PipecatCallerSettings, core: Settings | None = None) -> Any:
    if not (core or get_settings()).sarvam_api_key:
        raise DependencyUnavailableError("SARVAM_API_KEY is required for the TTS stage")
    module = _require("pipecat.services.sarvam.tts", "sarvam")
    settings = module.SarvamTTSService.Settings(
        model=caller.tts_model,
        voice=caller.tts_voice,
        language=_pipecat_language(caller.language) or caller.language,
    )
    return module.SarvamTTSService(
        api_key=(core or get_settings()).sarvam_api_key,
        sample_rate=caller.out_sample_rate,
        settings=settings,
    )


def build_llm(core: Settings | None = None, *, system_instruction: str | None = None) -> Any:
    settings = core or get_settings()
    if not settings.openrouter_api_key:
        raise DependencyUnavailableError(
            "OPENROUTER_API_KEY is required for the LLM stage"
        )
    module = _require("pipecat.services.openai.llm", "openai")
    llm_settings = module.OpenAILLMService.Settings(
        model=settings.openrouter_model, system_instruction=system_instruction
    )
    return module.OpenAILLMService(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        settings=llm_settings,
    )


def build_vad(sample_rate: int) -> Any:
    module = _require("pipecat.audio.vad.silero", "silero")
    vad_params = _require("pipecat.audio.vad.vad_analyzer", "silero")
    return module.SileroVADAnalyzer(
        sample_rate=sample_rate,
        params=vad_params.VADParams(stop_secs=0.5),
    )


__all__ = ["build_llm", "build_stt", "build_tts", "build_vad"]
