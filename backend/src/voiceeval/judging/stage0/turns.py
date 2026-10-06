"""Canonical turn table (spec §2.2.7).

Turns carry the diarized speaker, media-clock boundaries, text, word list,
language spans and audio references into the clean originals and the mixed
track. Word-level timings and ASR confidence are only available when the runner
emitted them; when absent they are left empty rather than invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.metrics.signals import AttemptSignals, TurnView


@dataclass
class TurnRecord:
    turn_id: int | str
    speaker: str
    t_start: int | None
    t_end: int | None
    text: str
    words: list[dict] = field(default_factory=list)
    asr_conf: float | None = None
    lang_spans: list[dict] = field(default_factory=list)
    overlap_with: list[Any] = field(default_factory=list)
    audio_refs: list[dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> int | None:
        if self.t_start is None or self.t_end is None:
            return None
        return max(0, self.t_end - self.t_start)


def _turn_key(turn: TurnView) -> int | str:
    if turn.sequence_no is not None:
        return int(turn.sequence_no)
    return turn.turn_id or ""


def _audio_refs(speaker: str, start: int | None, end: int | None) -> list[dict]:
    if start is None or end is None:
        return []
    if speaker == "caller":
        return [
            {"source": "caller_original", "start_ms": start, "end_ms": end},
            {"source": "mixed", "channel": "left", "start_ms": start, "end_ms": end},
        ]
    return [
        {"source": "agent_original", "start_ms": start, "end_ms": end},
        {"source": "mixed", "channel": "right", "start_ms": start, "end_ms": end},
    ]


def build_turns(
    signals: AttemptSignals,
    *,
    overlap_frames: tuple[int, ...] = (),
    frame_ms: int = 10,
) -> list[TurnRecord]:
    records: list[TurnRecord] = []
    for turn in signals.turns:
        text = turn.reference_text or turn.observed_text or ""
        if not text:
            continue
        record = TurnRecord(
            turn_id=_turn_key(turn),
            speaker=turn.speaker,
            t_start=turn.start_ms,
            t_end=turn.end_ms,
            text=text,
            words=[],
            asr_conf=None,
            lang_spans=[],
            audio_refs=_audio_refs(turn.speaker, turn.start_ms, turn.end_ms),
        )
        records.append(record)

    # Populate overlap_with from the frame-level overlap set.
    if overlap_frames and records:
        overlap_ms = {frame * frame_ms for frame in overlap_frames}
        for record in records:
            if record.t_start is None or record.t_end is None:
                continue
            if any(record.t_start <= moment <= record.t_end for moment in overlap_ms):
                for other in records:
                    if other is record or other.speaker == record.speaker:
                        continue
                    if (
                        other.t_start is not None
                        and other.t_end is not None
                        and other.t_start <= record.t_end
                        and other.t_end >= record.t_start
                    ):
                        record.overlap_with.append(other.turn_id)
    return records


__all__ = ["TurnRecord", "build_turns"]
