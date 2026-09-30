"""Deterministic evaluation metrics.

The metric registry is the versioned catalogue of measurable quantities; the
engine evaluates deterministic metrics from observed truth and persists results
with explicit availability semantics (never turning missing observability into
a zero).
"""

from voiceeval.metrics.catalog import (
    DEFAULT_METRICS,
    DETERMINISTIC_METRIC_KEYS,
    HYBRID_METRIC_KEYS,
    JUDGE_METRIC_KEYS,
    build_default_registry,
)
from voiceeval.metrics.deterministic import DETERMINISTIC_METRICS, MetricContext
from voiceeval.metrics.engine import (
    MetricEngine,
    build_attempt_inputs,
    evaluate_deterministic,
    expected_tools,
)
from voiceeval.metrics.outcome import EvidenceSpec, MetricOutcome
from voiceeval.metrics.registry import (
    MetricRegistry,
    MetricSpec,
    get_metric_registry,
    set_metric_registry,
)
from voiceeval.metrics.signals import AttemptSignals
from voiceeval.metrics.wer import corpus_wer, word_error_rate

__all__ = [
    "AttemptSignals",
    "DEFAULT_METRICS",
    "DETERMINISTIC_METRIC_KEYS",
    "DETERMINISTIC_METRICS",
    "EvidenceSpec",
    "HYBRID_METRIC_KEYS",
    "JUDGE_METRIC_KEYS",
    "MetricContext",
    "MetricEngine",
    "MetricOutcome",
    "MetricRegistry",
    "MetricSpec",
    "build_attempt_inputs",
    "build_default_registry",
    "corpus_wer",
    "evaluate_deterministic",
    "expected_tools",
    "get_metric_registry",
    "set_metric_registry",
    "word_error_rate",
]
