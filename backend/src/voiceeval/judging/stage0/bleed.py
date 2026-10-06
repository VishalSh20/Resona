"""Cross-channel bleed detection (spec §2.2.6).

Each clean original must correlate with its own mixed channel and not with the
other speaker's channel. Significant cross-speaker energy raises a caveat that
lowers confidence on overlap/barge-in metrics rather than changing a score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from voiceeval.judging.stage0.alignment import envelope


@dataclass(frozen=True)
class BleedResult:
    bleed_detected: bool
    caller_own_corr: float
    caller_cross_corr: float
    agent_own_corr: float
    agent_cross_corr: float
    missing_channel: bool


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    length = min(x.size, y.size)
    if length < 2:
        return 0.0
    x = x[:length] - x[:length].mean()
    y = y[:length] - y[:length].mean()
    denom = float(np.sqrt((x**2).sum() * (y**2).sum()))
    if denom <= 0:
        return 0.0
    return float((x * y).sum() / denom)


def detect_bleed(
    caller_original: np.ndarray,
    agent_original: np.ndarray,
    mixed_left: np.ndarray,
    mixed_right: np.ndarray,
    sample_rate: int,
    *,
    bleed_tau: float = 0.25,
) -> BleedResult:
    caller_env = envelope(caller_original, sample_rate)
    agent_env = envelope(agent_original, sample_rate)
    left_env = envelope(mixed_left, sample_rate)
    right_env = envelope(mixed_right, sample_rate)

    caller_own = _corr(caller_env, left_env)
    caller_cross = _corr(caller_env, right_env)
    agent_own = _corr(agent_env, right_env)
    agent_cross = _corr(agent_env, left_env)

    missing_channel = (
        float(np.abs(left_env).max()) < 1e-6 or float(np.abs(right_env).max()) < 1e-6
    )
    bleed = (
        caller_cross > bleed_tau
        or agent_cross > bleed_tau
        or missing_channel
    )
    return BleedResult(
        bleed_detected=bool(bleed),
        caller_own_corr=caller_own,
        caller_cross_corr=caller_cross,
        agent_own_corr=agent_own,
        agent_cross_corr=agent_cross,
        missing_channel=missing_channel,
    )


__all__ = ["BleedResult", "detect_bleed"]
