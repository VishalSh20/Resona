"""Metric value-representation validation tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.db.repositories.metrics import _validate_value_representation


def test_computed_numeric_accepts_single_value():
    _validate_value_representation(
        "computed", "numeric", value_numeric=720.0, value_boolean=None, value_text=None, value_category=None
    )


def test_computed_wrong_column_rejected():
    with pytest.raises(ValidationError):
        _validate_value_representation(
            "computed", "numeric", value_numeric=None, value_boolean=True, value_text=None, value_category=None
        )


def test_computed_missing_value_rejected():
    with pytest.raises(ValidationError):
        _validate_value_representation(
            "computed", "numeric", value_numeric=None, value_boolean=None, value_text=None, value_category=None
        )


def test_computed_multiple_values_rejected():
    with pytest.raises(ValidationError):
        _validate_value_representation(
            "computed", "numeric", value_numeric=1.0, value_boolean=None, value_text="x", value_category=None
        )


def test_not_available_must_not_carry_value():
    with pytest.raises(ValidationError):
        _validate_value_representation(
            "not_available", None, value_numeric=1.0, value_boolean=None, value_text=None, value_category=None
        )


def test_not_available_without_value_is_fine():
    _validate_value_representation(
        "not_available", None, value_numeric=None, value_boolean=None, value_text=None, value_category=None
    )


def test_computed_requires_value_type():
    with pytest.raises(ValidationError):
        _validate_value_representation(
            "computed", None, value_numeric=None, value_boolean=None, value_text=None, value_category=None
        )
