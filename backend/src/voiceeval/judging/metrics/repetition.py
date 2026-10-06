"""repetition (spec §6.2): unjustified repeats, lower is better."""

from __future__ import annotations

from voiceeval.judging.evidence.quote_check import normalize
from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import (
    agent_turns,
    answer_credit,
    caller_turns,
    run_probe,
)
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "Share of agent turns that are unjustified repeats."


def _jaccard(a: str, b: str) -> float:
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    agents = agent_turns(ctx)
    if not agents:
        return MetricEvaluation(
            metric_key="repetition", status="not_applicable",
            direction="lower_is_better", breakdown={"detail": "no_agent_turns"},
        )
    callers = caller_turns(ctx)
    probe = get_probe("rep.cand.v1")
    probes = []
    findings: list[FindingRecord] = []
    repeat_weight = 0.0

    for i in range(len(agents)):
        for j in range(i + 1, min(len(agents), i + 10)):
            if _jaccard(agents[i].text, agents[j].text) < 0.6:
                continue
            between = [c.text for c in callers if _between(c, agents[i], agents[j])]
            state = {
                "earlier_turn": agents[i].text,
                "later_turn": agents[j].text,
                "caller_turns_between": between,
                "slot_info": "",
            }
            answer, record, _ = await run_probe(ctx, probe, state, turn_ids=[agents[j].turn_id])
            probes.append(record)
            credit = answer_credit(probe, answer)
            if credit is None:
                continue
            repeat_weight += credit
            if credit >= 0.5:
                findings.append(
                    FindingRecord(
                        severity="major", type="unjustified_repeat", turn_ids=[agents[j].turn_id],
                        quote=agents[j].text, explanation="Unjustified repetition of earlier content.",
                        probe_id=probe.probe_id,
                    )
                )

    rate = repeat_weight / len(agents)
    normalized = 100 * (1 - min(1.0, 2 * rate))
    confidence_values = [p.confidence for p in probes if p.confidence is not None]
    return MetricEvaluation(
        metric_key="repetition",
        value=rate,
        direction="lower_is_better",
        normalized=normalized,
        confidence=(sum(confidence_values) / len(confidence_values)) if confidence_values else None,
        method="code+jev",
        breakdown={"rate": round(rate, 4), "agent_turns": len(agents), "candidates": len(probes)},
        probes=probes,
        findings=findings,
    )


def _between(caller, earlier, later) -> bool:
    if earlier.t_start is None or later.t_start is None or caller.t_start is None:
        return False
    return earlier.t_start <= caller.t_start <= later.t_start


__all__ = ["evaluate"]
