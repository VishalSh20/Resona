"""Interruption and overlap planning (§8.2 yield, §8.3 barge-in).

Rule-based and persona-gated. The framework models users interrupting the agent,
not the reverse, so barge-in is our logic. This module decides *whether* the
caller yields or cuts in and in *which* overlap mode; the session layer performs
it with per-speech interruption control.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from voiceeval.runtime.caller.persona import PersonaProfile


class OverlapMode(StrEnum):
    COOPERATIVE = "cooperative"  # short interjection
    COMPETITIVE = "competitive"  # hold the floor until the target stops
    CUT_OFF = "cut-off"  # take the floor, don't relent


@dataclass(frozen=True)
class BargeInDecision:
    attempt: bool
    trigger: str | None
    mode: OverlapMode
    reason: str = ""


@dataclass
class InterruptionContext:
    target_turn_ms: int
    target_words: int = 0
    question_complete: bool = False
    end_of_turn_probability: float = 0.0
    repeated: bool = False
    scripted_trigger: str | None = None


_TRIGGER_MODE: dict[str, OverlapMode] = {
    "early_answer": OverlapMode.COOPERATIVE,
    "repetition": OverlapMode.COOPERATIVE,
    "monologue_impatience": OverlapMode.COMPETITIVE,
    "competitive": OverlapMode.COMPETITIVE,
    "escalation": OverlapMode.CUT_OFF,
    "emotional": OverlapMode.CUT_OFF,
}


class InterruptionPlanner:
    def __init__(
        self,
        persona: PersonaProfile,
        *,
        min_target_speech_ms: int = 400,
        min_target_words: int = 2,
        false_interruption_timeout_ms: int = 700,
        monologue_patience_ms: int = 8000,
    ) -> None:
        self.persona = persona
        self.min_target_speech_ms = min_target_speech_ms
        self.min_target_words = min_target_words
        self.false_interruption_timeout_ms = false_interruption_timeout_ms
        self.monologue_patience_ms = monologue_patience_ms

    # ------------------------------------------------------------- §8.2 yield
    def effective_yield_threshold_ms(self) -> float:
        """Higher ``yield_threshold`` means the caller yields sooner."""
        scale = 1.5 - self.persona.yield_threshold  # 0.5 .. 1.5
        return self.min_target_speech_ms * scale

    def should_yield(
        self, *, target_speech_ms: int, target_words: int, still_speaking: bool = True
    ) -> bool:
        if not still_speaking:
            return False
        enough_time = target_speech_ms >= self.effective_yield_threshold_ms()
        enough_words = target_words >= self.min_target_words
        if self.persona.yield_threshold >= 0.8:
            return enough_time and target_words >= 1
        return enough_time and enough_words

    def is_false_interruption(self, *, target_speech_ms: int, target_words: int) -> bool:
        """Short noise or a one-word 'okay' is not a real interruption."""
        return (
            target_speech_ms < self.effective_yield_threshold_ms()
            or target_words < self.min_target_words
        )

    def hold_floor_initial_ms(self) -> int:
        """Hold-the-floor personas ignore interruptions for the first N ms."""
        if self.persona.yield_threshold <= 0.2:
            return int(self.persona.floor_hold_cap_ms * 0.5)
        return 0

    # ---------------------------------------------------------- §8.3 barge-in
    def barge_in_trigger(self, ctx: InterruptionContext) -> str | None:
        enabled = set(self.persona.barge_in_triggers)

        if ctx.scripted_trigger:
            return ctx.scripted_trigger
        if ctx.repeated and (
            "repetition" in enabled or self.persona.irritability >= 0.4
        ):
            return "repetition"
        patience_ms = self.monologue_patience_ms * (1.0 - 0.5 * self.persona.irritability)
        if ctx.target_turn_ms >= patience_ms and "monologue_impatience" in enabled:
            return "monologue_impatience"
        if (
            ctx.question_complete
            and ctx.end_of_turn_probability >= 0.7
            and "early_answer" in enabled
        ):
            return "early_answer"
        if self.persona.irritability >= 0.7 and "emotional" in enabled:
            return "emotional"
        return None

    def should_barge_in(self, ctx: InterruptionContext) -> BargeInDecision:
        trigger = self.barge_in_trigger(ctx)
        if trigger is None:
            return BargeInDecision(False, None, OverlapMode.COOPERATIVE, "no trigger")
        return BargeInDecision(
            True, trigger, self.overlap_mode(trigger), f"trigger={trigger}"
        )

    def overlap_mode(self, trigger: str) -> OverlapMode:
        return _TRIGGER_MODE.get(trigger, OverlapMode.COOPERATIVE)

    @property
    def floor_hold_cap_ms(self) -> float:
        return self.persona.floor_hold_cap_ms


__all__ = [
    "BargeInDecision",
    "InterruptionContext",
    "InterruptionPlanner",
    "OverlapMode",
]
