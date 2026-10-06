"""LLM provider abstraction and decision model.

Two seams power the evaluator-generation workflows (and any future GenAI
workflow): :class:`~voiceeval.llm.base.BaseGenerationModel` for semantic
generation and :class:`~voiceeval.llm.base.DecisionModel` for bounded,
typed decisions (Jev).
"""

from voiceeval.llm.base import (
    BaseGenerationModel,
    DecisionAnswer,
    DecisionModel,
    DecisionQuestion,
    GenerationModel,
    GenerationRequest,
    GenerationResponse,
    LLMError,
    StaticDecisionModel,
    StaticGenerationModel,
    StructuredOutputError,
)
from voiceeval.llm.jev import (
    JevDecisionModel,
    get_decision_model,
    set_decision_model,
)
from voiceeval.llm.providers import (
    AnthropicProvider,
    OpenAICompatibleProvider,
    get_generation_model,
    set_generation_model,
)

__all__ = [
    "AnthropicProvider",
    "BaseGenerationModel",
    "DecisionAnswer",
    "DecisionModel",
    "DecisionQuestion",
    "GenerationModel",
    "GenerationRequest",
    "GenerationResponse",
    "JevDecisionModel",
    "LLMError",
    "OpenAICompatibleProvider",
    "StaticDecisionModel",
    "StaticGenerationModel",
    "StructuredOutputError",
    "get_decision_model",
    "get_generation_model",
    "set_decision_model",
    "set_generation_model",
]
