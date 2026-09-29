"""Consistent API error model.

All domain/API errors derive from :class:`VoiceEvalError` and carry a stable
machine-readable ``code`` plus a human-readable ``message``. The global
exception handler renders them into a single envelope shape.
"""

from __future__ import annotations


class VoiceEvalError(Exception):
    """Base class for all application errors surfaced to the API."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def envelope(self, request_id: str | None) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id,
            }
        }


class ResourceNotFoundError(VoiceEvalError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class ValidationError(VoiceEvalError):
    code = "VALIDATION_ERROR"
    status_code = 400


class ConflictError(VoiceEvalError):
    code = "CONFLICT"
    status_code = 409


class InvalidStateTransitionError(VoiceEvalError):
    code = "INVALID_STATE_TRANSITION"
    status_code = 409


class ImmutableResourceError(VoiceEvalError):
    code = "IMMUTABLE_RESOURCE"
    status_code = 409


class AuthenticationError(VoiceEvalError):
    code = "UNAUTHENTICATED"
    status_code = 401


class AuthorizationError(VoiceEvalError):
    code = "FORBIDDEN"
    status_code = 403


class DependencyUnavailableError(VoiceEvalError):
    code = "DEPENDENCY_UNAVAILABLE"
    status_code = 503


class ConnectionFailedError(VoiceEvalError):
    """A target/transport connection failed during call execution."""

    code = "CONNECTION_FAILED"
    status_code = 502
