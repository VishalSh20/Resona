"""Object store and signed media URL tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import AuthorizationError, ResourceNotFoundError, ValidationError
from voiceeval.storage import (
    LocalObjectStore,
    get_object_store,
    set_object_store,
    sign_media_key,
    signed_media_path,
    verify_media_key,
)


def test_local_store_roundtrip(tmp_path):
    store = LocalObjectStore(tmp_path)
    uri = store.put("attempts/att_1/caller.pcm", b"audio-bytes")
    assert uri == "local://attempts/att_1/caller.pcm"
    assert store.get("attempts/att_1/caller.pcm") == b"audio-bytes"
    assert store.exists("attempts/att_1/caller.pcm") is True


def test_local_store_rejects_unsafe_keys(tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(ValidationError):
        store.put("../escape", b"x")
    with pytest.raises(ValidationError):
        store.get("/etc/passwd")


def test_missing_object_raises(tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(ResourceNotFoundError):
        store.get("nope")


def test_signed_url_verifies():
    expires_at, signature = sign_media_key("key/one", expires_in_seconds=60, now=1000)
    assert expires_at == 1060
    verify_media_key("key/one", expires_at=expires_at, signature=signature, now=1000)


def test_signed_url_rejects_tampering_and_expiry():
    expires_at, signature = sign_media_key("key/one", expires_in_seconds=60, now=1000)
    with pytest.raises(AuthorizationError):
        verify_media_key("key/one", expires_at=expires_at, signature="bad", now=1000)
    with pytest.raises(AuthorizationError):
        verify_media_key("key/one", expires_at=expires_at, signature=signature, now=2000)


def test_signed_media_path_contains_bindings():
    path = signed_media_path("some/key", expires_in_seconds=60, now=1000)
    assert path.startswith("/api/v1/media/blob?")
    assert "key=some/key" in path and "exp=1060" in path and "sig=" in path


def test_factory_defaults_to_local(tmp_path, monkeypatch):
    from voiceeval.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "object_storage_mode", "local")
    monkeypatch.setattr(settings, "local_object_storage_path", str(tmp_path))
    set_object_store(None)
    try:
        store = get_object_store()
        assert isinstance(store, LocalObjectStore)
    finally:
        set_object_store(None)
