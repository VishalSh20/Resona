"""20-call soak harness for the LiveKit caller (§11, §14.4).

Runs N simulated attempts through the admission controller to validate the
concurrency caps and detect slot leaks. It does not require a LiveKit server —
real calls are exercised separately in CI-lite transport smoke runs.

Usage: ``python scripts/soak_livekit.py [concurrency]``
"""

from __future__ import annotations

import asyncio
import sys

from voiceeval.core.config import get_settings
from voiceeval.runtime.livekit.admission import AdmissionController

DEFAULT_CONCURRENCY = 20


async def _attempt(controller: AdmissionController, index: int, peak: dict[str, int]) -> bool:
    attempt_id = f"soak_{index}"
    try:
        # Distinct target keys so the soak exercises the global cap, not the
        # per-target cap.
        controller.acquire(attempt_id=attempt_id, target_key=f"soak-target-{index}")
    except Exception:
        return False
    peak["value"] = max(peak["value"], controller.in_flight)
    await asyncio.sleep(0.01)
    controller.release(attempt_id)
    return True


async def run(concurrency: int) -> int:
    settings = get_settings()
    controller = AdmissionController(
        max_concurrent_calls=settings.livekit_max_concurrent_calls,
        max_concurrent_per_target=min(
            settings.livekit_max_concurrent_per_target, concurrency
        ),
    )
    peak = {"value": 0}
    results = await asyncio.gather(
        *(_attempt(controller, i, peak) for i in range(concurrency))
    )
    admitted = sum(1 for ok in results if ok)
    cap = settings.livekit_max_concurrent_calls
    print(
        f"soak: requested={concurrency} admitted={admitted} peak_in_flight={peak['value']} "
        f"cap={cap} leaked={controller.in_flight}"
    )
    assert controller.in_flight == 0, "admission slots leaked"
    assert peak["value"] <= cap, "peak exceeded the configured cap"
    return 0


def main() -> int:
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONCURRENCY
    return asyncio.run(run(concurrency))


if __name__ == "__main__":
    raise SystemExit(main())
