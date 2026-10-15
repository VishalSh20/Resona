"""Audio conversion between LiveKit frames and the canonical ``AudioChunk``.

LiveKit's ``AudioFrame`` is imported lazily so this module (and the TargetLink
contract) can be exercised in tests without the SDK installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from voiceeval.runtime.connections import AudioChunk

if TYPE_CHECKING:  # pragma: no cover - typing only
    from livekit import rtc

_SAMPLE_WIDTH_BYTES = 2  # pcm_s16le


def duration_ms(data_len: int, sample_rate: int, channels: int = 1) -> int:
    """Duration in milliseconds of raw PCM ``pcm_s16le`` bytes."""
    if sample_rate <= 0 or channels <= 0:
        return 0
    frames = data_len // (_SAMPLE_WIDTH_BYTES * channels)
    return int(frames * 1000 / sample_rate)


def pcm_bytes_to_chunk(
    data: bytes, *, sample_rate: int, channels: int = 1
) -> AudioChunk:
    return AudioChunk(
        data=data,
        sample_rate=sample_rate,
        channels=channels,
        format="pcm_s16le",
        duration_ms=duration_ms(len(data), sample_rate, channels),
    )


def frame_to_chunk(frame: "rtc.AudioFrame") -> AudioChunk:
    data = bytes(frame.data)
    sample_rate = int(frame.sample_rate)
    channels = int(getattr(frame, "num_channels", 1) or 1)
    return AudioChunk(
        data=data,
        sample_rate=sample_rate,
        channels=channels,
        format="pcm_s16le",
        duration_ms=duration_ms(len(data), sample_rate, channels),
    )


def chunk_to_frame(chunk: AudioChunk) -> "rtc.AudioFrame":
    """Build a LiveKit ``AudioFrame`` from a canonical chunk.

    ``samples_per_channel`` is derived from the byte length so the frame is
    self-consistent; LiveKit requires it to match the PCM payload.
    """
    from livekit import rtc  # local import: SDK optional at import time

    samples_per_channel = len(chunk.data) // (_SAMPLE_WIDTH_BYTES * chunk.channels)
    frame = rtc.AudioFrame(
        data=chunk.data,
        sample_rate=chunk.sample_rate,
        num_channels=chunk.channels,
        samples_per_channel=samples_per_channel,
    )
    return frame


def frame_metadata(frame: Any) -> dict[str, Any]:
    """Small helper for logging/tests: read the shape of a frame duck-typed."""
    data = bytes(getattr(frame, "data", b""))
    sample_rate = int(getattr(frame, "sample_rate", 0) or 0)
    channels = int(getattr(frame, "num_channels", 1) or 1)
    return {
        "bytes": len(data),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_ms": duration_ms(len(data), sample_rate, channels),
    }


__all__ = [
    "chunk_to_frame",
    "duration_ms",
    "frame_metadata",
    "frame_to_chunk",
    "pcm_bytes_to_chunk",
]
