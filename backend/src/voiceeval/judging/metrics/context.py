"""context_retention (spec §7.2): correct use of earlier information."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import (
    agent_turns,
    answer_credit,
    finalize,
    run_probe,
)
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "Does the agent correctly use earlier information, without re-asking known facts or contradictions?"


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    facts = ctx.ledger_items("fact")
    agents = agent_turns(ctx)
    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []
    critical_contradiction = False
    critical_reasks: dict[str, int] = {}

    use_probe = get_probe("ctx.use.v1")
    for index, turn in enumerate(agents):
        relevant = facts[:5]
        if not relevant:
            continue
        for fact in relevant:
            stated = getattr(fact, "stated_turn", None)
            distance = _distance(stated, turn.turn_id)
            critical = bool(getattr(fact, "critical", False))
            weight = (1 + min(distance / 10, 1.0)) * (2.0 if critical else 1.0)
            state = {
                "agent_turn": turn.text,
                "relevant_facts": [getattr(fact, "text", "")],
                "fact_critical": critical,
                "turn_distance": distance,
            }
            answer, record, _ = await run_probe(ctx, use_probe, state, turn_ids=[turn.turn_id], weight=weight)
            probes.append(record)
            credit = answer_credit(use_probe, answer)
            if credit is None:
                continue
            credits.append((credit, weight))
            labels = answer.probabilities or {}
            if critical and (labels.get("contradicts_fact", 0) > 0.5 or labels.get("ignores_active_constraint", 0) > 0.5):
                critical_contradiction = True
                findings.append(
                    FindingRecord(
                        severity="critical",
                        type="contradicts_fact",
                        turn_ids=[turn.turn_id],
                        quote=turn.text,
                        explanation=f"Critical fact contradicted/ignored: {getattr(fact, 'text', '')[:100]}",
                        probe_id=use_probe.probe_id,
                    )
                )
            if labels.get("re_asks_known_fact", 0) > 0.5:
                key = getattr(fact, "fact_id", getattr(fact, "text", ""))
                critical_reasks[key] = critical_reasks.get(key, 0) + 1

    raw = weighted_mean(credits)
    caps: list[int] = []
    if critical_contradiction:
        caps.append(2)
    if any(count >= 2 for count in critical_reasks.values()):
        caps.append(3)

    return await finalize(
        ctx,
        metric_key="context_retention",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown={"contradictions": int(critical_contradiction), "re_asks": sum(critical_reasks.values())},
        rubric=_RUBRIC,
        status_on_missing="not_applicable",
    )


def _distance(stated, current) -> float:
    try:
        return float(abs(int(str(current)) - int(str(stated))))
    except (TypeError, ValueError):
        return 0.0


__all__ = ["evaluate"]
