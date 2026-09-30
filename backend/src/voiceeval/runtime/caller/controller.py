"""Caller controller.

Owns the caller loop described in the runtime design:

    Observed Agent Output
      -> State Update / Policy Evaluation
      -> Action Selection
      -> Natural-language Realization
      -> TTS
      -> Audio Transmission

The controller exposes a stable interface (``start``, ``observe_agent_event``,
``select_action``, ``realize``, ``stream_audio``, ``stop``) so a Pipecat-backed
implementation can be substituted without the runner knowing. The LLM/provider
realizes language; it never owns scenario state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.runtime.caller.actions import (
    ACKNOWLEDGE_RESOLUTION,
    DEFAULT_ACTIONS,
    END_CALL,
    ActionSelector,
)
from voiceeval.runtime.caller.language import LanguageController
from voiceeval.runtime.caller.policy import CallerObservation, PolicyEngine
from voiceeval.runtime.caller.state import ScenarioState, StateMutation
from voiceeval.runtime.connections import AudioChunk, RawAgentEvent
from voiceeval.runtime.events import (
    CanonicalEvent,
    CanonicalEventBuilder,
    EventSource,
    EventType,
)
from voiceeval.runtime.media.tts import TTS
from voiceeval.runtime.scenario import Scenario

TERMINAL_NATURAL_SUCCESS = "NATURAL_SUCCESS"
TERMINAL_OBJECTIVE_FAILURE = "IRRECOVERABLE_OBJECTIVE_FAILURE"
_MAX_ACTIONS_PER_STEP = 3


@dataclass
class CallerStep:
    """The caller's output for one observation."""

    events: list[CanonicalEvent] = field(default_factory=list)
    audio: list[AudioChunk] = field(default_factory=list)
    turn_id: str | None = None
    action: str | None = None
    terminal: bool = False
    terminal_reason: str | None = None


class CallerController:
    def __init__(
        self,
        scenario: Scenario,
        *,
        tts: TTS,
        builder: CanonicalEventBuilder,
        policy: PolicyEngine | None = None,
        selector: ActionSelector | None = None,
        language: LanguageController | None = None,
        max_agent_turns: int = 16,
    ) -> None:
        self._scenario = scenario
        self._tts = tts
        self._builder = builder
        self._policy = policy or PolicyEngine(scenario)
        self._selector = selector or ActionSelector(scenario.allowed_actions)
        self._language = language or LanguageController.from_scenario(scenario.language)
        self._max_agent_turns = max_agent_turns

        self.state = ScenarioState.initial(
            facts=scenario.facts,
            user_goal=scenario.objective,
            initial_state=scenario.initial_state,
            allowed_actions=scenario.allowed_actions or list(DEFAULT_ACTIONS),
        )
        self._turn_index = 0
        self._agent_turns = 0
        self._no_progress_turns = 0
        self._started = False
        self._stopped = False

    # -- properties -----------------------------------------------------------

    @property
    def policy(self) -> PolicyEngine:
        return self._policy

    @property
    def turn_index(self) -> int:
        return self._turn_index

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> CallerStep:
        """Initialize scenario state. The caller speaks first only if asked."""
        self._started = True
        event = self._builder.build(
            EventType.CALLER_STATE_INITIALIZED,
            source=EventSource.CALLER,
            payload={
                "user_goal": self.state.user_goal,
                "facts": self.state.facts,
                "allowed_actions": self.state.allowed_actions,
                "state_version": self.state.state_version,
            },
        )
        return CallerStep(events=[event])

    async def stop(self) -> None:
        self._stopped = True

    # -- observation ----------------------------------------------------------

    async def observe_agent_event(
        self,
        raw: RawAgentEvent | None,
        canonical: list[CanonicalEvent],
    ) -> CallerStep:
        """Update state from an observed agent event and act on it."""
        events: list[CanonicalEvent] = []
        progress = False
        recovery_requested = False

        for observation in self._observations(canonical):
            outcome = self._policy.observe(self.state, observation)
            for mutation in outcome.mutations:
                events.append(self._mutation_event(mutation))
            progress = progress or outcome.progress

        self._agent_turns += 1
        if progress:
            self._no_progress_turns = 0
        else:
            self._no_progress_turns += 1

        if self._should_recover(progress):
            mutation, exhausted = self._policy.record_recovery(self.state)
            events.append(self._mutation_event(mutation))
            events.append(
                self._builder.build(
                    EventType.CALLER_RECOVERY_USED,
                    source=EventSource.CALLER,
                    payload={
                        "recovery_count": self.state.recovery_count,
                        "max_attempts": self._policy.max_recovery_attempts,
                        "exhausted": exhausted,
                    },
                )
            )
            recovery_requested = not exhausted

        step = await self._act(events, recovery_requested=recovery_requested)
        return step

    # -- action / realization -------------------------------------------------

    def select_action(self) -> str:
        return self._selector.select(
            self.state,
            required_satisfied=self._policy.required_assertions_satisfied(self.state),
        )

    async def realize(self, action: str) -> tuple[str, str]:
        return self._language.realize(
            action, turn_index=self._turn_index, facts=self.state.facts
        )

    async def stream_audio(self, text: str, *, turn_id: str, language: str):
        return await self._tts.speak(text, language=language, turn_id=turn_id)

    # -- internals ------------------------------------------------------------

    async def _act(
        self, events: list[CanonicalEvent], *, recovery_requested: bool
    ) -> CallerStep:
        step = CallerStep(events=events)
        for _ in range(_MAX_ACTIONS_PER_STEP):
            action = self._selector.select(
                self.state,
                required_satisfied=self._policy.required_assertions_satisfied(
                    self.state
                ),
                recovery_requested=recovery_requested,
            )
            step.action = action
            events.append(
                self._builder.build(
                    EventType.CALLER_ACTION_SELECTED,
                    source=EventSource.CALLER,
                    payload={"action": action},
                )
            )

            if action == END_CALL:
                satisfied = self._policy.required_assertions_satisfied(self.state)
                reason = (
                    TERMINAL_NATURAL_SUCCESS if satisfied else TERMINAL_OBJECTIVE_FAILURE
                )
                self.state.terminal_status = reason
                events.append(
                    self._builder.build(
                        EventType.CALLER_TERMINAL,
                        source=EventSource.CALLER,
                        payload={
                            "reason": reason,
                            "assertions_satisfied": satisfied,
                            "unsatisfied": self._policy.unsatisfied_required(self.state),
                        },
                    )
                )
                step.terminal = True
                step.terminal_reason = reason
                return step

            language, text = await self.realize(action)
            if action == ACKNOWLEDGE_RESOLUTION:
                self._apply(events, "acknowledged", True)

            turn_id = new_id(EntityKind.TURN)
            self._apply(events, "turn_count", self._turn_index + 1)

            events.append(
                self._builder.build(
                    EventType.CALLER_UTTERANCE_REALIZED,
                    source=EventSource.CALLER,
                    payload={"action": action, "text": text, "language": language},
                    turn_id=turn_id,
                )
            )
            events.append(
                self._builder.build(
                    EventType.TURN_START,
                    source=EventSource.RUNTIME,
                    payload={
                        "speaker": "caller",
                        "reference_text": text,
                        "transcript_source": "caller_reference",
                    },
                    turn_id=turn_id,
                )
            )
            speech = await self.stream_audio(text, turn_id=turn_id, language=language)
            events.extend(speech.events)
            step.audio.extend(speech.chunks)
            events.append(
                self._builder.build(
                    EventType.TURN_END,
                    source=EventSource.RUNTIME,
                    payload={"speaker": "caller"},
                    turn_id=turn_id,
                )
            )

            step.turn_id = turn_id
            self._turn_index += 1

            if not (
                self.state.acknowledged
                and self._policy.required_assertions_satisfied(self.state)
            ):
                return step
        return step

    def _apply(
        self, events: list[CanonicalEvent], path: str, value: Any
    ) -> CanonicalEvent:
        mutation = self.state.apply(path, value)
        event = self._mutation_event(mutation)
        events.append(event)
        return event

    def _mutation_event(self, mutation: StateMutation) -> CanonicalEvent:
        return self._builder.build(
            EventType.CALLER_STATE_MUTATED,
            source=EventSource.CALLER,
            payload={
                "state_path": mutation.state_path,
                "previous": mutation.previous_value,
                "new": mutation.new_value,
                "state_version": mutation.state_version,
            },
        )

    def _should_recover(self, progress: bool) -> bool:
        if progress or self._policy.required_assertions_satisfied(self.state):
            return False
        if self._policy.max_recovery_attempts <= 0:
            return False
        if self.state.recovery_count >= self._policy.max_recovery_attempts:
            return False
        # Only recover once the caller has done its part (identity verified) and
        # the agent is still not fulfilling the objective.
        if not self.state.authentication_state:
            return False
        return self._no_progress_turns >= 1

    def _observations(self, canonical: list[CanonicalEvent]) -> list[CallerObservation]:
        observations: list[CallerObservation] = []
        last_tool_name: str | None = None
        for event in canonical:
            if event.type == EventType.TOOL_CALL_START.value:
                last_tool_name = event.payload.get("tool_name")
            elif event.type == EventType.AGENT_TEXT_FINAL.value:
                observations.append(
                    CallerObservation(
                        kind="agent_text",
                        text=event.payload.get("text"),
                        assertions=list(event.payload.get("assertions") or []),
                    )
                )
            elif event.type == EventType.TOOL_CALL_RESULT.value:
                observations.append(
                    CallerObservation(
                        kind="tool_result",
                        tool_name=event.payload.get("tool_name") or last_tool_name,
                        tool_arguments=event.payload.get("arguments"),
                        tool_status=event.payload.get("status"),
                    )
                )
            elif event.type == EventType.AGENT_LANGUAGE_DETECTED.value:
                observations.append(
                    CallerObservation(
                        kind="agent_language",
                        language=event.payload.get("language"),
                    )
                )
        return observations
