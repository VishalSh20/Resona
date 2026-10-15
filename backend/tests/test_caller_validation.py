"""Trait-composition validation wired into scenario and generation validators (§7)."""

from __future__ import annotations

from voiceeval.domain.enums import MetricKey, Personality
from voiceeval.generation.deterministic import validate_profile
from voiceeval.generation.models import CallerProfile, SimulationInput
from voiceeval.services.validation.validators import validate_scenario

_PERSONA = {"traits": [], "age": 30}


def _scenario(traits):
    return {"persona": {"age": 30, "traits": traits}, "facts": []}


def test_scenario_validator_accepts_valid_composition():
    assert validate_scenario(_scenario(["SKEPTICAL", "CONCISE"])).passed


def test_scenario_validator_rejects_contradictory_pair():
    check = validate_scenario(_scenario(["CONCISE", "VERBOSE"]))
    assert check.passed is False
    assert "contradictory" in (check.details or "")


def test_scenario_validator_rejects_too_many_traits():
    check = validate_scenario(
        _scenario(["SKEPTICAL", "CONCISE", "EMOTIONAL", "REPETITIVE"])
    )
    assert check.passed is False


def test_scenario_validator_rejects_unknown_trait():
    assert validate_scenario(_scenario(["NOT_A_TRAIT"])).passed is False


def test_generation_profile_validator_enforces_composition():
    simulation = SimulationInput(
        languages=["en"],
        metric_set=[MetricKey.RELEVANCY],
        personalities=[Personality.CONCISE, Personality.VERBOSE],
        evaluator_count=1,
    )
    profile = CallerProfile(
        major_language="en",
        personality=[Personality.CONCISE, Personality.VERBOSE],
    )
    result = validate_profile(profile, simulation)
    assert result.passed is False
    assert any("contradictory" in e for e in result.errors)
