"""Simulation configuration-layer tests (service + request contracts).

Pure unit tests: the service is wired to fake repositories, so no database is
required. The agent (target) is a required property of the Simulation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.db.models import domain
from voiceeval.schemas.simulations import SimulationCreate
from voiceeval.services.simulations import SimulationService

_SIM_FIELDS = {
    "name": "Credit Card Support",
    "description": "handle blocked cards",
    "agent_target_id": "agt_1",
    "languages": ["en", "hi"],
    "call_ambience": ["QUIET"],
    "metric_set": ["task_completion"],
    "personalities": ["IMPATIENT"],
    "knowledge_base": {},
    "evaluator_count": 3,
}


class _FakeTargets:
    def __init__(self, *, missing: set[str] | None = None) -> None:
        self.missing = missing or set()

    async def get_target(self, target_id: str):
        if target_id in self.missing:
            raise ResourceNotFoundError(f"target '{target_id}' not found")
        return object()


class _FakeSimulationRepo:
    def __init__(self) -> None:
        self.created_kwargs: dict | None = None

    async def create_simulation(self, **kwargs) -> domain.Simulation:
        self.created_kwargs = kwargs
        return domain.Simulation(id="sim_1", **kwargs)


def _service(
    *, targets: _FakeTargets | None = None
) -> tuple[SimulationService, _FakeSimulationRepo]:
    service = SimulationService(session=None)
    repo = _FakeSimulationRepo()
    service._targets = targets or _FakeTargets()
    service._simulations = repo
    return service, repo


async def test_create_simulation_persists_fields():
    service, repo = _service()

    simulation = await service.create_simulation(**_SIM_FIELDS)

    assert simulation.id == "sim_1"
    assert simulation.agent_target_id == "agt_1"
    assert simulation.metric_set == ["task_completion"]
    assert simulation.evaluator_count == 3
    assert repo.created_kwargs == {**_SIM_FIELDS, "created_by": None}


async def test_create_simulation_validates_target():
    service, repo = _service(targets=_FakeTargets(missing={"agt_missing"}))

    with pytest.raises(ResourceNotFoundError):
        await service.create_simulation(
            **{**_SIM_FIELDS, "agent_target_id": "agt_missing"}
        )

    assert repo.created_kwargs is None


def _sim_kwargs(**overrides):
    data = {
        **_SIM_FIELDS,
        "target_revision_id": "targetrev_1",
    }
    data.update(overrides)
    return data


def test_simulation_create_enforces_evaluator_count_bounds():
    for count in (1, 100):
        assert (
            SimulationCreate(**_sim_kwargs(evaluator_count=count)).evaluator_count
            == count
        )
    for count in (0, 101):
        with pytest.raises(PydanticValidationError):
            SimulationCreate(**_sim_kwargs(evaluator_count=count))


def test_simulation_create_requires_name_agent_and_revision():
    with pytest.raises(PydanticValidationError):
        SimulationCreate(**_sim_kwargs(name=""))
    with pytest.raises(PydanticValidationError):
        SimulationCreate(**{k: v for k, v in _sim_kwargs().items() if k != "agent_target_id"})
    with pytest.raises(PydanticValidationError):
        SimulationCreate(**{k: v for k, v in _sim_kwargs().items() if k != "target_revision_id"})
