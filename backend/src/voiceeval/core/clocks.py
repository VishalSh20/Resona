"""Explicit clock helpers.

The runtime deals with several distinct clock domains (wall clock, runner
monotonic, media/RTP). This module centralizes wall-clock/monotonic sources so
that call sites declare which clock they intend rather than reaching for
``time.time()`` ad hoc.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Wall-clock UTC timestamp for human-facing metadata."""
    return datetime.now(timezone.utc)


def monotonic_ms() -> int:
    """Monotonic clock in milliseconds for latency/ordering within a process."""
    return int(time.monotonic() * 1000)


def wall_clock_iso() -> str:
    return utc_now().isoformat()
