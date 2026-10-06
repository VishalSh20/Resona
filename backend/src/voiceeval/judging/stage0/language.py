"""Language timeline (spec §2.2.8).

Text LID is a script/lexicon heuristic that runs everywhere; audio LID is an
optional hook supplied by an audio-capable LLM (Stage 1 evidence). The timeline
reports per-speaker dominant language, switch points and a code-mixing index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Romanized Hindi/Marathi function words used as a lightweight LID signal.
_HINGLISH_MARKERS = frozenset(
    {
        "hai", "hain", "kya", "nahi", "nahin", "aap", "mera", "meri", "mujhe",
        "karo", "kar", "karna", "tha", "thi", "the", "aur", "par", "lekin",
        "kaise", "kahan", "kyun", "achha", "theek", "ji", "haan", "matlab",
        "bhai", "yaar", "liye", "wala", "wali", "abhi", "phir", "bhi", "toh",
    }
)

_SCRIPT_RANGES = (
    ("hi", 0x0900, 0x097F),  # Devanagari (Hindi/Marathi)
    ("ta", 0x0B80, 0x0BFF),
    ("te", 0x0C00, 0x0C7F),
    ("bn", 0x0980, 0x09FF),
    ("kn", 0x0C80, 0x0CFF),
)


def detect_token_language(token: str) -> str:
    for language, low, high in _SCRIPT_RANGES:
        if any(low <= ord(char) <= high for char in token):
            return language
    stripped = token.strip().lower().strip(".,!?;:\"'()")
    if stripped in _HINGLISH_MARKERS:
        return "hi"
    if any(char.isalpha() for char in token):
        return "en"
    return "other"


def _content_tokens(text: str) -> list[str]:
    return [tok for tok in text.split() if any(ch.isalnum() for ch in tok)]


@dataclass(frozen=True)
class LanguageProfile:
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def dominant(self) -> str | None:
        if not self.counts:
            return None
        return max(self.counts, key=self.counts.get)

    @property
    def code_mixing_index(self) -> float:
        total = self.total
        if total <= 1:
            return 0.0
        return 1.0 - (self.counts[self.dominant] / total)


@dataclass(frozen=True)
class SpeakerTimeline:
    dominant: str | None
    profile: LanguageProfile
    switch_token_indices: tuple[int, ...]
    microphone_audio_language: str | None = None


@dataclass(frozen=True)
class LanguageTimeline:
    caller: SpeakerTimeline
    agent: SpeakerTimeline
    tool_events: list[dict] = field(default_factory=list)


def analyze_text(text: str) -> SpeakerTimeline:
    tokens = _content_tokens(text)
    counts: dict[str, int] = {}
    languages: list[str] = []
    switch_indices: list[int] = []
    previous: str | None = None
    for index, token in enumerate(tokens):
        language = detect_token_language(token)
        languages.append(language)
        counts[language] = counts.get(language, 0) + 1
        if previous is not None and language != previous and language != "other":
            switch_indices.append(index)
        if language != "other":
            previous = language
    return SpeakerTimeline(
        dominant=max(counts, key=counts.get) if counts else None,
        profile=LanguageProfile(counts),
        switch_token_indices=tuple(switch_indices),
    )


def build_language_timeline(
    caller_texts: list[str],
    agent_texts: list[str],
    *,
    tool_events: list[dict] | None = None,
    caller_audio_language: str | None = None,
    agent_audio_language: str | None = None,
) -> LanguageTimeline:
    caller = analyze_text(" ".join(caller_texts))
    agent = analyze_text(" ".join(agent_texts))
    return LanguageTimeline(
        caller=SpeakerTimeline(
            dominant=caller.dominant,
            profile=caller.profile,
            switch_token_indices=caller.switch_token_indices,
            microphone_audio_language=caller_audio_language,
        ),
        agent=SpeakerTimeline(
            dominant=agent.dominant,
            profile=agent.profile,
            switch_token_indices=agent.switch_token_indices,
            microphone_audio_language=agent_audio_language,
        ),
        tool_events=tool_events or [],
    )


def consensus_language(text_language: str | None, audio_language: str | None) -> str | None:
    """Consensus of text and audio LID; prefer text, fall back to audio."""
    if text_language and audio_language:
        return text_language if text_language == audio_language else text_language
    return text_language or audio_language


__all__ = [
    "LanguageProfile",
    "LanguageTimeline",
    "SpeakerTimeline",
    "analyze_text",
    "build_language_timeline",
    "consensus_language",
    "detect_token_language",
]
