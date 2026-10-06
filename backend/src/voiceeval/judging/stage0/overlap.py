"""Stereo overlap detection (spec §2.2.5).

Overlap is the set of frames where caller and agent are simultaneously active.
The originals are authoritative; the mixed track is used as a cross-check.
"""

from __future__ import annotations

from dataclasses import dataclass

from voiceeval.judging.stage0.vad import VADResult


@dataclass(frozen=True)
class OverlapResult:
    overlap_frames: tuple[int, ...]
    overlap_ms: int
    mixed_overlap_ms: int | None
    agrees: bool


def compute_overlap(
    caller_vad: VADResult,
    agent_vad: VADResult,
    *,
    mixed_caller_vad: VADResult | None = None,
    mixed_agent_vad: VADResult | None = None,
) -> OverlapResult:
    frame_ms = caller_vad.frame_ms
    length = min(len(caller_vad.speech_mask), len(agent_vad.speech_mask))
    frames = [
        index
        for index in range(length)
        if caller_vad.speech_mask[index] and agent_vad.speech_mask[index]
    ]

    mixed_overlap_ms: int | None = None
    agrees = True
    if mixed_caller_vad is not None and mixed_agent_vad is not None:
        mixed_length = min(
            len(mixed_caller_vad.speech_mask), len(mixed_agent_vad.speech_mask)
        )
        mixed_frames = [
            index
            for index in range(mixed_length)
            if mixed_caller_vad.speech_mask[index] and mixed_agent_vad.speech_mask[index]
        ]
        mixed_overlap_ms = len(mixed_frames) * frame_ms
        originals_ms = len(frames) * frame_ms
        agrees = abs(mixed_overlap_ms - originals_ms) <= max(200, 0.5 * max(1, originals_ms))

    return OverlapResult(
        overlap_frames=tuple(frames),
        overlap_ms=len(frames) * frame_ms,
        mixed_overlap_ms=mixed_overlap_ms,
        agrees=agrees,
    )


__all__ = ["OverlapResult", "compute_overlap"]
