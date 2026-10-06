"""kb_groundedness (spec §6.2): KB-checkable claims entailed by retrieved chunks."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, run_probe
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_KB_TYPES = {"domain_fact", "policy_statement"}


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    collection_id = (ctx.evaluator_content.get("kb_collection_id") or "").strip()
    if not collection_id or not ctx.retrieval.enabled(collection_id):
        return MetricEvaluation(
            metric_key="kb_groundedness", status="not_applicable",
            breakdown={"detail": "no_kb_collection"},
        )

    claims = [c for c in ctx.ledger_items("claim") if getattr(c, "type", "") in _KB_TYPES]
    if not claims:
        return MetricEvaluation(
            metric_key="kb_groundedness", status="not_applicable",
            breakdown={"detail": "no_kb_checkable_claims"},
        )

    probe = get_probe("kb.entail.v1")
    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []
    contradicted = 0

    for claim in claims:
        text = getattr(claim, "text", "")
        turn_ids = list(getattr(claim, "turn_ids", []) or [])
        queries = [text, _entity_query(text), f"What policy applies to: {text}"]
        chunks = []
        for query in queries:
            chunks.extend(await ctx.retrieval.retrieve(query, collection_id=collection_id, k=8))
        unique = {chunk.chunk_id: chunk for chunk in chunks}
        top = list(unique.values())[:5]
        if not top:
            credits.append((None, 1.0))
            continue
        answer, record, _ = await run_probe(
            ctx, probe,
            {"claim": text, "chunks": [chunk.text for chunk in top]},
            turn_ids=turn_ids,
        )
        probes.append(record)
        credit = answer_credit(probe, answer)
        weight = 3.0 if getattr(claim, "severity", "") == "critical" else 1.0
        credits.append((credit, weight))
        labels = answer.probabilities or {}
        if labels.get("contradicted", 0) > 0.5:
            contradicted += 1
            findings.append(
                FindingRecord(
                    severity="critical", type="kb_contradiction", turn_ids=turn_ids,
                    quote=getattr(claim, "quote", None),
                    explanation=f"KB contradicts claim: {text[:100]}", probe_id=probe.probe_id,
                )
            )

    ratio = weighted_mean(credits)
    if ratio is None:
        return MetricEvaluation(
            metric_key="kb_groundedness", status="insufficient_evidence",
            breakdown={"detail": "no_retrieved_chunks"},
        )
    return MetricEvaluation(
        metric_key="kb_groundedness",
        value=ratio,
        direction="higher_is_better",
        normalized=ratio * 100,
        confidence=0.7,
        method="retrieval+jev",
        breakdown={"contradicted_rate": contradicted / max(1, len(claims)), "claims": len(claims)},
        probes=probes,
        findings=findings,
    )


def _entity_query(text: str) -> str:
    words = [w for w in text.split() if w[:1].isupper()]
    return " ".join(words[:6]) or text


__all__ = ["evaluate"]
