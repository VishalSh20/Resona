"""Caller action selection.

The selector picks the caller's next action from a small, deterministic
vocabulary. It is deliberately not an LLM: the scenario state machine decides
*what* the caller should do; realization only decides *how* it is phrased.
"""

from __future__ import annotations

from voiceeval.runtime.caller.state import ScenarioState

PRESENT_PROBLEM = "present_problem"
PROVIDE_INFORMATION = "provide_information"
CLARIFY = "clarify"
RECOVER = "recover"
ACKNOWLEDGE_RESOLUTION = "acknowledge_resolution"
END_CALL = "end_call"
ANSWER = "answer"
PUSH_BACK = "push_back"

DEFAULT_ACTIONS = [
    PRESENT_PROBLEM,
    PROVIDE_INFORMATION,
    CLARIFY,
    RECOVER,
    ACKNOWLEDGE_RESOLUTION,
    END_CALL,
]

#: Reactive conversational necessities: a scenario cannot disable answering a
#: direct question or objecting to abuse, the way it can disable ``recover``.
_ALWAYS_PERMITTED = frozenset({ANSWER, PUSH_BACK})


class ActionSelector:
    """Deterministic priority order over the scenario's allowed actions."""

    def __init__(self, allowed_actions: list[str] | None = None) -> None:
        self._allowed = list(allowed_actions) if allowed_actions else list(DEFAULT_ACTIONS)

    @property
    def allowed(self) -> list[str]:
        return list(self._allowed)

    def _permitted(self, action: str) -> bool:
        return action in self._allowed or action in _ALWAYS_PERMITTED

    def select(
        self,
        state: ScenarioState,
        *,
        required_satisfied: bool,
        recovery_requested: bool = False,
    ) -> str:
        if state.terminal_status:
            return END_CALL
        if required_satisfied and state.acknowledged:
            return END_CALL
        if required_satisfied:
            return ACKNOWLEDGE_RESOLUTION if self._permitted(ACKNOWLEDGE_RESOLUTION) else CLARIFY
        if recovery_requested and self._permitted(RECOVER):
            return RECOVER
        # The opening turn states the problem; only afterwards does the caller
        # volunteer information or clarify.
        if state.turn_count == 0:
            return PRESENT_PROBLEM if self._permitted(PRESENT_PROBLEM) else CLARIFY
        # Volunteer the caller's facts once; re-offering the same facts every
        # turn is a loop, not a conversation. Direct fact questions are answered
        # again via the pipeline's FACT_REQUEST override, not here.
        already_provided = bool(state.known_information.get("provided_information"))
        if (
            not state.authentication_state
            and not already_provided
            and self._permitted(PROVIDE_INFORMATION)
        ):
            return PROVIDE_INFORMATION
        return CLARIFY if self._permitted(CLARIFY) else self._allowed[0]
