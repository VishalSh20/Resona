"""Metric evaluation plumbing (spec §7 pattern).

Shared context and result types, plus the projection of a judge evaluation onto
the existing :class:`MetricOutcome` contract so the deterministic-style
persistence/aggregation layers keep working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from voiceeval.core.config import Settings
from voiceeval.judging.evidence.builder import Ledgers
from voiceeval.judging.evidence.result import LedgerResult
from voiceeval.judging.probes.jev import JevRunner, ProbeAnswer
from voiceeval.judging.retrieval.base import Retrieval
from voiceeval.judging.schemas import FindingRecord, ProbeRecord, SanityBlock
from voiceeval.judging.stage0.runner import Stage0Result
from voiceeval.llm.base import BaseGenerationModel
from voiceeval.metrics.outcome import (
    MetricOutcome,
    computed,
    invalid,
    not_applicable,
    not_available,
)
from voiceeval.metrics.registry import MetricSpec
from voiceeval.metrics.signals import AttemptSignals

MetricEvaluator = Callable[["MetricContext"], Awaitable["MetricEvaluation"]]


@dataclass
class MetricContext:
    spec: MetricSpec
    stage0: Stage0Result
    signals: AttemptSignals
    ledgers: Ledgers
    evaluator_content: dict[str, Any]
    judge_prompt: str
    scenario: str
    language_policy: dict[str, Any]
    capabilities: frozenset[str]
    runner: JevRunner
    llm: BaseGenerationModel | None
    retrieval: Retrieval
    settings: Settings
    verify: Any | None = None

    def ledger_items(self, key: str) -> list[Any]:
        return self.ledgers.items(key)

    def ledger(self, key: str) -> LedgerResult | None:
        return self.ledgers.get(key)


@dataclass
class MetricEvaluation:
    metric_key: str
    status: str = "ok"  # ok | not_applicable | not_measurable | insufficient_evidence | invalid
    value: float | str | bool | None = None
    direction: str | None = None
    normalized: float | None = None
    confidence: float | None = None
    method: str | None = None
    summary: str | None = None
    breakdown: dict[str, Any] = field(default_factory=dict)
    sanity: SanityBlock | None = None
    probes: list[ProbeRecord] = field(default_factory=list)
    findings: list[FindingRecord] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def probe_confidence(self) -> float | None:
        values = [p.confidence for p in self.probes if p.confidence is not None]
        if not values:
            return None
        return sum(values) / len(values)


def probe_record(
    probe_id: str,
    answer: ProbeAnswer,
    *,
    weight: float = 1.0,
    turn_ids: list[int | str] | None = None,
    escalated: bool = False,
    variants_agree: bool | None = None,
) -> ProbeRecord:
    return ProbeRecord(
        probe_id=probe_id,
        type=answer.type,
        turn_ids=turn_ids,
        probabilities=answer.probabilities,
        confidence=answer.confidence,
        value=_float_or_none(answer.value),
        weight=weight,
        resolver=answer.resolver,
        escalated=escalated,
        variants_agree=variants_agree,
        jev_model=answer.model,
    )


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def not_measurable(metric_key: str, detail: str, *, caveats: list[str] | None = None) -> MetricEvaluation:
    return MetricEvaluation(
        metric_key=metric_key,
        status="not_measurable",
        breakdown={"detail": detail},
        caveats=caveats or [],
    )


def not_applicable_metric(metric_key: str, detail: str) -> MetricEvaluation:
    return MetricEvaluation(metric_key=metric_key, status="not_applicable", breakdown={"detail": detail})


def to_outcome(spec: MetricSpec, evaluation: MetricEvaluation) -> MetricOutcome:
    """Project a judge evaluation onto the shared metric-outcome contract."""
    evidence = [
        _finding_evidence(finding) for finding in evaluation.findings if finding.turn_ids
    ]
    if evaluation.status == "ok" and evaluation.value is not None:
        outcome = computed(
            spec,
            evaluation.value,
            measurement_basis={
                "method": evaluation.method or spec.method,
                "direction": evaluation.direction,
                "normalized": evaluation.normalized,
                "confidence": evaluation.confidence,
                "breakdown": evaluation.breakdown,
                "summary": evaluation.summary,
                "sanity": evaluation.sanity.model_dump(mode="json") if evaluation.sanity else None,
                "probes": [p.model_dump(mode="json") for p in evaluation.probes],
                "caveats": evaluation.caveats,
            },
            evidence=evidence,
            confidence=evaluation.confidence,
        )
    elif evaluation.status == "not_applicable":
        outcome = not_applicable(spec, str(evaluation.breakdown.get("detail", "not applicable")))
    elif evaluation.status == "invalid":
        outcome = invalid(spec, str(evaluation.breakdown.get("detail", "invalid")))
    elif evaluation.status == "insufficient_evidence":
        outcome = not_available(
            spec, f"insufficient evidence: {evaluation.breakdown.get('detail', '')}"
        )
    else:
        outcome = not_available(
            spec, str(evaluation.breakdown.get("detail", "not measurable"))
        )
    return outcome


def _finding_evidence(finding: FindingRecord):
    from voiceeval.metrics.outcome import EvidenceSpec

    source_type = "turn"
    source_id = str(finding.turn_ids[0]) if finding.turn_ids else "finding"
    return EvidenceSpec(
        source_type=source_type,
        source_id=source_id,
        start_ms=finding.t_start_ms,
        end_ms=finding.t_end_ms,
        quote=finding.quote,
        rationale=finding.explanation,
    )


def _load_evaluators() -> dict[str, MetricEvaluator]:
    from voiceeval.judging.metrics import (
        code_switch,
        context,
        empathy,
        hallucination,
        instruction,
        kb,
        language_consistency,
        relevance,
        repetition,
        semantic,
        signal,
        task_completion,
    )

    return {
        # signal / latency (§6.1)
        "ttfa": signal.evaluate_ttfa,
        "ttft": signal.evaluate_ttft,
        "barge_in_latency": signal.evaluate_barge_in_latency,
        "barge_in_success_rate": signal.evaluate_barge_in_success_rate,
        "language_detection_accuracy": signal.evaluate_language_detection_accuracy,
        # judge metrics (§7)
        "relevancy": relevance.evaluate,
        "context_retention": context.evaluate,
        "instruction_following": instruction.evaluate,
        "empathy": empathy.evaluate,
        "hallucination": hallucination.evaluate,
        "semantic_preservation": semantic.evaluate,
        "language_consistency": language_consistency.evaluate,
        # hybrid (§6.2)
        "repetition": repetition.evaluate,
        "task_completion": task_completion.evaluate,
        "kb_groundedness": kb.evaluate,
        "code_switching_accuracy": code_switch.evaluate,
    }


_REGISTRY: dict[str, MetricEvaluator] | None = None


def all_evaluators() -> dict[str, MetricEvaluator]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _load_evaluators()
    return _REGISTRY


def get_evaluator(metric_key: str) -> MetricEvaluator | None:
    return all_evaluators().get(metric_key)


async def evaluate_metric(ctx: MetricContext) -> MetricEvaluation:
    evaluator = get_evaluator(ctx.spec.metric_key)
    if evaluator is None:
        return MetricEvaluation(
            metric_key=ctx.spec.metric_key,
            status="invalid",
            breakdown={"detail": f"no evaluator for '{ctx.spec.metric_key}'"},
        )
    return await evaluator(ctx)


__all__ = [
    "MetricContext",
    "MetricEvaluation",
    "MetricEvaluator",
    "all_evaluators",
    "evaluate_metric",
    "get_evaluator",
    "not_applicable_metric",
    "not_measurable",
    "probe_record",
    "to_outcome",
]
