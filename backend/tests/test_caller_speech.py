"""Speech planner, language segments and TTS fallback (§9)."""

from __future__ import annotations

import pytest

from voiceeval.domain.enums import Personality
from voiceeval.runtime.caller.language import LanguageController
from voiceeval.runtime.caller.persona import PersonaResolver
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.caller.speech_plan import SpeechPlanner
from voiceeval.runtime.connections import AudioChunk
from voiceeval.runtime.livekit.tts_fallback import FallbackTTSProvider
from voiceeval.runtime.providers.base import SynthesisRequest

_RESOLVER = PersonaResolver()


def _plan(persona_traits, text, **kwargs):
    planner = SpeechPlanner(_RESOLVER.resolve(persona_traits))
    return planner.plan(text, **kwargs)


def test_hesitant_persona_plans_intra_utterance_pauses():
    segments = _plan(
        [Personality.HESITANT],
        "Well, I think so, maybe, I am not sure.",
        rng=SeededRng("s1"),
    )
    assert any(s.kind == "pause" for s in segments)
    assert any(s.kind == "speech" for s in segments)


def test_concise_persona_has_no_planned_pauses():
    segments = _plan([Personality.CONCISE], "Yes, that is correct.")
    assert all(s.kind == "speech" for s in segments)


def test_filler_prefix_when_generation_is_slow():
    segments = _plan(
        [Personality.HESITANT], "Yes.", include_filler=True, rng=SeededRng("s2")
    )
    assert segments[0].kind == "filler"


def test_language_segments_without_code_switch_is_single():
    controller = LanguageController(primary="en-IN")
    assert controller.realize_segments("priority_absent") == [
        ("Okay, please continue.", "en-IN")
    ]


def test_language_segments_alternate_sentences():
    controller = LanguageController(
        primary="en-IN",
        secondary="hi-IN",
        code_switch=True,
        templates={"en-IN": {"present_problem": "Hello there. How are you?"}},
    )
    segments = controller.realize_segments("present_problem")
    assert segments[0] == ("Hello there.", "en-IN")
    assert segments[1] == ("How are you?", "hi-IN")


class _StubTTS:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    async def synthesize(self, request: SynthesisRequest):
        self.calls.append(request.text)
        yield AudioChunk(data=b"\x00\x00", sample_rate=16_000, duration_ms=1)


class _FailingTTS:
    name = "failing"

    async def synthesize(self, request: SynthesisRequest):
        raise RuntimeError("streaming blew up")
        yield  # pragma: no cover - makes this an async generator


async def _drain(provider, text="Hello world. Second sentence."):
    chunks = []
    async for chunk in provider.synthesize(SynthesisRequest(text=text)):
        chunks.append(chunk)
    return chunks


async def test_tts_fallback_uses_rest_provider_when_streaming_fails():
    rest = _StubTTS("rest")
    errors: list[tuple[str, Exception]] = []
    provider = FallbackTTSProvider(
        _FailingTTS(), rest=rest, on_error=lambda name, exc: errors.append((name, exc))
    )
    chunks = await _drain(provider)
    assert chunks
    # REST path sentence-chunks the text.
    assert rest.calls == ["Hello world.", "Second sentence."]
    assert errors and errors[0][0] == "failing"


async def test_tts_fallback_raises_when_all_providers_fail():
    provider = FallbackTTSProvider(_FailingTTS())
    with pytest.raises(RuntimeError):
        await _drain(provider)
