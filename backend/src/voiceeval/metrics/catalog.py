"""The default metric catalog.

Registers every metric the v1 evaluation pipeline understands, with its
capability requirements and normalization/aggregation configuration. Judge-backed
metrics (implemented in :mod:`voiceeval.judging`) and hybrid metrics are
registered here too, so a single registry describes the whole catalogue and the
aggregation/composite layers can normalize any metric uniformly.
"""

from __future__ import annotations

from voiceeval.domain.enums import MetricValueType
from voiceeval.metrics.registry import MetricRegistry, MetricSpec
from voiceeval.services.capabilities import (
    CAPABILITY_AGENT_AUDIO_EGRESS,
    CAPABILITY_CALLER_AUDIO_INGRESS,
    CAPABILITY_INTERRUPTIONS,
    CAPABILITY_TARGET_TEXT_STREAM,
)

_CAT_CONTINUOUS = {"kind": "continuous"}
_CAT_ORDINAL = {"kind": "ordinal", "min": 1, "max": 5}
_CAT_BOOLEAN = {"kind": "boolean"}
_CAT_CATEGORY = {"kind": "category"}

TASK_COMPLETION_CATEGORY_MAP = {
    "completed": 100.0,
    "partial": 60.0,
    "failed": 0.0,
    "unknown": None,
}


def _linear(best: float, worst: float) -> dict:
    return {
        "kind": "linear",
        "best": best,
        "worst": worst,
        "direction": "lower_is_better" if worst >= best else "higher_is_better",
    }


DEFAULT_METRICS: list[MetricSpec] = [
    # latency & turn-taking -------------------------------------------------
    MetricSpec(
        metric_key="ttfa",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="latency",
        unit="ms",
        required_capabilities=frozenset(
            {CAPABILITY_CALLER_AUDIO_INGRESS, CAPABILITY_AGENT_AUDIO_EGRESS}
        ),
        method="signal",
        required_evidence=frozenset({"event"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config=_linear(best=0, worst=2000),
        composite_category="latency",
    ),
    MetricSpec(
        metric_key="ttft",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="latency",
        unit="ms",
        required_capabilities=frozenset({CAPABILITY_TARGET_TEXT_STREAM}),
        method="signal",
        required_evidence=frozenset({"event"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config=_linear(best=0, worst=2000),
        composite_category="latency",
    ),
    MetricSpec(
        metric_key="barge_in_latency",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="latency",
        unit="ms",
        required_capabilities=frozenset({CAPABILITY_INTERRUPTIONS}),
        method="signal",
        required_evidence=frozenset({"event"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config=_linear(best=0, worst=2000),
        composite_category="latency",
    ),
    MetricSpec(
        metric_key="barge_in_success_rate",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="latency",
        unit="ratio",
        required_capabilities=frozenset({CAPABILITY_INTERRUPTIONS}),
        method="signal",
        required_evidence=frozenset({"event"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config={"kind": "ratio"},
        composite_category="latency",
    ),
    # language detection -----------------------------------------------------
    MetricSpec(
        metric_key="language_detection_accuracy",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="language",
        unit="ratio",
        method="signal",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config={"kind": "ratio"},
        composite_category="language",
    ),
    # conversation quality (judge) ------------------------------------------
    MetricSpec(
        metric_key="relevancy",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="conversation",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="conversation",
    ),
    MetricSpec(
        metric_key="context_retention",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="conversation",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="conversation",
    ),
    MetricSpec(
        metric_key="instruction_following",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="conversation",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="conversation",
    ),
    MetricSpec(
        metric_key="empathy",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="conversation",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="conversation",
    ),
    # task & knowledge quality (judge) ---------------------------------------
    MetricSpec(
        metric_key="hallucination",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="task",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn", "tool_call"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="task",
    ),
    # language quality (judge) -----------------------------------------------
    MetricSpec(
        metric_key="semantic_preservation",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="language",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="language",
    ),
    MetricSpec(
        metric_key="language_consistency",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="language",
        scale_min=1,
        scale_max=5,
        method="probe",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_ORDINAL,
        normalization_config=_CAT_ORDINAL,
        composite_category="language",
    ),
    # hybrid -----------------------------------------------------------------
    MetricSpec(
        metric_key="repetition",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="conversation",
        unit="ratio",
        method="hybrid",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config={"kind": "ratio"},
        composite_category="conversation",
    ),
    MetricSpec(
        metric_key="task_completion",
        version="1.0",
        value_type=MetricValueType.CATEGORY,
        family="task",
        method="react",
        required_evidence=frozenset({"turn", "tool_call", "state_transition"}),
        aggregation_config=_CAT_CATEGORY,
        normalization_config={
            "kind": "category",
            "mapping": TASK_COMPLETION_CATEGORY_MAP,
        },
        composite_category="task",
    ),
    MetricSpec(
        metric_key="kb_groundedness",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="task",
        unit="ratio",
        method="hybrid",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config={"kind": "ratio"},
        composite_category="task",
    ),
    MetricSpec(
        metric_key="code_switching_accuracy",
        version="1.0",
        value_type=MetricValueType.NUMERIC,
        family="language",
        unit="ratio",
        method="hybrid",
        required_evidence=frozenset({"turn"}),
        aggregation_config=_CAT_CONTINUOUS,
        normalization_config={"kind": "ratio"},
        composite_category="language",
    ),
]

# Every metric key in the catalog, in catalog order. Used as the default
# ``Simulation.metric_set`` so a new simulation starts with the full catalogue.
ALL_METRIC_KEYS: list[str] = [spec.metric_key for spec in DEFAULT_METRICS]

DETERMINISTIC_METRIC_KEYS = frozenset(
    {
        "ttfa",
        "ttft",
        "barge_in_latency",
        "barge_in_success_rate",
        "language_detection_accuracy",
    }
)

JUDGE_METRIC_KEYS = frozenset(
    {
        "relevancy",
        "context_retention",
        "instruction_following",
        "empathy",
        "hallucination",
        "semantic_preservation",
        "language_consistency",
    }
)

HYBRID_METRIC_KEYS = frozenset(
    {
        "repetition",
        "task_completion",
        "kb_groundedness",
        "code_switching_accuracy",
    }
)


def build_default_registry() -> MetricRegistry:
    registry = MetricRegistry()
    for spec in DEFAULT_METRICS:
        registry.register(spec)
    return registry


__all__ = [
    "DEFAULT_METRICS",
    "DETERMINISTIC_METRIC_KEYS",
    "HYBRID_METRIC_KEYS",
    "JUDGE_METRIC_KEYS",
    "TASK_COMPLETION_CATEGORY_MAP",
    "build_default_registry",
]
