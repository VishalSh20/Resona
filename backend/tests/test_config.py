"""Configuration tests."""

from __future__ import annotations

from voiceeval.core.config import Settings


def test_defaults_are_safe():
    s = Settings(_env_file=None)
    assert s.object_storage_mode == "local"
    assert s.jwt_issuer == "voiceeval"
    assert s.app_env == "development"


def test_runtime_timeout_defaults():
    s = Settings(_env_file=None)
    assert s.conversation_stall_ms == 10_000
    assert s.wall_clock_timeout_ms == 180_000
    assert s.max_wall_clock_timeout_ms == 300_000


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OBJECT_STORAGE_MODE", "s3")
    s = Settings(_env_file=None)
    assert s.app_env == "production"
    assert s.object_storage_mode == "s3"
