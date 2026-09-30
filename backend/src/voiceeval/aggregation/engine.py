"""The aggregation engine (v0.4).

Collapses per-call-run metric results into per-evaluator aggregates (with
coverage), then normalizes and weights them into a composite score. Aggregates
are derived, so they are rebuilt idempotently for a Run rather than appended to.
Coverage is always exposed alongside any statistic, and the composite stays
``INCOMPLETE`` when a critical metric is unavailable or coverage falls below
policy.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.aggregation.composite import (
    DEFAULT_CATEGORY_WEIGHTS,
    DEFAULT_COMPOSITE_VERSION,
    DEFAULT_COVERAGE_POLICY,
    CompositeMetricInput,
    compute_composite,
)
from voiceeval.aggregation.stats import AggregateStats, aggregate
from voiceeval.core.logging import bind_execution_context
from voiceeval.db.models import results
from voiceeval.db.repositories import (
    CallAttemptRepository,
    CallRunRepository,
    JudgeRepository,
    MetricRepository,
    ResultRepository,
    RunEvaluatorRepository,
    RunRepository,
)
from voiceeval.domain.enums import (
    AggregateScope,
    AttemptStatus,
    CallRunStatus,
    MetricStatus,
    MetricValueType,
)
from voiceeval.metrics.registry import MetricRegistry, MetricSpec, get_metric_registry
from voiceeval.observability.tracing import span
from voiceeval.realtime.pubsub import (
    AGGREGATE_UPDATED,
    COMPOSITE_UPDATED,
    publish_plan_event,
)

logger = logging.getLogger("voiceeval.aggregation")

AGGREGATION_VERSION = "aggregation.v1"


def _result_value(result: results.MetricResult) -> float | bool | str | None:
    if result.status != MetricStatus.COMPUTED.value:
        return None
    if result.value_type == MetricValueType.NUMERIC.value:
        return float(result.value_numeric) if result.value_numeric is not None else None
    if result.value_type == MetricValueType.BOOLEAN.value:
        return result.value_boolean
    if result.value_type == MetricValueType.TEXT.value:
        return result.value_text
    if result.value_type == MetricValueType.CATEGORY.value:
        return result.value_category
    return None


class AggregationEngine:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: MetricRegistry | None = None,
    ) -> None:
        self._session = session
        self._registry = registry or get_metric_registry()
        self._run_repo = RunRepository(session)
        self._evaluators = RunEvaluatorRepository(session)
        self._call_runs = CallRunRepository(session)
        self._attempts = CallAttemptRepository(session)
        self._judges = JudgeRepository(session)
        self._metrics = MetricRepository(session)
        self._results = ResultRepository(session)

    async def is_run_evaluation_complete(self, run_id: str) -> bool:
        """Whether every call run that can be evaluated has been judged.

        A call run is settled when it is terminal and either has no eligible
        attempt (nothing to judge) or already has a judge execution. Aggregation
        must wait for this, because call-run status turns terminal before
        evaluation runs.
        """
        for call_run in await self._call_runs.list_runs(run_id):
            if call_run.status in {
                CallRunStatus.QUEUED.value,
                CallRunStatus.RUNNING.value,
            }:
                return False
            attempts = await self._attempts.list_attempts(call_run.id)
            eligible = [
                attempt
                for attempt in attempts
                if attempt.status == AttemptStatus.TERMINAL.value
                and attempt.eligible_for_evaluation
            ]
            if not eligible:
                continue
            if not await self._judges.list_executions(call_run.id):
                return False
        return True

    # -- aggregates -----------------------------------------------------------

    async def aggregate_run(self, run_id: str) -> list[results.AggregateResult]:
        with bind_execution_context(plan_id=run_id):
            with span("aggregation.aggregate_run", run_id=run_id):
                return await self._aggregate_run(run_id)

    async def _aggregate_run(self, run_id: str) -> list[results.AggregateResult]:
        await self._run_repo.get_run(run_id)
        evaluators = await self._evaluators.list_evaluators(run_id)
        call_runs = await self._call_runs.list_runs(run_id)
        definitions = {
            definition.id: definition
            for definition in await self._metrics.list_definitions()
        }
        by_definition_key = {
            (definition.metric_key, definition.version): definition
            for definition in definitions.values()
        }

        await self._results.clear_aggregates(run_id)
        written: list[results.AggregateResult] = []

        for evaluator in evaluators:
            evaluator_call_runs = [
                run for run in call_runs if run.run_evaluator_id == evaluator.id
            ]
            if not evaluator_call_runs:
                continue
            run_results: dict[str, dict[str, results.MetricResult]] = {}
            for run in evaluator_call_runs:
                run_results[run.id] = {
                    result.metric_definition_id: result
                    for result in await self._metrics.list_results(run.id)
                }

            for spec in self._registry.all():
                definition = by_definition_key.get((spec.metric_key, spec.version))
                if definition is None:
                    continue
                values: list[float | bool | str] = []
                computed = 0
                for run in evaluator_call_runs:
                    result = run_results[run.id].get(definition.id)
                    if result is None:
                        continue
                    if result.status == MetricStatus.COMPUTED.value:
                        value = _result_value(result)
                        if value is not None:
                            values.append(value)
                            computed += 1
                stats = aggregate(
                    values,
                    spec.value_type.value,
                    sample_count=len(evaluator_call_runs),
                    coverage_count=computed,
                    config=spec.aggregation_config,
                )
                aggregate_row = await self._results.create_aggregate(
                    run_id=run_id,
                    scope=AggregateScope.EVALUATOR.value,
                    run_evaluator_id=evaluator.id,
                    metric_definition_id=definition.id,
                    sample_count=stats.sample_count,
                    coverage_count=stats.coverage_count,
                    percentile_status=stats.percentile_status,
                    availability_ratio=stats.availability_ratio,
                    mean=stats.mean,
                    median=stats.median,
                    min_value=stats.min_value,
                    max_value=stats.max_value,
                    stddev=stats.stddev,
                    p95=stats.p95,
                    category_counts=_category_payload(stats),
                    aggregation_version=AGGREGATION_VERSION,
                )
                await publish_plan_event(
                    run_id,
                    AGGREGATE_UPDATED,
                    {
                        "run_evaluator_id": evaluator.id,
                        "metric_key": spec.metric_key,
                        "coverage_count": stats.coverage_count,
                        "sample_count": stats.sample_count,
                    },
                )
                written.append(aggregate_row)
        return written

    # -- composite ------------------------------------------------------------

    async def compute_composite(self, run_id: str) -> results.CompositeScoreResult:
        with bind_execution_context(plan_id=run_id):
            with span("aggregation.compute_composite", run_id=run_id):
                return await self._compute_composite(run_id)

    async def _compute_composite(self, run_id: str) -> results.CompositeScoreResult:
        await self._run_repo.get_run(run_id)
        definition = await self._results.get_or_create_composite_definition(
            version=DEFAULT_COMPOSITE_VERSION,
            weights=DEFAULT_CATEGORY_WEIGHTS,
            coverage_policy=DEFAULT_COVERAGE_POLICY,
            critical_metrics=DEFAULT_COVERAGE_POLICY.get("required_metrics"),
        )

        aggregates = await self._results.list_aggregates(run_id)
        definitions = {
            definition_row.id: definition_row
            for definition_row in await self._metrics.list_definitions()
        }

        per_metric: dict[str, list[Any]] = {}
        spec_by_key: dict[str, MetricSpec] = {}
        for row in aggregates:
            definition_row = definitions.get(row.metric_definition_id)
            if definition_row is None:
                continue
            spec = self._registry.get(definition_row.metric_key, definition_row.version)
            spec_by_key[spec.metric_key] = spec
            if spec.composite_category is None:
                continue
            representative = _representative_value(spec, row)
            if representative is None:
                continue
            per_metric.setdefault(spec.metric_key, []).append(representative)

        inputs: list[CompositeMetricInput] = []
        for metric_key, spec in spec_by_key.items():
            if spec.composite_category is None:
                continue
            values = per_metric.get(metric_key) or []
            value = _collapse(values, spec)
            inputs.append(
                CompositeMetricInput(
                    metric_key=metric_key,
                    category=spec.composite_category,
                    normalization_config=spec.normalization_config,
                    value=value,
                )
            )

        outcome = compute_composite(
            inputs,
            weights=definition.weights or DEFAULT_CATEGORY_WEIGHTS,
            coverage_policy=definition.coverage_policy or DEFAULT_COVERAGE_POLICY,
        )

        await self._results.clear_composite_results(run_id)
        composite = await self._results.create_composite_result(
            run_id=run_id,
            definition_id=definition.id,
            status=outcome.status,
            score_0_100=outcome.score_0_100,
            coverage_ratio=outcome.coverage_ratio,
            unavailable_weight=outcome.unavailable_weight,
            category_scores=outcome.category_scores,
        )
        await publish_plan_event(
            run_id,
            COMPOSITE_UPDATED,
            {
                "status": outcome.status,
                "score_0_100": outcome.score_0_100,
                "coverage_ratio": outcome.coverage_ratio,
            },
        )
        return composite


def _category_payload(stats: AggregateStats) -> dict | None:
    if stats.category_counts is None and stats.distribution is None:
        return None
    payload: dict[str, Any] = dict(stats.category_counts or {})
    if stats.distribution is not None:
        payload["distribution"] = stats.distribution
    return payload


def _representative_value(
    spec: MetricSpec, row: results.AggregateResult
) -> float | bool | str | None:
    if spec.value_type in (MetricValueType.NUMERIC, MetricValueType.BOOLEAN):
        return float(row.mean) if row.mean is not None else None
    if spec.value_type == MetricValueType.CATEGORY:
        counts = (row.category_counts or {}).get("counts") or {}
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]
    return None


def _collapse(values: list[Any], spec: MetricSpec) -> Any:
    if not values:
        return None
    if spec.value_type == MetricValueType.CATEGORY:
        return Counter(str(value) for value in values).most_common(1)[0][0]
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


__all__ = ["AGGREGATION_VERSION", "AggregationEngine"]
