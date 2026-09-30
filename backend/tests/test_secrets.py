"""Encrypted provider-secret round-trip tests."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from voiceeval.core.errors import ValidationError
from voiceeval.services.secrets import decrypt_secret, encrypt_secret


def _settings(key: str | None):
    return type("Settings", (), {"secret_encryption_key": key})()


def test_encrypt_decrypt_round_trip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("voiceeval.services.secrets.get_settings", lambda: _settings(key))

    encrypted = encrypt_secret("sk-123456")
    assert encrypted != "sk-123456"
    assert decrypt_secret(encrypted) == "sk-123456"


def test_encrypt_requires_configured_key(monkeypatch):
    monkeypatch.setattr("voiceeval.services.secrets.get_settings", lambda: _settings(None))

    with pytest.raises(ValidationError):
        encrypt_secret("sk-123456")


def test_decrypt_rejects_tampered_value(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("voiceeval.services.secrets.get_settings", lambda: _settings(key))

    with pytest.raises(ValidationError):
        decrypt_secret("not-a-valid-fernet-token")
