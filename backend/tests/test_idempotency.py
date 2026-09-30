"""Idempotency service tests."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from voiceeval.core.errors import ConflictError
from voiceeval.db.models.support import IdempotencyKey
from voiceeval.services.idempotency import IdempotencyService, hash_request


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, existing=None, *, flush_error=None):
        self._existing = existing
        self._flush_error = flush_error
        self.added = []
        self.flushed = 0

    async def execute(self, stmt):
        return _Result(self._existing)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1
        if self._flush_error is not None:
            raise self._flush_error


async def test_reserve_new_key_creates_record():
    session = _FakeSession(None)
    record = await IdempotencyService(session).reserve("key-1", "scope")
    assert record.key == "key-1"
    assert session.flushed == 1
    assert len(session.added) == 1


async def test_reserve_stores_request_hash():
    session = _FakeSession(None)
    record = await IdempotencyService(session).reserve(
        "key-1", "scope", request_hash=hash_request({"a": 1})
    )
    assert record.request_hash == hash_request({"a": 1})


async def test_reserve_duplicate_key_raises_conflict():
    existing = IdempotencyKey(id="x", key="key-1", scope="scope")
    session = _FakeSession(existing)
    with pytest.raises(ConflictError):
        await IdempotencyService(session).reserve("key-1", "scope")


async def test_same_key_same_body_is_a_plain_duplicate():
    body_hash = hash_request({"a": 1})
    existing = IdempotencyKey(
        id="x", key="key-1", scope="scope", request_hash=body_hash
    )
    session = _FakeSession(existing)
    with pytest.raises(ConflictError) as exc:
        await IdempotencyService(session).reserve(
            "key-1", "scope", request_hash=body_hash
        )
    assert "already been used" in str(exc.value)


async def test_same_key_different_body_is_flagged():
    existing = IdempotencyKey(
        id="x", key="key-1", scope="scope", request_hash=hash_request({"a": 1})
    )
    session = _FakeSession(existing)
    with pytest.raises(ConflictError) as exc:
        await IdempotencyService(session).reserve(
            "key-1", "scope", request_hash=hash_request({"a": 2})
        )
    assert "different request" in str(exc.value)


async def test_concurrent_duplicate_surfaces_as_conflict_not_500():
    # Two requests pass the existence check; the loser hits the DB unique
    # constraint. That must become a clean 409, never an integrity error.
    error = IntegrityError("INSERT", {}, Exception("duplicate key"))
    session = _FakeSession(None, flush_error=error)
    with pytest.raises(ConflictError):
        await IdempotencyService(session).reserve("key-1", "scope")
