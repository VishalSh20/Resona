"""Aggregation and composite scoring.

Collapses per-run metric results into per-evaluator aggregates with explicit
coverage, then normalizes and weights them into a versioned composite score.
Percentiles are only reported for sufficiently large samples, and missing metric
weight is never silently redistributed.
"""

from voiceeval.aggregation.composite import (
    DEFAULT_CATEGORY_WEIGHTS,
    DEFAULT_COMPOSITE_VERSION,
    DEFAULT_COVERAGE_POLICY,
    CompositeMetricInput,
    CompositeOutcome,
    compute_composite,
    normalize_value,
)
from voiceeval.aggregation.stats import (
    DEFAULT_PERCENTILE_MIN_SAMPLE,
    AggregateStats,
    aggregate,
)


def __getattr__(name: str):
    # The run-scoped aggregation engine is part of the deferred execution/results
    # pass; import it lazily so the pure statistics/composite utilities do not
    # depend on it.
    if name in {"AGGREGATION_VERSION", "AggregationEngine"}:
        from voiceeval.aggregation import engine

        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AGGREGATION_VERSION",
    "AggregateStats",
    "AggregationEngine",
    "CompositeMetricInput",
    "CompositeOutcome",
    "DEFAULT_CATEGORY_WEIGHTS",
    "DEFAULT_COMPOSITE_VERSION",
    "DEFAULT_COVERAGE_POLICY",
    "DEFAULT_PERCENTILE_MIN_SAMPLE",
    "aggregate",
    "compute_composite",
    "normalize_value",
]
