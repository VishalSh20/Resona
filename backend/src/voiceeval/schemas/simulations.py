"""Simulation request/response contracts (v0.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from voiceeval.schemas.runs import RunRead


class SimulationCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    # The agent under test belongs to the Simulation; the first Run is bound to
    # ``target_revision_id`` (a revision of that same agent).
    agent_target_id: str
    target_revision_id: str
    languages: list[str] = Field(default_factory=list)
    call_ambience: list[str] = Field(default_factory=list)
    metric_set: list[str] = Field(default_factory=list)
    personalities: list[str] = Field(default_factory=list)
    knowledge_base: dict[str, Any] = Field(default_factory=dict)
    evaluator_count: int = Field(ge=1, le=100)


class SimulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    agent_target_id: str
    languages: list[str]
    call_ambience: list[str]
    metric_set: list[str]
    personalities: list[str]
    knowledge_base: dict[str, Any]
    evaluator_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SimulationCreatedRead(BaseModel):
    """Result of creating a Simulation: the simulation plus its first Run."""

    simulation: SimulationRead
    run: RunRead


__all__ = ["SimulationCreate", "SimulationCreatedRead", "SimulationRead"]
