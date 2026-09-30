"""Versioned metric registry.

Every metric the evaluation pipeline can produce is registered once, with its
value type, required capabilities, required evidence, implementation version and
aggregation/normalization configuration. Metrics are versioned explicitly: a
change to the computation registers a new version rather than mutating history.

The registry is the single source of truth for metric *metadata*; the computation
itself lives in the metric modules and is bound to a ``metric_key`` here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voiceeval.core.errors import ValidationError
from voiceeval.domain.enums import MetricValueType


@dataclass(frozen=True)
class MetricSpec:
    metric_key: str
    version: str
    value_type: MetricValueType
    family: str
    unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    method: str = "deterministic"
    required_capabilities: frozenset[str] = frozenset()
    required_evidence: frozenset[str] = frozenset()
    implementation_version: str = "1.0.0"
    aggregation_config: dict[str, Any] = field(default_factory=dict)
    normalization_config: dict[str, Any] = field(default_factory=dict)
    composite_category: str | None = None

    def as_definition_kwargs(self) -> dict[str, Any]:
        """Shape the spec for ``MetricRepository.create_definition``."""
        return {
            "metric_key": self.metric_key,
            "version": self.version,
            "family": self.family,
            "value_type": self.value_type.value,
            "unit": self.unit,
            "scale_min": self.scale_min,
            "scale_max": self.scale_max,
            "required_capabilities": {
                "capabilities": sorted(self.required_capabilities)
            },
            "required_evidence": {"evidence": sorted(self.required_evidence)},
            "implementation_version": self.implementation_version,
            "aggregation_config": self.aggregation_config,
            "normalization_config": self.normalization_config,
        }


class MetricRegistry:
    """A versioned registry of metric specs, keyed by ``(metric_key, version)``."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], MetricSpec] = {}
        self._latest: dict[str, str] = {}

    def register(self, spec: MetricSpec) -> MetricSpec:
        if not spec.metric_key:
            raise ValidationError("metric spec requires a metric_key")
        if not spec.version:
            raise ValidationError(f"metric '{spec.metric_key}' requires a version")
        key = (spec.metric_key, spec.version)
        if key in self._by_key:
            raise ValidationError(
                f"metric '{spec.metric_key}' version '{spec.version}' already "
                "registered"
            )
        self._by_key[key] = spec
        # Later registrations of the same key are treated as the latest version.
        self._latest[spec.metric_key] = spec.version
        return spec

    def has(self, metric_key: str, version: str | None = None) -> bool:
        if version is None:
            return metric_key in self._latest
        return (metric_key, version) in self._by_key

    def get(self, metric_key: str, version: str | None = None) -> MetricSpec:
        resolved = version or self._latest.get(metric_key)
        if resolved is None:
            raise ValidationError(f"unknown metric '{metric_key}'")
        spec = self._by_key.get((metric_key, resolved))
        if spec is None:
            raise ValidationError(
                f"unknown metric '{metric_key}' version '{resolved}'"
            )
        return spec

    def all(self) -> list[MetricSpec]:
        return [self._by_key[key] for key in sorted(self._by_key)]

    def keys(self) -> list[str]:
        return sorted(self._latest)


_DEFAULT_REGISTRY: MetricRegistry | None = None


def get_metric_registry() -> MetricRegistry:
    """Return the process-wide default registry (built on first use)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        from voiceeval.metrics.catalog import build_default_registry

        _DEFAULT_REGISTRY = build_default_registry()
    return _DEFAULT_REGISTRY


def set_metric_registry(registry: MetricRegistry | None) -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry


__all__ = [
    "MetricRegistry",
    "MetricSpec",
    "get_metric_registry",
    "set_metric_registry",
]
