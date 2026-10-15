"""LiveKit Agents job entrypoint for one call attempt (§4.1).

Dispatch creates the room and issues an explicit named-agent dispatch carrying
only ``attempt_id`` + a short-lived runner token. This job then: connects the
runner telemetry WebSocket and registers, fetches the scenario/facts/manifest
from the backend, connects the TargetLink, runs the caller conversation while
recording both audio directions, and uploads the recordings (per-speaker mono +
a stereo call recording) to object storage with their metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from voiceeval.core.config import get_settings
from voiceeval.runtime.caller.rng import SeededRng
from voiceeval.runtime.connections import CloseReason
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.livekit.connection_setup import prepare_target_link
from voiceeval.runtime.livekit.conversation import LinkConversationRunner
from voiceeval.runtime.livekit.media import persist_media_records
from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.livekit.runtime import LiveKitCallerRuntime
from voiceeval.runtime.loader import load_attempt_context
from voiceeval.runtime.providers.base import TTSProvider
from voiceeval.runtime.providers.deterministic import DeterministicTTS
from voiceeval.runtime.providers.sarvam import (
    SarvamBulbulStreamingTTS,
    SarvamConnection,
)
from voiceeval.runtime.runner import RUNNER_VERSION
from voiceeval.runtime.telemetry import RunnerWebSocketClient

logger = logging.getLogger("voiceeval.livekit.job")


#: Heavy modules the job imports on its critical path. Importing them here (per
#: process, at startup) keeps the first call from stalling on import/first use —
#: which otherwise delays turns and can exceed the job's exit grace.
_WARM_MODULES = (
    "boto3",
    "botocore.client",
    "asyncpg",
    "sarvamai",
    "sarvamai.text_to_speech_streaming.client",
    "sarvamai.speech_to_text.client",
    "voiceeval.storage.s3",
    "voiceeval.runtime.providers.sarvam",
    "voiceeval.runtime.livekit.target_links.bridge",
    "voiceeval.runtime.livekit.target_links.room",
    "voiceeval.runtime.livekit.target_links.sip",
    "voiceeval.runtime.livekit.target_links.whip",
)


def _warm_modules() -> None:
    import importlib

    for name in _WARM_MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - optional modules
            logger.debug("warm import skipped for %s: %s", name, exc)


def prewarm(proc: Any) -> None:
    """Warm everything a job touches, once per process (§5, §11).

    Simulations run back-to-back, so the goal is to make the first turn and the
    final upload as warm as possible: VAD model, provider SDKs, the DB driver,
    and the object-store client (TLS) are all paid for here rather than mid-call.
    Best-effort — any failure only costs the warmth, never the run.
    """
    try:
        from voiceeval.runtime.livekit.session import load_silero_vad

        proc.userdata["vad"] = load_silero_vad()
    except Exception as exc:  # pragma: no cover - optional at link-boundary mode
        logger.warning("prewarm skipped: %s", exc)

    _warm_modules()

    # Object store: build the client now so the first upload does not pay
    # botocore's import + TLS handshake on the job's critical path.
    try:
        from voiceeval.storage import get_object_store

        warm = getattr(get_object_store(), "warm", None)
        if warm is not None:
            warm()
    except Exception as exc:  # pragma: no cover - optional at link-boundary mode
        logger.warning("object-store prewarm skipped: %s", exc)

    # DB driver/engine: creating the engine imports asyncpg up front.
    try:
        from voiceeval.db.session import get_engine

        get_engine()
    except Exception as exc:  # pragma: no cover - depends on DB availability
        logger.warning("db prewarm skipped: %s", exc)

    # TTS provider choice for this deployment (constructs nothing heavy, but
    # resolves settings and imports the Sarvam path).
    try:
        _build_tts(16_000)
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning("tts prewarm skipped: %s", exc)


def _build_tts(sample_rate: int, *, speaker: str = "shubh") -> TTSProvider:
    settings = get_settings()
    if settings.sarvam_api_key:
        connection = SarvamConnection(api_key=settings.sarvam_api_key, speaker=speaker)
        # One socket per call: per-utterance connects cost ~1 s of dead air.
        return SarvamBulbulStreamingTTS(connection)
    return DeterministicTTS(sample_rate=sample_rate)


def _build_asr(bundle: Any, recording: Any) -> Any | None:
    """A factory for our own streaming ASR over the target's audio, or None.

    When present, the caller listens to the target's *audio* (transcribed by us)
    instead of trusting the provider's captions.
    """
    settings = get_settings()
    if not settings.sarvam_api_key:
        return None
    from voiceeval.runtime.providers.sarvam import (
        SarvamConnection,
        SarvamStreamingASR,
    )

    # The target may speak anything — Hindi, English, Hinglish — regardless of
    # the caller's scripted language. Auto-detect per utterance ("unknown");
    # pinning to the scenario language turns code-mixed speech into garbage,
    # and garbage text is what drives the clarify loop.
    language = "unknown"

    def factory() -> SarvamStreamingASR:
        return SarvamStreamingASR(
            SarvamConnection(api_key=settings.sarvam_api_key),
            language=language,
            sample_rate=recording.sample_rate,
        )

    return factory


async def _emit_lifecycle(
    telemetry: RunnerWebSocketClient, builder: CanonicalEventBuilder, status: str
) -> None:
    """Report a connecting/running transition (the LiveKit job has no hook)."""
    await telemetry.send_event(
        builder.build(
            EventType.ATTEMPT_LIFECYCLE,
            source=EventSource.RUNTIME.value,
            payload={"status": status},
        )
    )


async def _emit_terminal(
    telemetry: RunnerWebSocketClient, builder: CanonicalEventBuilder, reason: str
) -> None:
    from voiceeval.runtime.livekit.failure import terminal_payload

    await telemetry.send_event(
        builder.build(
            EventType.ATTEMPT_TERMINAL,
            source=EventSource.RUNTIME.value,
            payload=terminal_payload(reason),
        )
    )


async def _start_connection_session(
    factory: Any,
    attempt_id: str,
    prepared: Any,
    target_revision: Any,
) -> str | None:
    """Record a runtime connection session, if the target has a stored endpoint."""
    if not prepared.endpoint_id or target_revision is None:
        return None
    from voiceeval.db.repositories import IntegrationRepository

    try:
        async with factory() as session:
            connection = await IntegrationRepository(
                session
            ).create_connection_session(
                endpoint_id=prepared.endpoint_id,
                revision_id=target_revision.id,
                status="connecting",
            )
            await session.commit()
            return connection.id
    except Exception as exc:  # pragma: no cover - persistence must not break the call
        logger.warning("attempt %s: connection session not recorded: %s", attempt_id, exc)
        return None


async def _finish_connection_session(
    factory: Any,
    connection_id: str | None,
    *,
    status: str,
    provider_session_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if not connection_id:
        return
    from voiceeval.db.repositories import IntegrationRepository

    try:
        async with factory() as session:
            await IntegrationRepository(session).update_connection_session(
                connection_id,
                status=status,
                provider_session_id=provider_session_id,
                error_message=error_message,
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - persistence must not break the call
        logger.warning("connection session %s not updated: %s", connection_id, exc)


async def _join_presence_participant(room_name: str, attempt_id: str) -> Any:
    """Join the attempt room as a standard (non-agent) participant.

    Provider agents that call ``ctx.wait_for_participant()`` ignore agent-kind
    participants, so an agent-only room never reaches their ``session.start``.
    A standard participant makes the room look like a normal user call.
    """
    from livekit import api, rtc  # type: ignore

    settings = get_settings()
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(f"caller-{attempt_id}")
        .with_name("caller")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    await room.connect(settings.livekit_url, token, rtc.RoomOptions(auto_subscribe=True))
    logger.info("joined presence participant caller-%s to room %s", attempt_id, room_name)
    return room


async def entrypoint(ctx: Any) -> None:
    settings = get_settings()
    await ctx.connect()

    metadata = json.loads(getattr(ctx.job, "metadata", "") or "{}")
    attempt_id = metadata.get("attempt_id")
    presence_room: Any | None = None
    if os.environ.get("CALLER_PRESENCE_PARTICIPANT", "1") == "1":
        try:
            presence_room = await _join_presence_participant(
                getattr(ctx.room, "name", ""), attempt_id or "unknown"
            )
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            logger.warning("presence participant join failed: %s", exc)
    telemetry_url = metadata.get("telemetry_url")
    runner_id = metadata.get("runner_id") or f"runner-{attempt_id}"
    if not attempt_id or not telemetry_url:
        raise ValueError("job metadata must carry attempt_id and telemetry_url")

    telemetry = RunnerWebSocketClient(
        url=telemetry_url,
        attempt_id=attempt_id,
        runner_id=runner_id,
        runner_version=RUNNER_VERSION,
    )
    await telemetry.connect()
    builder = CanonicalEventBuilder(attempt_id)

    from voiceeval.db.session import get_session_factory

    factory = get_session_factory()

    # 1. Load scenario + facts + persona + target link from the frozen manifest,
    # then resolve the link (minting a per-call endpoint when the provider needs one).
    async with factory() as session:
        bundle = await load_attempt_context(session, attempt_id)
        prepared = await prepare_target_link(
            session,
            bundle.target_link,
            bundle.manifest,
            bundle.target_revision,
            sample_rate=16_000,
        )
    logger.info(
        "attempt %s: objective=%r facts=%d actions=%d",
        attempt_id,
        (bundle.scenario.objective or "")[:80],
        len(bundle.scenario.facts),
        len(bundle.scenario.allowed_actions),
    )

    # 2. Connect the target link (the audio boundary we own).
    from voiceeval.runtime.livekit.target_links.registry import get_target_link_registry

    link = get_target_link_registry().create(
        prepared.transport,
        endpoint_config=prepared.endpoint_config,
        room=presence_room or getattr(ctx, "room", None),
        sample_rate=16_000,
    )
    connection_id = await _start_connection_session(
        factory, attempt_id, prepared, bundle.target_revision
    )
    await _emit_lifecycle(telemetry, builder, "connecting")
    try:
        await link.connect()
    except Exception as exc:
        await _finish_connection_session(
            factory, connection_id, status="failed", error_message=str(exc)
        )
        # Terminalize so a failed connect is not left hanging at ``starting``.
        await _emit_terminal(telemetry, builder, "CONNECTION_FAILURE")
        await telemetry.close()
        raise
    await _finish_connection_session(
        factory,
        connection_id,
        status="connected",
        provider_session_id=prepared.provider_session_id,
    )
    await _emit_lifecycle(telemetry, builder, "running")

    # 3. Run the conversation, recording caller + agent audio in-process.
    recording = AttemptRecording(sample_rate=link.capabilities().sample_rate)
    pipeline_runtime = LiveKitCallerRuntime(
        bundle.scenario, bundle.persona, rng=SeededRng(bundle.seed)
    )

    async def _emit(event) -> None:
        await telemetry.send_event(event)

    runner = LinkConversationRunner(
        attempt_id=attempt_id,
        link=link,
        pipeline=pipeline_runtime.pipeline,
        builder=builder,
        recording=recording,
        tts=_build_tts(recording.sample_rate, speaker=bundle.persona.speaker),
        emit=_emit,
        asr_factory=_build_asr(bundle, recording),
    )

    # The conversation loop no longer emits the terminal itself: we must upload
    # the recordings FIRST, because the terminal makes the control plane delete
    # the room, which shuts this job down and would cancel the upload.
    reason: str | None = None
    try:
        reason = await runner.run()
        logger.info("attempt %s ended: %s", attempt_id, reason)
    except asyncio.CancelledError:
        reason = "CANCELLED"
    except Exception:
        logger.exception("attempt %s crashed", attempt_id)
        reason = "JOB_CRASH"
    reason = reason or "TARGET_HUNG_UP"

    # 4. Seal the recordings and upload them with their metadata. Bounded: a slow
    # or flaky object store must not stall the job past its shutdown grace (the
    # terminal is still emitted below, so the attempt never hangs).
    try:
        records = recording.finalize()
        async with factory() as media_session:
            stored = await asyncio.wait_for(
                persist_media_records(media_session, attempt_id, records),
                timeout=60,
            )
        logger.info("attempt %s uploaded %d media artifacts", attempt_id, stored)
    except Exception:  # pragma: no cover - depends on object storage
        logger.exception("media persistence failed for %s", attempt_id)

    # 5. Report the (classified) terminal — this is what lets the control plane
    # delete the room and free the slot.
    try:
        await _emit_terminal(telemetry, builder, reason)
    except Exception:  # pragma: no cover - best-effort
        logger.debug("terminal emit failed for %s", attempt_id)

    # 6. Teardown the connection and telemetry.
    try:
        await link.close(CloseReason.RUNNER_SHUTDOWN)
    except Exception:  # pragma: no cover - teardown races
        logger.debug("link close failed for %s", attempt_id)
    if presence_room is not None:
        try:
            await presence_room.disconnect()
        except Exception:  # pragma: no cover - best-effort
            logger.debug("presence room disconnect failed for %s", attempt_id)
    await _finish_connection_session(factory, connection_id, status="terminated")
    try:
        await telemetry.close()
    except Exception:  # pragma: no cover - best-effort flush
        logger.debug("telemetry close failed for %s", attempt_id)
    # The control plane deletes the room on the terminal path; the job just
    # disconnects its own participants.


def main() -> None:
    from livekit.agents import WorkerOptions, cli  # type: ignore

    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="voiceeval-caller",
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            # Simulations run back-to-back: keep a pool of pre-warmed processes so
            # a new call never waits on a cold import, and give the (now heavier)
            # prewarm and the end-of-call upload room to finish.
            num_idle_processes=4,
            initialize_process_timeout=30.0,
            shutdown_process_timeout=60.0,
        )
    )


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()


__all__ = ["entrypoint", "main", "prewarm"]
