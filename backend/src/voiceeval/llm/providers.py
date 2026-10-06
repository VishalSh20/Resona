"""Concrete generation providers and the model factory.

OpenAI and OpenRouter share an OpenAI-compatible chat-completions surface;
Anthropic has its own messages API. Each provider is deliberately thin — the
workflows depend only on :class:`~voiceeval.llm.base.BaseGenerationModel`, and
provider branching is isolated in :func:`get_generation_model`.
"""

from __future__ import annotations

from typing import Any

import httpx

from voiceeval.core.config import get_settings
from voiceeval.core.errors import DependencyUnavailableError
from voiceeval.llm.base import BaseGenerationModel, GenerationRequest, GenerationResponse, LLMError

_DEFAULT_TIMEOUT_S = 60.0


class OpenAICompatibleProvider(BaseGenerationModel):
    """OpenAI chat-completions provider (also used for OpenRouter)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        missing_key_message: str = "the generation model API key is not configured",
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._default_model = default_model or "gpt-4o-mini"
        self._timeout_s = timeout_s
        self._missing_key_message = missing_key_message

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not self._api_key:
            raise DependencyUnavailableError(self._missing_key_message)

        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"generation request failed: {exc}") from exc

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected generation response shape") from exc
        return GenerationResponse(text=text, model=payload["model"], raw=body)


class AnthropicProvider(BaseGenerationModel):
    """Anthropic Messages API provider."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self._default_model = default_model or "claude-3-5-haiku-latest"
        self._timeout_s = timeout_s

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not self._api_key:
            raise DependencyUnavailableError(
                "ANTHROPIC_API_KEY is not configured; generation cannot run"
            )

        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "max_tokens": 4096,
            "temperature": request.temperature,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(
                    f"{self._base_url}/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"generation request failed: {exc}") from exc

        try:
            text = "".join(
                block.get("text", "")
                for block in body["content"]
                if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMError("unexpected Anthropic response shape") from exc
        return GenerationResponse(text=text, model=payload["model"], raw=body)


_generation_model: BaseGenerationModel | None = None


def get_generation_model() -> BaseGenerationModel:
    """Return the process-wide generation model (configured by ``llm_provider``)."""
    global _generation_model
    if _generation_model is None:
        settings = get_settings()
        provider = settings.llm_provider
        if provider == "anthropic":
            _generation_model = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                default_model=settings.anthropic_model,
            )
        elif provider == "openrouter":
            _generation_model = OpenAICompatibleProvider(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                default_model=settings.openrouter_model,
                missing_key_message="OPENROUTER_API_KEY is not configured",
            )
        else:
            _generation_model = OpenAICompatibleProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                default_model=settings.openai_model,
                missing_key_message="OPENAI_API_KEY is not configured",
            )
    return _generation_model


def set_generation_model(model: BaseGenerationModel | None) -> None:
    global _generation_model
    _generation_model = model


__all__ = [
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "get_generation_model",
    "set_generation_model",
]
