"""Voice activity detection (spec §2.2.2).

Silero VAD (ONNX) is used when a model is available; otherwise a deterministic
energy VAD keeps the pipeline runnable (CI, tests, missing model). Both produce
the same 10 ms-frame speech mask with a 300 ms hangover.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("voiceeval.judging.vad")

SILERO_SAMPLE_RATE = 16_000
SILERO_WINDOW = 512


@dataclass(frozen=True)
class VADResult:
    frame_ms: int
    speech_mask: tuple[bool, ...]
    segments: tuple[tuple[int, int], ...]
    source: str

    def is_speech_ms(self, t_ms: int) -> bool:
        index = int(t_ms // self.frame_ms)
        if 0 <= index < len(self.speech_mask):
            return self.speech_mask[index]
        return False

    def active_between(self, start_ms: int, end_ms: int) -> bool:
        start = max(0, int(start_ms // self.frame_ms))
        end = min(len(self.speech_mask), int(end_ms // self.frame_ms) + 1)
        return any(self.speech_mask[start:end])

    def onset_ms(self) -> int | None:
        return self.segments[0][0] if self.segments else None

    def end_ms(self) -> int | None:
        return self.segments[-1][1] if self.segments else None


def _segments_from_mask(mask: np.ndarray, frame_ms: int, hangover_frames: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, active in enumerate(mask):
        if active and start is None:
            start = index
        elif not active and start is not None:
            # Apply hangover: extend the end until the last active frame.
            segments.append((start * frame_ms, (index + hangover_frames) * frame_ms))
            start = None
    if start is not None:
        segments.append((start * frame_ms, (len(mask) + hangover_frames) * frame_ms))
    return segments


def energy_vad(
    samples: np.ndarray,
    sample_rate: int,
    *,
    frame_ms: int = 10,
    hangover_ms: int = 300,
) -> VADResult:
    mono = np.asarray(samples, dtype=np.float32).reshape(-1)
    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    n_frames = mono.size // frame_len
    if n_frames == 0:
        return VADResult(frame_ms, (), (), "energy")

    trimmed = mono[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(trimmed**2, axis=1) + 1e-12)
    noise_floor = float(np.percentile(rms, 20))
    peak = float(np.percentile(rms, 95))
    # Adaptive floor vs. the quietest frames, capped relative to the peak so a
    # mostly-speech capture is not mistaken for silence; a small absolute floor
    # keeps pure-silence input quiet.
    threshold = max(min(noise_floor * 2.5, peak * 0.3), 0.005)
    mask = rms > threshold
    hangover_frames = max(0, hangover_ms // frame_ms)
    segments = _segments_from_mask(mask, frame_ms, hangover_frames)
    return VADResult(
        frame_ms=frame_ms,
        speech_mask=tuple(bool(value) for value in mask.tolist()),
        segments=tuple(segments),
        source="energy",
    )


def _resample(mono: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return mono
    duration = mono.size / source_rate
    target_len = int(duration * target_rate)
    if target_len <= 0:
        return np.zeros(0, dtype=np.float32)
    source_times = np.linspace(0, duration, mono.size, endpoint=False)
    target_times = np.linspace(0, duration, target_len, endpoint=False)
    return np.interp(target_times, source_times, mono).astype(np.float32)


class SileroVAD:
    """Lazy ONNX wrapper. ``run`` returns ``None`` when unavailable."""

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or os.environ.get("SILERO_ONNX_PATH")
        self._session = None

    def _load(self):
        if self._session is not None:
            return self._session
        if not self._model_path or not os.path.exists(self._model_path):
            return None
        try:  # pragma: no cover - depends on optional model artifact
            import onnxruntime  # type: ignore

            self._session = onnxruntime.InferenceSession(
                self._model_path, providers=["CPUExecutionProvider"]
            )
        except Exception as exc:  # pragma: no cover
            logger.info("silero VAD unavailable: %s", exc)
            self._session = None
        return self._session

    def run(self, samples: np.ndarray, sample_rate: int, *, frame_ms: int, hangover_ms: int):
        session = self._load()
        if session is None:
            return None
        try:  # pragma: no cover - depends on optional model artifact
            mono = _resample(
                np.asarray(samples, dtype=np.float32).reshape(-1),
                sample_rate,
                SILERO_SAMPLE_RATE,
            )
            state = np.zeros((2, 1, 128), dtype=np.float32)
            sr = np.array(SILERO_SAMPLE_RATE, dtype=np.int64)
            probs: list[float] = []
            for start in range(0, mono.size - SILERO_WINDOW + 1, SILERO_WINDOW):
                window = mono[start : start + SILERO_WINDOW].reshape(1, -1)
                out = session.run(None, {"input": window, "state": state, "sr": sr})
                probs.append(float(out[0][0][0]))
                state = out[1]
        except Exception as exc:  # pragma: no cover
            logger.info("silero VAD inference failed, using energy fallback: %s", exc)
            return None

        if not probs:
            return None
        window_ms = int(SILERO_WINDOW * 1000 / SILERO_SAMPLE_RATE)
        frames_per = max(1, window_ms // frame_ms)
        expanded: list[bool] = []
        for prob in probs:
            expanded.extend([prob > 0.5] * frames_per)
        mask = np.array(expanded, dtype=bool)
        hangover_frames = max(0, hangover_ms // frame_ms)
        segments = _segments_from_mask(mask, frame_ms, hangover_frames)
        return VADResult(
            frame_ms=frame_ms,
            speech_mask=tuple(bool(value) for value in mask.tolist()),
            segments=tuple(segments),
            source="silero",
        )


def run_vad(
    samples: np.ndarray,
    sample_rate: int,
    *,
    frame_ms: int = 10,
    hangover_ms: int = 300,
    enable_silero: bool = True,
    silero: SileroVAD | None = None,
) -> VADResult:
    if enable_silero:
        detector = silero or SileroVAD()
        result = detector.run(samples, sample_rate, frame_ms=frame_ms, hangover_ms=hangover_ms)
        if result is not None:
            return result
    return energy_vad(samples, sample_rate, frame_ms=frame_ms, hangover_ms=hangover_ms)


__all__ = ["SileroVAD", "VADResult", "energy_vad", "run_vad"]
