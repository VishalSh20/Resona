"""task_completion (spec §6.2): category from goal conditions + ranked evidence."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, run_probe
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    goals = ctx.ledger_items("goal")
    if not goals:
        return MetricEvaluation(
            metric_key="task_completion", status="not_applicable",
            breakdown={"detail": "no_goal_conditions"},
        )

    probe = get_probe("tc.cond.v1")
    probes = []
    findings: list[FindingRecord] = []
    conditions: list[dict] = []
    critical_miss = False
    any_met = False
    any_partial = False
    any_insufficient = False

    evidence = {
        "tool": _tool_evidence(ctx),
        "conversation": ctx.stage0.agent_text(),
        "external_state": "",
    }

    for goal in goals:
        critical = bool(getattr(goal, "critical", False))
        source = getattr(goal, "verification_source", "conversation")
        condition = getattr(goal, "condition", "")
        verdict = "insufficient_evidence"

        # Hard rule: tool/external_state conditions cannot be met on conversation alone.
        allowed_evidence = evidence
        if source in {"tool", "external_state"}:
            allowed_evidence = {"tool": evidence["tool"], "external_state": evidence["external_state"], "conversation": ""}
        if any(allowed_evidence.get(k, "") for k in allowed_evidence):
            answer, record, _ = await run_probe(
                ctx, probe,
                {"required_condition": condition, "verification_source": source, "evidence": allowed_evidence},
                turn_ids=list(getattr(goal, "turn_ids", []) or []),
                weight=2.0 if critical else 1.0,
                critical=critical,
            )
            probes.append(record)
            labels = answer.probabilities or {}
            verdict = max(labels, key=labels.get) if labels else "insufficient_evidence"
        else:
            any_insufficient = True

        conditions.append({"goal_id": getattr(goal, "goal_id", ""), "verdict": verdict, "critical": critical})
        if verdict == "met":
            any_met = True
        elif verdict == "partially_met":
            any_partial = True
        elif verdict == "insufficient_evidence":
            any_insufficient = True
        if critical and verdict in {"not_met", "contradicted"}:
            critical_miss = True
            findings.append(
                FindingRecord(
                    severity="critical", type="critical_condition_not_met",
                    quote=condition[:120], explanation=f"Critical condition not met: {condition[:120]}",
                    probe_id=probe.probe_id,
                )
            )

    category = _decide_category(conditions, critical_miss, any_met, any_partial, any_insufficient)
    value: str | None = category
    status = "ok" if category != "unknown" else "insufficient_evidence"

    return MetricEvaluation(
        metric_key="task_completion",
        status=status,
        value=value,
        direction=None,
        confidence=0.8 if category != "unknown" else 0.4,
        method="react+jev",
        breakdown={"conditions": conditions, "category": category},
        probes=probes,
        findings=findings,
    )


def _decide_category(conditions, critical_miss, any_met, any_partial, any_insufficient) -> str:
    if any_insufficient and not critical_miss:
        return "unknown"
    if conditions and all(c["verdict"] == "met" for c in conditions):
        return "completed"
    if critical_miss and not (any_met or any_partial):
        return "failed"
    if any_met or any_partial:
        return "partial"
    return "failed"


def _tool_evidence(ctx: MetricContext) -> str:
    lines = []
    for call in ctx.signals.tool_calls:
        lines.append(f"{call.tool_name} status={call.status} args={call.arguments} result={call.result}")
    return "\n".join(lines)


__all__ = ["evaluate"]
