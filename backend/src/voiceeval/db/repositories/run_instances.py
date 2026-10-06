"""Run persistence (one concrete instantiation of a Simulation)."""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import InvalidStateTransitionError
from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import RunStatus
from voiceeval.domain.state_machines import transition_run


class RunRepository(Repository):
    async def create_run(
        self,
        *,
        simulation_id: str,
        target_revision_id: str,
        evaluator_count: int,
    ) -> domain.Run:
        run = domain.Run(
            id=new_id(EntityKind.RUN),
            simulation_id=simulation_id,
            target_revision_id=target_revision_id,
            evaluator_count=evaluator_count,
            status=RunStatus.DRAFT.value,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, run_id: str) -> domain.Run:
        return await self._get(domain.Run, run_id, name="run")

    async def list_runs(self, simulation_id: str) -> list[domain.Run]:
        result = await self._session.execute(
            select(domain.Run)
            .where(domain.Run.simulation_id == simulation_id)
            .order_by(domain.Run.created_at)
        )
        return list(result.scalars().all())

    async def transition_run(self, run: domain.Run, target: RunStatus) -> domain.Run:
        current = RunStatus(run.status)
        try:
            transition_run(current, target)
        except InvalidStateTransitionError:
            raise
        run.status = target.value
        if target is RunStatus.RUNNING and run.started_at is None:
            run.started_at = utc_now()
        if target in {RunStatus.COMPLETED, RunStatus.CANCELLED}:
            run.finished_at = utc_now()
        await self._session.flush()
        return run


__all__ = ["RunRepository"]
