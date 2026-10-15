"""FloorTracker and InterruptionPlanner behavior (§8.1–§8.3)."""

from __future__ import annotations

from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.floor import FloorEventKind, FloorState, FloorTracker
from voiceeval.runtime.caller.interruption import (
    InterruptionContext,
    InterruptionPlanner,
    OverlapMode,
)
from voiceeval.runtime.caller.persona import PersonaResolver

_RESOLVER = PersonaResolver()


def _planner(*traits: Personality) -> InterruptionPlanner:
    return InterruptionPlanner(_RESOLVER.resolve(list(traits)))


def test_floor_target_speaking_and_silence():
    tracker = FloorTracker(clock=lambda: 0)
    tracker.note_target_vad(True, at_ms=0)
    assert tracker.state == FloorState.TARGET_SPEAKING
    tracker.note_target_vad(False, at_ms=500)
    assert tracker.state == FloorState.TARGET_PAUSED  # within pause window, EOT low
    tracker.note_end_of_turn_probability(0.9)
    tracker.note_target_vad(False, at_ms=600)
    assert tracker.state == FloorState.SILENCE


def test_floor_overlap_events():
    tracker = FloorTracker(clock=lambda: 0)
    tracker.note_target_vad(True, at_ms=0)
    events = tracker.note_caller_playout(True, at_ms=100)
    assert tracker.state == FloorState.OVERLAP
    assert any(e.kind == FloorEventKind.OVERLAP_START for e in events)
    events = tracker.note_caller_playout(False, at_ms=300)
    assert tracker.state == FloorState.TARGET_SPEAKING
    assert any(e.kind == FloorEventKind.OVERLAP_END for e in events)


def test_floor_yield_when_target_speaks_after_caller():
    tracker = FloorTracker(clock=lambda: 0)
    tracker.note_caller_playout(True, at_ms=0)
    assert tracker.state == FloorState.CALLER_SPEAKING
    events = tracker.note_target_vad(True, at_ms=200)
    assert tracker.state == FloorState.OVERLAP
    # target-only speech after both stops then target resumes
    tracker.note_caller_playout(False, at_ms=250)
    tracker.note_target_vad(True, at_ms=300)


def test_floor_non_speech_resets_turn():
    tracker = FloorTracker(clock=lambda: 0)
    tracker.note_target_vad(True, at_ms=0)
    tracker.note_target_transcript("hello there you")
    tracker.note_non_speech(True)
    assert tracker.state == FloorState.SILENCE
    assert tracker.turn.words == 0


def test_false_interruption_detection():
    planner = _planner(Personality.COOPERATIVE)
    assert planner.is_false_interruption(target_speech_ms=100, target_words=1) is True
    assert planner.is_false_interruption(target_speech_ms=1200, target_words=5) is False


def test_supportive_yields_faster_than_interruptor():
    supportive = _planner(Personality.SUPPORTIVE)
    interruptor = _planner(Personality.INTERRUPTOR)
    args = {"target_speech_ms": 500, "target_words": 2}
    assert supportive.should_yield(**args) is True
    assert interruptor.should_yield(**args) is False


def test_barge_in_trigger_for_impatient_monologue():
    planner = _planner(Personality.IMPATIENT)
    decision = planner.should_barge_in(
        InterruptionContext(target_turn_ms=20_000, target_words=40)
    )
    assert decision.attempt is True
    assert decision.trigger == "monologue_impatience"
    assert decision.mode == OverlapMode.COMPETITIVE


def test_scripted_trigger_always_fires():
    planner = _planner(Personality.COOPERATIVE)
    decision = planner.should_barge_in(
        InterruptionContext(target_turn_ms=100, scripted_trigger="during_readback")
    )
    assert decision.attempt is True
    assert decision.trigger == "during_readback"


def test_early_answer_requires_high_end_of_turn_and_interruptor():
    planner = _planner(Personality.INTERRUPTOR)
    decision = planner.should_barge_in(
        InterruptionContext(
            target_turn_ms=1000, question_complete=True, end_of_turn_probability=0.9
        )
    )
    assert decision.attempt is True
    assert decision.trigger == "early_answer"
    assert decision.mode == OverlapMode.COOPERATIVE


def test_no_barge_in_for_cooperative_caller():
    planner = _planner(Personality.COOPERATIVE)
    assert planner.should_barge_in(
        InterruptionContext(target_turn_ms=1000, target_words=5)
    ).attempt is False
