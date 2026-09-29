"""JWT authentication tests."""

from __future__ import annotations

import time

import pytest

from voiceeval.auth.jwt import create_runner_token, create_token, decode_token
from voiceeval.core.errors import AuthenticationError


def test_create_and_decode_user_token():
    token, claims = create_token("user-1", "user")
    decoded = decode_token(token)
    assert decoded.sub == "user-1"
    assert decoded.scope == "user"
    assert decoded.issuer == claims.issuer
    assert decoded.exp == claims.exp


def test_runner_token_carries_attempt_id():
    token = create_runner_token("runner-17", "att_abc")
    decoded = decode_token(token)
    assert decoded.scope == "runner"
    assert decoded.attempt_id == "att_abc"


def test_expired_token_rejected():
    token, _ = create_token("user-1", "user", expires_in_seconds=-1)
    with pytest.raises(AuthenticationError, match="expired"):
        decode_token(token)


def test_tampered_token_rejected():
    token, _ = create_token("user-1", "user")
    with pytest.raises(AuthenticationError):
        decode_token(token[:-2] + "xx")


def test_missing_scope_rejected():
    import jwt as pyjwt

    from voiceeval.core.config import get_settings

    s = get_settings()
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "user-1", "iss": s.jwt_issuer, "iat": now, "exp": now + 60},
        s.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError, match="scope"):
        decode_token(token)
