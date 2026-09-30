"""Evidence, aggregate and composite-score persistence (v0.4).

Aggregates and composite scores are keyed by the domain ``Run`` (with an
optional ``run_evaluator_id`` for evaluator-scoped aggregates).
"""

from __future__ import annotations

from sqlalchemy import delete, select

from voiceeval.core.ids import new_plain_ulid
from voiceeval.db.models import results
from voiceeval.db.repositories.base import Repository


class ResultRepository(Repository):
    async def add_evidence(
        self,
        *,
        metric_result_id: str,
        source_type: str,
        source_id: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        quote: str | None = None,
        rationale: str | None = None,
    ) -> results.Evidence:
        evidence = results.Evidence(
            id=new_plain_ulid(),
            metric_result_id=metric_result_id,
            source_type=source_type,
            source_id=source_id,
            start_ms=start_ms,
            end_ms=end_ms,
            quote=quote,
            rationale=rationale,
        )
        self._session.add(evidence)
        await self._session.flush()
        return evidence

    async def list_evidence(self, metric_result_id: str) -> list[results.Evidence]:
        result = await self._session.execute(
            select(results.Evidence).where(
                results.Evidence.metric_result_id == metric_result_id
            )
        )
        return list(result.scalars().all())

    async def create_aggregate(
        self,
        *,
        run_id: str,
        scope: str,
        metric_definition_id: str,
        sample_count: int,
        coverage_count: int,
        percentile_status: str,
        run_evaluator_id: str | None = None,
        availability_ratio: float | None = None,
        mean: float | None = None,
        median: float | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        stddev: float | None = None,
        p95: float | None = None,
        category_counts: dict | None = None,
        aggregation_version: str | None = None,
    ) -> results.AggregateResult:
        aggregate = results.AggregateResult(
            id=new_plain_ulid(),
            run_id=run_id,
            scope=scope,
            run_evaluator_id=run_evaluator_id,
            metric_definition_id=metric_definition_id,
            sample_count=sample_count,
            coverage_count=coverage_count,
            availability_ratio=availability_ratio,
            mean=mean,
            median=median,
            min_value=min_value,
            max_value=max_value,
            stddev=stddev,
            p95=p95,
            percentile_status=percentile_status,
            category_counts=category_counts,
            aggregation_version=aggregation_version,
        )
        self._session.add(aggregate)
        await self._session.flush()
        return aggregate

    async def get_aggregate(self, aggregate_id: str) -> results.AggregateResult:
        return await self._get(
            results.AggregateResult, aggregate_id, name="aggregate result"
        )

    async def list_aggregates(
        self,
        run_id: str,
        *,
        run_evaluator_id: str | None = None,
    ) -> list[results.AggregateResult]:
        stmt = select(results.AggregateResult).where(
            results.AggregateResult.run_id == run_id
        )
        if run_evaluator_id is not None:
            stmt = stmt.where(
                results.AggregateResult.run_evaluator_id == run_evaluator_id
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def clear_aggregates(self, run_id: str) -> None:
        """Drop a run's aggregates so they can be rebuilt idempotently."""
        await self._session.execute(
            delete(results.AggregateResult).where(
                results.AggregateResult.run_id == run_id
            )
        )
        await self._session.flush()

    async def create_composite_definition(
        self,
        *,
        version: str,
        weights: dict | None = None,
        normalization: dict | None = None,
        coverage_policy: dict | None = None,
        critical_metrics: list | None = None,
    ) -> results.CompositeScoreDefinition:
        definition = results.CompositeScoreDefinition(
            id=new_plain_ulid(),
            version=version,
            weights=weights,
            normalization=normalization,
            coverage_policy=coverage_policy,
            critical_metrics=critical_metrics,
        )
        self._session.add(definition)
        await self._session.flush()
        return definition

    async def create_composite_result(
        self,
        *,
        run_id: str,
        definition_id: str,
        status: str,
        score_0_100: float | None = None,
        coverage_ratio: float | None = None,
        unavailable_weight: float | None = None,
        category_scores: dict | None = None,
    ) -> results.CompositeScoreResult:
        composite = results.CompositeScoreResult(
            id=new_plain_ulid(),
            run_id=run_id,
            definition_id=definition_id,
            status=status,
            score_0_100=score_0_100,
            coverage_ratio=coverage_ratio,
            unavailable_weight=unavailable_weight,
            category_scores=category_scores,
        )
        self._session.add(composite)
        await self._session.flush()
        return composite

    async def get_composite_result(
        self, composite_id: str
    ) -> results.CompositeScoreResult:
        return await self._get(
            results.CompositeScoreResult, composite_id, name="composite score result"
        )

    async def find_composite_definition(
        self, version: str
    ) -> results.CompositeScoreDefinition | None:
        result = await self._session.execute(
            select(results.CompositeScoreDefinition)
            .where(results.CompositeScoreDefinition.version == version)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_create_composite_definition(
        self,
        *,
        version: str,
        weights: dict | None = None,
        normalization: dict | None = None,
        coverage_policy: dict | None = None,
        critical_metrics: list | None = None,
    ) -> results.CompositeScoreDefinition:
        existing = await self.find_composite_definition(version)
        if existing is not None:
            return existing
        return await self.create_composite_definition(
            version=version,
            weights=weights,
            normalization=normalization,
            coverage_policy=coverage_policy,
            critical_metrics=critical_metrics,
        )

    async def get_composite_result_for_run(
        self, run_id: str
    ) -> results.CompositeScoreResult | None:
        result = await self._session.execute(
            select(results.CompositeScoreResult)
            .where(results.CompositeScoreResult.run_id == run_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def clear_composite_results(self, run_id: str) -> None:
        await self._session.execute(
            delete(results.CompositeScoreResult).where(
                results.CompositeScoreResult.run_id == run_id
            )
        )
        await self._session.flush()

    async def list_evidence_for_results(
        self, metric_result_ids: list[str]
    ) -> list[results.Evidence]:
        if not metric_result_ids:
            return []
        result = await self._session.execute(
            select(results.Evidence).where(
                results.Evidence.metric_result_id.in_(metric_result_ids)
            )
        )
        return list(result.scalars().all())


__all__ = ["ResultRepository"]
