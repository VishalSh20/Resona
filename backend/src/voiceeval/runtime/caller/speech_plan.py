"""Speech planner (L3) — §9.4.

Turns a realized utterance into a segment list: speech, planned intra-utterance
pauses (Hesitant / Emotional), and fillers that mask slow generation. Pauses are
planned as silence *between* segments so the caller never ends its own turn
during a planned pause.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.caller.rng import SeededRng

_FILLERS: dict[str, tuple[str, ...]] = {
    "en-IN": ("um", "uh", "well", "you know"),
    "hi-IN": ("अरे", "मतलब", "वो"),
}

_CLAUSE_SPLIT = re.compile(r"(?<=[,;:.!?])\s+")


@dataclass(frozen=True)
class SpeechSegment:
    kind: str  # "speech" | "pause" | "filler"
    text: str | None = None
    duration_ms: int | None = None
    language: str | None = None


class SpeechPlanner:
    def __init__(
        self,
        persona: PersonaProfile,
        *,
        filler_cap: int = 2,
        pause_min_ms: int = 180,
        pause_max_ms: int = 520,
    ) -> None:
        self.persona = persona
        self.filler_cap = filler_cap
        self.pause_min_ms = pause_min_ms
        self.pause_max_ms = pause_max_ms

    def _filler(self, language: str, rng: SeededRng | None) -> str:
        options = _FILLERS.get(language) or _FILLERS["en-IN"]
        if rng is not None:
            return str(rng.choice("filler.word", options))
        return options[0]

    def plan(
        self,
        text: str,
        *,
        language: str = "en-IN",
        include_filler: bool = False,
        rng: SeededRng | None = None,
    ) -> list[SpeechSegment]:
        segments: list[SpeechSegment] = []
        fillers_used = 0

        if include_filler and self.persona.disfluency_rate > 0.05:
            segments.append(SpeechSegment("filler", text=self._filler(language, rng), language=language))
            fillers_used += 1

        clauses = [c for c in _CLAUSE_SPLIT.split((text or "").strip()) if c]
        if not clauses:
            return segments

        # Only hesitation-heavy personas insert intra-utterance pauses.
        insert_pauses = self.persona.disfluency_rate >= 0.25
        for index, clause in enumerate(clauses):
            if (
                insert_pauses
                and index > 0
                and fillers_used < self.filler_cap
                and self.persona.disfluency_rate >= 0.35
                and rng is not None
                and rng.chance("pause.use_filler", 0.4)
            ):
                segments.append(SpeechSegment("filler", text=self._filler(language, rng), language=language))
                fillers_used += 1
            elif insert_pauses and index > 0:
                duration = self.pause_min_ms
                if rng is not None:
                    duration = int(rng.uniform("pause.ms", self.pause_min_ms, self.pause_max_ms))
                segments.append(SpeechSegment("pause", duration_ms=duration, language=language))
            segments.append(SpeechSegment("speech", text=clause, language=language))

        return segments


__all__ = ["SpeechPlanner", "SpeechSegment"]
