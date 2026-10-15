"""Pipecat caller recording taps: chunk duration and direction capture."""

from __future__ import annotations

import struct

from pipecat.frames.frames import (
    InputAudioRawFrame,
    OutputAudioRawFrame,
    TextFrame,
)

from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.pipecat_caller.recording import (
    AgentAudioTap,
    CallerAudioTap,
    _to_chunk,
)


def _pcm(seconds: float, rate: int = 16_000, channels: int = 1) -> bytes:
    samples = int(seconds * rate) * channels
    return struct.pack(f"<{samples}h", *([0] * samples))


def test_to_chunk_computes_duration_from_bytes():
    chunk = _to_chunk(
        OutputAudioRawFrame(audio=_pcm(1.0), sample_rate=16_000, num_channels=1)
    )
    assert chunk.duration_ms == 1000

    stereo = _to_chunk(
        OutputAudioRawFrame(audio=_pcm(0.5, channels=2), sample_rate=16_000, num_channels=2)
    )
    assert stereo.duration_ms == 500


def test_audio_taps_target_the_right_directions():
    assert AgentAudioTap.frame_types == (InputAudioRawFrame,)
    assert CallerAudioTap.frame_types == (OutputAudioRawFrame,)


async def test_tap_appends_audio_to_the_recording():
    recording = AttemptRecording(sample_rate=16_000)

    class _Probe(AgentAudioTap):
        async def push_frame(self, frame, direction=None):  # no qa: swallow push
            return None

    tap = _Probe(recording)
    await tap.process_frame(
        InputAudioRawFrame(audio=_pcm(0.25), sample_rate=16_000, num_channels=1),
        direction=None,
    )
    assert recording.agent_duration_ms == 250


async def test_tap_passes_non_audio_frames_through():
    recording = AttemptRecording(sample_rate=16_000)
    pushed: list = []

    class _Probe(CallerAudioTap):
        async def push_frame(self, frame, direction=None):
            pushed.append(frame)

    tap = _Probe(recording)
    await tap.process_frame(TextFrame(text="hello"), direction=None)
    assert len(pushed) == 1
    assert recording.caller_duration_ms == 0
