"""Live plan WebSocket for UI observation.

Subscribes to the plan's Redis Pub/Sub channel and forwards state-change
envelopes to the client. This channel is strictly observational — it is never
part of the audio path.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from voiceeval.core.errors import VoiceEvalError
from voiceeval.realtime.pubsub import get_pubsub, plan_events_channel
from voiceeval.realtime.runner_auth import authenticate_user

logger = logging.getLogger("voiceeval.realtime")

WS_POLICY_VIOLATION = 1008


async def run_live(websocket: WebSocket, run_id: str, token: str | None = None) -> None:
    try:
        authenticate_user(token)
    except VoiceEvalError as exc:
        await websocket.close(code=WS_POLICY_VIOLATION, reason=exc.code)
        return

    await websocket.accept()
    pubsub = get_pubsub()
    channel = plan_events_channel(run_id)

    async def forward() -> None:
        async for message in pubsub.subscribe(channel):
            await websocket.send_json(message)

    async def wait_disconnect() -> None:
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            return

    forward_task = asyncio.create_task(forward())
    disconnect_task = asyncio.create_task(wait_disconnect())
    done, pending = await asyncio.wait(
        {forward_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            logger.warning("live plan stream error: %s", exc)


# Deprecated v0.3 name; the channel is run-scoped now.
plan_live = run_live
