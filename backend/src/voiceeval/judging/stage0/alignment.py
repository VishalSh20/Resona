"""Cross-artifact alignment (spec §2.2.4).

The three tracks are expected to share one call clock. We estimate the offset of
each clean original against its mixed channel using normalized energy-envelope
cross-correlation, then flag ``alignment_conflict`` when the estimates disagree
beyond a calibrated tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FRAME_MS = 10


def envelope(samples: np.ndarray, sample_rate: int, frame_ms: int = FRAME_MS) -> np.ndarray:
    mono = np.asarray(samples, dtype=np.float32).reshape(-1)
    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    n_frames = mono.size // frame_len
    if n_frames == 0:
        return np.zeros(1, dtype=np.float32)
    trimmed = mono[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(trimmed**2, axis=1) + 1e-12)
    peak = float(rms.max())
    return rms / peak if peak > 0 else rms


def best_lag_frames(a: np.ndarray, b: np.ndarray, max_lag: int) -> tuple[int, float]:
    """Return the lag (frames) and correlation of ``a`` relative to ``b``.

    Positive lag means ``a`` is delayed relative to ``b``.
    """
    max_lag = max(0, min(max_lag, min(a.size, b.size) - 1))
    if max_lag == 0:
        return 0, _corr(a, b)
    best_lag, best_corr = 0, -np.inf
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            x, y = a[lag:], b[: b.size - lag]
        else:
            x, y = a[: a.size + lag], b[-lag:]
        if x.size < 2:
            continue
        corr = _corr(x, y)
        if corr > best_corr:
            best_lag, best_corr = lag, corr
    return best_lag, float(best_corr)


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2 or y.size < 2:
        return 0.0
    x = x - x.mean()
    y = y - y.mean()
    denom = float(np.sqrt((x**2).sum() * (y**2).sum()))
    if denom <= 0:
        return 0.0
    return float((x * y).sum() / denom)


@dataclass(frozen=True)
class AlignmentResult:
    caller_offset_ms: int
    agent_offset_ms: int
    drift_ms: int
    caller_corr: float
    agent_corr: float
    ok: bool
    within_tolerance: bool


def estimate_alignment(
    caller_original: np.ndarray,
    agent_original: np.ndarray,
    mixed_left: np.ndarray,
    mixed_right: np.ndarray,
    sample_rate: int,
    *,
    tolerance_ms: int,
    max_lag_ms: int = 2000,
) -> AlignmentResult:
    max_lag = max(1, max_lag_ms // FRAME_MS)
    caller_env = envelope(caller_original, sample_rate)
    agent_env = envelope(agent_original, sample_rate)
    left_env = envelope(mixed_left, sample_rate)
    right_env = envelope(mixed_right, sample_rate)

    caller_lag, caller_corr = best_lag_frames(caller_env, left_env, max_lag)
    agent_lag, agent_corr = best_lag_frames(agent_env, right_env, max_lag)

    caller_offset_ms = caller_lag * FRAME_MS
    agent_offset_ms = agent_lag * FRAME_MS
    drift_ms = abs(caller_offset_ms - agent_offset_ms)
    within = drift_ms <= tolerance_ms
    return AlignmentResult(
        caller_offset_ms=caller_offset_ms,
        agent_offset_ms=agent_offset_ms,
        drift_ms=drift_ms,
        caller_corr=caller_corr,
        agent_corr=agent_corr,
        ok=within,
        within_tolerance=within,
    )


__all__ = ["AlignmentResult", "best_lag_frames", "envelope", "estimate_alignment"]
