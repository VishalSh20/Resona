"""instruction_following (spec §7.3): compliance with atomic instructions."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, finalize, run_probe
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord

_RUBRIC = "Does the agent comply with the atomic instructions in the judge prompt?"

_SEVERITY_WEIGHT = {"critical": 3.0, "major": 2.0, "minor": 1.0}


def _evaluate_code_instruction(instruction, transcript: str) -> tuple[float | None, dict]:
    """A small set of deterministic instruction checks (§7.3)."""
    text = getattr(instruction, "text", "").lower()
    if "must not" in text or "forbidden" in text:
        forbidden = text.split("must not", 1)[-1].strip(" :")
        violated = bool(forbidden) and forbidden in transcript.lower()
        return (0.0 if violated else 1.0), {"kind": "forbidden_string", "target": forbidden}
    return None, {"kind": "unsupported_code_check"}


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    instructions = ctx.ledger_items("instruction")
    if not instructions:
        return MetricEvaluation(
            metric_key="instruction_following",
            status="not_applicable",
            breakdown={"detail": "no_instructions"},
        )

    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []
    triggered_probe = get_probe("if.trigger.v1")
    comply_probe = get_probe("if.comply.v1")
    applicable = 0
    critical_violation = False
    major_violations = 0

    transcript = ctx.stage0.agent_text()
    for instruction in instructions:
        severity = getattr(instruction, "severity", "major")
        weight = _SEVERITY_WEIGHT.get(severity, 1.0)
        itype = getattr(instruction, "type", "must")
        evaluator = getattr(instruction, "evaluator", "jev")
        instruction_text = getattr(instruction, "text", "")

        state = {"instruction": instruction_text, "window": ctx.stage0.agent_text()}

        if itype in {"conditional", "ordering"} and getattr(instruction, "trigger", None):
            trigger_answer, trigger_record, _ = await run_probe(
                ctx,
                triggered_probe,
                {"instruction": instruction_text, "trigger": getattr(instruction, "trigger", "")},
            )
            probes.append(trigger_record)
            if float(trigger_answer.value or 0.0) < 0.5:
                continue

        applicable += 1
        if evaluator == "code":
            credit, detail = _evaluate_code_instruction(instruction, transcript)
            if credit is not None:
                credits.append((credit, weight))
                continue

        answer, record, _ = await run_probe(ctx, comply_probe, state, weight=weight)
        probes.append(record)
        credit = answer_credit(comply_probe, answer)
        if credit is None:
            continue
        credits.append((credit, weight))
        if credit < 0.3:
            findings.append(
                FindingRecord(
                    severity=severity if severity in {"critical", "major", "minor"} else "major",
                    type="instruction_violation",
                    quote=instruction_text[:120],
                    explanation=f"Instruction not followed: {instruction_text[:120]}",
                    probe_id=comply_probe.probe_id,
                )
            )
            if severity == "critical":
                critical_violation = True
            elif severity == "major":
                major_violations += 1

    raw = weighted_mean(credits)
    caps: list[int] = []
    if critical_violation:
        caps.append(2)
    if major_violations >= 2:
        caps.append(3)

    return await finalize(
        ctx,
        metric_key="instruction_following",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown={"n_applicable": applicable, "n_total": len(instructions)},
        rubric=_RUBRIC,
    )


__all__ = ["evaluate"]
