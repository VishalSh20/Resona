"""Tests for the provider-agnostic LLM abstraction."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from voiceeval.llm import (
    DecisionAnswer,
    DecisionQuestion,
    GenerationRequest,
    StaticDecisionModel,
    StaticGenerationModel,
    StructuredOutputError,
)


class Foo(BaseModel):
    name: str
    value: int


async def test_static_generation_model_consumes_queue():
    model = StaticGenerationModel(["one", "two"])
    first = await model.generate(GenerationRequest(system="s", user="u"))
    second = await model.generate(GenerationRequest(system="s", user="u"))
    assert first.text == "one"
    assert second.text == "two"
    assert len(model.requests) == 2


async def test_structured_parses_json_object():
    model = StaticGenerationModel('{"name": "x", "value": 3}')
    foo = await model.structured(Foo, system="s", user="u")
    assert foo == Foo(name="x", value=3)


async def test_structured_many_parses_items():
    model = StaticGenerationModel(
        '{"items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}'
    )
    items = await model.structured_many(Foo, system="s", user="u")
    assert items == [Foo(name="a", value=1), Foo(name="b", value=2)]


async def test_structured_many_parses_bare_array():
    model = StaticGenerationModel('[{"name": "a", "value": 1}]')
    items = await model.structured_many(Foo, system="s", user="u")
    assert items == [Foo(name="a", value=1)]


async def test_structured_invalid_json_raises():
    model = StaticGenerationModel("not json")
    with pytest.raises(StructuredOutputError):
        await model.structured(Foo, system="s", user="u")


async def test_static_decision_model():
    model = StaticDecisionModel({"ok": DecisionAnswer(type="noul", value=0.9)})
    answers = await model.decide(
        state={"x": 1},
        questions={
            "ok": DecisionQuestion(
                type="noul",
                instructions="is it ok?",
                criteria={"true": "yes", "false": "no"},
            )
        },
    )
    assert answers["ok"].value == 0.9
