"""Caller policy engine.

The policy engine is the authoritative interpreter of observed agent behaviour:
it converts provider observations into *explicit* state mutations. The language
model never mutates state directly — it only realizes language. Every mutation
goes through :meth:`ScenarioState.apply`, which bumps ``state_version`` and
yields a transition record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.runtime.caller.state import ScenarioState, StateMutation
from voiceeval.runtime.scenario import Scenario

_ASSERTIONS_KEY = "assertions"
_TOOL_RESULTS_KEY = "tool_results"
_AGENT_LANGUAGE_KEY = "agent_language"
_LAST_AGENT_TEXT_KEY = "last_agent_text"


@dataclass
class CallerObservation:
    """A behaviour observed from the target agent, already canonicalized."""

    kind: str
    text: str | None = None
    assertions: list[str] = field(default_factory=list)
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_status: str | None = None
    language: str | None = None


@dataclass
class ObservationOutcome:
    mutations: list[StateMutation] = field(default_factory=list)
    progress: bool = False


class PolicyEngine:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._assertion_ids = {a.id for a in scenario.assertions}

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    @property
    def max_recovery_attempts(self) -> int:
        return self._scenario.max_recovery_attempts

    # -- observations ---------------------------------------------------------

    def observe(
        self, state: ScenarioState, observation: CallerObservation
    ) -> ObservationOutcome:
        if observation.kind == "agent_text":
            return self._observe_agent_text(state, observation)
        if observation.kind == "tool_result":
            return self._observe_tool_result(state, observation)
        if observation.kind == "agent_language":
            return self._observe_agent_language(state, observation)
        return ObservationOutcome()

    def _observe_agent_text(
        self, state: ScenarioState, observation: CallerObservation
    ) -> ObservationOutcome:
        outcome = ObservationOutcome()
        assertions = state.known_information.setdefault(_ASSERTIONS_KEY, {})
        satisfied = set(filter(None, assertions.get("satisfied", [])))
        newly = [
            assertion
            for assertion in observation.assertions
            if assertion in self._assertion_ids and assertion not in satisfied
        ]
        if newly:
            satisfied.update(newly)
            outcome.mutations.append(
                state.apply(
                    f"known_information.{_ASSERTIONS_KEY}",
                    {"satisfied": sorted(satisfied)},
                )
            )
            outcome.progress = True
        if observation.text:
            outcome.mutations.append(
                state.apply(f"known_information.{_LAST_AGENT_TEXT_KEY}", observation.text)
            )
        return outcome

    def _observe_tool_result(
        self, state: ScenarioState, observation: CallerObservation
    ) -> ObservationOutcome:
        outcome = ObservationOutcome()
        results = list(state.known_information.get(_TOOL_RESULTS_KEY, []))
        results.append(
            {
                "tool_name": observation.tool_name,
                "status": observation.tool_status,
                "arguments": observation.tool_arguments,
            }
        )
        mutation = state.apply(f"known_information.{_TOOL_RESULTS_KEY}", results)
        outcome.mutations.append(mutation)
        if observation.tool_status == "succeeded" and not state.authentication_state:
            outcome.mutations.append(state.apply("authentication_state", True))
            outcome.progress = True
        return outcome

    def _observe_agent_language(
        self, state: ScenarioState, observation: CallerObservation
    ) -> ObservationOutcome:
        if not observation.language:
            return ObservationOutcome()
        mutation = state.apply(f"known_information.{_AGENT_LANGUAGE_KEY}", observation.language)
        return ObservationOutcome(mutations=[mutation])

    # -- assertions -----------------------------------------------------------

    def satisfied_assertion_ids(self, state: ScenarioState) -> set[str]:
        assertions = state.known_information.get(_ASSERTIONS_KEY) or {}
        return set(assertions.get("satisfied", []))

    def unsatisfied_required(self, state: ScenarioState) -> list[str]:
        satisfied = self.satisfied_assertion_ids(state)
        return [
            assertion.id
            for assertion in self._scenario.required_assertions
            if assertion.id not in satisfied
        ]

    def required_assertions_satisfied(self, state: ScenarioState) -> bool:
        return not self.unsatisfied_required(state)

    # -- recovery -------------------------------------------------------------

    def record_recovery(self, state: ScenarioState) -> tuple[StateMutation, bool]:
        """Increment the recovery counter and report whether it is exhausted."""
        count = state.recovery_count + 1
        mutation = state.apply("recovery_count", count)
        exhausted = count >= max(1, self.max_recovery_attempts)
        return mutation, exhausted
