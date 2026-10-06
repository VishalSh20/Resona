"""Run and RunEvaluator request/response contracts (v0.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from voiceeval.generation.models import SimulationWorkflowSpec


class RunCreate(BaseModel):
    target_revision_id: str


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    target_revision_id: str
    evaluator_count: int
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunEvaluatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    sequence_no: int
    scenario: str
    scenario_config: dict[str, Any] = Field(default_factory=dict)
    expected_output_prompt: str
    metrics: list[str]
    languages: dict[str, str | None]
    personality: list[str]
    result: dict[str, Any] | None = None


class RunEvaluatorUpdate(BaseModel):
    scenario: str | None = None
    scenario_config: dict[str, Any] | None = None
    expected_output_prompt: str | None = None
    metrics: list[str] | None = None
    languages: dict[str, str | None] | None = None
    personality: list[str] | None = None


class GenerateEvaluationsRequest(BaseModel):
    workflow_spec: SimulationWorkflowSpec


class GenerateEvaluationsResponse(BaseModel):
    run_id: str
    count: int
    evaluators: list[RunEvaluatorRead]


class SimulationPreferencesRequest(BaseModel):
    description: str
    available_metrics: list[str]
    available_personalities: list[str]


class SimulationPreferencesResponse(BaseModel):
    metrics: list[str]
    personalities: list[str]


__all__ = [
    "GenerateEvaluationsRequest",
    "GenerateEvaluationsResponse",
    "RunCreate",
    "RunEvaluatorRead",
    "RunEvaluatorUpdate",
    "RunRead",
    "SimulationPreferencesRequest",
    "SimulationPreferencesResponse",
]
