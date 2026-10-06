"""Simulation persistence (v0.4 configuration domain)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository


class SimulationRepository(Repository):
    async def create_simulation(
        self,
        *,
        name: str,
        description: str | None,
        agent_target_id: str,
        languages: list[str],
        call_ambience: list[str],
        metric_set: list[str],
        personalities: list[str],
        knowledge_base: dict[str, Any],
        evaluator_count: int,
        created_by: str | None = None,
    ) -> domain.Simulation:
        simulation = domain.Simulation(
            id=new_id(EntityKind.SIMULATION),
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
        self._session.add(simulation)
        await self._session.flush()
        return simulation

    async def get_simulation(self, simulation_id: str) -> domain.Simulation:
        return await self._get(domain.Simulation, simulation_id, name="simulation")

    async def list_simulations(self) -> list[domain.Simulation]:
        result = await self._session.execute(
            select(domain.Simulation).order_by(domain.Simulation.created_at)
        )
        return list(result.scalars().all())


__all__ = ["SimulationRepository"]
