"""hallucination (spec §7.5): 5 = no hallucination."""

from __future__ import annotations

import re

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, finalize, run_probe
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "Are the agent's assertions supported by a legitimate source, with no fabricated specifics?"

_NUMBER = re.compile(r"\b\d[\d,./:-]*\b")
_CRITICAL_TYPES = {"action_claim"}
_CRITICAL_HINTS = ("money", "policy", "legal", "medical", "identifier", "account", "amount")


def _claim_weight(claim) -> float:
    ctype = getattr(claim, "type", "")
    if ctype in _CRITICAL_TYPES or getattr(claim, "severity", "") == "critical":
        return 3.0
    text = getattr(claim, "text", "").lower()
    if any(hint in text for hint in _CRITICAL_HINTS):
        return 3.0
    if ctype == "domain_fact":
        return 2.0
    return 1.0


def _numeric_contradiction(claim_text: str, caller_facts: list[str]) -> bool:
    claim_numbers = set(_NUMBER.findall(claim_text))
    if not claim_numbers:
        return False
    for fact in caller_facts:
        if claim_text.split()[0:1] and fact and any(token in fact for token in claim_text.split()[:3]):
            fact_numbers = set(_NUMBER.findall(fact))
            if fact_numbers and not (claim_numbers <= fact_numbers):
                return True
    return False


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    claims = ctx.ledger_items("claim")
    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []

    caller_facts = [getattr(f, "text", "") for f in ctx.ledger_items("fact")]
    tool_summary = _tool_summary(ctx)
    scenario = ctx.scenario
    prompt = ctx.judge_prompt

    action_probe = get_probe("hal.action.v1")
    support_probe = get_probe("hal.support.v1")
    critical_issue = False
    major_issues = 0

    for claim in claims:
        weight = _claim_weight(claim)
        text = getattr(claim, "text", "")
        turn_ids = list(getattr(claim, "turn_ids", []) or [])
        quote = getattr(claim, "quote", None)

        if _numeric_contradiction(text, caller_facts):
            credits.append((0.0, weight))
            critical_issue = True
            findings.append(
                FindingRecord(
                    severity="critical",
                    type="numeric_contradiction",
                    turn_ids=turn_ids,
                    quote=quote,
                    explanation=f"Number/date contradicted by evidence: {text[:100]}",
                    probe_id="hal.code",
                )
            )
            continue

        if getattr(claim, "type", "") in _CRITICAL_TYPES:
            answer, record, _ = await run_probe(
                ctx, action_probe,
                {"claim": text, "tool_calls_in_window": tool_summary},
                turn_ids=turn_ids, weight=weight,
            )
            probes.append(record)
            credit = answer_credit(action_probe, answer)
            if credit is not None:
                credits.append((credit, weight))
                if credit < 0.5:
                    critical_issue = True
                    findings.append(
                        FindingRecord(
                            severity="critical", type="action_hallucination", turn_ids=turn_ids,
                            quote=quote, explanation=f"Claimed action not backed by a tool call: {text[:100]}",
                            probe_id=action_probe.probe_id,
                        )
                    )
            continue

        answer, record, _ = await run_probe(
            ctx, support_probe,
            {"claim": text, "evidence": {"caller": caller_facts, "tool": tool_summary, "kb": [], "prompt": prompt[:2000], "scenario": scenario}},
            turn_ids=turn_ids, weight=weight,
        )
        probes.append(record)
        credit = answer_credit(support_probe, answer)
        if credit is None:
            continue
        credits.append((credit, weight))
        labels = answer.probabilities or {}
        if labels.get("fabricated_specific", 0) > 0.5 or labels.get("contradicted_by_evidence", 0) > 0.5:
            if weight >= 2.0:
                critical_issue = weight >= 3.0
            if weight == 2.0:
                major_issues += 1
            findings.append(
                FindingRecord(
                    severity="critical" if weight >= 3.0 else "major",
                    type="unsupported_claim",
                    turn_ids=turn_ids,
                    quote=quote,
                    explanation=f"Unsupported claim: {text[:100]}",
                    probe_id=support_probe.probe_id,
                )
            )

    raw = weighted_mean(credits)
    caps: list[int] = []
    if critical_issue:
        caps.append(2)
    if major_issues >= 2:
        caps.append(3)

    return await finalize(
        ctx,
        metric_key="hallucination",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown={"claims": len(claims), "major_issues": major_issues},
        rubric=_RUBRIC,
        status_on_missing="not_applicable",
    )


def _tool_summary(ctx: MetricContext) -> str:
    lines = []
    for call in ctx.signals.tool_calls:
        lines.append(f"{call.tool_name} status={call.status} args={call.arguments} result={call.result}")
    return "\n".join(lines) or "(no tool calls)"


__all__ = ["evaluate"]
