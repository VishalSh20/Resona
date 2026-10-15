"""Recording taps for the pipecat caller.

Both directions are captured at the audio boundary: the target's audio as it
enters the pipeline and our synthesized audio as it leaves. Capture reuses the
shared, transport-agnostic :class:`AttemptRecording` — per-speaker mono tracks
plus a stereo call recording — the same artifact set the LiveKit caller uploads.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.livekit.recording import AttemptRecording

_AudioFrame = InputAudioRawFrame | OutputAudioRawFrame


def _to_chunk(frame: _AudioFrame) -> AudioChunk:
    channels = frame.num_channels or 1
    duration_ms = int(
        len(frame.audio) * 1000 / (2 * channels * max(1, frame.sample_rate))
    )
    return AudioChunk(
        data=frame.audio,
        sample_rate=frame.sample_rate,
        channels=channels,
        duration_ms=duration_ms,
    )


class _AudioTap(FrameProcessor):
    """Pass-through processor that records the audio frames it is handed."""

    frame_types: tuple[type, ...] = ()

    def __init__(self, append: Callable[[AudioChunk], None]) -> None:
        super().__init__()
        self._append = append

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, self.frame_types):
            self._append(_to_chunk(frame))
        await self.push_frame(frame, direction)


class AgentAudioTap(_AudioTap):
    """Records the target's audio as it enters the pipeline."""

    frame_types = (InputAudioRawFrame,)

    def __init__(self, recording: AttemptRecording) -> None:
        super().__init__(recording.append_agent)


class CallerAudioTap(_AudioTap):
    """Records our synthesized audio as it leaves the pipeline."""

    frame_types = (OutputAudioRawFrame,)

    def __init__(self, recording: AttemptRecording) -> None:
        super().__init__(recording.append_caller)


__all__ = ["AgentAudioTap", "CallerAudioTap", "_AudioTap"]
