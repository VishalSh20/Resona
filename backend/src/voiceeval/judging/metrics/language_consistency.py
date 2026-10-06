"""language_consistency (spec §7.7): keeping the expected language over time."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, run_probe
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.schemas import FindingRecord
from voiceeval.judging.stage0.language import analyze_text

_RUBRIC = "Does the agent keep the expected language over time, without unjustified drift?"


def _expected(policy: dict, caller_lang: str | None) -> str | None:
    mode = (policy or {}).get("mode", "mirror_caller")
    if mode == "mirror_caller":
        return caller_lang
    if isinstance(mode, str) and mode.startswith("fixed:"):
        return mode.split(":", 1)[1].split("[")[0]
    return caller_lang


def _anchor_from_fraction(fraction: float, longest_run: int) -> int:
    if fraction < 0.02 and longest_run == 0:
        return 5
    if fraction < 0.05:
        return 4
    if fraction < 0.15:
        return 3
    if fraction < 0.35 or longest_run >= 3:
        return 2
    return 1


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    ordered = sorted(
        [t for t in ctx.stage0.turns if t.text], key=lambda t: t.t_start or 0
    )
    why_probe = get_probe("lc.why.v1")
    probes = []
    findings: list[FindingRecord] = []
    deviations: list[tuple[float, bool]] = []  # (token_weight, justified)
    longest_run = 0
    current_run = 0
    previous_caller_lang: str | None = None

    total_tokens = 0
    agent_tokens = 0
    for turn in ordered:
        tokens = max(1, len(turn.text.split()))
        total_tokens += tokens
        if turn.speaker == "caller":
            previous_caller_lang = analyze_text(turn.text).dominant
            continue
        agent_tokens += tokens
        dominant = analyze_text(turn.text).dominant
        expected = _expected(ctx.language_policy, previous_caller_lang)
        if not dominant or not expected or dominant == expected or dominant == "mixed_hinglish":
            current_run = 0
            continue

        state = {
            "policy": ctx.language_policy,
            "deviation_span": turn.text,
            "agent_turn": turn.text,
            "preceding_caller_turn_lang": previous_caller_lang,
            "explicit_caller_request": False,
            "timeline_summary": ctx.stage0.language.model_dump() if hasattr(ctx.stage0.language, "model_dump") else {},
        }
        answer, record, _ = await run_probe(ctx, why_probe, state, turn_ids=[turn.turn_id], weight=float(tokens))
        probes.append(record)
        credit = answer_credit(why_probe, answer)
        justified = credit is None or credit >= 0.5
        deviations.append((float(tokens), justified))
        if not justified:
            current_run += 1
            longest_run = max(longest_run, current_run)
            findings.append(
                FindingRecord(
                    severity="major", type="language_drift", turn_ids=[turn.turn_id],
                    quote=turn.text, explanation="Unjustified language deviation.",
                    probe_id=why_probe.probe_id,
                )
            )
        else:
            current_run = 0
    if not deviations:
        return MetricEvaluation(
            metric_key="language_consistency",
            value=5.0,
            direction="higher_is_better",
            normalized=100.0,
            confidence=0.7,
            method="code+jev",
            breakdown={"unjustified_fraction": 0.0, "longest_run": 0},
            probes=probes,
            caveats=list(ctx.stage0.caveats),
        )

    unjustified_weight = sum(weight for weight, justified in deviations if not justified)
    denominator = max(1, agent_tokens)
    fraction = unjustified_weight / denominator
    value = _anchor_from_fraction(fraction, longest_run)
    caps = [2] if longest_run >= 3 else []
    if caps:
        value = min([value, *caps])

    return MetricEvaluation(
        metric_key="language_consistency",
        value=float(value),
        direction="higher_is_better",
        normalized=(value - 1) / 4 * 100,
        confidence=0.75,
        method="code+jev",
        breakdown={
            "unjustified_fraction": round(fraction, 4),
            "longest_run": longest_run,
            "caps_applied": caps,
        },
        probes=probes,
        findings=findings,
        caveats=list(ctx.stage0.caveats),
    )


__all__ = ["evaluate"]
