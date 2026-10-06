"""Stage 0 orchestration: load, validate, align (spec §2.2).

Produces the canonical two-speaker timeline that every downstream metric reads:
validated media, caller/agent VAD, overlap, alignment, bleed, the turn table and
the language timeline. Missing or invalid media is reported, never substituted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voiceeval.core.config import Settings, get_settings
from voiceeval.judging.resolver import MediaBundle
from voiceeval.judging.schemas import MediaValidation
from voiceeval.judging.stage0.alignment import AlignmentResult, estimate_alignment
from voiceeval.judging.stage0.bleed import BleedResult, detect_bleed
from voiceeval.judging.stage0.language import LanguageTimeline, build_language_timeline
from voiceeval.judging.stage0.overlap import OverlapResult, compute_overlap
from voiceeval.judging.stage0.turns import TurnRecord, build_turns
from voiceeval.judging.stage0.vad import VADResult, SileroVAD, run_vad
from voiceeval.metrics.signals import AttemptSignals


@dataclass
class Stage0Result:
    attempt_id: str
    validation: MediaValidation
    caller_vad: VADResult | None = None
    agent_vad: VADResult | None = None
    overlap: OverlapResult | None = None
    alignment: AlignmentResult | None = None
    bleed: BleedResult | None = None
    turns: list[TurnRecord] = field(default_factory=list)
    language: LanguageTimeline | None = None
    caveats: list[str] = field(default_factory=list)

    @property
    def integrity_ok(self) -> bool:
        return self.validation.integrity_ok

    @property
    def alignment_conflict(self) -> bool:
        return bool(self.alignment is not None and not self.alignment.within_tolerance)

    def turn_by_id(self, turn_id: int | str) -> TurnRecord | None:
        for turn in self.turns:
            if turn.turn_id == turn_id:
                return turn
        return None

    def caller_text(self) -> str:
        return "\n".join(turn.text for turn in self.turns if turn.speaker == "caller")

    def agent_text(self) -> str:
        return "\n".join(turn.text for turn in self.turns if turn.speaker == "agent")


class Stage0Runner:
    def __init__(self, *, settings: Settings | None = None, silero: SileroVAD | None = None) -> None:
        self._settings = settings or get_settings()
        self._silero = silero

    def run(self, bundle: MediaBundle, signals: AttemptSignals) -> Stage0Result:
        settings = self._settings
        caveats: list[str] = []

        caller = bundle.caller_original
        agent = bundle.agent_original
        mixed = bundle.mixed

        integrity_ok = bundle.complete and all(
            media.integrity.ok for media in bundle.media.values()
        )
        for media in bundle.media.values():
            for error in media.integrity.errors:
                caveats.append(f"{media.role}: {error}")
            for warning in media.integrity.warnings:
                caveats.append(f"{media.role}: {warning}")

        caller_vad = self._vad(caller, settings)
        agent_vad = self._vad(agent, settings)
        mixed_left_vad = None
        mixed_right_vad = None
        if mixed is not None and mixed.wav is not None and mixed.wav.channels >= 2:
            mixed_left_vad = run_vad(
                mixed.wav.channel(0),
                mixed.wav.sample_rate,
                frame_ms=settings.vad_frame_ms,
                hangover_ms=settings.vad_hangover_ms,
                enable_silero=settings.silero_vad_enabled,
                silero=self._silero,
            )
            mixed_right_vad = run_vad(
                mixed.wav.channel(1),
                mixed.wav.sample_rate,
                frame_ms=settings.vad_frame_ms,
                hangover_ms=settings.vad_hangover_ms,
                enable_silero=settings.silero_vad_enabled,
                silero=self._silero,
            )

        overlap: OverlapResult | None = None
        if caller_vad is not None and agent_vad is not None:
            overlap = compute_overlap(
                caller_vad,
                agent_vad,
                mixed_caller_vad=mixed_left_vad,
                mixed_agent_vad=mixed_right_vad,
            )

        alignment: AlignmentResult | None = None
        bleed: BleedResult | None = None
        if (
            caller is not None
            and agent is not None
            and mixed is not None
            and caller.wav is not None
            and agent.wav is not None
            and mixed.wav is not None
            and mixed.wav.channels >= 2
        ):
            alignment = estimate_alignment(
                caller.wav.mono(),
                agent.wav.mono(),
                mixed.wav.channel(0),
                mixed.wav.channel(1),
                mixed.wav.sample_rate,
                tolerance_ms=settings.alignment_tolerance_ms,
            )
            if not alignment.within_tolerance:
                caveats.append("alignment_conflict")
            bleed = detect_bleed(
                caller.wav.mono(),
                agent.wav.mono(),
                mixed.wav.channel(0),
                mixed.wav.channel(1),
                mixed.wav.sample_rate,
                bleed_tau=settings.bleed_tau,
            )
            if bleed.bleed_detected:
                caveats.append("channel_bleed")

        turns = build_turns(
            signals,
            overlap_frames=overlap.overlap_frames if overlap else (),
            frame_ms=settings.vad_frame_ms,
        )
        language = build_language_timeline(
            signals.caller_reference_texts(),
            signals.observed_agent_texts(),
        )

        validation = MediaValidation(
            integrity_ok=integrity_ok,
            alignment_ok=bool(alignment.within_tolerance) if alignment else False,
            caller_offset_ms=alignment.caller_offset_ms if alignment else None,
            agent_offset_ms=alignment.agent_offset_ms if alignment else None,
            drift_ms=alignment.drift_ms if alignment else None,
            bleed_detected=bool(bleed.bleed_detected) if bleed else False,
            caveats=caveats,
        )
        return Stage0Result(
            attempt_id=bundle.attempt_id,
            validation=validation,
            caller_vad=caller_vad,
            agent_vad=agent_vad,
            overlap=overlap,
            alignment=alignment,
            bleed=bleed,
            turns=turns,
            language=language,
            caveats=caveats,
        )

    def _vad(self, media, settings) -> VADResult | None:
        if media is None or media.wav is None:
            return None
        return run_vad(
            media.wav.mono(),
            media.wav.sample_rate,
            frame_ms=settings.vad_frame_ms,
            hangover_ms=settings.vad_hangover_ms,
            enable_silero=settings.silero_vad_enabled,
            silero=self._silero,
        )


__all__ = ["Stage0Result", "Stage0Runner"]
