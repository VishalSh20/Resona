"""Signal and turn-taking metrics (spec §6.1). All code, no LLM arithmetic."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from voiceeval.judging.config import BACKCHANNEL_LEXICON
from voiceeval.judging.metrics.base import (
    MetricContext,
    MetricEvaluation,
    not_measurable,
    probe_record,
)
from voiceeval.judging.probes.registry import get_probe
from voiceeval.judging.stage0.language import analyze_text
from voiceeval.judging.stage0.turns import TurnRecord
from voiceeval.judging.stage0.vad import VADResult
from voiceeval.services.capabilities import (
    CAPABILITY_AGENT_AUDIO_EGRESS,
    CAPABILITY_CALLER_AUDIO_INGRESS,
    CAPABILITY_INTERRUPTIONS,
    CAPABILITY_TARGET_TEXT_STREAM,
)


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.array(values, dtype=float)
    return {
        "p50": float(np.percentile(array, 50)),
        "p90": float(np.percentile(array, 90)),
        "mean": float(array.mean()),
        "max": float(array.max()),
        "n": float(len(values)),
    }


def _paired_turns(turns: list[TurnRecord]) -> list[tuple[TurnRecord, TurnRecord]]:
    ordered = sorted(turns, key=lambda t: (t.t_start if t.t_start is not None else 0))
    pairs: list[tuple[TurnRecord, TurnRecord]] = []
    for index, turn in enumerate(ordered):
        if turn.speaker != "caller":
            continue
        for following in ordered[index + 1 :]:
            if following.speaker == "agent":
                pairs.append((turn, following))
                break
    return pairs


def _agent_first_audio(agent_turn: TurnRecord, agent_vad: VADResult | None) -> int | None:
    if agent_vad is None:
        return agent_turn.t_start
    start = agent_turn.t_start if agent_turn.t_start is not None else 0
    end = agent_turn.t_end if agent_turn.t_end is not None else start + 60_000
    for seg_start, _ in agent_vad.segments:
        if start - 200 <= seg_start <= end + 200:
            return seg_start
    return agent_turn.t_start


async def evaluate_ttfa(ctx: MetricContext) -> MetricEvaluation:
    if not {CAPABILITY_CALLER_AUDIO_INGRESS, CAPABILITY_AGENT_AUDIO_EGRESS} <= ctx.capabilities:
        return not_measurable(ctx.spec.metric_key, "capability_missing")
    if ctx.stage0.caller_vad is None or ctx.stage0.agent_vad is None:
        return not_measurable(ctx.spec.metric_key, "audio_artifacts_unavailable")
    if not ctx.stage0.validation.alignment_ok:
        return not_measurable(ctx.spec.metric_key, "alignment_unreliable")

    latencies: list[float] = []
    early_start = 0
    for caller_turn, agent_turn in _paired_turns(ctx.stage0.turns):
        if caller_turn.t_end is None:
            continue
        caller_end = caller_turn.t_end
        if ctx.stage0.agent_vad.is_speech_ms(caller_end):
            early_start += 1
            continue
        first_audio = _agent_first_audio(agent_turn, ctx.stage0.agent_vad)
        if first_audio is None:
            continue
        latencies.append(max(0.0, float(first_audio - caller_end)))

    stats = _stats(latencies)
    if stats is None:
        return not_measurable(ctx.spec.metric_key, "no_eligible_turns")
    return MetricEvaluation(
        metric_key="ttfa",
        direction="lower_is_better",
        value=stats["p50"],
        confidence=0.9 if not ctx.stage0.validation.bleed_detected else 0.7,
        method="code",
        breakdown={**stats, "agent_early_start": early_start},
        caveats=list(ctx.stage0.caveats),
    )


async def evaluate_ttft(ctx: MetricContext) -> MetricEvaluation:
    if CAPABILITY_TARGET_TEXT_STREAM not in ctx.capabilities:
        return not_measurable(ctx.spec.metric_key, "capability_missing")
    text_first = ctx.signals.agent_text_first_ms()
    if text_first is None:
        return not_measurable(ctx.spec.metric_key, "no_agent_text_stream")
    pairs = _paired_turns(ctx.stage0.turns)
    if not pairs:
        return not_measurable(ctx.spec.metric_key, "no_caller_turn")
    caller_end = next((t.t_end for t in ctx.stage0.turns if t.speaker == "caller" and t.t_end), None)
    if caller_end is None:
        return not_measurable(ctx.spec.metric_key, "no_caller_end")
    latency = max(0.0, float(text_first - caller_end))
    return MetricEvaluation(
        metric_key="ttft",
        direction="lower_is_better",
        value=latency,
        confidence=0.8,
        method="code",
        breakdown={"value_ms": latency},
    )


@dataclass
class _Interruption:
    onset_ms: int
    turn: TurnRecord
    classification: str


async def _classify_interruption(ctx: MetricContext, turn: TurnRecord) -> tuple[str, object | None]:
    duration_s = (turn.duration_ms or 0) / 1000.0
    tokens = turn.text.split()
    token_count = len(tokens)
    normalized = [token.strip(".,!?;:").lower() for token in tokens]
    all_backchannel = bool(normalized) and all(token in BACKCHANNEL_LEXICON for token in normalized)
    if duration_s < 1.0 and token_count <= 3 and all_backchannel:
        return "backchannel", None
    if duration_s >= 2.0 or token_count >= 5:
        return "real_interruption", None

    probe = get_probe("bi.class.v1")
    answer = await ctx.runner.run_single(
        {
            "caller_utterance": turn.text,
            "preceding_agent_speech_tail": "",
            "duration_s": duration_s,
            "token_count": token_count,
        },
        probe.probe_id,
        probe.question(),
    )
    record = probe_record(probe.probe_id, answer, turn_ids=[turn.turn_id])
    value = answer.probabilities or {}
    if not value:
        label = "real_interruption" if float(answer.value or 0) >= 0.5 else "backchannel"
    else:
        label = max(value, key=value.get)
    return label, record


async def _interruptions(ctx: MetricContext) -> tuple[list[_Interruption], list, list[str]]:
    interruptions: list[_Interruption] = []
    probes = []
    caveats: list[str] = []
    if ctx.stage0.overlap is None or ctx.stage0.agent_vad is None:
        return interruptions, probes, caveats
    frame_ms = ctx.stage0.agent_vad.frame_ms
    for turn in ctx.stage0.turns:
        if turn.speaker != "caller" or turn.t_start is None:
            continue
        if not any(frame * frame_ms >= turn.t_start for frame in ctx.stage0.overlap.overlap_frames):
            continue
        label, record = await _classify_interruption(ctx, turn)
        if record is not None:
            probes.append(record)
        if label == "backchannel":
            continue
        if ctx.stage0.validation.bleed_detected:
            caveats.append("channel_bleed")
        interruptions.append(_Interruption(onset_ms=turn.t_start, turn=turn, classification=label))
    return interruptions, probes, caveats


def _yield_latency_ms(ctx: MetricContext, onset_ms: int) -> tuple[float | None, bool]:
    """First sustained agent silence after caller onset; ``(latency, censored)``."""
    settings = ctx.settings
    vad = ctx.stage0.agent_vad
    if vad is None:
        return None, False
    frame_ms = vad.frame_ms
    silence_needed = max(1, settings.yield_silence_ms // frame_ms)
    censor_ms = settings.bargein_censor_ms
    onset_frame = max(0, onset_ms // frame_ms)
    run = 0
    for index in range(onset_frame, len(vad.speech_mask)):
        if not vad.speech_mask[index]:
            run += 1
            if run >= silence_needed:
                silence_start = (index - silence_needed + 1) * frame_ms
                latency = float(silence_start - onset_ms)
                return latency, latency > censor_ms
        else:
            run = 0
        if (index - onset_frame) * frame_ms > censor_ms:
            break
    return float(censor_ms), True


async def evaluate_barge_in_latency(ctx: MetricContext) -> MetricEvaluation:
    if CAPABILITY_INTERRUPTIONS not in ctx.capabilities:
        return not_measurable(ctx.spec.metric_key, "capability_missing")
    interruptions, probes, caveats = await _interruptions(ctx)
    latencies: list[float] = []
    for interruption in interruptions:
        latency, _ = _yield_latency_ms(ctx, interruption.onset_ms)
        if latency is not None:
            latencies.append(latency)
    stats = _stats(latencies)
    if stats is None:
        return MetricEvaluation(
            metric_key="barge_in_latency",
            status="not_applicable",
            direction="lower_is_better",
            breakdown={"detail": "no_real_interruptions"},
            probes=probes,
        )
    return MetricEvaluation(
        metric_key="barge_in_latency",
        direction="lower_is_better",
        value=stats["p50"],
        confidence=0.85 if not caveats else 0.6,
        method="code+jev",
        breakdown=stats,
        probes=probes,
        caveats=caveats,
    )


async def evaluate_barge_in_success_rate(ctx: MetricContext) -> MetricEvaluation:
    if CAPABILITY_INTERRUPTIONS not in ctx.capabilities:
        return not_measurable(ctx.spec.metric_key, "capability_missing")
    settings = ctx.settings
    interruptions, probes, caveats = await _interruptions(ctx)
    if not interruptions:
        return MetricEvaluation(
            metric_key="barge_in_success_rate",
            status="not_applicable",
            direction="higher_is_better",
            breakdown={"detail": "no_real_interruptions"},
            probes=probes,
        )
    successes = 0
    for interruption in interruptions:
        latency, censored = _yield_latency_ms(ctx, interruption.onset_ms)
        if latency is not None and not censored and latency <= settings.t_yield_ms:
            successes += 1
    rate = successes / len(interruptions)
    return MetricEvaluation(
        metric_key="barge_in_success_rate",
        direction="higher_is_better",
        value=rate,
        normalized=rate * 100,
        confidence=0.85 if not caveats else 0.6,
        method="code+jev",
        breakdown={"successes": successes, "interruptions": len(interruptions), "t_yield_ms": settings.t_yield_ms},
        probes=probes,
        caveats=caveats,
    )


def _expected_language(policy: dict, caller_lang: str | None) -> str | None:
    mode = (policy or {}).get("mode", "mirror_caller")
    if mode == "mirror_caller":
        return caller_lang
    if isinstance(mode, str) and mode.startswith("fixed:"):
        return mode.split(":", 1)[1].split("[")[0]
    return caller_lang


async def evaluate_language_detection_accuracy(ctx: MetricContext) -> MetricEvaluation:
    ordered = sorted(
        [t for t in ctx.stage0.turns if t.text], key=lambda t: t.t_start or 0
    )
    evaluated = 0
    matches = 0
    probes = []
    for index, turn in enumerate(ordered):
        if turn.speaker != "caller":
            continue
        if len(turn.text.split()) < 3:
            continue
        caller_lang = analyze_text(turn.text).dominant
        agent_next = next(
            (t for t in ordered[index + 1 :] if t.speaker == "agent" and t.text), None
        )
        if agent_next is None:
            continue
        agent_lang = analyze_text(agent_next.text).dominant
        expected = _expected_language(ctx.language_policy, caller_lang)
        evaluated += 1
        if agent_lang and expected and (agent_lang == expected or agent_lang == "mixed_hinglish"):
            matches += 1

    if evaluated == 0:
        return MetricEvaluation(
            metric_key="language_detection_accuracy",
            status="not_applicable",
            direction="higher_is_better",
            breakdown={"detail": "no_content_turns"},
        )
    accuracy = matches / evaluated
    return MetricEvaluation(
        metric_key="language_detection_accuracy",
        direction="higher_is_better",
        value=accuracy,
        normalized=accuracy * 100,
        confidence=0.7,
        method="code+jev",
        breakdown={"matches": matches, "evaluated_turns": evaluated},
        probes=probes,
    )


__all__ = [
    "evaluate_barge_in_latency",
    "evaluate_barge_in_success_rate",
    "evaluate_language_detection_accuracy",
    "evaluate_ttfa",
    "evaluate_ttft",
]
