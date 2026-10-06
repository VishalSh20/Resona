"""Persistence for a judge run.

Writes the Stage-1 ledgers, projects every metric onto ``metric_result`` (with
evidence), then attaches the per-metric probes and findings. The full §9 result
document is persisted on the judge execution by the engine.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.models import results
from voiceeval.db.repositories import (
    JudgeFindingRepository,
    JudgeLedgerRepository,
    MetricProbeRepository,
)
from voiceeval.judging.evidence.builder import LEDGER_KEYS, Ledgers
from voiceeval.judging.metrics.base import MetricEvaluation, to_outcome
from voiceeval.metrics.engine import MetricResultWriter
from voiceeval.metrics.registry import MetricRegistry


class JudgeStorage:
    def __init__(self, session: AsyncSession, registry: MetricRegistry) -> None:
        self._registry = registry
        self._writer = MetricResultWriter(session, registry)
        self._ledgers = JudgeLedgerRepository(session)
        self._probes = MetricProbeRepository(session)
        self._findings = JudgeFindingRepository(session)

    async def write_ledgers(self, execution_id: str, ledgers: Ledgers) -> None:
        for key in LEDGER_KEYS:
            ledger = ledgers.get(key)
            if ledger is None:
                continue
            await self._ledgers.create(
                judge_execution_id=execution_id,
                ledger_type=key,
                status=ledger.status,
                payload=ledger.payload(),
                caveats=ledger.caveats,
            )

    async def write_metrics(
        self,
        *,
        execution_id: str,
        run_id: str,
        attempt_id: str,
        plan_id: str,
        evaluations: list[MetricEvaluation],
    ) -> list[results.MetricResult]:
        outcomes = [
            to_outcome(self._registry.get(evaluation.metric_key), evaluation)
            for evaluation in evaluations
        ]
        written = await self._writer.write(
            run_id=run_id,
            attempt_id=attempt_id,
            plan_id=plan_id,
            outcomes=outcomes,
            judge_execution_id=execution_id,
        )
        for evaluation, metric_result in zip(evaluations, written):
            for probe in evaluation.probes:
                await self._probes.create(
                    metric_result_id=metric_result.id,
                    probe_id=probe.probe_id,
                    type=probe.type,
                    turn_ids=probe.turn_ids,
                    probabilities=probe.probabilities,
                    confidence=probe.confidence,
                    value=probe.value,
                    weight=probe.weight,
                    resolver=probe.resolver,
                    escalated=probe.escalated,
                    variants_agree=probe.variants_agree,
                    jev_model=probe.jev_model,
                )
            for finding in evaluation.findings:
                await self._findings.create(
                    metric_result_id=metric_result.id,
                    severity=finding.severity,
                    type=finding.type,
                    turn_ids=finding.turn_ids,
                    t_start=finding.t_start_ms,
                    t_end=finding.t_end_ms,
                    quote=finding.quote,
                    explanation=finding.explanation,
                    probe_id=finding.probe_id,
                )
        return written


__all__ = ["JudgeStorage"]
