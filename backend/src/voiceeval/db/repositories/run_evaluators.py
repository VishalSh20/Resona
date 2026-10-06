"""RunEvaluator persistence (one concrete caller scenario inside a Run)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository


class RunEvaluatorRepository(Repository):
    async def create_evaluator(
        self,
        *,
        run_id: str,
        sequence_no: int,
        scenario: str,
        expected_output_prompt: str,
        metrics: list[str],
        languages: dict[str, str | None],
        personality: list[str],
        scenario_config: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> domain.RunEvaluator:
        evaluator = domain.RunEvaluator(
            id=new_id(EntityKind.RUN_EVALUATOR),
            run_id=run_id,
            sequence_no=sequence_no,
            scenario=scenario,
            scenario_config=scenario_config or {},
            expected_output_prompt=expected_output_prompt,
            metrics=metrics,
            languages=languages,
            personality=personality,
            result=result,
        )
        self._session.add(evaluator)
        await self._session.flush()
        return evaluator

    async def create_many(
        self,
        run_id: str,
        drafts: list[dict[str, Any]],
    ) -> list[domain.RunEvaluator]:
        """Bulk-create evaluators, assigning stable sequence numbers 1..N."""
        start = await self._next_sequence_no(run_id)
        created: list[domain.RunEvaluator] = []
        for offset, draft in enumerate(drafts):
            created.append(
                await self.create_evaluator(
                    run_id=run_id,
                    sequence_no=start + offset,
                    scenario=draft["scenario"],
                    expected_output_prompt=draft["expected_output_prompt"],
                    metrics=draft["metrics"],
                    languages=draft["languages"],
                    personality=draft["personality"],
                    scenario_config=draft.get("scenario_config"),
                )
            )
        return created

    async def get_evaluator(self, evaluator_id: str) -> domain.RunEvaluator:
        return await self._get(
            domain.RunEvaluator, evaluator_id, name="run evaluator"
        )

    async def list_evaluators(self, run_id: str) -> list[domain.RunEvaluator]:
        result = await self._session.execute(
            select(domain.RunEvaluator)
            .where(domain.RunEvaluator.run_id == run_id)
            .order_by(domain.RunEvaluator.sequence_no)
        )
        return list(result.scalars().all())

    async def update_evaluator(
        self,
        evaluator: domain.RunEvaluator,
        *,
        scenario: str | None = None,
        expected_output_prompt: str | None = None,
        metrics: list[str] | None = None,
        languages: dict[str, str | None] | None = None,
        personality: list[str] | None = None,
        scenario_config: dict[str, Any] | None = None,
    ) -> domain.RunEvaluator:
        if scenario is not None:
            evaluator.scenario = scenario
        if scenario_config is not None:
            evaluator.scenario_config = scenario_config
        if expected_output_prompt is not None:
            evaluator.expected_output_prompt = expected_output_prompt
        if metrics is not None:
            evaluator.metrics = metrics
        if languages is not None:
            evaluator.languages = languages
        if personality is not None:
            evaluator.personality = personality
        await self._session.flush()
        return evaluator

    async def _next_sequence_no(self, run_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(domain.RunEvaluator.sequence_no), 0)).where(
                domain.RunEvaluator.run_id == run_id
            )
        )
        return int(result.scalar_one()) + 1


__all__ = ["RunEvaluatorRepository"]
