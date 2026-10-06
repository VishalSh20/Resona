"""empathy (spec §7.4): recognizing and responding to the caller's emotional state."""

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

_RUBRIC = "Does the agent recognize the caller's emotional state and respond with fitting acknowledgment and tone?"


async def evaluate(ctx: MetricContext) -> MetricEvaluation:
    emotions = ctx.ledger_items("emotion")
    moments = [item for item in emotions if getattr(item, "intensity", 0) >= 1]
    probes = []
    findings: list[FindingRecord] = []
    credits: list[tuple[float | None, float]] = []
    caveats: list[str] = []
    intensity3_low = False

    ack_probe = get_probe("emp.ack.v1")
    tone_probe = get_probe("emp.tone.v1")
    script_probe = get_probe("emp.script.v1")
    move_probe = get_probe("emp.move.v1")
    agents = agent_turns(ctx)

    if moments:
        for moment in moments:
            intensity = float(getattr(moment, "intensity", 1))
            turn_ids = list(getattr(moment, "turn_ids", []) or [])
            state = {
                "caller_turn_text": getattr(moment, "quote", ""),
                "caller_annotation": {
                    "emotions": getattr(moment, "emotion_labels", []),
                    "intensity": intensity,
                    "prosody": getattr(moment, "prosody_cues", []),
                },
                "agent_response_turns": [a.text for a in agents],
                "agent_voice_annotation": getattr(moment, "agent_voice", None),
            }
            for probe, weight_scale in ((ack_probe, 1.5), (tone_probe, 1.0), (script_probe, 0.5), (move_probe, 1.0)):
                answer, record, _ = await run_probe(
                    ctx, probe, state, turn_ids=turn_ids, weight=probe.weight * intensity
                )
                probes.append(record)
                credit = answer_credit(probe, answer)
                if credit is not None:
                    credits.append((credit, probe.weight * intensity))
                if probe is ack_probe and intensity >= 3 and credit is not None and credit <= 0.1:
                    intensity3_low = True
                    findings.append(
                        FindingRecord(
                            severity="critical",
                            type="ignored_intensity3",
                            turn_ids=turn_ids,
                            quote=getattr(moment, "quote", None),
                            explanation="High-intensity emotional moment not acknowledged.",
                            probe_id=ack_probe.probe_id,
                        )
                    )
        raw = weighted_mean(credits)
        caps = [2] if intensity3_low else []
        breakdown = {"opportunities": len(moments)}
    else:
        # No emotional moments: baseline courtesy with a hard cap at 4 (§7.4).
        base_probe = get_probe("emp.base.v1")
        for turn in agents[:5]:
            answer, record, _ = await run_probe(ctx, base_probe, {"agent_turn": turn.text}, turn_ids=[turn.turn_id])
            probes.append(record)
            credit = answer_credit(base_probe, answer)
            if credit is not None:
                credits.append((credit, 1.0))
        raw = weighted_mean(credits)
        caps = [4]
        breakdown = {"opportunities": 0}

    no_prosody = ctx.stage0.validation.bleed_detected or not _has_audio_annotation(emotions)
    if no_prosody:
        caveats.append("no_prosody")

    evaluation = await finalize(
        ctx,
        metric_key="empathy",
        raw=raw,
        probes=probes,
        findings=findings,
        caps=caps,
        breakdown=breakdown,
        rubric=_RUBRIC,
    )
    if not moments and evaluation.confidence is not None:
        evaluation.confidence *= 0.7
    if no_prosody and evaluation.confidence is not None:
        evaluation.confidence *= 0.8
    evaluation.caveats.extend(caveats)
    return evaluation


def _has_audio_annotation(emotions) -> bool:
    return any(getattr(item, "prosody_cues", None) for item in emotions)


__all__ = ["evaluate"]
