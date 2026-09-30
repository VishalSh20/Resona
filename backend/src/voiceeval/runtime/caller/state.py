"""Structured caller scenario state.

This is the caller's authoritative truth. The language model may realize the
caller's utterances but must never invent arbitrary state transitions; every
mutation goes through :meth:`ScenarioState.apply`, which increments
``state_version`` and returns a transition record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Phase = str


@dataclass(frozen=True)
class StateMutation:
    state_path: str
    previous_value: Any
    new_value: Any
    state_version: int


@dataclass
class ScenarioState:
    facts: dict[str, Any]
    user_goal: str
    current_intent: str
    authentication_state: bool
    known_information: dict[str, Any]
    recovery_count: int
    allowed_actions: list[str]
    conversation_phase: Phase
    terminal_status: str | None = None
    state_version: int = 0
    acknowledged: bool = False
    turn_count: int = 0

    @classmethod
    def initial(
        cls,
        *,
        facts: dict[str, Any],
        user_goal: str,
        initial_state: dict[str, Any],
        allowed_actions: list[str],
    ) -> "ScenarioState":
        return cls(
            facts=dict(facts),
            user_goal=user_goal,
            current_intent="present_problem",
            authentication_state=bool(initial_state.get("authenticated", False)),
            known_information=dict(initial_state),
            recovery_count=0,
            allowed_actions=list(allowed_actions),
            conversation_phase="opening",
        )

    def apply(self, state_path: str, new_value: Any) -> StateMutation:
        previous = self._read(state_path)
        self._write(state_path, new_value)
        self.state_version += 1
        return StateMutation(
            state_path=state_path,
            previous_value=previous,
            new_value=new_value,
            state_version=self.state_version,
        )

    def _read(self, path: str) -> Any:
        target: Any = self
        for part in path.split("."):
            if isinstance(target, dict):
                target = target.get(part)
            else:
                target = getattr(target, part, None)
            if target is None:
                return None
        return target

    def _write(self, path: str, value: Any) -> None:
        parts = path.split(".")
        target: Any = self
        for part in parts[:-1]:
            target = target[part] if isinstance(target, dict) else getattr(target, part)
        last = parts[-1]
        if isinstance(target, dict):
            target[last] = value
        else:
            setattr(target, last, value)


def transition_from_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Shape a caller-owned state transition for the event payload."""
    return {
        "state_path": payload.get("state_path"),
        "previous": payload.get("previous_value"),
        "new": payload.get("new_value"),
        "state_version": payload.get("state_version"),
    }
