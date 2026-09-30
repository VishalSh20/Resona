"""Humanness distribution checks (§12).

Compares measured caller behavior (response latency, overlap rate, utterance
length, filler rate) against per-persona bands. This is the layer that answers
"does the caller behave like the persona it was configured as?" — unit-testable
without audio.
"""

from __future__ import annotations

from dataclasses import dataclass

from voiceeval.runtime.caller.persona import PersonaProfile


@dataclass(frozen=True)
class HumannessSample:
    response_latency_ms: int = 0
    overlap: bool = False
    utterance_len: int = 0
    filler: bool = False


@dataclass(frozen=True)
class Band:
    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


def expected_bands(persona: PersonaProfile) -> dict[str, Band]:
    """Starting-point bands derived from the resolved persona parameters."""
    return {
        "response_latency_ms": Band(
            persona.response_latency_ms * 0.5, persona.response_latency_ms * 1.8
        ),
        "overlap_rate": Band(
            max(0.0, persona.overlap_tendency - 0.15),
            min(1.0, persona.overlap_tendency + 0.15),
        ),
        "utterance_len": Band(
            max(1.0, persona.utterance_length * 4),
            persona.utterance_length * 24 + 3,
        ),
        "filler_rate": Band(
            max(0.0, persona.disfluency_rate - 0.15),
            min(1.0, persona.disfluency_rate + 0.25),
        ),
    }


def distribution(samples: list[HumannessSample]) -> dict[str, float]:
    if not samples:
        return {
            "response_latency_ms": 0.0,
            "overlap_rate": 0.0,
            "utterance_len": 0.0,
            "filler_rate": 0.0,
        }
    count = len(samples)
    return {
        "response_latency_ms": sum(s.response_latency_ms for s in samples) / count,
        "overlap_rate": sum(1 for s in samples if s.overlap) / count,
        "utterance_len": sum(s.utterance_len for s in samples) / count,
        "filler_rate": sum(1 for s in samples if s.filler) / count,
    }


def check_humanness(
    samples: list[HumannessSample], persona: PersonaProfile
) -> list[str]:
    """Return human-readable violations of the persona's bands (empty == pass)."""
    if not samples:
        return ["no samples"]
    bands = expected_bands(persona)
    measured = distribution(samples)
    return [
        f"{name} {measured[name]:.3f} outside [{band.low:.3f}, {band.high:.3f}]"
        for name, band in bands.items()
        if not band.contains(measured[name])
    ]


__all__ = [
    "Band",
    "HumannessSample",
    "check_humanness",
    "distribution",
    "expected_bands",
]
