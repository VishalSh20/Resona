"""Metric-definition and metric-result persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from voiceeval.core.errors import ValidationError
from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import results
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import MetricStatus, MetricValueType


class MetricRepository(Repository):
    async def create_definition(
        self,
        *,
        metric_key: str,
        version: str,
        value_type: str,
        family: str | None = None,
        unit: str | None = None,
        scale_min: float | None = None,
        scale_max: float | None = None,
        required_capabilities: dict | None = None,
        required_evidence: dict | None = None,
        implementation_version: str | None = None,
        aggregation_config: dict | None = None,
        normalization_config: dict | None = None,
    ) -> results.MetricDefinition:
        definition = results.MetricDefinition(
            id=new_id(EntityKind.METRIC),
            metric_key=metric_key,
            version=version,
            family=family,
            value_type=value_type,
            unit=unit,
            scale_min=scale_min,
            scale_max=scale_max,
            required_capabilities=required_capabilities,
            required_evidence=required_evidence,
            implementation_version=implementation_version,
            aggregation_config=aggregation_config,
            normalization_config=normalization_config,
        )
        self._session.add(definition)
        await self._session.flush()
        return definition

    async def get_definition(self, definition_id: str) -> results.MetricDefinition:
        return await self._get(
            results.MetricDefinition, definition_id, name="metric definition"
        )

    async def find_definition(
        self, metric_key: str, version: str
    ) -> results.MetricDefinition | None:
        result = await self._session.execute(
            select(results.MetricDefinition)
            .where(results.MetricDefinition.metric_key == metric_key)
            .where(results.MetricDefinition.version == version)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_definitions(self) -> list[results.MetricDefinition]:
        result = await self._session.execute(select(results.MetricDefinition))
        return list(result.scalars().all())

    async def create_result(
        self,
        *,
        call_run_id: str,
        call_attempt_id: str,
        metric_definition_id: str,
        status: str,
        value_type: str | None = None,
        value_numeric: float | None = None,
        value_boolean: bool | None = None,
        value_text: str | None = None,
        value_category: str | None = None,
        unit: str | None = None,
        scale_min: float | None = None,
        scale_max: float | None = None,
        method: str | None = None,
        measurement_basis: dict | None = None,
        confidence: float | None = None,
        judge_execution_id: str | None = None,
        computed_at: datetime | None = None,
    ) -> results.MetricResult:
        _validate_value_representation(
            status,
            value_type,
            value_numeric=value_numeric,
            value_boolean=value_boolean,
            value_text=value_text,
            value_category=value_category,
        )
        result = results.MetricResult(
            id=new_id(EntityKind.METRIC),
            call_run_id=call_run_id,
            call_attempt_id=call_attempt_id,
            metric_definition_id=metric_definition_id,
            status=status,
            value_type=value_type,
            value_numeric=value_numeric,
            value_boolean=value_boolean,
            value_text=value_text,
            value_category=value_category,
            unit=unit,
            scale_min=scale_min,
            scale_max=scale_max,
            method=method,
            measurement_basis=measurement_basis,
            confidence=confidence,
            judge_execution_id=judge_execution_id,
            computed_at=computed_at,
        )
        self._session.add(result)
        await self._session.flush()
        return result

    async def get_result(self, result_id: str) -> results.MetricResult:
        return await self._get(results.MetricResult, result_id, name="metric result")

    async def list_results(self, call_run_id: str) -> list[results.MetricResult]:
        result = await self._session.execute(
            select(results.MetricResult).where(
                results.MetricResult.call_run_id == call_run_id
            )
        )
        return list(result.scalars().all())

    async def list_results_for_attempt(
        self, call_attempt_id: str
    ) -> list[results.MetricResult]:
        result = await self._session.execute(
            select(results.MetricResult).where(
                results.MetricResult.call_attempt_id == call_attempt_id
            )
        )
        return list(result.scalars().all())


def _validate_value_representation(
    status: str,
    value_type: str | None,
    *,
    value_numeric: float | None,
    value_boolean: bool | None,
    value_text: str | None,
    value_category: str | None,
) -> None:
    values = {
        "value_numeric": value_numeric,
        "value_boolean": value_boolean,
        "value_text": value_text,
        "value_category": value_category,
    }
    present = [name for name, value in values.items() if value is not None]

    if status != MetricStatus.COMPUTED.value:
        if present:
            raise ValidationError(
                f"metric result status '{status}' must not carry a value"
            )
        return

    if value_type is None:
        raise ValidationError("computed metric result requires a value_type")
    expected = {
        MetricValueType.NUMERIC.value: "value_numeric",
        MetricValueType.BOOLEAN.value: "value_boolean",
        MetricValueType.TEXT.value: "value_text",
        MetricValueType.CATEGORY.value: "value_category",
    }.get(value_type)
    if expected is None:
        raise ValidationError(f"unknown metric value_type '{value_type}'")
    if present != [expected]:
        raise ValidationError(
            f"value_type '{value_type}' requires exactly '{expected}' to be set"
        )
