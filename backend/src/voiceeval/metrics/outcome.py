"""Metric outcomes and evidence.

A :class:`MetricOutcome` is the typed result of evaluating one metric against one
attempt. Its ``status`` is one of the five documented availability values; a
metric that could not be observed is never silently turned into a zero.
Evidence is expressed as :class:`EvidenceSpec` pointers that reference the
observed-truth object (turn, event, tool call, audio region, state transition)
that supports the value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import MetricStatus, MetricValueType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from voiceeval.metrics.registry import MetricSpec

_VALUE_COLUMN = {
    MetricValueType.NUMERIC: "value_numeric",
    MetricValueType.BOOLEAN: "value_boolean",
    MetricValueType.TEXT: "value_text",
    MetricValueType.CATEGORY: "value_category",
}


@dataclass(frozen=True)
class EvidenceSpec:
    """A pointer to the observed-truth object supporting a metric value."""

    source_type: str
    source_id: str
    start_ms: int | None = None
    end_ms: int | None = None
    quote: str | None = None
    rationale: str | None = None


@dataclass
class MetricOutcome:
    metric_key: str
    version: str
    status: MetricStatus
    value_type: MetricValueType | None = None
    value: float | bool | str | None = None
    unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    method: str | None = None
    measurement_basis: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    evidence: list[EvidenceSpec] = field(default_factory=list)
    detail: str | None = None

    @property
    def is_computed(self) -> bool:
        return self.status is MetricStatus.COMPUTED

    def value_column(self) -> str | None:
        if self.status is not MetricStatus.COMPUTED or self.value_type is None:
            return None
        return _VALUE_COLUMN[MetricValueType(self.value_type)]

    def typed_value(self) -> float | bool | str | None:
        """Return the value only when the status is COMPUTED."""
        return self.value if self.status is MetricStatus.COMPUTED else None

    def validate(self) -> None:
        """Enforce the availability contract in-process before persistence."""
        if self.status is MetricStatus.COMPUTED:
            if self.value_type is None:
                raise ValidationError("computed metric outcome requires a value_type")
            if self.value is None:
                raise ValidationError("computed metric outcome requires a value")
            return
        # Non-computed outcomes must not carry a value or a value_type.
        if self.value is not None or self.value_type is not None:
            raise ValidationError(
                f"metric outcome status '{self.status.value}' must not carry a value"
            )


def _spec_fields(spec: "MetricSpec") -> dict[str, Any]:
    return {
        "metric_key": spec.metric_key,
        "version": spec.version,
        "value_type": spec.value_type,
        "unit": spec.unit,
        "scale_min": spec.scale_min,
        "scale_max": spec.scale_max,
        "method": spec.method,
    }


def computed(
    spec: "MetricSpec",
    value: float | bool | str,
    *,
    measurement_basis: dict[str, Any] | None = None,
    evidence: list[EvidenceSpec] | None = None,
    confidence: float | None = None,
) -> MetricOutcome:
    outcome = MetricOutcome(
        status=MetricStatus.COMPUTED,
        value=value,
        measurement_basis=measurement_basis or {},
        evidence=evidence or [],
        confidence=confidence,
        **_spec_fields(spec),
    )
    return outcome


def unavailable(
    spec: "MetricSpec",
    status: MetricStatus,
    detail: str,
    *,
    measurement_basis: dict[str, Any] | None = None,
    evidence: list[EvidenceSpec] | None = None,
) -> MetricOutcome:
    return MetricOutcome(
        status=status,
        measurement_basis=measurement_basis or {},
        evidence=evidence or [],
        detail=detail,
        metric_key=spec.metric_key,
        version=spec.version,
        method=spec.method,
    )


def not_available(
    spec: "MetricSpec",
    detail: str,
    **kwargs: Any,
) -> MetricOutcome:
    return unavailable(spec, MetricStatus.NOT_AVAILABLE, detail, **kwargs)


def not_applicable(
    spec: "MetricSpec",
    detail: str,
    **kwargs: Any,
) -> MetricOutcome:
    return unavailable(spec, MetricStatus.NOT_APPLICABLE, detail, **kwargs)


def invalid(spec: "MetricSpec", detail: str, **kwargs: Any) -> MetricOutcome:
    return unavailable(spec, MetricStatus.INVALID, detail, **kwargs)


def error(spec: "MetricSpec", detail: str, **kwargs: Any) -> MetricOutcome:
    return unavailable(spec, MetricStatus.ERROR, detail, **kwargs)
