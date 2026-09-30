"""Authentication routes.

These are the only unauthenticated surfaces under ``/api/v1`` besides the signed
media blob. ``register`` and ``login`` mint a user-scope JWT; ``me`` returns the
signed-in identity.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from voiceeval.api.dependencies import SessionDep
from voiceeval.auth.dependencies import get_current_claims
from voiceeval.auth.jwt import TokenClaims
from voiceeval.auth.service import AuthService
from voiceeval.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    result = await AuthService(session).register(
        email=payload.email, password=payload.password, username=payload.username
    )
    await session.commit()
    return TokenResponse(
        access_token=result.token,
        user=UserRead(
            id=result.user.id,
            email=result.user.email,
            username=result.user.username,
            roles=result.roles,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    result = await AuthService(session).login(
        email=payload.email, password=payload.password
    )
    await session.commit()
    return TokenResponse(
        access_token=result.token,
        user=UserRead(
            id=result.user.id,
            email=result.user.email,
            username=result.user.username,
            roles=result.roles,
        ),
    )


@router.get("/me", response_model=UserRead)
async def me(
    session: SessionDep,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
) -> UserRead:
    service = AuthService(session)
    user = await service.get_user(claims.sub)
    return UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        roles=await service.list_roles(user.id),
    )
