"""Bounded LLM *Analyze* job (§6.3): structured output only, no free text.

Rules from :class:`TurnAnalyzer` cover the common cases; when the rule reading is
low-confidence, a small structured LLM call classifies the rest. The model is
injected so tests can drive it with a deterministic stub.
"""

from __future__ import annotations

from pydantic import BaseModel

from voiceeval.llm.base import BaseGenerationModel
from voiceeval.runtime.caller.turn_analyzer import TurnAnalyzer, TurnKind, TurnReading

_SYSTEM = (
    "You classify a caller-facing agent utterance into exactly one kind. "
    "Respond only with the requested JSON."
)
_KINDS = ", ".join(str(k) for k in TurnKind)


class _TurnReadingOut(BaseModel):
    kind: str
    fact_key: str | None = None


class TargetAnalyzer:
    def __init__(
        self,
        *,
        rules: TurnAnalyzer | None = None,
        model: BaseGenerationModel | None = None,
    ) -> None:
        self._rules = rules or TurnAnalyzer()
        self._model = model

    async def analyze(
        self, text: str, *, previous_text: str | None = None
    ) -> TurnReading:
        reading = self._rules.analyze(text, previous_text=previous_text)
        if self._model is None or reading.kind != TurnKind.STATEMENT:
            return reading
        try:
            out = await self._model.structured(
                _TurnReadingOut,
                system=_SYSTEM,
                user=(
                    f"Allowed kinds: {_KINDS}.\n"
                    f"Previous agent utterance: {previous_text or '(none)'}\n"
                    f"Current agent utterance: {text}"
                ),
            )
            return TurnReading(
                TurnKind(out.kind) if out.kind in set(TurnKind) else TurnKind.STATEMENT,
                fact_key=out.fact_key,
                is_question=out.kind == str(TurnKind.QUESTION),
                confidence=0.6,
            )
        except Exception:
            # Analysis must never block the call; fall back to the rule reading.
            return reading


__all__ = ["TargetAnalyzer"]
