"""Authentication request/response contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    roles: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
