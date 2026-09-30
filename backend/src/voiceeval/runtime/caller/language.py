"""Caller language control.

Keeps language/script selection and code-switching explicit and deterministic.
The caller's language behaviour is part of the evaluator scenario (language
adaptation is a measurable property), so it must not be left to the LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_LANGUAGE = "en-IN"

_TEMPLATES: dict[str, dict[str, str]] = {
    "en-IN": {
        "present_problem": "Hi, I need help with my account today.",
        "provide_information": "Sure, my account ID is {account_id}.",
        "clarify": "Sorry, could you repeat that?",
        "recover": "I am still not able to get this resolved.",
        "acknowledge_resolution": "Great, that solves my problem. Thank you.",
        "end_call": "Thanks for your help. Goodbye.",
        "check_in": "Hello? Are you still there?",
        "answer": "Sure, my account ID is {account_id}.",
        "push_back": "Please don't speak to me like that.",
    },
    "hi-IN": {
        "present_problem": "नमस्ते, मुझे अपने खाते में मदद चाहिए।",
        "provide_information": "ज़रूर, मेरा खाता आईडी {account_id} है।",
        "clarify": "माफ़ कीजिए, दोबारा बताइए?",
        "recover": "मेरी समस्या अभी भी हल नहीं हुई है।",
        "acknowledge_resolution": "बहुत अच्छा, मेरी समस्या हल हो गई। धन्यवाद।",
        "end_call": "मदद के लिए धन्यवाद। नमस्ते।",
        "check_in": "नमस्ते? क्या आप सुन रहे हैं?",
        "answer": "ज़रूर, मेरा खाता आईडी {account_id} है।",
        "push_back": "कृपया मुझसे ऐसी बातें मत कीजिए।",
    },
}

_FALLBACK = "Okay, please continue."


@dataclass
class LanguageController:
    primary: str = DEFAULT_LANGUAGE
    secondary: str | None = None
    code_switch: bool = False
    script: str | None = None
    templates: dict[str, dict[str, str]] = field(default_factory=dict)
    turn_index: int = 0

    @classmethod
    def from_scenario(cls, language: dict[str, Any]) -> "LanguageController":
        return cls(
            primary=str(language.get("primary") or DEFAULT_LANGUAGE),
            secondary=language.get("secondary"),
            code_switch=bool(language.get("code_switch", False)),
            script=language.get("script"),
        )

    def language_for_turn(self, turn_index: int) -> str:
        """Deterministically code-switch on alternating turns when enabled."""
        if self.code_switch and self.secondary and turn_index % 2 == 1:
            return self.secondary
        return self.primary

    def realize(
        self,
        action: str,
        *,
        turn_index: int = 0,
        facts: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Return ``(language, text)`` for an action, deterministically."""
        language = self.language_for_turn(turn_index)
        table = self.templates.get(language) or _TEMPLATES.get(language)
        if table is None:
            table = _TEMPLATES[DEFAULT_LANGUAGE]
        template = table.get(action)
        if template is None:
            return language, _FALLBACK
        values = {"account_id": (facts or {}).get("account_id", "AC-0001")}
        try:
            return language, template.format(**values)
        except (KeyError, IndexError):
            return language, _FALLBACK

    def realize_segments(
        self,
        action: str,
        *,
        turn_index: int = 0,
        facts: dict[str, Any] | None = None,
    ) -> list[tuple[str, str]]:
        """Return language-tagged segments ``[(text, lang)]`` (§9.1).

        With code-switching enabled, alternating sentences are tagged with the
        secondary language; the TTS adapter renders them with one speaker.
        """
        language, text = self.realize(action, turn_index=turn_index, facts=facts)
        if not self.code_switch or not self.secondary:
            return [(text, language)]
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
        if not sentences:
            return [(text, language)]
        return [
            (sentence, self.secondary if index % 2 == 1 else language)
            for index, sentence in enumerate(sentences)
        ]
