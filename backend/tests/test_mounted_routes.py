"""The browser live WS and results read surfaces are mounted."""

from __future__ import annotations

from voiceeval.main import app
from voiceeval.realtime.routes import live_router
from voiceeval.schemas.results import JudgeExecutionRead


def test_live_run_websocket_is_mounted():
    paths = {getattr(route, "path", None) for route in live_router.routes}
    assert "/api/v1/runs/{run_id}/live" in paths


def test_results_and_blob_paths_are_registered():
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/runs/{run_id}/call-runs",
        "/api/v1/call-runs/{call_run_id}/attempts",
        "/api/v1/call-attempts/{attempt_id}",
        "/api/v1/call-attempts/{attempt_id}/media",
        "/api/v1/metric-results/{metric_result_id}",
        "/api/v1/judge-executions/{judge_execution_id}",
        "/api/v1/media/{media_artifact_id}/url",
        "/api/v1/media/blob",
    ):
        assert path in paths, f"{path} is not mounted"


def test_judge_execution_read_carries_the_result_document():
    payload = JudgeExecutionRead.model_validate(
        {
            "id": "judge_1",
            "call_run_id": "callrun_1",
            "call_attempt_id": "attempt_1",
            "status": "completed",
            "rubric_version": "2026.10-v1.1",
            "evidence_coverage": 0.93,
            "needs_human_review": False,
            "alignment_conflict": False,
            "latency_ms": 8421,
            "parsed_output": {
                "run_id": "run_1",
                "rubric_version": "2026.10-v1.1",
                "metrics": [
                    {
                        "metric_key": "context_retention",
                        "status": "ok",
                        "value": 3,
                        "findings": [
                            {
                                "severity": "major",
                                "type": "re_ask",
                                "turn_ids": [14, 22],
                                "t_start_ms": 61200,
                                "t_end_ms": 64000,
                            }
                        ],
                    }
                ],
            },
        }
    )
    assert payload.needs_human_review is False
    assert payload.parsed_output is not None
    assert payload.parsed_output["metrics"][0]["findings"][0]["t_start_ms"] == 61200
