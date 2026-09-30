"""Aggregation statistics.

Aggregation depends on the metric's value type. Continuous metrics expose
mean/median/min/max/stddev; boolean metrics expose true/false counts and a
success rate; categorical metrics expose category counts and percentages;
ordinal metrics expose mean/median and a distribution.

Percentiles are only reported once the sample is large enough. With the MVP's
three repetitions, ``p95`` is ``null`` and ``percentile_status`` is
``insufficient_sample`` — three samples never imply a stable P95.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

DEFAULT_PERCENTILE_MIN_SAMPLE = 20


@dataclass
class AggregateStats:
    value_type: str
    sample_count: int
    coverage_count: int
    availability_ratio: float
    values: list[float | bool | str] = field(default_factory=list)
    mean: float | None = None
    median: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    stddev: float | None = None
    p95: float | None = None
    percentile_status: str = "not_applicable"
    category_counts: dict[str, Any] | None = None
    distribution: dict[str, int] | None = None


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = fraction * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def aggregate(
    values: list[float | bool | str],
    value_type: str,
    *,
    sample_count: int,
    coverage_count: int | None = None,
    config: dict[str, Any] | None = None,
) -> AggregateStats:
    """Aggregate ``values`` according to ``value_type``.

    ``sample_count`` is the number of logical samples expected (e.g. the repeat
    count); ``coverage_count`` defaults to the number of computed values.
    """
    config = config or {}
    coverage = len(values) if coverage_count is None else coverage_count
    availability = (coverage / sample_count) if sample_count else 0.0
    stats = AggregateStats(
        value_type=value_type,
        sample_count=sample_count,
        coverage_count=coverage,
        availability_ratio=availability,
        values=list(values),
    )

    if value_type == "boolean":
        true_count = sum(1 for value in values if value is True or value == "true")
        false_count = len(values) - true_count
        stats.category_counts = {
            "true": true_count,
            "false": false_count,
            "success_rate": (true_count / len(values)) if values else None,
        }
        stats.mean = stats.category_counts["success_rate"]
        return stats

    if value_type == "category" or value_type == "text":
        counts: dict[str, int] = {}
        for value in values:
            counts[str(value)] = counts.get(str(value), 0) + 1
        total = len(values)
        stats.category_counts = {
            "counts": counts,
            "percentages": {
                key: (count / total if total else 0.0) for key, count in counts.items()
            },
        }
        return stats

    # numeric / ordinal
    numeric = [float(value) for value in values]
    if numeric:
        ordered = sorted(numeric)
        stats.mean = sum(numeric) / len(numeric)
        stats.median = _median(ordered)
        stats.min_value = ordered[0]
        stats.max_value = ordered[-1]
        stats.stddev = _stddev(numeric)

        min_sample = int(config.get("percentile_min_sample", DEFAULT_PERCENTILE_MIN_SAMPLE))
        if len(numeric) >= min_sample:
            stats.p95 = _percentile(ordered, 0.95)
            stats.percentile_status = "computed"
        else:
            stats.p95 = None
            stats.percentile_status = "insufficient_sample"

        if config.get("kind") == "ordinal":
            distribution: dict[str, int] = {}
            for value in numeric:
                key = str(int(value)) if float(value).is_integer() else str(value)
                distribution[key] = distribution.get(key, 0) + 1
            stats.distribution = distribution
    return stats


def _median(sorted_values: list[float]) -> float:
    length = len(sorted_values)
    mid = length // 2
    if length % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


__all__ = ["DEFAULT_PERCENTILE_MIN_SAMPLE", "AggregateStats", "aggregate"]
