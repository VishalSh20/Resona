"""Stage 0 audio DSP: decode, VAD, alignment, overlap, bleed (spec §2.2)."""

from __future__ import annotations

import io
import wave

import numpy as np

from voiceeval.judging.stage0.alignment import estimate_alignment
from voiceeval.judging.stage0.bleed import detect_bleed
from voiceeval.judging.stage0.overlap import compute_overlap
from voiceeval.judging.stage0.vad import energy_vad, run_vad
from voiceeval.judging.stage0.wav import decode_wav, validate_riff

SR = 16_000


def wav_bytes(samples: np.ndarray, sample_rate: int = SR) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def tone(duration_ms: int, *, amplitude: float = 0.5) -> np.ndarray:
    n = int(SR * duration_ms / 1000)
    t = np.arange(n) / SR
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def silence(duration_ms: int) -> np.ndarray:
    return np.zeros(int(SR * duration_ms / 1000), dtype=np.float32)


def test_decode_and_validate_roundtrip():
    data = wav_bytes(tone(200))
    wav = decode_wav(data)
    assert wav.sample_rate == SR
    assert wav.channels == 1
    assert abs(wav.duration_ms - 200) <= 2
    assert validate_riff(data) == []


def test_validate_rejects_non_wav():
    assert validate_riff(b"not a wav file") == ["not a RIFF/WAVE container"]


def test_energy_vad_detects_speech_burst():
    samples = np.concatenate([silence(300), tone(500), silence(300)])
    result = energy_vad(samples, SR, frame_ms=10, hangover_ms=50)
    assert result.segments
    first_start = result.segments[0][0]
    assert 250 <= first_start <= 400


def test_run_vad_falls_back_without_silero():
    result = run_vad(tone(300), SR, enable_silero=True)
    assert result.source in {"energy", "silero"}
    assert result.segments


def test_alignment_recovers_known_offset():
    n = int(SR * 2)
    base = np.random.RandomState(0).randn(n).astype(np.float32) * 0.1
    shift_samples = int(SR * 0.2)
    shifted = np.concatenate([np.zeros(shift_samples, dtype=np.float32), base])[:n]
    # The agent original and the mixed right channel disagree by 200 ms.
    result = estimate_alignment(base, base, base, shifted, SR, tolerance_ms=50)
    assert result.caller_offset_ms == 0
    assert abs(result.agent_offset_ms) >= 150
    assert not result.within_tolerance
    assert result.drift_ms >= 150


def test_overlap_detected_when_both_active():
    caller = energy_vad(tone(600), SR, hangover_ms=0)
    agent = energy_vad(np.concatenate([silence(200), tone(200)]), SR, hangover_ms=0)
    overlap = compute_overlap(caller, agent)
    assert overlap.overlap_ms > 0


def test_bleed_detected_on_cross_channel_energy():
    caller = tone(400)
    agent = silence(400)
    left = caller
    right = caller  # caller energy leaks into the agent channel
    result = detect_bleed(caller, agent, left, right, SR, bleed_tau=0.25)
    assert result.bleed_detected
