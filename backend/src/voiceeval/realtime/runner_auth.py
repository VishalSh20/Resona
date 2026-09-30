"""WebSocket authentication for the runner control channel and live UI channel.

Runner tokens are short-lived and scoped to a single attempt; the live UI
channel uses a normal user JWT. Both are passed as a ``token`` query parameter
because browsers cannot set an Authorization header on a WebSocket handshake.
"""

from __future__ import annotations

from voiceeval.auth.jwt import TokenClaims, decode_token
from voiceeval.core.errors import AuthenticationError, AuthorizationError


def authenticate_runner(token: str | None, attempt_id: str) -> TokenClaims:
    """Validate a runner token against the attempt in the path.

    Rejects missing/invalid/expired tokens, tokens without the ``runner`` scope,
    and tokens whose ``attempt_id`` does not match the requested attempt.
    """
    if not token:
        raise AuthenticationError("missing runner token")
    claims = decode_token(token)
    if claims.scope != "runner":
        raise AuthorizationError("runner scope required")
    if claims.attempt_id != attempt_id:
        raise AuthorizationError("runner token is not valid for this attempt")
    return claims


def authenticate_user(token: str | None) -> TokenClaims:
    """Validate a normal user JWT for the live UI channel."""
    if not token:
        raise AuthenticationError("missing token")
    claims = decode_token(token)
    if claims.scope != "user":
        raise AuthorizationError("user scope required")
    return claims
