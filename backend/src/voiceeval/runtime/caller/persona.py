"""Persona resolution: traits → a versioned, orthogonal parameter profile (§7).

A persona is a resolved profile over eight orthogonal parameter groups (Voice,
Temperament, Turn-taking, Speech style, Cooperation, Cognition, Language,
Environment). Resolution order is: **neutral baseline → trait deltas →
scenario overrides → seeded jitter**. The resolved profile is snapshotted into
the execution manifest so a call is reproducible and explainable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.caller.traits import (
    NUMERIC_BOUNDS,
    TRAIT_BARGE_IN_TRIGGERS,
    TRAIT_DELTAS,
    validate_trait_selection,
)

PERSONA_PROFILE_VERSION = "persona.v1"

#: A plain, mildly cooperative adult — the neutral baseline traits are added to.
NEUTRAL_BASELINE: dict[str, float] = {
    "pace": 1.0,
    "base_loudness": 0.5,
    "patience": 0.6,
    "irritability": 0.2,
    "agreeableness": 0.6,
    "hostility_ceiling": 0.2,
    "response_latency_ms": 600.0,
    "endpointing_delay_ms": 700.0,
    "overlap_tendency": 0.15,
    "yield_threshold": 0.5,
    "floor_hold_cap_ms": 4000.0,
    "utterance_length": 0.5,
    "disfluency_rate": 0.1,
    "formality": 0.5,
    "backchannel_rate": 0.3,
    "cooperation": 0.7,
    "mishear_rate": 0.05,
    "offtopic_rate": 0.05,
}

#: Seeded jitter sigma per numeric field (keeps calls from sounding identical).
JITTER_SIGMA: dict[str, float] = {
    "response_latency_ms": 80.0,
    "endpointing_delay_ms": 60.0,
    "overlap_tendency": 0.05,
    "disfluency_rate": 0.03,
    "patience": 0.03,
    "irritability": 0.03,
}


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return max(low, min(high, value))


@dataclass(frozen=True)
class PersonaProfile:
    version: str
    traits: tuple[str, ...]
    speaker: str = "shubh"
    pace: float = 1.0
    base_loudness: float = 0.5
    patience: float = 0.6
    irritability: float = 0.2
    agreeableness: float = 0.6
    hostility_ceiling: float = 0.2
    response_latency_ms: float = 600.0
    endpointing_delay_ms: float = 700.0
    overlap_tendency: float = 0.15
    yield_threshold: float = 0.5
    floor_hold_cap_ms: float = 4000.0
    utterance_length: float = 0.5
    disfluency_rate: float = 0.1
    formality: float = 0.5
    backchannel_rate: float = 0.3
    cooperation: float = 0.7
    mishear_rate: float = 0.05
    offtopic_rate: float = 0.05
    primary_language: str = "en-IN"
    secondary_language: str | None = None
    mixing: str = "none"
    mix_ratio: float = 0.0
    ambient: str = "quiet"
    line_quality: str = "clean"
    barge_in_triggers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaProfile":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class PersonaResolver:
    """Resolves a trait selection into a :class:`PersonaProfile`."""

    def resolve(
        self,
        traits: list[str | Personality],
        *,
        overrides: dict[str, Any] | None = None,
        rng: SeededRng | None = None,
        language: dict[str, Any] | None = None,
        speaker: str | None = None,
        ambient: str | None = None,
        line_quality: str | None = None,
    ) -> PersonaProfile:
        selected = [Personality(str(t)) for t in traits]
        validate_trait_selection(selected)

        values: dict[str, float] = dict(NEUTRAL_BASELINE)
        triggers: list[str] = []
        for trait in selected:
            for field_name, delta in TRAIT_DELTAS.get(trait, {}).items():
                values[field_name] = values.get(field_name, 0.0) + delta
            triggers.extend(TRAIT_BARGE_IN_TRIGGERS.get(trait, ()))

        # Scenario overrides (only numeric persona knobs; unknown keys ignored).
        for key, raw in (overrides or {}).items():
            if key in values and isinstance(raw, (int, float)):
                values[key] = float(raw)

        # Seeded jitter last, then clamp.
        if rng is not None:
            for field_name, sigma in JITTER_SIGMA.items():
                values[field_name] = rng.gauss(f"persona.{field_name}", values[field_name], sigma)

        for field_name, bounds in NUMERIC_BOUNDS.items():
            if field_name in values:
                values[field_name] = _clamp(values[field_name], bounds)

        lang = language or {}
        primary = str(lang.get("primary") or "en-IN")
        secondary = lang.get("secondary")
        mixing = str(lang.get("mixing") or ("code-switch" if lang.get("code_switch") else "none"))
        mix_ratio = float(lang.get("mix_ratio", 0.0) or 0.0)

        return PersonaProfile(
            version=PERSONA_PROFILE_VERSION,
            traits=tuple(t.value for t in selected),
            speaker=speaker or "shubh",
            primary_language=primary,
            secondary_language=secondary,
            mixing=mixing,
            mix_ratio=mix_ratio,
            ambient=ambient or "quiet",
            line_quality=line_quality or "clean",
            barge_in_triggers=tuple(sorted(set(triggers))),
            **values,
        )


__all__ = [
    "JITTER_SIGMA",
    "NEUTRAL_BASELINE",
    "PERSONA_PROFILE_VERSION",
    "PersonaProfile",
    "PersonaResolver",
]
