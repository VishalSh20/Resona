"""Composable persona trait deltas (migration doc §7).

The 14 traits are treated as composable trait *deltas* on a neutral baseline,
not mutually exclusive archetypes. Each trait applies at a fixed strength (no
intensity levels); deltas are added to the baseline and clamped. Seeded jitter is
applied last (see :mod:`voiceeval.runtime.caller.persona`).
"""

from __future__ import annotations

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import Personality

#: Hard < 3 traits per caller (§7 composition rules).
MAX_TRAITS = 3

#: Rejected at config validation (§7).
CONTRADICTORY_PAIRS: frozenset[frozenset[Personality]] = frozenset(
    {
        frozenset({Personality.CONCISE, Personality.VERBOSE}),
        frozenset({Personality.COOPERATIVE, Personality.UNCOOPERATIVE}),
        frozenset({Personality.SUPPORTIVE, Personality.ABUSIVE}),
        frozenset({Personality.INTERRUPTOR, Personality.HESITANT}),
    }
)

#: Inclusive clamp ranges for numeric persona parameters. Values outside a range
#: after deltas+jitter are clamped, never rejected.
NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "pace": (0.5, 1.6),
    "base_loudness": (0.0, 1.0),
    "patience": (0.0, 1.0),
    "irritability": (0.0, 1.0),
    "agreeableness": (0.0, 1.0),
    "hostility_ceiling": (0.0, 1.0),
    "response_latency_ms": (0.0, 5000.0),
    "endpointing_delay_ms": (0.0, 3000.0),
    "overlap_tendency": (0.0, 1.0),
    "yield_threshold": (0.0, 1.0),
    "floor_hold_cap_ms": (0.0, 20_000.0),
    "utterance_length": (0.0, 1.0),
    "disfluency_rate": (0.0, 1.0),
    "formality": (0.0, 1.0),
    "backchannel_rate": (0.0, 1.0),
    "cooperation": (0.0, 1.0),
    "mishear_rate": (0.0, 1.0),
    "offtopic_rate": (0.0, 1.0),
}

#: Fixed-strength deltas per trait. Keys are PersonaProfile field names.
TRAIT_DELTAS: dict[Personality, dict[str, float]] = {
    Personality.SUPPORTIVE: {
        "agreeableness": 0.25,
        "irritability": -0.15,
        "yield_threshold": 0.2,
        "backchannel_rate": 0.2,
        "hostility_ceiling": -0.1,
        "patience": 0.1,
    },
    Personality.COOPERATIVE: {
        "cooperation": 0.3,
        "agreeableness": 0.1,
        "response_latency_ms": -100.0,
    },
    Personality.UNCOOPERATIVE: {
        "cooperation": -0.5,
        "agreeableness": -0.2,
        "offtopic_rate": 0.15,
        "yield_threshold": -0.1,
    },
    Personality.SKEPTICAL: {
        "agreeableness": -0.15,
        "patience": 0.05,
        "utterance_length": 0.1,
    },
    Personality.DEMANDING: {
        "irritability": 0.25,
        "hostility_ceiling": 0.2,
        "patience": -0.15,
        "utterance_length": 0.1,
        "formality": 0.1,
    },
    Personality.ABUSIVE: {
        "irritability": 0.5,
        "hostility_ceiling": 0.5,
        "agreeableness": -0.4,
        "yield_threshold": -0.35,
        "floor_hold_cap_ms": 3000.0,
        "patience": -0.3,
    },
    Personality.CONCISE: {
        "utterance_length": -0.35,
        "disfluency_rate": -0.05,
        "backchannel_rate": -0.05,
    },
    Personality.VERBOSE: {
        "utterance_length": 0.45,
        "floor_hold_cap_ms": 4000.0,
        "disfluency_rate": 0.05,
    },
    Personality.HESITANT: {
        "disfluency_rate": 0.3,
        "response_latency_ms": 500.0,
        "endpointing_delay_ms": 400.0,
        "yield_threshold": 0.3,
    },
    Personality.REPETITIVE: {
        "utterance_length": 0.15,
        "floor_hold_cap_ms": 1500.0,
    },
    Personality.CONFUSED: {
        "mishear_rate": 0.35,
        "response_latency_ms": 400.0,
        "disfluency_rate": 0.1,
    },
    Personality.EMOTIONAL: {
        "irritability": 0.2,
        "pace": 0.1,
        "disfluency_rate": 0.15,
        "backchannel_rate": 0.05,
    },
    Personality.INTERRUPTOR: {
        "overlap_tendency": 0.5,
        "floor_hold_cap_ms": 5000.0,
        "yield_threshold": -0.4,
        "response_latency_ms": -200.0,
        "patience": -0.1,
    },
    Personality.IMPATIENT: {
        "response_latency_ms": -350.0,
        "endpointing_delay_ms": -400.0,
        "patience": -0.35,
        "utterance_length": -0.1,
        "irritability": 0.15,
    },
}

#: Barge-in triggers each trait enables (§8.3). Union of the selected traits'.
TRAIT_BARGE_IN_TRIGGERS: dict[Personality, tuple[str, ...]] = {
    Personality.INTERRUPTOR: ("early_answer", "repetition", "competitive"),
    Personality.IMPATIENT: ("monologue_impatience",),
    Personality.DEMANDING: ("monologue_impatience", "escalation"),
    Personality.ABUSIVE: ("emotional", "monologue_impatience"),
    Personality.EMOTIONAL: ("emotional",),
    Personality.REPETITIVE: ("repetition",),
}


def trait_composition_errors(traits: list[Personality]) -> list[str]:
    """Return §7 composition-rule violations as human-readable strings."""
    errors: list[str] = []
    if len(traits) > MAX_TRAITS:
        errors.append(
            f"at most {MAX_TRAITS} persona traits per caller; got {len(traits)}"
        )
    if len(set(traits)) != len(traits):
        errors.append("persona traits must be unique")
    chosen = set(traits)
    for pair in CONTRADICTORY_PAIRS:
        if pair <= chosen:
            a, b = sorted(str(t) for t in pair)
            errors.append(f"contradictory persona traits: {a} + {b}")
    return errors


def validate_trait_selection(traits: list[Personality]) -> None:
    """Enforce §7 composition rules; raise :class:`ValidationError` on violation."""
    errors = trait_composition_errors(traits)
    if errors:
        raise ValidationError("; ".join(errors))


__all__ = [
    "CONTRADICTORY_PAIRS",
    "MAX_TRAITS",
    "NUMERIC_BOUNDS",
    "TRAIT_BARGE_IN_TRIGGERS",
    "TRAIT_DELTAS",
    "trait_composition_errors",
    "validate_trait_selection",
]
