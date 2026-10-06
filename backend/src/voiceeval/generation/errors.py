"""Generation-workflow error types."""

from __future__ import annotations

from voiceeval.core.errors import VoiceEvalError


class GenerationError(VoiceEvalError):
    code = "GENERATION_ERROR"
    status_code = 502


class GenerationValidationError(VoiceEvalError):
    code = "GENERATION_VALIDATION_ERROR"
    status_code = 422
