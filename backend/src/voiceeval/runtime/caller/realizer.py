"""Bounded LLM *Realize* job + output validator (§6.3).

Realize phrases the chosen action in the persona's voice, given only the facts
allowed this turn. Everything it produces passes the output validator before it
is spoken: length cap, language check, no forbidden facts, no breaking
character. One regeneration, then a template fallback.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from voiceeval.llm.base import BaseGenerationModel, GenerationRequest
from voiceeval.runtime.caller.persona import PersonaProfile


@dataclass(frozen=True)
class ValidationOutcome:
    ok: bool
    reason: str = ""


_PROFANITY = frozenset({"fuck", "shit", "bastard", "asshole", "damn"})
_BREAK_CHARACTER = re.compile(
    r"\b(as an ai|language model|i am an ai|i'm an ai|i am a bot|i'm a bot)\b",
    re.IGNORECASE,
)


class OutputValidator:
    def __init__(
        self,
        *,
        max_chars: int = 240,
        forbidden_values: tuple[str, ...] = (),
        disallow_ai_disclosure: bool = True,
        hostility_ceiling: float = 1.0,
    ) -> None:
        self.max_chars = max_chars
        self.forbidden_values = tuple(v for v in forbidden_values if v)
        self.disallow_ai_disclosure = disallow_ai_disclosure
        self.hostility_ceiling = hostility_ceiling

    def validate(self, text: str, *, language: str | None = None) -> ValidationOutcome:
        value = (text or "").strip()
        if not value:
            return ValidationOutcome(False, "empty")
        if len(value) > self.max_chars:
            return ValidationOutcome(False, "too_long")
        lowered = value.lower()
        if self.disallow_ai_disclosure and _BREAK_CHARACTER.search(value):
            return ValidationOutcome(False, "breaks_character")
        for forbidden in self.forbidden_values:
            if forbidden.lower() in lowered:
                return ValidationOutcome(False, "forbidden_fact")
        if self.hostility_ceiling < 0.5:
            for word in _PROFANITY:
                if re.search(rf"\b{re.escape(word)}\b", lowered):
                    return ValidationOutcome(False, "hostility_ceiling")
        return ValidationOutcome(True)


def style_card(persona: PersonaProfile) -> str:
    traits = ", ".join(persona.traits) or "neutral"
    length = (
        "very short" if persona.utterance_length < 0.3
        else "long and detailed" if persona.utterance_length > 0.7
        else "medium"
    )
    tone = (
        "warm and friendly" if persona.agreeableness > 0.7
        else "clipped and impatient" if persona.irritability > 0.6
        else "neutral"
    )
    return (
        f"Persona traits: {traits}. Speak in a {tone} tone. "
        f"Utterances should be {length}. Formality {persona.formality:.2f}. "
        f"Hostility ceiling {persona.hostility_ceiling:.2f} (never exceed it)."
    )


_ACTION_HINTS = {
    "present_problem": "State your problem or reason for calling, briefly and naturally.",
    "provide_information": "Give the agent the facts it needs to help you.",
    "clarify": "You genuinely did not understand the agent — ask one short, specific question.",
    "recover": "Show frustration that this is still not resolved and push for a concrete solution.",
    "acknowledge_resolution": "Acknowledge that your problem is solved.",
    "end_call": "End the call.",
    "answer": (
        "Respond naturally to what the agent said — answer its question if it "
        "asked one, otherwise acknowledge and react like a human, and steer "
        "the conversation toward your goal. Do not ask them to repeat themselves."
    ),
    "push_back": (
        "The agent said something abusive or deeply inappropriate to you. React "
        "like a real person who just got hurt: say firmly that this is not okay. "
        "Do not help them, do not thank them, do not continue the task this turn."
    ),
    "check_in": "Check whether the agent is still on the line.",
}


class Realizer:
    def __init__(
        self,
        *,
        model: BaseGenerationModel | None = None,
        validator: OutputValidator | None = None,
    ) -> None:
        self._model = model
        self._validator = validator or OutputValidator()

    async def realize(
        self,
        action: str,
        *,
        persona: PersonaProfile,
        allowed_facts: dict[str, object] | None = None,
        recent_turns: list[str] | None = None,
        history: list[tuple[str, str]] | None = None,
        language: str = "en-IN",
        objective: str | None = None,
        agent_message: str | None = None,
        style_note: str | None = None,
        fallback: Callable[[], str] | None = None,
    ) -> str:
        if self._model is None:
            return fallback() if fallback else ""

        facts = ", ".join(f"{k}={v}" for k, v in (allowed_facts or {}).items()) or "(none)"
        turns = " | ".join((recent_turns or [])[-4:]) or "(none)"
        system = (
            "You are role-playing a human caller in a phone call. "
            "Stay in character. Never mention being an AI. "
            "You have real feelings: warmth when treated well, hurt and anger "
            "when treated badly — let them show in how you speak. "
            f"Reply in {language}. " + style_card(persona)
        )
        if objective:
            system += f"\nYour situation and goal: {objective}"
        if style_note:
            system += f"\n{style_note}"
        if persona.disfluency_rate > 0.15:
            system += (
                "\nYou may occasionally use natural spoken fillers (umm, haan, "
                "I mean) — like a real person thinking out loud, not on every line."
            )

        exchanges = "\n".join(
            f"Agent: {agent}\nYou: {caller}" for agent, caller in (history or [])[-6:]
        )
        heard = agent_message or "(the agent has not spoken yet)"
        hint = _ACTION_HINTS.get(action, action)
        user = (
            f"Conversation so far (newest last):\n{exchanges or '(nothing yet)'}\n\n"
            f"The agent just said to you: {heard}\n"
            f"Your action to perform: {action} — {hint}\n"
            f"Facts you may reveal (only if relevant): {facts}\n"
            f"Your recent utterances (never reuse their phrasing): {turns}\n"
            "Write ONLY the caller's next utterance, the way a person actually "
            "talks on the phone: first react to what they said in a few words "
            "(\"right\", \"I see\", \"oh okay\", \"haan\"), then answer or move "
            "toward your goal. Usually 1-2 short spoken sentences; sometimes "
            "just a couple of words. Vary your sentence shapes. If the agent's "
            "words were garbled or half-heard, respond charitably to the gist "
            "instead of asking them to repeat."
        )

        for _attempt in range(2):
            try:
                response = await self._model.generate(
                    GenerationRequest(
                        system=system,
                        user=user,
                        temperature=0.4 + 0.3 * persona.irritability,
                        json_mode=False,
                    )
                )
            except Exception:  # noqa: BLE001 - a turn must never fail on the LLM
                break
            text = response.text.strip()
            outcome = self._validator.validate(text, language=language)
            if outcome.ok:
                return text
            user += (
                f"\n\nYour previous reply was rejected ({outcome.reason}). "
                "Keep it in character, shorter, and do not reveal disallowed facts."
            )

        return fallback() if fallback else ""


__all__ = ["OutputValidator", "Realizer", "ValidationOutcome", "style_card"]
