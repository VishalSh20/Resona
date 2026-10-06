"""Emotion timeline (spec §3.2/§7.4).

Caller emotional state is annotated from the clean caller track; agent voice
characteristics from the clean agent track. When no audio-capable model is
available the builder falls back to text cues and raises ``no_prosody``.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import EmotionItem

_EMOTION_LEXICON: dict[str, tuple[str, ...]] = {
    "anger": ("angry", "furious", "ridiculous", "unacceptable", "worst"),
    "frustration": ("frustrated", "still", "again", "waiting", "keeps", "useless"),
    "anxiety": ("worried", "urgent", "asap", "immediately", "please"),
    "sadness": ("upset", "disappointed", "sorry"),
    "joy": ("thanks", "thank you", "great", "perfect", "appreciate"),
}

_INTENSITY_HINTS = ("very", "really", "extremely", "so", "!!", "!!!")

AudioAnnotator = Callable[[list[dict]], Awaitable[list[dict]]]


def _heuristic_emotion(turn) -> EmotionItem:
    lowered = turn.text.lower()
    labels: list[str] = []
    cues: list[str] = []
    for label, words in _EMOTION_LEXICON.items():
        hits = [word for word in words if word in lowered]
        if hits:
            labels.append(label)
            cues.extend(hits)
    if not labels:
        labels = ["neutral"]
    intensity = 0 if labels == ["neutral"] else 1
    if intensity:
        if any(hint in lowered for hint in _INTENSITY_HINTS):
            intensity = 3
        elif "!" in turn.text or "please" in lowered:
            intensity = 2
    return EmotionItem(
        turn_id=turn.turn_id,
        emotion_labels=labels,
        intensity=intensity,
        text_cues=cues,
        prosody_cues=[],
        agent_voice=None,
        turn_ids=[turn.turn_id],
        quote=turn.text,
    )


async def build_emotion_timeline(
    llm,
    inputs: LedgerInputs,
    *,
    audio_annotator: AudioAnnotator | None = None,
) -> LedgerResult:
    caller_turns = [turn for turn in inputs.stage0.turns if turn.speaker == "caller"]
    caveats: list[str] = []

    items: list[EmotionItem] = []
    if audio_annotator is not None:
        try:
            payload = [
                {"turn_id": turn.turn_id, "text": turn.text, "audio": turn.audio_refs}
                for turn in caller_turns
            ]
            for raw in await audio_annotator(payload):
                items.append(EmotionItem.model_validate(raw))
        except Exception:  # noqa: BLE001 - audio is best-effort
            items = []
    if not items:
        items = [_heuristic_emotion(turn) for turn in caller_turns]
        caveats.append("no_prosody")

    return LedgerResult(
        ledger_type="emotion",
        status="ok",
        items=list(items),
        caveats=caveats,
    )


__all__ = ["AudioAnnotator", "build_emotion_timeline"]
