"""Persistence for the voice-agent judge's per-run forensic detail.

Stage-1 ledgers, per-metric probes and findings are written alongside the
projected ``metric_result`` rows so every score can be traced back to the exact
bounded decision that produced it (judge spec §8/§9).
"""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import results
from voiceeval.db.repositories.base import Repository


class JudgeLedgerRepository(Repository):
    async def create(
        self,
        *,
        judge_execution_id: str,
        ledger_type: str,
        status: str = "ok",
        payload: dict | None = None,
        caveats: list | None = None,
    ) -> results.JudgeLedger:
        ledger = results.JudgeLedger(
            id=new_id(EntityKind.LEDGER),
            judge_execution_id=judge_execution_id,
            ledger_type=ledger_type,
            status=status,
            payload=payload,
            caveats=caveats,
        )
        self._session.add(ledger)
        await self._session.flush()
        return ledger

    async def list_for_execution(self, judge_execution_id: str) -> list[results.JudgeLedger]:
        result = await self._session.execute(
            select(results.JudgeLedger)
            .where(results.JudgeLedger.judge_execution_id == judge_execution_id)
            .order_by(results.JudgeLedger.ledger_type)
        )
        return list(result.scalars().all())


class MetricProbeRepository(Repository):
    async def create(
        self,
        *,
        metric_result_id: str,
        probe_id: str,
        type: str,
        turn_ids: list | None = None,
        probabilities: dict | None = None,
        confidence: float | None = None,
        value: float | None = None,
        weight: float | None = None,
        resolver: str = "jev",
        escalated: bool = False,
        variants_agree: bool | None = None,
        jev_model: str | None = None,
    ) -> results.MetricProbe:
        probe = results.MetricProbe(
            id=new_id(EntityKind.PROBE),
            metric_result_id=metric_result_id,
            probe_id=probe_id,
            type=type,
            turn_ids=turn_ids,
            probabilities=probabilities,
            confidence=confidence,
            value=value,
            weight=weight,
            resolver=resolver,
            escalated=escalated,
            variants_agree=variants_agree,
            jev_model=jev_model,
        )
        self._session.add(probe)
        await self._session.flush()
        return probe

    async def list_for_metric(self, metric_result_id: str) -> list[results.MetricProbe]:
        result = await self._session.execute(
            select(results.MetricProbe).where(
                results.MetricProbe.metric_result_id == metric_result_id
            )
        )
        return list(result.scalars().all())


class JudgeFindingRepository(Repository):
    async def create(
        self,
        *,
        metric_result_id: str,
        severity: str,
        type: str,
        turn_ids: list | None = None,
        t_start: int | None = None,
        t_end: int | None = None,
        quote: str | None = None,
        explanation: str | None = None,
        probe_id: str | None = None,
    ) -> results.JudgeFinding:
        finding = results.JudgeFinding(
            id=new_id(EntityKind.FINDING),
            metric_result_id=metric_result_id,
            severity=severity,
            type=type,
            turn_ids=turn_ids,
            t_start=t_start,
            t_end=t_end,
            quote=quote,
            explanation=explanation,
            probe_id=probe_id,
        )
        self._session.add(finding)
        await self._session.flush()
        return finding

    async def list_for_metric(self, metric_result_id: str) -> list[results.JudgeFinding]:
        result = await self._session.execute(
            select(results.JudgeFinding).where(
                results.JudgeFinding.metric_result_id == metric_result_id
            )
        )
        return list(result.scalars().all())


__all__ = [
    "JudgeFindingRepository",
    "JudgeLedgerRepository",
    "MetricProbeRepository",
]
