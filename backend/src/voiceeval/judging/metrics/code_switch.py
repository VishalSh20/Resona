"""code_switching_accuracy (spec §6.2): handling the caller's language mixing."""

from __future__ import annotations

from voiceeval.judging.metrics.base import MetricContext, MetricEvaluation
from voiceeval.judging.metrics.judge_common import answer_credit, run_probe
from voiceeval.judging.probes.interpret import weighted_mean
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.stage0.language import analyze_text


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    ordered = sorted([t for t in ctx.stage0.turns if t.text], key=lambda t: t.t_start or 0)
    mix_probe = get_probe("cs.mix.v1")
    terms_probe = get_probe("cs.terms.v1")
    probes = []
    credits: list[tuple[float | None, float]] = []
    appropriate = 0
    evaluated = 0

    previous_caller = None
    for turn in ordered:
        if turn.speaker == "caller":
            previous_caller = turn
            continue
        eligible = False
        features: dict = {}
        if previous_caller is not None:
            caller_profile = analyze_text(previous_caller.text)
            features = {
                "caller_cmi": caller_profile.profile.code_mixing_index,
                "caller_switches": list(caller_profile.switch_token_indices),
            }
            eligible = caller_profile.profile.code_mixing_index > 0.1 or bool(caller_profile.switch_token_indices)
        if not eligible:
            continue

        evaluated += 1
        agent_profile = analyze_text(turn.text)
        state = {
            "caller_turn": previous_caller.text if previous_caller else "",
            "agent_turn": turn.text,
            "features": {**features, "agent_cmi": agent_profile.profile.code_mixing_index},
            "language_policy": ctx.language_policy,
        }
        for probe in (mix_probe, terms_probe):
            answer, record, _ = await run_probe(ctx, probe, state, turn_ids=[turn.turn_id])
            probes.append(record)
            credit = answer_credit(probe, answer)
            if credit is not None:
                credits.append((credit, probe.weight))
                if probe is mix_probe and credit >= 0.7:
                    appropriate += 1

    if evaluated == 0:
        return MetricEvaluation(
            metric_key="code_switching_accuracy", status="not_applicable",
            direction="higher_is_better", breakdown={"detail": "no_eligible_turns"},
        )
    value = weighted_mean(credits)
    if value is None:
        return MetricEvaluation(
            metric_key="code_switching_accuracy", status="insufficient_evidence",
            breakdown={"detail": "no_credits"},
        )
    return MetricEvaluation(
        metric_key="code_switching_accuracy",
        value=value,
        direction="higher_is_better",
        normalized=value * 100,
        confidence=0.7,
        method="code+jev",
        breakdown={"eligible_turns": evaluated, "appropriate_rate": appropriate / max(1, evaluated)},
        probes=probes,
    )


__all__ = ["evaluate"]
