"""Aggregation and composite tests.

Covers per-type statistics, the small-sample percentile rule, coverage, and the
composite coverage policy: critical metrics missing or insufficient coverage
yields INCOMPLETE, and missing weight is reported rather than redistributed.
"""

from __future__ import annotations

import pytest

from voiceeval.aggregation.composite import (
    CompositeMetricInput,
    compute_composite,
    normalize_value,
)
from voiceeval.aggregation.stats import aggregate


# --- statistics --------------------------------------------------------------


def test_continuous_statistics():
    stats = aggregate([3.0, 4.0, 5.0], "numeric", sample_count=3)
    assert stats.mean == 4.0
    assert stats.median == 4.0
    assert stats.min_value == 3.0
    assert stats.max_value == 5.0
    assert stats.stddev == pytest.approx(1.0)


def test_small_sample_never_implies_p95():
    stats = aggregate([3.0, 4.0, 5.0], "numeric", sample_count=3)
    assert stats.p95 is None
    assert stats.percentile_status == "insufficient_sample"


def test_p95_computed_with_enough_samples():
    values = [float(i) for i in range(1, 25)]
    stats = aggregate(values, "numeric", sample_count=len(values))
    assert stats.percentile_status == "computed"
    assert stats.p95 is not None


def test_boolean_statistics():
    stats = aggregate([True, False, True], "boolean", sample_count=3)
    assert stats.category_counts["true"] == 2
    assert stats.category_counts["false"] == 1
    assert stats.category_counts["success_rate"] == pytest.approx(2 / 3)


def test_categorical_statistics():
    stats = aggregate(
        ["fulfilled", "fulfilled", "not_fulfilled"], "category", sample_count=3
    )
    assert stats.category_counts["counts"] == {"fulfilled": 2, "not_fulfilled": 1}
    assert stats.category_counts["percentages"]["fulfilled"] == pytest.approx(2 / 3)


def test_ordinal_distribution():
    stats = aggregate(
        [5.0, 4.0, 4.0, 3.0], "numeric", sample_count=4, config={"kind": "ordinal"}
    )
    assert stats.distribution == {"5": 1, "4": 2, "3": 1}


def test_coverage_ratio_and_unavailable():
    stats = aggregate([4.0, 5.0], "numeric", sample_count=3, coverage_count=2)
    assert stats.sample_count == 3
    assert stats.coverage_count == 2
    assert stats.availability_ratio == pytest.approx(2 / 3)


# --- normalization -----------------------------------------------------------


def test_linear_normalization_lower_is_better():
    assert normalize_value({"kind": "linear", "best": 0, "worst": 2000}, 0) == 100.0
    assert normalize_value({"kind": "linear", "best": 0, "worst": 2000}, 2000) == 0.0
    assert normalize_value({"kind": "linear", "best": 0, "worst": 2000}, 1000) == 50.0


def test_ordinal_normalization():
    assert normalize_value({"kind": "ordinal", "min": 1, "max": 5}, 1) == 0.0
    assert normalize_value({"kind": "ordinal", "min": 1, "max": 5}, 5) == 100.0


def test_category_normalization_unknown_maps_to_none():
    config = {"kind": "category", "mapping": {"fulfilled": 100.0, "unknown": None}}
    assert normalize_value(config, "fulfilled") == 100.0
    assert normalize_value(config, "unknown") is None


# --- composite ---------------------------------------------------------------


def _inputs(*, omit_motive: bool = False, ttfa: float | None = 720.0):
    items = [
        CompositeMetricInput(
            "semantic_understanding",
            "conversation",
            {"kind": "ordinal", "min": 1, "max": 5},
            4.0,
        ),
        CompositeMetricInput(
            "ttfa", "voice", {"kind": "linear", "best": 0, "worst": 2000}, ttfa
        ),
        CompositeMetricInput(
            "language_adaptation",
            "language",
            {"kind": "ordinal", "min": 1, "max": 5},
            4.0,
        ),
    ]
    if not omit_motive:
        items.insert(
            0,
            CompositeMetricInput(
                "motive_fulfillment",
                "motive",
                {"kind": "category", "mapping": {"fulfilled": 100.0}},
                "fulfilled",
            ),
        )
    return items


def test_composite_complete_when_all_present():
    outcome = compute_composite(_inputs())
    assert outcome.status == "complete"
    assert outcome.score_0_100 is not None
    assert outcome.coverage_ratio == 1.0
    assert outcome.unavailable_weight == 0.0


def test_missing_critical_metric_makes_composite_incomplete():
    outcome = compute_composite(_inputs(omit_motive=True))
    assert outcome.status == "incomplete"
    assert "motive_fulfillment" in outcome.missing_metrics
    # The missing weight is reported, never redistributed.
    assert outcome.unavailable_weight > 0
    assert outcome.category_scores["motive"] is None


def test_low_coverage_makes_composite_incomplete():
    outcome = compute_composite(
        _inputs(ttfa=None),
        coverage_policy={"required_metrics": ["motive_fulfillment"], "minimum_coverage_ratio": 0.95},
    )
    assert outcome.status == "incomplete"
    assert outcome.coverage_ratio < 0.95


def test_no_metrics_is_unavailable():
    outcome = compute_composite([])
    assert outcome.status == "unavailable"
    assert outcome.score_0_100 is None
