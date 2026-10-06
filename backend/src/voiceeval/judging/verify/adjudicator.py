"""LLM adjudicator (spec §5.3).

Receives the packet (plus, in production, tools) and returns the same label set
with a rationale. Its verdict replaces Jev's for aggregation; Jev's
probabilities are kept in the record.
"""

from __future__ import annotations

from typing import Any

from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import ProbeSpec
from voiceeval.judging.verify.labels import ask_label, label_to_answer
from voiceeval.llm.base import BaseGenerationModel


class Adjudicator:
    def __init__(self, llm: BaseGenerationModel | None, *, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    async def adjudicate(
        self, probe: ProbeSpec, state: dict[str, Any], jev_answer: ProbeAnswer
    ) -> ProbeAnswer | None:
        if self._llm is None:
            return None
        verdict = await ask_label(self._llm, probe, state, model=self._model, jev_answer=jev_answer)
        if verdict is None:
            return None
        return label_to_answer(probe, verdict.label, verdict.confidence, "llm_adjudicated")


__all__ = ["Adjudicator"]
