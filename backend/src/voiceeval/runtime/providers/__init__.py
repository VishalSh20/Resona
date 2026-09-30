"""Caller speech providers (TTS/ASR).

The caller runtime depends on provider *interfaces*, never on a concrete vendor.
Sarvam (Bulbul TTS / Saaras ASR) is the v1 implementation; deterministic
in-process providers back the local/test runtime so an end-to-end call can be
exercised without a network or credentials.
"""

from voiceeval.runtime.providers.base import (
    ASRProvider,
    SynthesisRequest,
    Transcript,
    TTSProvider,
)
from voiceeval.runtime.providers.deterministic import (
    DeterministicASR,
    DeterministicTTS,
)
from voiceeval.runtime.providers.sarvam import SarvamBulbulTTS, SarvamSaarasASR

__all__ = [
    "ASRProvider",
    "DeterministicASR",
    "DeterministicTTS",
    "SarvamBulbulTTS",
    "SarvamSaarasASR",
    "SynthesisRequest",
    "TTSProvider",
    "Transcript",
]
