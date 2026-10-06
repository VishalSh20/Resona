"""Integration provider + account request/response contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CredentialFieldRead(BaseModel):
    key: str
    label: str
    secret: bool = True
    required: bool = True


class IntegrationProviderRead(BaseModel):
    id: str
    slug: str
    display_name: str
    credentials: list[CredentialFieldRead]


class IntegrationAccountCreate(BaseModel):
    provider_id: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class IntegrationAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_id: str
    name: str
    config: dict[str, Any]
    status: str
