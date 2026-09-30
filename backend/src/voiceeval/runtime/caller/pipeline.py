"""The per-turn decision pipeline (§6.2).

```
interim/final text ─▶ TurnAnalyzer ─▶ ScenarioState.apply ─▶ PersonaDynamics.update
                                                                   │
        ActionSelector (deterministic, allowed_actions) ◀──────────┘
                  │ action + constraints
                  ▼
        InterruptionPlanner / timing  ─▶  Realizer (LLM) ─▶ validator ─▶ speech
```

The LLM never picks the action: the deterministic selector does. Interruption
timing is separate (interim) via :meth:`CallerDecisionPipeline.decide_barge_in`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from voiceeval.runtime.caller.actions import (
    ACKNOWLEDGE_RESOLUTION,
    ANSWER,
    CLARIFY,
    DEFAULT_ACTIONS,
    END_CALL,
    PROVIDE_INFORMATION,
    PUSH_BACK,
    RECOVER,
    ActionSelector,
)
from voiceeval.runtime.caller.analyzer import TargetAnalyzer
from voiceeval.runtime.caller.interruption import (
    BargeInDecision,
    InterruptionContext,
    InterruptionPlanner,
)
from voiceeval.runtime.caller.language import LanguageController
from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.caller.policy import CallerObservation, PolicyEngine
from voiceeval.runtime.caller.realizer import Realizer
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.caller.state import ScenarioState
from voiceeval.runtime.caller.turn_analyzer import TurnKind, TurnReading
from voiceeval.runtime.scenario import Scenario


@dataclass
class PersonaDynamics:
    """Irritation / patience / engagement that rise on triggers and decay (§6.1)."""

    persona: PersonaProfile
    irritation: float = 0.0
    patience_budget: float = 1.0
    engagement: float = 1.0

    def update(self, reading: TurnReading, *, silence_ms: int = 0) -> None:
        gain = 0.1 + 0.4 * self.persona.irritability
        if reading.kind in (TurnKind.REPEAT, TurnKind.HOLD_TRANSFER_CLOSING):
            self.irritation += gain
            self.patience_budget -= gain
        elif reading.kind == TurnKind.MONOLOGUE:
            self.irritation += gain * 0.5
            self.patience_budget -= gain * 0.5
        elif reading.kind in (TurnKind.ERROR_APOLOGY,):
            self.irritation += gain * 0.3
        elif reading.kind in (TurnKind.QUESTION, TurnKind.CONFIRMATION_REQUEST):
            self.engagement = min(1.0, self.engagement + 0.05)
        if silence_ms > 4000:
            self.patience_budget -= 0.1 * (silence_ms / 1000.0)
            self.engagement = max(0.0, self.engagement - 0.1)
        self._clamp()

    def decay(self, amount: float = 0.02) -> None:
        self.irritation = max(0.0, self.irritation - amount)
        self.patience_budget = min(1.0, self.patience_budget + amount * 0.5)
        self._clamp()

    @property
    def exhausted(self) -> bool:
        return self.patience_budget <= 0.0

    def _clamp(self) -> None:
        self.irritation = max(0.0, min(1.0, self.irritation))
        self.patience_budget = max(0.0, min(1.0, self.patience_budget))
        self.engagement = max(0.0, min(1.0, self.engagement))


@dataclass
class Decision:
    action: str
    text: str
    language: str
    terminal: bool = False
    terminal_reason: str | None = None
    reading: TurnReading | None = None
    record: dict = field(default_factory=dict)


class _AssertionVerdict(BaseModel):
    satisfied: list[str]


class CallerDecisionPipeline:
    def __init__(
        self,
        scenario: Scenario,
        persona: PersonaProfile,
        *,
        analyzer: TargetAnalyzer | None = None,
        realizer: Realizer | None = None,
        selector: ActionSelector | None = None,
        policy: PolicyEngine | None = None,
        language: LanguageController | None = None,
        rng: SeededRng | None = None,
    ) -> None:
        self.scenario = scenario
        self.persona = persona
        self._analyzer = analyzer or TargetAnalyzer()
        self._realizer = realizer or Realizer()
        self._selector = selector or ActionSelector(scenario.allowed_actions)
        self._policy = policy or PolicyEngine(scenario)
        self._language = language or LanguageController.from_scenario(scenario.language)
        self._interruption = InterruptionPlanner(persona)
        self._rng = rng
        self.dynamics = PersonaDynamics(persona)
        self.state = ScenarioState.initial(
            facts=scenario.facts,
            user_goal=scenario.objective,
            initial_state=scenario.initial_state,
            allowed_actions=scenario.allowed_actions or list(DEFAULT_ACTIONS),
        )
        self.turn_index = 0
        self._recent_utterances: list[str] = []
        self._exchanges: list[tuple[str, str]] = []
        self._last_action: str | None = None

    @property
    def interruption(self) -> InterruptionPlanner:
        return self._interruption

    @property
    def policy(self) -> PolicyEngine:
        return self._policy

    def select_action(self) -> str:
        return self._selector.select(
            self.state,
            required_satisfied=self._policy.required_assertions_satisfied(self.state),
            recovery_requested=self.dynamics.irritation >= 0.7,
        )

    # --------------------------------------------------------------- decisions
    async def decide(
        self,
        target_text: str,
        *,
        previous_text: str | None = None,
        assertions: list[str] | None = None,
        silence_ms: int = 0,
    ) -> Decision:
        reading = await self._analyzer.analyze(target_text, previous_text=previous_text)

        outcome = self._policy.observe(
            self.state,
            CallerObservation(kind="agent_text", text=target_text, assertions=list(assertions or [])),
        )

        # Abuse is tracked as explicit state: the first offence gets a firm
        # push-back, the next one ends the call — a human doormat is not the
        # persona anyone is evaluating.
        abuse_count = int(self.state.known_information.get("abuse_count") or 0)
        if reading.kind == TurnKind.HOSTILE:
            abuse_count += 1
            self.state.apply("known_information.abuse_count", abuse_count)
            self.dynamics.irritation = min(1.0, self.dynamics.irritation + 0.5)
            self.dynamics.engagement = max(0.0, self.dynamics.engagement - 0.3)
        self.dynamics.update(reading, silence_ms=silence_ms)

        # Recovery is a response to the *target* failing (repeating itself,
        # erroring, deflecting) — not to the caller merely being irritated.
        recovery_requested = self.dynamics.irritation >= 0.7 and reading.kind in (
            TurnKind.REPEAT,
            TurnKind.ERROR_APOLOGY,
            TurnKind.HOLD_TRANSFER_CLOSING,
            TurnKind.DISCLAIMER,
        )
        required_satisfied = self._policy.required_assertions_satisfied(self.state)
        action = self._selector.select(
            self.state,
            required_satisfied=required_satisfied,
            recovery_requested=recovery_requested,
        )

        if reading.kind == TurnKind.HOSTILE:
            limit = 3 if self.persona.agreeableness >= 0.8 else 2
            action = END_CALL if abuse_count >= limit else PUSH_BACK
        elif action not in (END_CALL, ACKNOWLEDGE_RESOLUTION):
            # A direct fact question gets a direct answer, even if the facts
            # were already volunteered once.
            if (
                reading.kind == TurnKind.FACT_REQUEST
                and PROVIDE_INFORMATION in self.state.allowed_actions
            ):
                action = PROVIDE_INFORMATION
            # Any other question gets answered — never a canned "could you
            # repeat that?" to a question we understood.
            elif (
                reading.is_question
                and self.state.turn_count > 0
                and action in (CLARIFY, RECOVER)
            ):
                action = ANSWER
            # A coherent statement the selector had no rule for still deserves
            # a real response; CLARIFY is reserved for genuinely garbled input.
            elif (
                action == CLARIFY
                and self.state.turn_count > 0
                and reading.confidence > 0
                and target_text.strip()
            ):
                action = ANSWER
            # Two clarifies in a row *with the target simply repeating itself*
            # means the loop is stuck: escalate to recovery.
            elif (
                action == CLARIFY
                and self._last_action == CLARIFY
                and reading.is_repeat
                and RECOVER in self.state.allowed_actions
            ):
                action = RECOVER
        if action == RECOVER:
            _, recovery_exhausted = self._policy.record_recovery(self.state)
            if recovery_exhausted:
                action = END_CALL

        language = self._language.language_for_turn(self.turn_index)
        terminal = action == END_CALL
        terminal_reason = None
        if terminal:
            terminal_reason = (
                "TARGET_ABUSE"
                if reading.kind == TurnKind.HOSTILE
                else (
                    "NATURAL_SUCCESS"
                    if required_satisfied
                    else (
                        "RECOVERY_EXHAUSTED"
                        if self.state.recovery_count >= max(1, self._policy.max_recovery_attempts)
                        else "IRRECOVERABLE_OBJECTIVE_FAILURE"
                    )
                )
            )
            self.state.terminal_status = terminal_reason

        if action == ACKNOWLEDGE_RESOLUTION:
            self.state.apply("acknowledged", True)
        if action == PROVIDE_INFORMATION:
            self.state.apply("known_information.provided_information", True)
        self.state.apply("turn_count", self.turn_index + 1)
        self._last_action = action

        style_note = self._style_note(action, terminal_reason)
        allowed_facts = self.state.facts if action in (PROVIDE_INFORMATION, ANSWER) else {}
        fallback_language, fallback_text = self._language.realize(
            action, turn_index=self.turn_index, facts=self.state.facts
        )
        text = await self._realizer.realize(
            action,
            persona=self.persona,
            allowed_facts=allowed_facts,
            language=language,
            objective=self.scenario.objective,
            agent_message=target_text,
            recent_turns=self._recent_utterances,
            history=self._exchanges,
            style_note=style_note,
            fallback=lambda: fallback_text,
        )
        self._recent_utterances.append(text)
        self._recent_utterances = self._recent_utterances[-6:]
        self._exchanges.append((target_text, text))
        self._exchanges = self._exchanges[-6:]

        self.turn_index += 1
        record = {
            "action": action,
            "trigger": reading.kind.value,
            "reading": reading.to_dict(),
            "irritation": round(self.dynamics.irritation, 4),
            "patience_budget": round(self.dynamics.patience_budget, 4),
            "draws": [d.__dict__ for d in (self._rng.draws if self._rng else [])],
        }
        return Decision(
            action=action,
            text=text,
            language=language,
            terminal=terminal,
            terminal_reason=terminal_reason,
            reading=reading,
            record=record,
        )

    def _style_note(self, action: str, terminal_reason: str | None) -> str | None:
        """Emotional context handed to the realizer for this utterance."""
        if action == PUSH_BACK:
            return "You are hurt and angry right now; show it."
        if action == END_CALL:
            if terminal_reason == "NATURAL_SUCCESS":
                return "The call went well — end it warmly."
            if terminal_reason == "TARGET_ABUSE":
                return (
                    "You are ending the call because the agent abused you. "
                    "Say a firm, upset goodbye. Do NOT thank them."
                )
            return (
                "You are ending the call without your problem solved — "
                "disappointed and tired, not thankful."
            )
        return None

    async def assess_assertions(self) -> list[str]:
        """Judge which still-open required assertions the conversation satisfies.

        Providers that emit assertion events supply them out of band; on raw
        audio/bridge links nobody does, so without this the caller has no
        win-condition and every good call dies at the wall clock. Runs one
        small structured LLM call over the recent transcript — off the speech
        path, so a slow verdict never delays a turn.
        """
        model = getattr(self._realizer, "_model", None)
        if model is None:
            return []
        required = [a.id for a in self.scenario.required_assertions]
        open_ids = [
            a for a in required
            if a not in self._policy.satisfied_assertion_ids(self.state)
        ]
        if not open_ids:
            return []
        convo = "\n".join(
            f"Agent: {agent}\nCaller: {caller}" for agent, caller in self._exchanges[-10:]
        )
        if not convo.strip():
            return []
        try:
            verdict = await model.structured(
                _AssertionVerdict,
                system=(
                    "You judge whether a phone conversation satisfied the "
                    "caller's goals. Reply only with the requested JSON."
                ),
                user=(
                    f"The caller's objective: {self.scenario.objective}\n"
                    f"Open assertions (ids): {open_ids}\n\n"
                    f"Conversation so far:\n{convo}\n\n"
                    "Which of the open assertion ids are clearly satisfied by "
                    "what the agent actually said or did? List only ids you are "
                    "confident about."
                ),
            )
        except Exception:
            return []
        return [a for a in verdict.satisfied if a in open_ids]

    async def realize_probe(self, probe_index: int) -> Decision:
        """A short "are you still there?" check-in for long target silences.

        Not a scenario turn: no policy observation and no state mutation beyond
        advancing the language/utterance rhythm.
        """
        language, fallback_text = self._language.realize(
            "check_in", turn_index=self.turn_index, facts=self.state.facts
        )
        text = await self._realizer.realize(
            "check_in",
            persona=self.persona,
            allowed_facts={},
            language=language,
            objective=self.scenario.objective,
            agent_message=(
                "(the line has been silent for a while; check whether the "
                "agent is still there)"
            ),
            recent_turns=self._recent_utterances,
            history=self._exchanges,
            fallback=lambda: fallback_text,
        )
        self.turn_index += 1
        self._recent_utterances.append(text)
        self._recent_utterances = self._recent_utterances[-6:]
        return Decision(action="check_in", text=text, language=language)

    def decide_barge_in(
        self,
        *,
        target_turn_ms: int,
        target_words: int = 0,
        question_complete: bool = False,
        end_of_turn_probability: float = 0.0,
        repeated: bool = False,
        scripted_trigger: str | None = None,
    ) -> BargeInDecision:
        return self._interruption.should_barge_in(
            InterruptionContext(
                target_turn_ms=target_turn_ms,
                target_words=target_words,
                question_complete=question_complete,
                end_of_turn_probability=end_of_turn_probability,
                repeated=repeated,
                scripted_trigger=scripted_trigger,
            )
        )


__all__ = ["CallerDecisionPipeline", "Decision", "PersonaDynamics"]
