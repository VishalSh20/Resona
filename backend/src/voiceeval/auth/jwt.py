"""Minimal backend JWT.

Claims follow the design contract: ``sub``, ``iss``, ``exp``, ``iat``, ``scope``.
Two scopes are supported today — ``user`` (control-plane / API) and ``runner``
(the disposable call runner). There is intentionally no public signup flow.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import jwt

from voiceeval.core.config import get_settings
from voiceeval.core.errors import AuthenticationError

Scope = Literal["user", "runner"]


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    scope: Scope
    exp: int
    iat: int
    issuer: str
    attempt_id: str | None = None


def _now() -> int:
    return int(time.time())


def create_token(
    subject: str,
    scope: Scope,
    *,
    attempt_id: str | None = None,
    expires_in_seconds: int | None = None,
) -> tuple[str, TokenClaims]:
    """Create a signed JWT for ``subject`` with ``scope``.

    Returns the encoded token and its claims (useful for tests/diagnostics).
    """
    s = get_settings()
    now = _now()
    if expires_in_seconds is None:
        expires_in_seconds = s.jwt_access_token_expire_minutes * 60

    claims: dict[str, object] = {
        "sub": subject,
        "iss": s.jwt_issuer,
        "iat": now,
        "exp": now + expires_in_seconds,
        "scope": scope,
    }
    if attempt_id is not None:
        claims["attempt_id"] = attempt_id

    token = jwt.encode(claims, s.jwt_secret, algorithm="HS256")
    parsed = TokenClaims(
        sub=subject,
        scope=scope,
        exp=now + expires_in_seconds,
        iat=now,
        issuer=s.jwt_issuer,
        attempt_id=attempt_id,
    )
    return token, parsed


def decode_token(token: str) -> TokenClaims:
    """Validate and decode a JWT, raising AuthenticationError on failure."""
    s = get_settings()
    try:
        payload = jwt.decode(
            token,
            s.jwt_secret,
            algorithms=["HS256"],
            issuer=s.jwt_issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("token has expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthenticationError("invalid token issuer") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("invalid token") from exc

    scope = payload.get("scope")
    if scope not in ("user", "runner"):
        raise AuthenticationError("token is missing a valid scope")

    return TokenClaims(
        sub=payload["sub"],
        scope=scope,
        exp=payload["exp"],
        iat=payload.get("iat", 0),
        issuer=payload.get("iss", ""),
        attempt_id=payload.get("attempt_id"),
    )


def create_runner_token(
    runner_id: str,
    attempt_id: str,
    *,
    expires_in_seconds: int = 300,
) -> str:
    """Short-lived runner token scoped to a single attempt."""
    token, _ = create_token(
        runner_id,
        "runner",
        attempt_id=attempt_id,
        expires_in_seconds=expires_in_seconds,
    )
    return token


def create_user_token(
    subject: str,
    *,
    expires_in_seconds: int | None = None,
) -> str:
    """Create a user-scope token for the control-plane API.

    There is intentionally no public signup: operators mint tokens with
    ``python -m voiceeval.auth.cli`` (or embed the same call) and hand them to
    users/services.
    """
    token, _ = create_token(
        subject, "user", expires_in_seconds=expires_in_seconds
    )
    return token
