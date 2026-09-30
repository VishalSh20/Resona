"""Per-attempt seeded RNG and decision log (migration doc §8.7).

Every stochastic choice the caller makes — latency draws, filler use, barge-in
jitter, persona jitter — comes from one seeded generator, and every draw is
recorded so a failed evaluation can be explained and replayed at the decision
level.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class DecisionDraw:
    """One recorded random draw."""

    name: str
    kind: str
    value: Any


class SeededRng:
    """Deterministic RNG that records every draw it produces."""

    def __init__(self, seed: int | str | None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._draws: list[DecisionDraw] = []

    @property
    def seed(self) -> int | str | None:
        return self._seed

    @property
    def draws(self) -> list[DecisionDraw]:
        return list(self._draws)

    def uniform(self, name: str, low: float, high: float) -> float:
        value = self._rng.uniform(low, high)
        self._draws.append(DecisionDraw(name, "uniform", value))
        return value

    def gauss(self, name: str, mu: float, sigma: float) -> float:
        value = self._rng.gauss(mu, sigma)
        self._draws.append(DecisionDraw(name, "gauss", value))
        return value

    def chance(self, name: str, probability: float) -> bool:
        value = self._rng.random() < probability
        self._draws.append(DecisionDraw(name, "chance", value))
        return value

    def choice(self, name: str, options: Sequence[Any]) -> Any:
        value = self._rng.choice(list(options))
        self._draws.append(DecisionDraw(name, "choice", value))
        return value

    def jitter(self, name: str, value: float, *, sigma: float) -> float:
        """Return ``value`` nudged by seeded gaussian noise."""
        return value + self.gauss(name, 0.0, sigma)


__all__ = ["DecisionDraw", "SeededRng"]
