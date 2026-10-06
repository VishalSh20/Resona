"""Aggregation math (spec §8)."""

from __future__ import annotations

import pytest

from voiceeval.judging.probes.interpret import (
    choice_value,
    finalize_judge_metric,
    noul_value,
    score_value,
    to_1_5,
    weighted_mean,
)


def test_noul_value_and_invert():
    assert noul_value(0.9) == pytest.approx(0.9)
    assert noul_value(0.9, invert=True) == pytest.approx(0.1)


def test_choice_value_drops_on_na_majority():
    credits = {"good": 1.0, "bad": 0.0, "na": None}
    assert choice_value({"good": 0.2, "bad": 0.2, "na": 0.6}, credits) is None


def test_choice_value_expected_credit():
    credits = {"good": 1.0, "ok": 0.5, "bad": 0.0}
    value = choice_value({"good": 0.5, "ok": 0.25, "bad": 0.25}, credits)
    assert value == pytest.approx(0.625)


def test_score_value_uses_index_keyed_probabilities():
    # Real Decisions API keys probabilities by level index string and returns
    # score as the weighted position (0..n-1).
    value = score_value({"0": 0.0, "1": 0.01, "2": 0.99}, 3, score=1.99)
    assert value == pytest.approx(0.995)


def test_score_value_falls_back_to_score_field():
    assert score_value(None, 3, score=2.0) == pytest.approx(1.0)


def test_weighted_mean_ignores_none():
    assert weighted_mean([(1.0, 2.0), (None, 1.0), (0.0, 2.0)]) == pytest.approx(0.5)
    assert weighted_mean([(None, 1.0)]) is None


def test_to_1_5_is_monotonic_and_bounded():
    assert to_1_5(0.0) == pytest.approx(1.0)
    assert to_1_5(1.0) == pytest.approx(5.0)
    assert to_1_5(0.5) > to_1_5(0.3)


def test_finalize_applies_caps_after_mapping():
    assert finalize_judge_metric(0.95, []) == 5
    assert finalize_judge_metric(0.95, [3]) == 3
    assert finalize_judge_metric(None, [3]) is None
