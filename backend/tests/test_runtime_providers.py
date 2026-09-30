"""Provider tests: deterministic providers, WAV wrapping, Sarvam config guards.

These are offline: the live Sarvam streaming path is verified separately.
"""

from __future__ import annotations

import struct

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.providers.base import SynthesisRequest
from voiceeval.runtime.providers.deterministic import (
    DeterministicASR,
    DeterministicTTS,
)
from voiceeval.runtime.providers.sarvam import (
    DEFAULT_ASR_MODEL,
    DEFAULT_TTS_MODEL,
    SarvamConnection,
    pcm_to_wav,
)


# --- deterministic providers -------------------------------------------------


async def test_deterministic_tts_is_reproducible():
    tts = DeterministicTTS()
    request = SynthesisRequest(text="hello", language="en-IN", sample_rate=16000)
    first = [chunk.data async for chunk in tts.synthesize(request)]
    second = [chunk.data async for chunk in tts.synthesize(request)]
    assert first == second
    assert len(first) > 1  # a synthesis is many frames, not one


async def test_deterministic_tts_duration_depends_on_text():
    tts = DeterministicTTS()
    short = [
        c async for c in tts.synthesize(SynthesisRequest(text="hi", sample_rate=16000))
    ]
    long = [
        c
        async for c in tts.synthesize(
            SynthesisRequest(text="a much longer sentence here", sample_rate=16000)
        )
    ]
    assert sum(map(len, long)) > sum(map(len, short))


async def test_deterministic_asr_maps_by_byte_length():
    asr = DeterministicASR(mapping={"320": "hello"})
    audio = [AudioChunk(data=b"\x00" * 320, sample_rate=16000)]
    results = [t async for t in asr.transcribe(audio)]
    assert results[0].text == "hello"
    assert results[0].source == "independent_asr"


# --- WAV wrapping ------------------------------------------------------------


def test_pcm_to_wav_produces_valid_riff_header():
    pcm = b"\x01\x02" * 8  # 16 bytes
    wav = pcm_to_wav(pcm, sample_rate=16000, channels=1)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[12:16] == b"fmt "
    assert wav[36:40] == b"data"
    assert struct.unpack("<I", wav[4:8])[0] == 36 + len(pcm)
    assert struct.unpack("<I", wav[40:44])[0] == len(pcm)
    # fmt chunk: audio format, channels, sample rate, byte rate, block align, bits
    assert struct.unpack("<HHIIHH", wav[20:36]) == (1, 1, 16000, 32000, 2, 16)
    assert wav[44:] == pcm


def test_pcm_to_wav_handles_stereo_block_align():
    wav = pcm_to_wav(b"\x00" * 8, sample_rate=8000, channels=2)
    assert struct.unpack("<HHIIHH", wav[20:36]) == (1, 2, 8000, 32000, 4, 16)


# --- Sarvam configuration guards --------------------------------------------


def test_sarvam_defaults_are_current_models():
    connection = SarvamConnection()
    assert connection.tts_model == DEFAULT_TTS_MODEL == "bulbul:v3"
    assert connection.asr_model == DEFAULT_ASR_MODEL == "saaras:v4"


def test_sarvam_requires_api_key():
    with pytest.raises(ValidationError):
        SarvamConnection(api_key=None).require_key()


def test_sarvam_client_construction_without_key_raises():
    with pytest.raises(ValidationError):
        SarvamConnection(api_key=None).client()
