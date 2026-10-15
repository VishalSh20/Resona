"""LiveKitCallerRuntime — the ``CallerRuntime`` implementation for LiveKit.

Implements the existing :class:`voiceeval.runtime.caller.runtime.CallerRuntime`
protocol. The deterministic brain (policy/action selector/language) is reused
unchanged; the framework owns the media loop and this runtime takes over *when to
speak and what to say* (§6.4).
"""

from __future__ import annotations

from typing import Any

from voiceeval.llm.providers import get_generation_model
from voiceeval.runtime.caller.pipeline import CallerDecisionPipeline, Decision
from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.caller.realizer import OutputValidator, Realizer
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.connections import RawAgentEvent
from voiceeval.runtime.events import CanonicalEvent, EventType
from voiceeval.runtime.scenario import Scenario


def _text_from_canonical(canonical: list[CanonicalEvent]) -> tuple[str, list[str]]:
    """Extract the latest agent text and any satisfied assertion ids."""
    text = ""
    assertions: list[str] = []
    for event in canonical:
        if event.type == EventType.AGENT_TEXT_FINAL:
            text = str((event.payload or {}).get("text") or text)
        if event.type in (
            EventType.TOOL_CALL_RESULT,
            EventType.AGENT_TEXT_FINAL,
        ):
            payload = event.payload or {}
            for key in ("assertions", "satisfied"):
                value = payload.get(key)
                if isinstance(value, list):
                    assertions.extend(str(v) for v in value)
    return text, assertions


class LiveKitCallerRuntime:
    def __init__(
        self,
        scenario: Scenario,
        persona: PersonaProfile,
        *,
        session: Any | None = None,
        pipeline: CallerDecisionPipeline | None = None,
        rng: SeededRng | None = None,
    ) -> None:
        self._scenario = scenario
        self._persona = persona
        self._session = session
        # The realizer phrases the chosen action with the configured LLM; without
        # a model it silently degrades to fixed templates for every turn.
        self.pipeline = pipeline or CallerDecisionPipeline(
            scenario,
            persona,
            # Short utterances keep turns (and therefore calls) fast; a long
            # monologue makes the target sit in silence for 10-15s per turn.
            realizer=Realizer(
                model=get_generation_model(),
                validator=OutputValidator(max_chars=160),
            ),
            rng=rng,
        )
        self._started = False
        self._stopped = False

    @property
    def persona(self) -> PersonaProfile:
        return self._persona

    async def start(self, agent: Any | None = None, *, room: Any | None = None) -> Any:
        """Start the media session. ``agent`` is required by livekit 1.x's
        ``AgentSession.start``; the caller overrides its reply behaviour."""
        self._started = True
        if self._session is not None and agent is not None:
            if room is not None:
                await self._session.start(agent, room=room)
            else:
                await self._session.start(agent)
        return None

    async def observe_agent_event(
        self, raw: RawAgentEvent | None, canonical: list[CanonicalEvent]
    ) -> Decision:
        text, assertions = _text_from_canonical(canonical)
        return await self.pipeline.decide(text, assertions=assertions)

    def select_action(self) -> str:
        return self.pipeline.select_action()

    async def realize(self, action: str) -> tuple[str, str]:
        language = self.pipeline._language.language_for_turn(self.pipeline.turn_index)  # noqa: SLF001
        return language, action

    async def stream_audio(
        self, text: str, *, turn_id: str, language: str, allow_interruptions: bool = True
    ) -> Any:
        if self._session is None:
            return None
        # Per-speech interruption control (§8.3): overlapping speech is spoken
        # with interruptions disabled so the target's audio cannot cut us off.
        return await self._session.say(
            text, allow_interruptions=allow_interruptions
        )

    async def stop(self) -> None:
        self._stopped = True
        if self._session is not None and hasattr(self._session, "aclose"):
            await self._session.aclose()


__all__ = ["LiveKitCallerRuntime"]
