"""Benchmark request/response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BenchmarkCreate(BaseModel):
    benchmark_key: str
    name: str


class BenchmarkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    benchmark_key: str
    name: str


class BenchmarkVersionCreate(BaseModel):
    version: str
    manifest: dict[str, Any] | None = None
    manifest_hash: str | None = None


class BenchmarkVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    benchmark_id: str
    version: str
    status: str
    manifest: dict[str, Any] | None = None
    manifest_hash: str | None = None
    frozen_at: datetime | None = None
