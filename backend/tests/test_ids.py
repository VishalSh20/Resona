"""Identifier abstraction tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.core.ids import EntityKind, ensure_kind, kind_of, new_id


def test_new_id_has_prefix_and_ulid():
    value = new_id(EntityKind.RUN)
    assert value.startswith("run_")
    # ULID body is 26 chars, no separators beyond the prefix.
    assert len(value.split("_")[1]) == 26


def test_kind_of_round_trips():
    for kind in EntityKind:
        assert kind_of(new_id(kind)) is kind


def test_kind_of_unknown_prefix_is_none():
    assert kind_of("bogus_123") is None


def test_ensure_kind_validates():
    run_id = new_id(EntityKind.RUN)
    assert ensure_kind(run_id, EntityKind.RUN) == run_id


def test_ensure_kind_rejects_wrong_prefix():
    att_id = new_id(EntityKind.ATTEMPT)
    with pytest.raises(ValidationError):
        ensure_kind(att_id, EntityKind.RUN)
