"""Interpreting bounded answers and the fixed aggregation math (spec §4.3/§8).

All of this is code, never an LLM. Same inputs give the same output.
"""

from __future__ import annotations

from voiceeval.judging.config import ANCHORS


def noul_value(probability: float, invert: bool = False) -> float:
    """Probability of the condition, optionally inverted for "bad thing" questions."""
    return 1.0 - probability if invert else probability


def choice_value(
    probabilities: dict[str, float] | None,
    credits: dict[str, float | None],
) -> float | None:
    """Expected credit over applicable options.

    ``None`` credits are N/A options; when N/A probability reaches 50% the
    question drops out of the score entirely (returns ``None``).
    """
    if not probabilities:
        return None

    p_na = sum(
        probability
        for key, probability in probabilities.items()
        if credits.get(key) is None
    )
    if p_na >= 0.5:
        return None

    live = {
        key: probability
        for key, probability in probabilities.items()
        if credits.get(key) is not None
    }
    total = sum(live.values())
    if total <= 0:
        return None
    return sum(credits[key] * probability for key, probability in live.items()) / total


def score_value(
    probabilities: dict[str, float] | None,
    n_levels: int,
    *,
    score: float | None = None,
) -> float:
    """Normalized 0-1 position along an ordered scale.

    The Decisions API keys ``probabilities`` by the level index as a string
    ("0".."n-1") and returns ``score`` as the probability-weighted position.
    We prefer the explicit probabilities; ``score`` is a fallback.
    """
    levels = max(2, n_levels)
    if probabilities:
        weighted = 0.0
        total = 0.0
        for index in range(levels):
            probability = probabilities.get(str(index), probabilities.get(index, 0.0))
            weighted += index * probability
            total += probability
        if total > 0:
            return (weighted / total) / (levels - 1)
    if score is not None:
        return max(0.0, min(1.0, score / (levels - 1)))
    return 0.0


def weighted_mean(items: list[tuple[float | None, float]]) -> float | None:
    live = [(value, weight) for value, weight in items if value is not None]
    if not live:
        return None
    return sum(value * weight for value, weight in live) / sum(weight for _, weight in live)


def to_1_5(x: float, anchors: list[tuple[float, float]] | None = None) -> float:
    anchors = anchors or ANCHORS
    if x <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return anchors[-1][1]


def finalize_judge_metric(x: float | None, caps: list[int] | None = None) -> int | None:
    """Map a 0-1 aggregate to an integer 1-5 and apply the strict caps (§8)."""
    if x is None:
        return None
    score = int(to_1_5(x) + 0.5)
    score = max(1, min(5, score))
    if caps:
        score = min([score, *caps])
    return score


def normalized(x: float | str | bool | None) -> float | None:
    """Normalize a metric value to 0-100, higher is better, where meaningful."""
    if x is None or isinstance(x, str) or isinstance(x, bool):
        return None
    return float(x) * 100.0


__all__ = [
    "choice_value",
    "finalize_judge_metric",
    "normalized",
    "noul_value",
    "score_value",
    "to_1_5",
    "weighted_mean",
]
