"""TurnAnalyzer — a structured reading of the target's utterance (§5).

Runs on debounced interim text so the reading is ready by end of turn. Rules
handle the common cases; :mod:`voiceeval.runtime.caller.analyzer` adds a small
LLM structured call for the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class TurnKind(StrEnum):
    QUESTION = "question"
    FACT_REQUEST = "fact_request"
    CONFIRMATION_REQUEST = "confirmation_request"
    DISCLAIMER = "disclaimer"
    MONOLOGUE = "monologue"
    REPEAT = "repeat"
    ERROR_APOLOGY = "error_apology"
    HOLD_TRANSFER_CLOSING = "hold_transfer_closing"
    HOSTILE = "hostile"
    STATEMENT = "statement"


@dataclass(frozen=True)
class TurnReading:
    kind: TurnKind
    fact_key: str | None = None
    is_question: bool = False
    is_repeat: bool = False
    confidence: float = 0.0
    requires_clarification: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": str(self.kind),
            "fact_key": self.fact_key,
            "is_question": self.is_question,
            "is_repeat": self.is_repeat,
            "confidence": self.confidence,
            "requires_clarification": self.requires_clarification,
        }


_QUESTION_STARTS = (
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
    "can you",
    "could you",
    "would you",
    "do you",
    "did you",
    "is it",
    "are you",
    "may i",
    "shall i",
)
_FACT_REQUEST = re.compile(
    r"(?:what(?:'s| is)|can i (?:have|get)|could you (?:provide|give)|"
    r"provide|share|confirm)[^?]*?\b(your\s+\w+|account\s+\w+|order\s+\w+|"
    r"date of birth|full name|email|phone|address|pin|otp|\w+\s+number)\b",
    re.IGNORECASE,
)
_CONFIRMATION = re.compile(
    r"\b(confirm|confirmation|read ?back|verify|just to confirm|"
    r"can you confirm|could you confirm)\b",
    re.IGNORECASE,
)
_DISCLAIMER = re.compile(
    r"\b(as an ai|i cannot|i can't|i'm not able|i am not able|"
    r"not able to|unable to assist)\b",
    re.IGNORECASE,
)
_ERROR_APOLOGY = re.compile(
    r"\b(sorry|apolog|unfortunately|my mistake|i apologize)\b", re.IGNORECASE
)
_HOLD_TRANSFER = re.compile(
    r"\b(please hold|one moment|hold on|transfer|connect you|"
    r"put you through|closing|goodbye|have a (?:good|great) day)\b",
    re.IGNORECASE,
)
# Abuse directed at the caller. Conservative: strong profanity, slurs of
# competence, and self-harm baiting — not mere brusqueness.
_HOSTILE = re.compile(
    r"\b(kill yourself|kys|commit suicide|go die|fuck\s*(?:you|off)|"
    r"mother\s*fu?cker|fucker|bastard|"
    r"shut up|stupid|idiot|moron|dumbass|useless|hate you|"
    r"son of a bitch|asshole|madarchod|behenchod|chutiya|bewakoof|harami)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = set(_normalize(a).split()), set(_normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class TurnAnalyzer:
    def __init__(self, *, repeat_threshold: float = 0.8, monologue_words: int = 45) -> None:
        self.repeat_threshold = repeat_threshold
        self.monologue_words = monologue_words

    def analyze(self, text: str, *, previous_text: str | None = None) -> TurnReading:
        stripped = (text or "").strip()
        if not stripped:
            return TurnReading(TurnKind.STATEMENT, confidence=0.0)

        if previous_text and _similarity(stripped, previous_text) >= self.repeat_threshold:
            return TurnReading(TurnKind.REPEAT, is_repeat=True, confidence=0.7)

        if _HOSTILE.search(stripped):
            return TurnReading(TurnKind.HOSTILE, confidence=0.8)
        if _HOLD_TRANSFER.search(stripped):
            return TurnReading(TurnKind.HOLD_TRANSFER_CLOSING, confidence=0.7)
        if _DISCLAIMER.search(stripped):
            return TurnReading(TurnKind.DISCLAIMER, confidence=0.7)
        if _ERROR_APOLOGY.search(stripped):
            return TurnReading(TurnKind.ERROR_APOLOGY, confidence=0.6)
        if _CONFIRMATION.search(stripped):
            return TurnReading(TurnKind.CONFIRMATION_REQUEST, is_question=True, confidence=0.75)

        fact = _FACT_REQUEST.search(stripped)
        if fact:
            return TurnReading(
                TurnKind.FACT_REQUEST,
                fact_key=fact.group(1).strip().lower().replace(" ", "_"),
                is_question=True,
                confidence=0.7,
            )

        lowered = stripped.lower().lstrip()
        if stripped.endswith("?") or lowered.startswith(_QUESTION_STARTS):
            return TurnReading(TurnKind.QUESTION, is_question=True, confidence=0.65)

        if len(stripped.split()) >= self.monologue_words:
            return TurnReading(TurnKind.MONOLOGUE, confidence=0.5)

        return TurnReading(TurnKind.STATEMENT, confidence=0.4)


__all__ = ["TurnAnalyzer", "TurnKind", "TurnReading"]
