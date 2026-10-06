"""Shared helpers for the probe-and-decide judge metrics (spec §7)."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation, probe_record
from voiceeval.judging.probes.interpret import (
    choice_value,
    finalize_judge_metric,
    noul_value,
    score_value,
)
from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import ProbeSpec
from voiceeval.judging.schemas import SanityBlock
from voiceeval.llm.base import LLMError

logger = logging.getLogger("voiceeval.judging.metrics")


def agent_turns(ctx: MetricContext):
    return [turn for turn in ctx.stage0.turns if turn.speaker == "agent" and turn.text]


def caller_turns(ctx: MetricContext):
    return [turn for turn in ctx.stage0.turns if turn.speaker == "caller" and turn.text]


def is_uncertain(ctx: MetricContext, probe: ProbeSpec, answer: ProbeAnswer) -> bool:
    settings = ctx.settings
    if probe.type == "noul":
        value = float(answer.value or 0.0)
        return settings.jev_escalation_lo < value < settings.jev_escalation_hi
    if answer.confidence is None:
        return False
    return answer.confidence < settings.jev_confidence_tau


async def run_probe(
    ctx: MetricContext,
    probe: ProbeSpec,
    state: dict[str, Any],
    *,
    turn_ids: list[int | str] | None = None,
    weight: float | None = None,
    critical: bool | None = None,
):
    """Run one probe, applying escalation/verification when required.

    Returns ``(answer, record, escalated)``.
    """
    weight = probe.weight if weight is None else weight
    critical = probe.critical if critical is None else critical
    try:
        answer = await ctx.runner.run_single(state, probe.probe_id, probe.question())
    except LLMError as exc:
        logger.info("probe %s failed: %s", probe.probe_id, exc)
        answer = ProbeAnswer(
            qid=probe.probe_id,
            type=probe.type,
            value=None,
            resolver="llm_fallback",
        )

    escalated = False
    variants_agree: bool | None = None
    if ctx.verify is not None and (critical or is_uncertain(ctx, probe, answer)):
        answer, escalated, variants_agree = await ctx.verify.adjudicate(
            probe, state, answer, turn_ids or []
        )

    record = probe_record(
        probe.probe_id,
        answer,
        weight=weight,
        turn_ids=turn_ids,
        escalated=escalated,
        variants_agree=variants_agree,
    )
    return answer, record, escalated


class HolisticScore(BaseModel):
    score: int = Field(ge=1, le=5)
    rationale: str = ""


async def sanity_score(
    ctx: MetricContext, metric_key: str, rubric: str, transcript: str
) -> tuple[int | None, int | None]:
    """Holistic 1-5 rating of the whole call; never used as the final score."""
    if ctx.llm is None:
        return None, None
    system = (
        "You rate an entire call on one dimension. Return a single integer 1-5 "
        "(higher is better) and a one-sentence rationale."
    )
    user = f"Dimension: {metric_key}\nRubric: {rubric}\n\nTranscript:\n{transcript}"
    try:
        result = await ctx.llm.structured(HolisticScore, system=system, user=user)
        return int(result.score), None
    except LLMError:
        return None, None


def caps_value(*caps: int | None) -> list[int]:
    return [cap for cap in caps if cap is not None]


async def finalize(
    ctx: MetricContext,
    *,
    metric_key: str,
    raw: float | None,
    probes: list,
    findings: list,
    caps: list[int] | None = None,
    breakdown: dict[str, Any] | None = None,
    rubric: str = "",
    method: str = "probe_and_decide",
    confidence: float | None = None,
    status_on_missing: str = "insufficient_evidence",
) -> MetricEvaluation:
    """Map a 0-1 aggregate to 1-5, apply caps, and run the sanity pass (§7)."""
    breakdown = dict(breakdown or {})
    if raw is None:
        return MetricEvaluation(
            metric_key=metric_key,
            status=status_on_missing,
            breakdown={**breakdown, "detail": "no_scoreable_evidence"},
            probes=list(probes),
            findings=list(findings),
        )
    value = finalize_judge_metric(raw, caps)
    if value is None:  # pragma: no cover - raw is not None here
        return MetricEvaluation(metric_key=metric_key, status="insufficient_evidence", probes=list(probes))
    holistic, _ = await sanity_score(ctx, metric_key, rubric, ctx.stage0.agent_text())
    gap = abs(holistic - value) if holistic is not None else None
    if confidence is None:
        confidences = [p.confidence for p in probes if p.confidence is not None]
        confidence = sum(confidences) / len(confidences) if confidences else None
    breakdown["raw_0_1"] = round(raw, 4)
    breakdown["caps_applied"] = caps or []
    return MetricEvaluation(
        metric_key=metric_key,
        value=float(value),
        direction="higher_is_better",
        normalized=(value - 1) / 4 * 100,
        confidence=confidence,
        method=method,
        summary=findings[0].explanation if findings else None,
        breakdown=breakdown,
        sanity=SanityBlock(holistic_llm_score=holistic, gap=gap) if holistic is not None else None,
        probes=list(probes),
        findings=list(findings),
    )


def answer_credit(probe: ProbeSpec, answer: ProbeAnswer) -> float | None:
    """Convert a probe answer into a 0-1 credit using the probe's credits."""
    if probe.type == "noul":
        if answer.value is None:
            return None
        return noul_value(float(answer.value), invert=probe.invert)
    if probe.type == "choice":
        return choice_value(answer.probabilities, probe.credits or {})
    if probe.type == "score":
        levels = probe.criteria if isinstance(probe.criteria, list) else []
        score = answer.value if isinstance(answer.value, (int, float)) else None
        return score_value(answer.probabilities, max(2, len(levels)), score=score)
    return None


__all__ = [
    "agent_turns",
    "answer_credit",
    "caller_turns",
    "caps_value",
    "finalize",
    "is_uncertain",
    "run_probe",
    "sanity_score",
]
