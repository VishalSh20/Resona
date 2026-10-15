"""Attempt recording: per-speaker mono tracks + stereo call recording + upload keys."""

from __future__ import annotations

import struct

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.livekit.media import media_object_key
from voiceeval.runtime.livekit.recording import AttemptRecording, interleave_stereo


def _mono(samples: list[int], rate: int = 24_000) -> AudioChunk:
    return AudioChunk(data=struct.pack(f"<{len(samples)}h", *samples), sample_rate=rate)


def test_interleave_places_caller_left_agent_right():
    left = struct.pack("<2h", 100, 200)
    right = struct.pack("<2h", 7, 8)
    stereo = interleave_stereo(left, right)
    assert struct.unpack("<4h", stereo) == (100, 7, 200, 8)


def test_interleave_pads_the_shorter_track():
    left = struct.pack("<1h", 5)
    right = struct.pack("<3h", 1, 2, 3)
    stereo = interleave_stereo(left, right)
    assert struct.unpack("<6h", stereo) == (5, 1, 0, 2, 0, 3)


def test_attempt_recording_seals_three_wav_artifacts():
    recording = AttemptRecording(sample_rate=24_000)
    recording.append_caller(_mono([1, 2, 3]))
    recording.append_agent(_mono([4, 5, 6]))
    records = recording.finalize()

    by_track = {r.track: r for r in records}
    assert set(by_track) == {"caller", "agent", "mixed"}
    assert {r.format for r in records} == {"wav"}
    assert by_track["caller"].channels == 1
    assert by_track["agent"].channels == 1
    assert by_track["mixed"].channels == 2
    assert by_track["mixed"].representation == "mixed"
    # 44-byte WAV header + 3 stereo frames * 2 channels * 2 bytes
    assert by_track["mixed"].size_bytes == 44 + 12
    # RIFF/WAVE container wrapping the exact PCM the recorder captured.
    raw = struct.pack("<3h", 1, 2, 3)
    assert by_track["caller"].data[:4] == b"RIFF"
    assert by_track["caller"].data[8:12] == b"WAVE"
    assert by_track["caller"].data[44:] == raw


def test_wav_header_carries_rate_and_channels():
    recording = AttemptRecording(sample_rate=24_000)
    recording.append_caller(_mono([1, 2, 3, 4]))
    recording.append_agent(_mono([5, 6, 7, 8]))
    mixed = next(r for r in recording.finalize() if r.track == "mixed")
    fmt = struct.unpack("<IHHIIHH", mixed.data[16:36])
    assert fmt[1] == 1  # PCM
    assert fmt[2] == 2  # channels (stereo)
    assert fmt[3] == 24_000  # sample rate
    assert fmt[6] == 16  # bits per sample


def test_attempt_recording_resamples_to_capture_rate():
    recording = AttemptRecording(sample_rate=24_000)
    # 50ms of 8kHz mono -> resampled to 24kHz.
    recording.append_agent(_mono([1] * 400, rate=8_000))
    records = recording.finalize()
    agent = next(r for r in records if r.track == "agent")
    assert agent.sample_rate == 24_000
    assert agent.duration_ms >= 40


def test_media_object_key_is_content_addressed():
    from voiceeval.runtime.media.recorder import MediaArtifactRecord

    record = MediaArtifactRecord(
        track="mixed",
        representation="mixed",
        format="wav",
        sample_rate=24_000,
        channels=2,
        duration_ms=10,
        size_bytes=4,
        sha256="abcdef0123456789",
    )
    assert media_object_key("att_1", record) == "media/att_1/mixed-mixed-abcdef012345.wav"
