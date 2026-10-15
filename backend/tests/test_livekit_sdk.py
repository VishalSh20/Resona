"""LiveKit SDK integration surface (skipped when the SDK is absent).

These lock the real API surface the caller glue depends on, so a version bump
that breaks it fails loudly instead of at call time.
"""

from __future__ import annotations

import inspect

import pytest

pytest.importorskip("livekit.agents")
pytest.importorskip("livekit.plugins.sarvam")

from livekit import api, rtc  # noqa: E402
from livekit.agents import AgentSession  # noqa: E402

from voiceeval.runtime.connections import AudioChunk  # noqa: E402
from voiceeval.runtime.livekit.session import (  # noqa: E402
    build_agent_session,
    build_sarvam_stt,
    build_sarvam_tts,
)
from voiceeval.runtime.livekit.target_links.audio import (  # noqa: E402
    chunk_to_frame,
    frame_to_chunk,
)


def test_audio_frame_round_trip_with_real_sdk():
    chunk = AudioChunk(data=b"\x00" * 960, sample_rate=24_000, channels=1)
    frame = chunk_to_frame(chunk)
    assert isinstance(frame, rtc.AudioFrame)
    back = frame_to_chunk(frame)
    assert back.sample_rate == 24_000
    assert back.duration_ms == 20


async def test_agent_session_accepts_sarvam_and_interruption_control():
    session = build_agent_session(
        vad=object(), stt=build_sarvam_stt(api_key="x"), tts=build_sarvam_tts(api_key="x")
    )
    assert isinstance(session, AgentSession)
    params = inspect.signature(session.say).parameters
    assert "allow_interruptions" in params  # §8.3 requires per-speech control
    # AgentSession.start requires an Agent positional in 1.x.
    assert "agent" in inspect.signature(session.start).parameters


def test_livekit_management_requests_construct():
    assert api.CreateRoomRequest(name="r", empty_timeout=60, max_participants=3)
    assert api.CreateAgentDispatchRequest(agent_name="caller", room="r", metadata="{}")
    assert api.CreateSIPParticipantRequest(
        room_name="r",
        sip_trunk_id="trunk",
        sip_call_to="+10000000000",
        sip_number="+10000000001",
        participant_identity="sip-target",
        wait_until_answered=True,
    )
