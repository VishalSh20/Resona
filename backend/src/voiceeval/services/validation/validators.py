"""Independent evaluator-content validators.

Each validator returns a :class:`Check`; none of them mutate state or touch the
database, so they are trivially unit-testable and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.traits import trait_composition_errors
from voiceeval.services.capabilities import CAPABILITY_MATRIX

REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "persona",
    "language",
    "motive",
    "behaviour",
    "stop_conditions",
    "evaluation_criteria",
)

EXPECTED_SCHEMA_VERSION = "evaluator.v1"


@dataclass(frozen=True)
class Check:
    key: str
    severity: Literal["error", "warning"]
    passed: bool
    details: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "severity": self.severity,
            "passed": self.passed,
            "details": self.details,
        }


def _error(key: str, passed: bool, details: str | None = None) -> Check:
    return Check(key=key, severity="error", passed=passed, details=details)


def _warning(key: str, passed: bool, details: str | None = None) -> Check:
    return Check(key=key, severity="warning", passed=passed, details=details)


def validate_schema(content: dict) -> Check:
    if content.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        return _error(
            "schema_validity",
            False,
            f"schema_version must be '{EXPECTED_SCHEMA_VERSION}'",
        )
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in content]
    if missing:
        return _error(
            "schema_validity", False, f"missing required keys: {', '.join(missing)}"
        )
    return _error("schema_validity", True)


def validate_scenario(content: dict) -> Check:
    persona = content.get("persona")
    if not isinstance(persona, dict) or not persona:
        return _error("scenario_validity", False, "persona must be a non-empty object")
    facts = content.get("facts")
    if facts is not None and not isinstance(facts, list):
        return _error("scenario_validity", False, "facts must be a list when present")
    traits = persona.get("traits") or persona.get("personality") or []
    if isinstance(traits, list) and traits:
        try:
            selected = [Personality(str(trait)) for trait in traits]
        except ValueError:
            return _error(
                "scenario_validity",
                False,
                f"unknown persona traits: {', '.join(str(t) for t in traits)}",
            )
        composition_errors = trait_composition_errors(selected)
        if composition_errors:
            return _error("scenario_validity", False, "; ".join(composition_errors))
    return _error("scenario_validity", True)


def validate_motive(content: dict) -> Check:
    motive = content.get("motive")
    if not isinstance(motive, dict):
        return _error("motive_validity", False, "motive must be an object")
    objective = motive.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        return _error("motive_validity", False, "motive.objective must be a non-empty string")
    assertions = motive.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        return _error("motive_validity", False, "motive.assertions must be a non-empty list")
    for i, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            return _error("motive_validity", False, f"assertion[{i}] must be an object")
        for field in ("id", "type", "required"):
            if field not in assertion:
                return _error(
                    "motive_validity", False, f"assertion[{i}] is missing '{field}'"
                )
    return _error("motive_validity", True)


def validate_state(content: dict) -> Check:
    initial_state = content.get("initial_state")
    if initial_state is not None and not isinstance(initial_state, dict):
        return _error("state_validity", False, "initial_state must be an object when present")
    return _error("state_validity", True)


def validate_success_conditions(content: dict) -> Check:
    stop = content.get("stop_conditions")
    if not isinstance(stop, dict):
        return _error(
            "success_conditions_validity", False, "stop_conditions must be an object"
        )
    if "natural_success" not in stop:
        return _error(
            "success_conditions_validity",
            False,
            "stop_conditions.natural_success is required",
        )
    return _error("success_conditions_validity", True)


def validate_behaviour(content: dict) -> Check:
    behaviour = content.get("behaviour")
    if not isinstance(behaviour, dict):
        return _error("behaviour_validity", False, "behaviour must be an object")
    allowed_actions = behaviour.get("allowed_actions")
    if not isinstance(allowed_actions, list) or not allowed_actions:
        return _error(
            "behaviour_validity",
            False,
            "behaviour.allowed_actions must be a non-empty list",
        )
    return _error("behaviour_validity", True)


def validate_language(content: dict) -> Check:
    language = content.get("language")
    if not isinstance(language, dict):
        return _error("language_validity", False, "language must be an object")
    primary = language.get("primary")
    if not isinstance(primary, str) or not primary.strip():
        return _error("language_validity", False, "language.primary must be a non-empty string")
    allowed = language.get("allowed")
    if not isinstance(allowed, list) or not allowed:
        return _error("language_validity", False, "language.allowed must be a non-empty list")
    return _error("language_validity", True)


def validate_criteria(content: dict) -> Check:
    criteria = content.get("evaluation_criteria")
    if not isinstance(criteria, list) or not criteria:
        return _error(
            "criteria_validity", False, "evaluation_criteria must be a non-empty list"
        )
    for i, item in enumerate(criteria):
        if not isinstance(item, dict) or not isinstance(item.get("metric"), str):
            return _error(
                "criteria_validity", False, f"evaluation_criteria[{i}] needs a 'metric'"
            )
    return _error("criteria_validity", True)


def validate_capabilities(content: dict) -> Check:
    criteria = content.get("evaluation_criteria", [])
    unknown = [
        item.get("metric")
        for item in criteria
        if isinstance(item, dict) and item.get("metric") not in CAPABILITY_MATRIX
    ]
    if unknown:
        return _error(
            "capability_validity",
            False,
            f"unknown metrics (no capability rule): {', '.join(unknown)}",
        )
    return _error("capability_validity", True)


ALL_VALIDATORS = (
    validate_schema,
    validate_scenario,
    validate_motive,
    validate_state,
    validate_success_conditions,
    validate_behaviour,
    validate_language,
    validate_criteria,
    validate_capabilities,
)


def run_validators(content: dict) -> list[Check]:
    return [validator(content) for validator in ALL_VALIDATORS]
