"""Scenario parsing.

Turns a canonical evaluator document (``evaluator.v1``) into the structured
objects the caller runtime drives: facts, motive assertions, behaviour and stop
conditions. The scenario is authoritative state; the LLM only realizes language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MotiveAssertion:
    id: str
    type: str
    required: bool
    expectation: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    objective: str
    facts: dict[str, Any]
    initial_state: dict[str, Any]
    assertions: list[MotiveAssertion]
    allowed_actions: list[str]
    max_recovery_attempts: int
    stop_conditions: dict[str, Any]
    language: dict[str, Any]
    persona: dict[str, Any]

    @property
    def required_assertions(self) -> list[MotiveAssertion]:
        return [a for a in self.assertions if a.required]


def _facts_to_dict(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {str(f["id"]): f.get("value") for f in facts if "id" in f}


def parse_scenario(content: dict[str, Any]) -> Scenario:
    motive = content.get("motive") or {}
    assertions = [
        MotiveAssertion(
            id=str(item.get("id")),
            type=str(item.get("type")),
            required=bool(item.get("required", False)),
            expectation=item.get("expectation") or {},
        )
        for item in (motive.get("assertions") or [])
    ]

    behaviour = content.get("behaviour") or {}
    recovery = behaviour.get("recovery") or {}

    return Scenario(
        objective=str(motive.get("objective") or ""),
        facts=_facts_to_dict(content.get("facts") or []),
        initial_state=dict(content.get("initial_state") or {}),
        assertions=assertions,
        allowed_actions=list(behaviour.get("allowed_actions") or []),
        max_recovery_attempts=int(recovery.get("max_attempts", 0)),
        stop_conditions=dict(content.get("stop_conditions") or {}),
        language=dict(content.get("language") or {}),
        persona=dict(content.get("persona") or {}),
    )
