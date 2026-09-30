"""Runner dispatch.

A physical attempt is executed by a disposable runner process. The dispatcher is
the seam between the control plane (which decides an attempt should run) and the
runner (which executes it). The default implementation spawns
``python -m voiceeval.runtime`` as an isolated process; the runner authenticates
with a short-lived attempt-scoped token.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Protocol, runtime_checkable

from voiceeval.auth.jwt import create_runner_token
from voiceeval.core.config import get_settings
from voiceeval.runtime.runner import RUNNER_VERSION
from voiceeval.runtime.telemetry import build_stream_url

logger = logging.getLogger("voiceeval.runner.dispatch")


@runtime_checkable
class RunnerDispatcher(Protocol):
    async def dispatch(self, attempt_id: str) -> None: ...


def runner_id_for(attempt_id: str) -> str:
    return f"runner-{attempt_id}"


class SubprocessRunnerDispatcher:
    """Spawn the runner as an isolated process (the production v1 path)."""

    def __init__(self, *, backend_url: str | None = None, python: str | None = None) -> None:
        self._backend_url = backend_url or get_settings().runner_backend_url
        self._python = python or sys.executable

    async def dispatch(self, attempt_id: str) -> None:
        runner_id = runner_id_for(attempt_id)
        token = create_runner_token(runner_id, attempt_id)
        url = build_stream_url(self._backend_url, attempt_id, token)
        command = [
            self._python,
            "-m",
            "voiceeval.runtime",
            "--attempt-id",
            attempt_id,
            "--telemetry-url",
            url,
            "--runner-id",
            runner_id,
            "--runner-version",
            RUNNER_VERSION,
        ]
        logger.info("dispatching runner process for attempt %s", attempt_id)
        await asyncio.create_subprocess_exec(*command)


class InlineRunnerDispatcher:
    """Run the runner in-process (fake/local execution and tests).

    Uses a telemetry sink that feeds the backend ingestion path directly, so an
    inline run produces the same event log and terminal outcome as a dispatched
    runner without a separate process.
    """

    async def dispatch(self, attempt_id: str) -> None:
        from voiceeval.db.session import get_session_factory
        from voiceeval.realtime.local_telemetry import LocalTelemetrySink
        from voiceeval.runtime.loader import build_runner_for_attempt

        factory = get_session_factory()
        async with factory() as session:
            sink = LocalTelemetrySink(session, attempt_id=attempt_id)
            runner = await build_runner_for_attempt(
                session, attempt_id, telemetry=sink, runner_id=runner_id_for(attempt_id)
            )
            await runner.run()
            # The terminal event and its materialized objects must be durable;
            # the dispatched path commits inside the runner's telemetry, so the
            # inline path commits here.
            await session.commit()


class LiveKitDispatcher:
    """Dispatch a LiveKit Agents caller job for the attempt (§4.1).

    Creates the room, issues an explicit named-agent dispatch, and hands the job
    only ``attempt_id`` + a short-lived runner token via job metadata — never
    configuration. The room is always deleted on the terminal path (see
    ``voiceeval.realtime.runner_ws``).
    """

    def __init__(self, *, backend_url: str | None = None) -> None:
        self._backend_url = backend_url or get_settings().runner_backend_url

    async def dispatch(self, attempt_id: str) -> None:
        from voiceeval.runtime.livekit.rooms import (
            LiveKitRoomManager,
            room_name_for_attempt,
        )

        # Resolve the target agent name from the frozen manifest so the room is
        # dispatched to the correct provider agent (not the caller worker).
        target_agent_name = await self._resolve_target_agent_name(attempt_id)
        if not target_agent_name:
            raise ValueError(f"could not resolve target agent name for attempt {attempt_id}")

        runner_id = runner_id_for(attempt_id)
        token = create_runner_token(runner_id, attempt_id)
        telemetry_url = build_stream_url(self._backend_url, attempt_id, token)
        room_name = room_name_for_attempt(attempt_id)
        metadata = json.dumps(
            {
                "attempt_id": attempt_id,
                "runner_id": runner_id,
                "runner_token": token,
                "telemetry_url": telemetry_url,
            }
        )
        manager = LiveKitRoomManager()
        await manager.create_room(room_name)
        # Dispatch the provider agent under test, then dispatch our caller worker
        # so it joins the same room and runs the caller persona.
        target_dispatch_id = await manager.dispatch_agent(
            room_name, agent_name=target_agent_name, metadata=metadata
        )
        caller_agent_name = "voiceeval-caller"
        caller_dispatch_id = await manager.dispatch_agent(
            room_name, agent_name=caller_agent_name, metadata=metadata
        )
        logger.info(
            "dispatched LiveKit caller for attempt %s (room=%s target_dispatch=%s caller_dispatch=%s target_agent=%s caller_agent=%s)",
            attempt_id,
            room_name,
            target_dispatch_id,
            caller_dispatch_id,
            target_agent_name,
            caller_agent_name,
        )

    async def _resolve_target_agent_name(self, attempt_id: str) -> str | None:
        """Best-effort target agent external id for dispatching the provider agent."""
        try:
            from voiceeval.db.models import domain
            from voiceeval.db.models import runtime as runtime_models
            from voiceeval.db.repositories import CallAttemptRepository
            from voiceeval.db.session import get_session_factory

            async with get_session_factory()() as session:
                attempt = await CallAttemptRepository(session).get_attempt(attempt_id)
                call_run = await session.get(runtime_models.CallRun, attempt.call_run_id)
                if call_run is None:
                    return None
                run = await session.get(domain.Run, call_run.run_id)
                if run is None or not run.target_revision_id:
                    return None
                target_revision = await session.get(
                    domain.AgentTargetRevision, run.target_revision_id
                )
                if target_revision is None:
                    return None
                target = await session.get(domain.AgentTarget, target_revision.agent_target_id)
                return target.external_agent_id if target else None
        except Exception:
            return None

    async def _resolve_target_key(self, attempt_id: str) -> str | None:
        """Best-effort target revision id for per-target concurrency gating."""
        try:
            from voiceeval.db.models import domain
            from voiceeval.db.models import runtime as runtime_models
            from voiceeval.db.repositories import CallAttemptRepository
            from voiceeval.db.session import get_session_factory

            async with get_session_factory()() as session:
                attempt = await CallAttemptRepository(session).get_attempt(attempt_id)
                call_run = await session.get(runtime_models.CallRun, attempt.call_run_id)
                if call_run is None:
                    return None
                run = await session.get(domain.Run, call_run.run_id)
                return run.target_revision_id if run else None
        except Exception:
            return None


_dispatcher: RunnerDispatcher | None = None


def get_dispatcher() -> RunnerDispatcher:
    global _dispatcher
    if _dispatcher is None:
        mode = get_settings().runner_dispatch_mode
        if mode == "inline":
            _dispatcher = InlineRunnerDispatcher()
        elif mode == "livekit":
            _dispatcher = LiveKitDispatcher()
        else:
            _dispatcher = SubprocessRunnerDispatcher()
    return _dispatcher


def set_dispatcher(dispatcher: RunnerDispatcher | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher
