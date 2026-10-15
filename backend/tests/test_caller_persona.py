"""Persona resolution, trait composition and seeded RNG (§7, §8.7)."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.persona import (
    NEUTRAL_BASELINE,
    PersonaProfile,
    PersonaResolver,
)
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.caller.traits import (
    CONTRADICTORY_PAIRS,
    MAX_TRAITS,
    NUMERIC_BOUNDS,
    validate_trait_selection,
)


def test_rejects_more_than_max_traits():
    assert MAX_TRAITS == 3
    with pytest.raises(ValidationError):
        validate_trait_selection(
            [
                Personality.CONCISE,
                Personality.SKEPTICAL,
                Personality.EMOTIONAL,
                Personality.REPETITIVE,
            ]
        )


@pytest.mark.parametrize("pair", sorted(CONTRADICTORY_PAIRS, key=lambda p: sorted(p)))
def test_rejects_contradictory_pairs(pair):
    with pytest.raises(ValidationError):
        validate_trait_selection(sorted(pair, key=str))


def test_accepts_valid_composition():
    validate_trait_selection([Personality.SKEPTICAL, Personality.CONCISE])


def test_resolver_applies_fixed_strength_deltas():
    resolver = PersonaResolver()
    abusive = resolver.resolve([Personality.ABUSIVE])
    assert abusive.irritability > NEUTRAL_BASELINE["irritability"]
    assert abusive.hostility_ceiling > NEUTRAL_BASELINE["hostility_ceiling"]
    assert abusive.yield_threshold < NEUTRAL_BASELINE["yield_threshold"]


def test_resolver_clamps_to_bounds():
    resolver = PersonaResolver()
    profile = resolver.resolve([Personality.ABUSIVE, Personality.DEMANDING])
    for name, (low, high) in NUMERIC_BOUNDS.items():
        value = getattr(profile, name)
        assert low <= value <= high, name


def test_resolver_is_deterministic_for_a_seed():
    resolver = PersonaResolver()
    a = resolver.resolve([Personality.HESITANT], rng=SeededRng("seed-1"))
    b = resolver.resolve([Personality.HESITANT], rng=SeededRng("seed-1"))
    assert a == b
    assert isinstance(a, PersonaProfile)
    assert a.version == "persona.v1"


def test_resolver_records_language_and_triggers():
    resolver = PersonaResolver()
    profile = resolver.resolve(
        [Personality.INTERRUPTOR],
        language={"primary": "hi-IN", "secondary": "en-IN", "mixing": "code-switch", "mix_ratio": 0.4},
    )
    assert profile.primary_language == "hi-IN"
    assert profile.secondary_language == "en-IN"
    assert profile.mixing == "code-switch"
    assert "early_answer" in profile.barge_in_triggers


def test_persona_profile_round_trips():
    resolver = PersonaResolver()
    profile = resolver.resolve([Personality.COOPERATIVE])
    assert PersonaProfile.from_dict(profile.to_dict()) == profile


def test_seeded_rng_reproducible_and_records_draws():
    a = SeededRng(7)
    b = SeededRng(7)
    assert a.uniform("latency", 0, 100) == b.uniform("latency", 0, 100)
    assert [d.name for d in a.draws] == ["latency"]
    assert a.chance("filler", 0.5) in (True, False)
    assert len(a.draws) == 2
