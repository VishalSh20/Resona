"""WebSocket route definitions.

Two distinct channels, deliberately separated from the audio path:
  * ``/internal/v1/attempts/{attempt_id}/stream`` — runner control/telemetry.
  * ``/api/v1/runs/{run_id}/live`` — UI observation of a run.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from voiceeval.realtime.live_ws import run_live
from voiceeval.realtime.runner_ws import runner_stream

internal_router = APIRouter(prefix="/internal/v1", tags=["internal"])

live_router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@internal_router.websocket("/attempts/{attempt_id}/stream")
async def runner_stream_route(
    websocket: WebSocket, attempt_id: str, token: str | None = None
) -> None:
    await runner_stream(websocket, attempt_id, token)


@live_router.websocket("/{run_id}/live")
async def run_live_route(
    websocket: WebSocket, run_id: str, token: str | None = None
) -> None:
    await run_live(websocket, run_id, token)
