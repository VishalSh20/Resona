"""Admission control for concurrent calls (§11).

The real bottleneck for 20 concurrent calls is usually *outside* LiveKit: a
target agent that supports few simultaneous calls, SIP trunk channel limits,
Sarvam concurrent streams and LLM rate limits. This limiter gates dispatch on
global and per-target concurrency before a room is created.

Process-local (matching the connection registry); a multi-process deployment
should back the counters with Redis.
"""

from __future__ import annotations

from threading import Lock

from voiceeval.core.config import get_settings
from voiceeval.core.errors import VoiceEvalError


class AdmissionError(VoiceEvalError):
    code = "CAPACITY_EXCEEDED"
    status_code = 429


class AdmissionController:
    def __init__(
        self,
        *,
        max_concurrent_calls: int = 20,
        max_concurrent_per_target: int = 1,
    ) -> None:
        self._max_calls = max(1, max_concurrent_calls)
        self._max_per_target = max(1, max_concurrent_per_target)
        self._lock = Lock()
        self._calls: dict[str, str] = {}  # attempt_id -> target_key

    @property
    def in_flight(self) -> int:
        with self._lock:
            return len(self._calls)

    def in_flight_for_target(self, target_key: str) -> int:
        with self._lock:
            return sum(1 for key in self._calls.values() if key == target_key)

    def acquire(self, *, attempt_id: str, target_key: str | None = None) -> None:
        """Reserve a slot or raise :class:`AdmissionError`. Idempotent per attempt."""
        key = target_key or "default"
        with self._lock:
            if attempt_id in self._calls:
                return
            if len(self._calls) >= self._max_calls:
                raise AdmissionError(
                    f"call concurrency limit reached ({self._max_calls})"
                )
            per_target = sum(1 for value in self._calls.values() if value == key)
            if per_target >= self._max_per_target:
                raise AdmissionError(
                    f"target '{key}' concurrency limit reached ({self._max_per_target})"
                )
            self._calls[attempt_id] = key

    def release(self, attempt_id: str) -> None:
        with self._lock:
            self._calls.pop(attempt_id, None)


_controller: AdmissionController | None = None


def get_admission_controller() -> AdmissionController:
    global _controller
    if _controller is None:
        settings = get_settings()
        _controller = AdmissionController(
            max_concurrent_calls=settings.livekit_max_concurrent_calls,
            max_concurrent_per_target=settings.livekit_max_concurrent_per_target,
        )
    return _controller


def set_admission_controller(controller: AdmissionController | None) -> None:
    global _controller
    _controller = controller


__all__ = [
    "AdmissionController",
    "AdmissionError",
    "get_admission_controller",
    "set_admission_controller",
]
