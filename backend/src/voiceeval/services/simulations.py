"""Simulation domain operations (v0.4)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.models import domain
from voiceeval.db.repositories import SimulationRepository, TargetRepository


class SimulationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._simulations = SimulationRepository(session)
        self._targets = TargetRepository(session)

    async def create_simulation(
        self,
        *,
        name: str,
        description: str | None = None,
        agent_target_id: str,
        languages: list[str],
        call_ambience: list[str],
        metric_set: list[str],
        personalities: list[str],
        knowledge_base: dict[str, Any],
        evaluator_count: int,
        created_by: str | None = None,
    ) -> domain.Simulation:
        await self._targets.get_target(agent_target_id)
        return await self._simulations.create_simulation(
            name=name,
            description=description,
            agent_target_id=agent_target_id,
            languages=languages,
            call_ambience=call_ambience,
            metric_set=metric_set,
            personalities=personalities,
            knowledge_base=knowledge_base,
            evaluator_count=evaluator_count,
            created_by=created_by,
        )

    async def get_simulation(self, simulation_id: str) -> domain.Simulation:
        return await self._simulations.get_simulation(simulation_id)

    async def list_simulations(self) -> list[domain.Simulation]:
        return await self._simulations.list_simulations()


__all__ = ["SimulationService"]
