"""Run + RunEvaluator configuration-layer tests (service with fake repos).

Covers the config+generation flow: the agent belongs to the Simulation, each
Run binds a revision of that agent, evaluators are generated only on the first
run, later runs copy them, and only personality is editable later.
"""

from __future__ import annotations

import pytest

from voiceeval.core.errors import (
    InvalidStateTransitionError,
    ResourceNotFoundError,
    ValidationError,
)
from voiceeval.db.models import domain
from voiceeval.domain.enums import RunStatus
from voiceeval.domain.state_machines import transition_run as _transition_run
from voiceeval.generation.models import RunEvaluatorDraft, SimulationWorkflowSpec
from voiceeval.services.runs import RunService


def _simulation() -> domain.Simulation:
    return domain.Simulation(
        id="sim_1",
        name="Credit Card Support",
        description="handle blocked cards",
        agent_target_id="agt_1",
        languages=["en", "hi"],
        call_ambience=["QUIET"],
        metric_set=["task_completion", "context_retention"],
        personalities=["IMPATIENT", "SKEPTICAL"],
        knowledge_base={},
        evaluator_count=2,
    )


def _run(
    run_id: str = "run_1",
    status: str = "draft",
    simulation_id: str = "sim_1",
    target_revision_id: str = "targetrev_1",
) -> domain.Run:
    return domain.Run(
        id=run_id,
        simulation_id=simulation_id,
        target_revision_id=target_revision_id,
        evaluator_count=2,
        status=status,
    )


def _evaluator(
    evaluator_id: str,
    run_id: str,
    sequence_no: int = 1,
    *,
    personality: list[str] | None = None,
    metrics: list[str] | None = None,
) -> domain.RunEvaluator:
    return domain.RunEvaluator(
        id=evaluator_id,
        run_id=run_id,
        sequence_no=sequence_no,
        scenario="caller wants their card unblocked",
        expected_output_prompt="judge the authentication flow",
        metrics=metrics if metrics is not None else ["task_completion"],
        languages={"major": "en", "minor": None},
        personality=personality if personality is not None else ["IMPATIENT"],
    )


def _draft(**overrides) -> RunEvaluatorDraft:
    data = {
        "scenario": "caller wants their card unblocked",
        "expected_output_prompt": "judge the authentication flow",
        "metrics": ["task_completion"],
        "languages": {"major": "en", "minor": None},
        "personality": ["IMPATIENT"],
    }
    data.update(overrides)
    return RunEvaluatorDraft(**data)


class _FakeRuns:
    def __init__(self, runs: list[domain.Run]) -> None:
        self.runs = list(runs)
        self.transitions: list[RunStatus] = []

    async def get_run(self, run_id: str) -> domain.Run:
        for run in self.runs:
            if run.id == run_id:
                return run
        raise ResourceNotFoundError(f"run '{run_id}' not found")

    async def list_runs(self, simulation_id: str) -> list[domain.Run]:
        return [r for r in self.runs if r.simulation_id == simulation_id]

    async def create_run(
        self, *, simulation_id: str, target_revision_id: str, evaluator_count: int
    ) -> domain.Run:
        run = domain.Run(
            id=f"run_{len(self.runs) + 1}",
            simulation_id=simulation_id,
            target_revision_id=target_revision_id,
            evaluator_count=evaluator_count,
            status=RunStatus.DRAFT.value,
        )
        self.runs.append(run)
        return run

    async def transition_run(self, run: domain.Run, target: RunStatus) -> domain.Run:
        _transition_run(RunStatus(run.status), target)
        run.status = target.value
        self.transitions.append(target)
        return run


class _FakeEvaluators:
    def __init__(self, rows: list[domain.RunEvaluator] | None = None) -> None:
        self.rows = list(rows or [])

    async def list_evaluators(self, run_id: str) -> list[domain.RunEvaluator]:
        return [e for e in self.rows if e.run_id == run_id]

    async def get_evaluator(self, evaluator_id: str) -> domain.RunEvaluator:
        for row in self.rows:
            if row.id == evaluator_id:
                return row
        raise ResourceNotFoundError(f"run evaluator '{evaluator_id}' not found")

    async def create_many(
        self, run_id: str, drafts: list[dict]
    ) -> list[domain.RunEvaluator]:
        created: list[domain.RunEvaluator] = []
        for offset, draft in enumerate(drafts, start=1):
            row = domain.RunEvaluator(
                id=f"re_{len(self.rows) + 1}",
                run_id=run_id,
                sequence_no=offset,
                **draft,
            )
            self.rows.append(row)
            created.append(row)
        return created

    async def update_evaluator(self, evaluator, **fields) -> domain.RunEvaluator:
        for field in (
            "scenario",
            "expected_output_prompt",
            "metrics",
            "languages",
            "personality",
        ):
            value = fields.get(field)
            if value is not None:
                setattr(evaluator, field, value)
        return evaluator


class _FakeSimulations:
    def __init__(self, simulation: domain.Simulation) -> None:
        self.simulation = simulation

    async def get_simulation(self, simulation_id: str) -> domain.Simulation:
        return self.simulation


class _Revision:
    def __init__(self, agent_target_id: str) -> None:
        self.agent_target_id = agent_target_id


class _FakeTargets:
    def __init__(self, agent_target_id: str = "agt_1") -> None:
        self.agent_target_id = agent_target_id

    async def get_revision(self, revision_id: str) -> _Revision:
        return _Revision(self.agent_target_id)


class _FakeWorkflow:
    def __init__(self, drafts: list[RunEvaluatorDraft]) -> None:
        self.drafts = drafts
        self.calls: list[tuple] = []

    async def run(self, *, simulation, workflow_spec):
        self.calls.append((simulation, workflow_spec))
        return list(self.drafts)


def _service(
    *,
    runs: list[domain.Run] | None = None,
    evaluators: _FakeEvaluators | None = None,
    workflow: _FakeWorkflow | None = None,
    agent_target_id: str = "agt_1",
) -> RunService:
    service = RunService(session=None, workflow=workflow)
    service._runs = _FakeRuns(runs if runs is not None else [_run()])
    service._evaluators = evaluators or _FakeEvaluators()
    service._simulations = _FakeSimulations(_simulation())
    service._targets = _FakeTargets(agent_target_id)
    return service


# --- create run --------------------------------------------------------------


async def test_create_run_seeds_evaluator_count_and_draft_status():
    service = _service(runs=[])

    run = await service.create_run("sim_1", "targetrev_1")

    assert run.id == "run_1"
    assert run.simulation_id == "sim_1"
    assert run.target_revision_id == "targetrev_1"
    assert run.evaluator_count == 2
    assert run.status == RunStatus.DRAFT.value


async def test_create_run_rejects_revision_of_other_agent():
    service = _service(runs=[], agent_target_id="agt_OTHER")

    with pytest.raises(ValidationError):
        await service.create_run("sim_1", "targetrev_1")


async def test_create_run_copies_first_run_evaluators():
    evaluators = _FakeEvaluators(
        [_evaluator("re_1", "run_1"), _evaluator("re_2", "run_1", sequence_no=2)]
    )
    service = _service(runs=[_run("run_1")], evaluators=evaluators)

    run2 = await service.create_run("sim_1", "targetrev_1")

    assert run2.id == "run_2"
    copied = [e for e in evaluators.rows if e.run_id == "run_2"]
    assert len(copied) == 2
    assert copied[0].scenario == "caller wants their card unblocked"


# --- generate evaluators -----------------------------------------------------


async def test_generate_evaluators_persists_drafts_in_sequence():
    workflow = _FakeWorkflow([_draft(), _draft()])
    service = _service(workflow=workflow)

    evaluators = await service.generate_evaluators(
        "run_1", SimulationWorkflowSpec(objective="evaluate")
    )

    assert [e.sequence_no for e in evaluators] == [1, 2]
    assert len(workflow.calls) == 1


async def test_generate_evaluators_rejected_when_run_not_editable():
    service = _service(
        runs=[_run("run_1", "running")], workflow=_FakeWorkflow([_draft()])
    )

    with pytest.raises(InvalidStateTransitionError):
        await service.generate_evaluators("run_1", SimulationWorkflowSpec())


async def test_generate_evaluators_rejected_on_non_first_run():
    service = _service(
        runs=[_run("run_1"), _run("run_2")], workflow=_FakeWorkflow([_draft()])
    )

    with pytest.raises(ValidationError):
        await service.generate_evaluators("run_2", SimulationWorkflowSpec())


# --- update evaluator --------------------------------------------------------


async def test_update_evaluator_enforces_simulation_membership():
    evaluators = _FakeEvaluators([_evaluator("re_1", "run_1")])
    service = _service(evaluators=evaluators)

    with pytest.raises(ValidationError):
        await service.update_evaluator("run_1", "re_1", metrics=["ttfa"])


async def test_update_evaluator_applies_valid_edit():
    evaluators = _FakeEvaluators([_evaluator("re_1", "run_1")])
    service = _service(runs=[_run("run_1", "ready")], evaluators=evaluators)

    updated = await service.update_evaluator("run_1", "re_1", scenario="new")

    assert updated.scenario == "new"


async def test_update_evaluator_rejected_when_run_not_editable():
    service = _service(runs=[_run("run_1", "running")])

    with pytest.raises(InvalidStateTransitionError):
        await service.update_evaluator("run_1", "re_1", scenario="x")


async def test_update_evaluator_restricted_on_non_first_run():
    evaluators = _FakeEvaluators(
        [_evaluator("re_1", "run_1"), _evaluator("re_2", "run_2")]
    )
    service = _service(runs=[_run("run_1"), _run("run_2")], evaluators=evaluators)

    # scenario is locked on a non-first run.
    with pytest.raises(ValidationError):
        await service.update_evaluator("run_2", "re_2", scenario="new")

    # personality remains editable.
    updated = await service.update_evaluator(
        "run_2", "re_2", personality=["SKEPTICAL"]
    )
    assert updated.personality == ["SKEPTICAL"]


# --- mark ready --------------------------------------------------------------


async def test_mark_ready_requires_at_least_one_evaluator():
    service = _service(runs=[_run()])

    with pytest.raises(ValidationError):
        await service.mark_ready("run_1")


async def test_mark_ready_transitions_draft_to_ready():
    evaluators = _FakeEvaluators([_evaluator("re_1", "run_1")])
    service = _service(runs=[_run()], evaluators=evaluators)

    run = await service.mark_ready("run_1")

    assert run.status == RunStatus.READY.value


async def test_mark_ready_rejects_already_ready_run():
    evaluators = _FakeEvaluators([_evaluator("re_1", "run_1")])
    service = _service(runs=[_run("run_1", "ready")], evaluators=evaluators)

    with pytest.raises(InvalidStateTransitionError):
        await service.mark_ready("run_1")
