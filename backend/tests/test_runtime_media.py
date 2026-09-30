"""Media engine tests: resampling, VAD, recording, caller TTS events."""

from __future__ import annotations

import pytest

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.events import CanonicalEventBuilder, EventType
from voiceeval.runtime.media import MediaRecorder, Resampler, TTS, VAD
from voiceeval.runtime.providers.deterministic import (
    DeterministicTTS,
    pcm_s16le_silence,
    pcm_s16le_tone,
)


def _chunk(ms=20, rate=16000, tone=True):
    data = (
        pcm_s16le_tone(220.0, ms, sample_rate=rate)
        if tone
        else pcm_s16le_silence(ms, sample_rate=rate)
    )
    return AudioChunk(data=data, sample_rate=rate, duration_ms=ms)


def test_resampler_halves_sample_count():
    chunk = _chunk(ms=20, rate=16000)
    resampled = Resampler.resample(chunk, 8000)
    assert resampled.sample_rate == 8000
    assert len(resampled) == len(chunk) // 2


def test_resampler_is_identity_at_same_rate():
    chunk = _chunk()
    assert Resampler.resample(chunk, 16000) is chunk


def test_vad_detects_speech_start_and_end():
    vad = VAD(hangover_frames=2)
    assert vad.push(_chunk(tone=True)).kind == "speech_start"
    assert vad.push(_chunk(tone=True)) is None
    assert vad.push(_chunk(tone=False)) is None  # hangover
    assert vad.push(_chunk(tone=False)).kind == "speech_end"


def test_media_recorder_hashes_and_finalizes():
    recorder = MediaRecorder(track="caller")
    recorder.append(_chunk())
    recorder.append(_chunk())
    record = recorder.finalize()
    assert record.size_bytes == 1280
    assert record.duration_ms == 40
    assert len(record.sha256) == 64
    assert record.track == "caller"


def test_media_recorder_rejects_double_finalize_and_late_append():
    recorder = MediaRecorder(track="caller")
    recorder.append(_chunk())
    recorder.finalize()
    with pytest.raises(RuntimeError):
        recorder.finalize()
    with pytest.raises(RuntimeError):
        recorder.append(_chunk())


async def test_tts_emits_canonical_events_and_records_audio():
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 0)
    recorder = MediaRecorder(track="caller")
    tts = TTS(DeterministicTTS(), builder, recorder=recorder)

    result = await tts.speak("Hello there", language="en-IN", turn_id="turn_1")

    types = [e.type for e in result.events]
    assert EventType.CALLER_MEDIA_START.value in types
    assert EventType.CALLER_MEDIA_CHUNK.value in types
    assert EventType.CALLER_MEDIA_END.value in types
    assert EventType.CALLER_AUDIBLE_START.value in types
    assert EventType.CALLER_AUDIBLE_END.value in types
    assert result.chunks and recorder.size_bytes > 0
    # Media timestamps advance within a single utterance.
    timestamps = [e.media_timestamp for e in result.events if e.media_timestamp]
    assert timestamps == sorted(timestamps)
