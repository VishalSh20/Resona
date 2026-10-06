"""semantic_preservation (spec §7.6): restatements keep meaning intact."""

from __future__ import annotations

import re

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, finalize, run_probe
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "When the agent restates, confirms, translates or passes information to tools, do entities, numbers, negations and meaning stay intact?"

_NUMBER = re.compile(r"\b\d[\d,./:-]*\b")


def _code_mismatch(source: str, restated: str) -> bool:
    source_numbers = set(_NUMBER.findall(source))
    restated_numbers = set(_NUMBER.findall(restated))
    if source_numbers and not (source_numbers <= restated_numbers):
        return True
    # Negation flip.
    source_neg = any(neg in source.lower() for neg in (" not ", " no ", " never "))
    restated_neg = any(neg in restated.lower() for neg in (" not ", " no ", " never "))
    return source_neg != restated_neg


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    pairs = ctx.ledger_items("preservation")
    if not pairs:
        return MetricEvaluation(
            metric_key="semantic_preservation",
            status="not_applicable",
            breakdown={"detail": "no_preservation_pairs"},
        )

    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []
    critical_entity_error = False

    keep_probe = get_probe("sp.keep.v1")
    add_probe = get_probe("sp.add.v1")
    qual_probe = get_probe("sp.qual.v1")
    sev_probe = get_probe("sp.sev.v1")
    reg_probe = get_probe("sp.reg.v1")

    for pair in pairs:
        source = getattr(pair, "source_span", "")
        restated = getattr(pair, "restated_span", "")
        kind = getattr(pair, "kind", "confirmation")
        turn_ids = list(getattr(pair, "turn_ids", []) or [])
        pair_weight = 2.0 if kind == "tool_arg" else 1.0

        if _code_mismatch(source, restated):
            credits.append((0.0, pair_weight * 2))
            critical_entity_error = True
            findings.append(
                FindingRecord(
                    severity="critical", type="entity_mismatch", turn_ids=turn_ids,
                    quote=getattr(pair, "quote", None),
                    explanation="Restatement changed an entity/number/negation.",
                    probe_id="sp.code",
                )
            )
            continue

        state = {"source_span": source, "restated_span": restated, "kind": kind}
        for probe, extra in ((keep_probe, 2.0), (add_probe, 1.5), (qual_probe, 1.5), (sev_probe, 2.0)):
            answer, record, _ = await run_probe(ctx, probe, state, turn_ids=turn_ids, weight=extra * pair_weight)
            probes.append(record)
            credit = answer_credit(probe, answer)
            if credit is not None:
                credits.append((credit, extra * pair_weight))
            if probe is sev_probe and credit is not None:
                labels = answer.probabilities or {}
                if labels.get("critical_entity_error", 0) > 0.5:
                    critical_entity_error = True
        if kind == "translation":
            answer, record, _ = await run_probe(ctx, reg_probe, state, turn_ids=turn_ids, weight=0.5 * pair_weight)
            probes.append(record)
            credit = answer_credit(reg_probe, answer)
            if credit is not None:
                credits.append((credit, 0.5 * pair_weight))

    raw = weighted_mean(credits)
    caps = [2] if critical_entity_error else []
    return await finalize(
        ctx,
        metric_key="semantic_preservation",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown={"pairs": len(pairs), "critical_entity_error": critical_entity_error},
        rubric=_RUBRIC,
    )


__all__ = ["evaluate"]
