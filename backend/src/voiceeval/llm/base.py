"""Provider-agnostic generation and decision contracts.

The evaluator-generation workflows never talk to a vendor SDK directly. They
depend on two thin protocols:

* :class:`GenerationModel` — understands semantics and produces text or typed
  (Pydantic) structured output. OpenAI/Anthropic/OpenRouter implement it.
* :class:`DecisionModel` — makes bounded, typed decisions (Jev via OpenRouter).

Keeping these seams separate from the workflows lets tests inject deterministic
implementations and lets other workflows reuse the same providers.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from voiceeval.core.errors import VoiceEvalError

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class LLMError(VoiceEvalError):
    code = "LLM_ERROR"
    status_code = 502


class StructuredOutputError(LLMError):
    code = "LLM_STRUCTURED_OUTPUT_ERROR"


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    user: str
    model: str | None = None
    temperature: float = 0.0
    json_mode: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResponse:
    text: str
    model: str
    raw: dict[str, Any] | None = None


@runtime_checkable
class GenerationModel(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResponse: ...


@dataclass(frozen=True)
class DecisionQuestion:
    type: Literal["noul", "choice", "score"]
    instructions: str
    # choice -> {"option": "description"}; score -> ["level0", "level1", ...];
    # noul -> {"true": "...", "false": "..."}
    criteria: dict[str, str] | list[str]


@dataclass(frozen=True)
class DecisionAnswer:
    type: str
    # noul -> probability of yes (float); choice -> selected option (str);
    # score -> probability-weighted position (float)
    value: Any
    confidence: float | None = None
    probabilities: dict[str, float] | None = None


@dataclass(frozen=True)
class DecisionResponse:
    """A full Decisions-API response, including model/cost provenance.

    The judge records ``model`` (the resolved snapshot id, e.g.
    ``typesafe/jev-1.13-20260917``) so a change in the underlying decision model
    can be detected and trigger the regression suite (spec §4.1).
    """

    answers: dict[str, DecisionAnswer]
    model: str | None = None
    cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: dict[str, Any] | None = None


@runtime_checkable
class DecisionModel(Protocol):
    async def decide(
        self, *, state: dict[str, Any], questions: dict[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]: ...


def _schema_instruction(model_cls: type[BaseModel], *, many: bool = False) -> str:
    """Render a JSON-schema instruction for the given model.

    We ask for a single JSON object matching the schema (or ``{"items": [...]}``
    when ``many`` is set), keeping the contract explicit but avoiding a fragile
    free-text parse.
    """
    schema = model_cls.model_json_schema()
    if many:
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array", "items": schema}},
            "required": ["items"],
        }
    return (
        "Respond with a single JSON object and nothing else. The JSON must "
        "conform exactly to this JSON Schema:\n"
        + json.dumps(schema)
        + "\nDo not include markdown fences, prose, or trailing commas."
    )


def _parse_structured(
    model_cls: type[_ModelT], text: str, *, many: bool = False
) -> _ModelT | list[_ModelT]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"model returned invalid JSON: {exc}") from exc

    if many:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict) and "items" in payload:
            items = payload["items"]
        else:
            raise StructuredOutputError("expected an array or {\"items\": [...]}")
        if not isinstance(items, list):
            raise StructuredOutputError("expected a JSON array of items")
        return [model_cls.model_validate(item) for item in items]

    return model_cls.model_validate(payload)


class BaseGenerationModel(ABC):
    """Shared base: subclasses implement ``generate``; structured output is free."""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError

    async def structured(
        self,
        model_cls: type[_ModelT],
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> _ModelT:
        user_prompt = f"{user}\n\n{_schema_instruction(model_cls)}"
        response = await self.generate(
            GenerationRequest(
                system=system,
                user=user_prompt,
                model=model,
                temperature=temperature,
                json_mode=True,
            )
        )
        return _parse_structured(model_cls, response.text)

    async def structured_many(
        self,
        model_cls: type[_ModelT],
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> list[_ModelT]:
        user_prompt = f"{user}\n\n{_schema_instruction(model_cls, many=True)}"
        response = await self.generate(
            GenerationRequest(
                system=system,
                user=user_prompt,
                model=model,
                temperature=temperature,
                json_mode=True,
            )
        )
        result = _parse_structured(model_cls, response.text, many=True)
        assert isinstance(result, list)
        return result


class StaticGenerationModel(BaseGenerationModel):
    """Deterministic generation model for tests and offline runs.

    ``responses`` may be a string, a list consumed in order, or a callable
    ``(GenerationRequest) -> str``. Callables may also return a pre-serialized
    JSON object (dict/list) which is rendered with ``json.dumps``.
    """

    def __init__(
        self,
        responses: str | list[str] | Any = None,
    ) -> None:
        self._responses = responses
        self._index = 0
        self.requests: list[GenerationRequest] = []

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.requests.append(request)
        source = self._responses
        if callable(source):
            text = source(request)
        elif isinstance(source, list):
            if not source:
                raise LLMError("StaticGenerationModel has no queued response")
            text = source[min(self._index, len(source) - 1)]
            self._index += 1
        elif isinstance(source, str):
            text = source
        else:
            raise LLMError("StaticGenerationModel has no response configured")

        if isinstance(text, (dict, list)):
            text = json.dumps(text)
        return GenerationResponse(text=str(text), model=request.model or "static")


class StaticDecisionModel:
    """Deterministic decision model for tests.

    ``answers`` maps a question key to a :class:`DecisionAnswer`. A callable may
    be provided instead and will be invoked with ``(key, DecisionQuestion)``.
    """

    def __init__(
        self,
        answers: dict[str, DecisionAnswer]
        | Any = None,
    ) -> None:
        self._answers = answers or {}
        self.calls: list[tuple[dict[str, Any], dict[str, DecisionQuestion]]] = []

    async def decide(
        self, *, state: dict[str, Any], questions: dict[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        self.calls.append((state, questions))
        source = self._answers
        if callable(source):
            return {key: source(key, q) for key, q in questions.items()}
        missing = [key for key in questions if key not in source]
        if missing:
            raise LLMError(f"StaticDecisionModel has no answer for {missing}")
        return {key: source[key] for key in questions}


__all__ = [
    "BaseGenerationModel",
    "DecisionAnswer",
    "DecisionModel",
    "DecisionQuestion",
    "DecisionResponse",
    "GenerationModel",
    "GenerationRequest",
    "GenerationResponse",
    "LLMError",
    "StaticDecisionModel",
    "StaticGenerationModel",
    "StructuredOutputError",
]
