"""relevancy (spec §7.1): do agent responses address what the caller asked."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import (
    agent_turns,
    answer_credit,
    caller_turns,
    finalize,
    run_probe,
)
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "Do agent responses address what the caller actually asked or needed and resolve each intent?"


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    probes = []
    findings: list[FindingRecord] = []
    intents = ctx.ledger_items("intent")
    agents = agent_turns(ctx)
    callers = caller_turns(ctx)

    turn_probe = get_probe("rel.turn.v1")
    tangent_probe = get_probe("rel.tangent.v1")
    turn_credits: list[tuple[float | None, float]] = []

    for index, turn in enumerate(agents):
        caller_last = callers[index - 1] if index > 0 and index - 1 < len(callers) else None
        state = {
            "agent_turn": turn.text,
            "caller_last_turn": caller_last.text if caller_last else "",
            "open_intents": [getattr(intent, "text", "") for intent in intents],
            "recent_context": [t.text for t in agents[max(0, index - 2) : index]],
        }
        answer, record, _ = await run_probe(ctx, turn_probe, state, turn_ids=[turn.turn_id])
        probes.append(record)
        credit = answer_credit(turn_probe, answer)
        if credit is not None:
            turn_credits.append((credit, 1.0))

        answer, record, _ = await run_probe(ctx, tangent_probe, state, turn_ids=[turn.turn_id])
        probes.append(record)
        credit = answer_credit(tangent_probe, answer)
        if credit is not None:
            turn_credits.append((credit, 0.5))

    intent_probe = get_probe("rel.intent.v1")
    intent_credits: list[tuple[float | None, float]] = []
    critical_low = 0
    for intent in intents:
        critical = bool(getattr(intent, "critical", False))
        weight = 2.0 if critical else 1.0
        state = {
            "intent": getattr(intent, "text", ""),
            "agent_turns_mentioning_intent": [t.text for t in agents],
            "final_state": "",
        }
        answer, record, _ = await run_probe(
            ctx, intent_probe, state, turn_ids=list(getattr(intent, "turn_ids", []) or []), weight=weight
        )
        probes.append(record)
        credit = answer_credit(intent_probe, answer)
        if credit is not None:
            intent_credits.append((credit, weight))
            if credit <= 0.2:
                if critical:
                    critical_low += 1
                findings.append(
                    FindingRecord(
                        severity="critical" if critical else "major",
                        type="intent_unresolved",
                        turn_ids=list(getattr(intent, "turn_ids", []) or []),
                        quote=getattr(intent, "quote", None),
                        explanation=f"Intent not resolved: {getattr(intent, 'text', '')[:120]}",
                        probe_id=intent_probe.probe_id,
                    )
                )

    turn_value = weighted_mean(turn_credits)
    intent_value = weighted_mean(intent_credits)
    values = [(turn_value, 0.6), (intent_value, 0.4)]
    raw = weighted_mean(values)

    caps = []
    if critical_low >= 2:
        caps.append(2)
    elif critical_low == 1:
        caps.append(3)

    return await finalize(
        ctx,
        metric_key="relevancy",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown={
            "turn_value": turn_value,
            "intent_value": intent_value,
            "critical_intents_unresolved": critical_low,
        },
        rubric=_RUBRIC,
    )


__all__ = ["evaluate"]
