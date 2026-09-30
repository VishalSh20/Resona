"""Composite score computation.

Never average raw metrics of different units. Each raw metric is normalized to
0-100 (using its versioned normalization config), combined into a category score,
weighted by category, and summed. Missing metrics are never redistributed: their
weight is reported as ``unavailable_weight`` and the composite is ``INCOMPLETE``
when a critical metric is unavailable or the coverage policy is not met.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_COMPOSITE_VERSION = "composite.v1"

DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "motive": 0.40,
    "conversation": 0.35,
    "voice": 0.15,
    "language": 0.10,
}

DEFAULT_COVERAGE_POLICY: dict[str, Any] = {
    "required_metrics": ["motive_fulfillment", "semantic_understanding"],
    "minimum_coverage_ratio": 0.90,
    "renormalize_optional_weights": False,
}


@dataclass(frozen=True)
class CompositeMetricInput:
    metric_key: str
    category: str | None
    normalization_config: dict[str, Any]
    value: float | bool | str | None
    weight: float | None = None  # within-category weight; equal share by default


@dataclass
class CompositeOutcome:
    status: str
    score_0_100: float | None
    coverage_ratio: float
    unavailable_weight: float
    category_scores: dict[str, float | None] = field(default_factory=dict)
    missing_metrics: list[str] = field(default_factory=list)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def normalize_value(normalization_config: dict[str, Any], value: Any) -> float | None:
    """Normalize a raw metric value to 0-100, or ``None`` if not representable."""
    if value is None:
        return None
    kind = normalization_config.get("kind", "linear")

    if kind == "linear":
        best = normalization_config.get("best")
        worst = normalization_config.get("worst")
        if best is None or worst is None or best == worst:
            return None
        return _clamp((worst - float(value)) / (worst - best) * 100.0)

    if kind == "ratio":
        return _clamp(float(value) * 100.0)

    if kind == "boolean":
        return 100.0 if value else 0.0

    if kind == "ordinal":
        low = float(normalization_config.get("min", 1))
        high = float(normalization_config.get("max", 5))
        if high == low:
            return None
        return _clamp((float(value) - low) / (high - low) * 100.0)

    if kind == "inverse_count":
        best = float(normalization_config.get("best", 0))
        worst = float(normalization_config.get("worst", 1))
        if worst == best:
            return None
        return _clamp((worst - float(value)) / (worst - best) * 100.0)

    if kind == "category":
        mapping = normalization_config.get("mapping") or {}
        mapped = mapping.get(str(value))
        return None if mapped is None else _clamp(float(mapped))

    return None


def compute_composite(
    metrics: list[CompositeMetricInput],
    *,
    weights: dict[str, float] | None = None,
    coverage_policy: dict[str, Any] | None = None,
) -> CompositeOutcome:
    weights = weights or DEFAULT_CATEGORY_WEIGHTS
    policy = coverage_policy or DEFAULT_COVERAGE_POLICY

    in_scope = [m for m in metrics if m.category in weights]
    if not in_scope:
        return CompositeOutcome(
            status="unavailable",
            score_0_100=None,
            coverage_ratio=0.0,
            unavailable_weight=1.0,
        )

    by_category: dict[str, list[CompositeMetricInput]] = {}
    for metric in in_scope:
        by_category.setdefault(str(metric.category), []).append(metric)

    total_weight = 0.0
    available_weight = 0.0
    score = 0.0
    missing: list[str] = []
    category_acc: dict[str, dict[str, Any]] = {}

    for category, category_metrics in by_category.items():
        category_weight = weights[category]
        equal_share = 1.0 / len(category_metrics)
        acc = category_acc.setdefault(category, {"score": 0.0, "weight": 0.0, "metrics": {}})
        for metric in category_metrics:
            share = metric.weight if metric.weight is not None else equal_share
            effective = category_weight * share
            total_weight += effective
            normalized = normalize_value(metric.normalization_config, metric.value)
            if normalized is None:
                missing.append(metric.metric_key)
                continue
            available_weight += effective
            score += normalized * effective
            acc["score"] += normalized * effective
            acc["weight"] += effective
            acc["metrics"][metric.metric_key] = round(normalized, 4)

    # A whole category with no metrics at all still carries its weight; that
    # weight is unavailable and must not be redistributed.
    for category, category_weight in weights.items():
        if category not in by_category:
            total_weight += category_weight

    coverage_ratio = (available_weight / total_weight) if total_weight else 0.0
    category_scores: dict[str, float | None] = {}
    for category in weights:
        acc = category_acc.get(category)
        if acc is None or acc["weight"] == 0.0:
            category_scores[category] = None
        else:
            category_scores[category] = round(acc["score"] / acc["weight"], 2)

    critical = set(policy.get("required_metrics") or [])
    # A required metric that was never supplied at all is just as unavailable as
    # one that was supplied without a value.
    supplied = {metric.metric_key for metric in in_scope}
    for key in critical:
        if key not in supplied and key not in missing:
            missing.append(key)
    critical_missing = [key for key in missing if key in critical]
    minimum = float(policy.get("minimum_coverage_ratio", 0.0))

    if critical_missing or coverage_ratio < minimum:
        status = "incomplete"
    else:
        status = "complete"

    return CompositeOutcome(
        status=status,
        score_0_100=round(score, 2) if available_weight > 0 else None,
        coverage_ratio=round(coverage_ratio, 4),
        unavailable_weight=round(1.0 - coverage_ratio, 4),
        category_scores=category_scores,
        missing_metrics=sorted(missing),
    )


__all__ = [
    "CompositeMetricInput",
    "CompositeOutcome",
    "DEFAULT_CATEGORY_WEIGHTS",
    "DEFAULT_COMPOSITE_VERSION",
    "DEFAULT_COVERAGE_POLICY",
    "compute_composite",
    "normalize_value",
]
