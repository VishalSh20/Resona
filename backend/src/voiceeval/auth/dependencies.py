"""FastAPI authentication dependencies.

Provides the smallest support model necessary for RBAC: a bearer-token
dependency that yields validated claims, and scope-restricted variants.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from voiceeval.auth.jwt import TokenClaims, decode_token
from voiceeval.core.errors import AuthenticationError, AuthorizationError

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None:
        raise AuthenticationError("missing bearer token")
    return credentials.credentials


def get_current_claims(
    token: Annotated[str, Depends(_extract_token)],
) -> TokenClaims:
    return decode_token(token)


def require_user(
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
) -> TokenClaims:
    if claims.scope != "user":
        raise AuthorizationError("user scope required")
    return claims


def require_runner(
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
) -> TokenClaims:
    if claims.scope != "runner":
        raise AuthorizationError("runner scope required")
    return claims


def get_request(request: Request) -> Request:
    return request
