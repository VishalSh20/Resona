"""Run progress projection for live-observation events.

Shared by the simulation handler and the execution orchestrator so both publish
the same ``run.progress`` shape without one importing the other.
"""

from __future__ import annotations

from voiceeval.domain.enums import CallRunStatus


def run_progress_payload(run_id: str, call_runs: list) -> dict:
    counts = {status.value: 0 for status in CallRunStatus}
    for call_run in call_runs:
        counts[call_run.status] = counts.get(call_run.status, 0) + 1
    return {
        "run_id": run_id,
        "total": len(call_runs),
        "queued": counts.get(CallRunStatus.QUEUED.value, 0),
        "running": counts.get(CallRunStatus.RUNNING.value, 0),
        "completed": counts.get(CallRunStatus.COMPLETED.value, 0),
        "infrastructure_failed": counts.get(
            CallRunStatus.INFRASTRUCTURE_FAILED.value, 0
        ),
        "cancelled": counts.get(CallRunStatus.CANCELLED.value, 0),
    }


__all__ = ["run_progress_payload"]
