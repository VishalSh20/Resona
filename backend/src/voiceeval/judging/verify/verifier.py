"""Cross-family verifier (spec §5.4).

Runs on critical verdicts and on disagreements. The final label is the majority
of ``{jev, adjudicator, verifier}``; if all three differ, the run is flagged for
human review. No silent averaging.
"""

from __future__ import annotations

from typing import Any

from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import ProbeSpec
from voiceeval.judging.verify.labels import (
    answer_label,
    ask_label,
    label_to_answer,
)
from voiceeval.llm.base import BaseGenerationModel


class Verifier:
    def __init__(self, llm: BaseGenerationModel | None, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    async def verify(
        self, probe: ProbeSpec, state: dict[str, Any], jev_answer: ProbeAnswer
    ) -> ProbeAnswer | None:
        if self._llm is None:
            return None
        verdict = await ask_label(self._llm, probe, state, model=self._model, jev_answer=jev_answer)
        if verdict is None:
            return None
        return label_to_answer(probe, verdict.label, verdict.confidence, "llm_adjudicated")


def majority_label(
    probe: ProbeSpec,
    jev_answer: ProbeAnswer,
    adjudicated: ProbeAnswer | None,
    verified: ProbeAnswer | None,
) -> tuple[str | None, bool]:
    """Return ``(majority_label, needs_human_review)``."""
    labels = [answer_label(probe, jev_answer)]
    if adjudicated is not None:
        labels.append(answer_label(probe, adjudicated))
    if verified is not None:
        labels.append(answer_label(probe, verified))
    concrete = [label for label in labels if label is not None]
    if not concrete:
        return None, False
    counts: dict[str, int] = {}
    for label in concrete:
        counts[label] = counts.get(label, 0) + 1
    top = max(counts.values())
    winners = [label for label, count in counts.items() if count == top]
    if len(winners) == 1:
        return winners[0], False
    # No majority: all three differ, or a 1-1 tie.
    return winners[0], len(concrete) >= 3 and len(counts) >= 3


__all__ = ["Verifier", "majority_label"]
