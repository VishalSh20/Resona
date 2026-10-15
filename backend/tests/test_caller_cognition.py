"""Cognition layer: turn analysis, realize/validate, decision pipeline (§5, §6)."""

from __future__ import annotations

from voiceeval.domain.enums import Personality
from voiceeval.llm.base import StaticGenerationModel
from voiceeval.runtime.caller.analyzer import TargetAnalyzer
from voiceeval.runtime.caller.pipeline import CallerDecisionPipeline
from voiceeval.runtime.caller.persona import PersonaResolver
from voiceeval.runtime.caller.realizer import OutputValidator, Realizer
from voiceeval.runtime.caller.turn_analyzer import TurnAnalyzer, TurnKind

_RESOLVER = PersonaResolver()


def test_turn_analyzer_common_rules():
    analyzer = TurnAnalyzer()
    assert analyzer.analyze("Could you confirm your date of birth?").kind == TurnKind.CONFIRMATION_REQUEST
    assert analyzer.analyze("Please hold while I transfer you.").kind == TurnKind.HOLD_TRANSFER_CLOSING
    assert analyzer.analyze("As an AI I cannot access that.").kind == TurnKind.DISCLAIMER
    assert analyzer.analyze("Sorry, that was my mistake.").kind == TurnKind.ERROR_APOLOGY
    assert analyzer.analyze("How can I help you today?").kind == TurnKind.QUESTION
    assert analyzer.analyze("Can I have your account number?").kind == TurnKind.FACT_REQUEST


def test_turn_analyzer_detects_repeat_and_monologue():
    analyzer = TurnAnalyzer(monologue_words=10)
    first = "Please provide the last four digits of your card"
    repeat = analyzer.analyze("Please provide the last four digits of your card", previous_text=first)
    assert repeat.kind == TurnKind.REPEAT and repeat.is_repeat
    long_text = " ".join(["word"] * 12)
    assert analyzer.analyze(long_text).kind == TurnKind.MONOLOGUE


async def test_analyzer_falls_back_to_llm_for_ambiguous_text():
    model = StaticGenerationModel('{"kind": "question", "fact_key": null}')
    analyzer = TargetAnalyzer(model=model)
    reading = await analyzer.analyze("hmm okay sure")
    assert reading.kind == TurnKind.QUESTION


async def test_analyzer_uses_rules_without_model():
    analyzer = TargetAnalyzer()
    reading = await analyzer.analyze("Could you confirm the address?")
    assert reading.kind == TurnKind.CONFIRMATION_REQUEST


def test_output_validator_rules():
    validator = OutputValidator(max_chars=40, forbidden_values=("AC-1234",), hostility_ceiling=0.2)
    assert validator.validate("Sure, one moment please.").ok
    assert validator.validate("x" * 50).reason == "too_long"
    assert validator.validate("As an AI, I cannot.").reason == "breaks_character"
    assert validator.validate("Your id is AC-1234").reason == "forbidden_fact"
    assert validator.validate("this is shit").reason == "hostility_ceiling"


async def test_realizer_uses_model_output():
    model = StaticGenerationModel("Sure, my account ID is AC-1234.")
    realizer = Realizer(model=model)
    text = await realizer.realize("provide_information", persona=_RESOLVER.resolve([]))
    assert text == "Sure, my account ID is AC-1234."


async def test_realizer_falls_back_when_validator_rejects():
    model = StaticGenerationModel("As an AI I cannot help with that.")
    realizer = Realizer(model=model)
    text = await realizer.realize(
        "clarify", persona=_RESOLVER.resolve([]), fallback=lambda: "Sorry, could you repeat that?"
    )
    assert text == "Sorry, could you repeat that?"


async def test_pipeline_reaches_natural_success(scenario):
    persona = _RESOLVER.resolve([Personality.COOPERATIVE])
    pipeline = CallerDecisionPipeline(scenario, persona)

    first = await pipeline.decide("Hi, how can I help?")
    assert first.action == "present_problem"
    assert first.terminal is False

    satisfied = ["authentication_complete", "objective_fulfilled"]
    second = await pipeline.decide("All done!", assertions=satisfied)
    assert second.action == "acknowledge_resolution"

    third = await pipeline.decide("You're welcome.", assertions=satisfied)
    assert third.terminal is True
    assert third.terminal_reason == "NATURAL_SUCCESS"
    assert third.record["action"] == "end_call"


def test_pipeline_barge_in_uses_persona(scenario):
    persona = _RESOLVER.resolve([Personality.INTERRUPTOR])
    pipeline = CallerDecisionPipeline(scenario, persona)
    decision = pipeline.decide_barge_in(
        target_turn_ms=1000, question_complete=True, end_of_turn_probability=0.9
    )
    assert decision.attempt is True
    assert decision.trigger == "early_answer"


async def test_pipeline_answers_questions_directly(scenario):
    model = StaticGenerationModel("About four or five drinks a day.")
    pipeline = CallerDecisionPipeline(
        scenario, _RESOLVER.resolve([]), realizer=Realizer(model=model)
    )
    await pipeline.decide("Hi, how can I help you?")
    first = await pipeline.decide("How much do you drink?")
    assert first.action == "provide_information"  # volunteers facts once
    second = await pipeline.decide("How much exactly, per day?")
    assert second.action == "answer"  # a question never gets a canned clarify
    assert second.text == "About four or five drinks a day."


async def test_pipeline_pushes_back_then_hangs_up_on_abuse(scenario):
    model = StaticGenerationModel("That is really not okay.")
    pipeline = CallerDecisionPipeline(
        scenario, _RESOLVER.resolve([]), realizer=Realizer(model=model)
    )
    await pipeline.decide("Hi, how can I help you?")
    first = await pipeline.decide("You are stupid and useless.")
    assert first.action == "push_back"
    assert first.terminal is False
    assert first.text == "That is really not okay."
    second = await pipeline.decide("Shut up, you moron.")
    assert second.terminal is True
    assert second.terminal_reason == "TARGET_ABUSE"
    # The goodbye is realized with the upset emotional context — never the
    # polite "Thanks for your help" template.
    assert second.text == "That is really not okay."


async def test_pipeline_terminal_text_is_realized_not_templated(scenario):
    model = StaticGenerationModel("Alright, guess this is going nowhere. Bye.")
    pipeline = CallerDecisionPipeline(
        scenario, _RESOLVER.resolve([]), realizer=Realizer(model=model)
    )
    step = await pipeline.decide("Hi, how can I help you?")
    # Force a terminal: mark required assertions satisfied twice (ack then end).
    satisfied = ["authentication_complete", "objective_fulfilled"]
    await pipeline.decide("All done!", assertions=satisfied)
    last = await pipeline.decide("You're welcome.", assertions=satisfied)
    assert last.terminal is True
    assert last.terminal_reason == "NATURAL_SUCCESS"
    assert last.text == "Alright, guess this is going nowhere. Bye."
