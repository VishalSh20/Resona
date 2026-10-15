"""LiveKit terminal classification + lifecycle wiring."""

from __future__ import annotations

from voiceeval.runtime.events import CanonicalEventBuilder, EventType
from voiceeval.runtime.livekit.conversation import LinkConversationRunner
from voiceeval.runtime.livekit.failure import terminal_payload
from voiceeval.realtime.runner_ws import _LIFECYCLE_STATUS
from voiceeval.domain.enums import AttemptStatus


def test_terminal_payload_success_is_completed_and_eligible():
    payload = terminal_payload("NATURAL_SUCCESS")
    assert payload["terminal_status"] == "completed"
    assert payload["failure_class"] is None
    assert payload["eligible"] is True


def test_terminal_payload_cancelled():
    payload = terminal_payload("CANCELLED")
    assert payload["terminal_status"] == "cancelled"
    assert payload["failure_class"] == "cancelled"
    assert payload["eligible"] is False


def test_terminal_payload_unknown_defaults_to_infrastructure_failure():
    payload = terminal_payload("something_unmapped")
    assert payload["terminal_status"] == "failed"
    assert payload["failure_class"] == "infrastructure"
    assert payload["eligible"] is False


def test_terminal_payload_target_outcome_is_completed_eligible():
    payload = terminal_payload("TARGET_HUNG_UP")
    assert payload["terminal_status"] == "completed"
    assert payload["eligible"] is True


def test_lifecycle_status_map_covers_connecting_and_running():
    assert _LIFECYCLE_STATUS["connecting"] == AttemptStatus.CONNECTING
    assert _LIFECYCLE_STATUS["running"] == AttemptStatus.RUNNING


async def test_conversation_emit_terminal_classifies_reason():
    emitted = []

    async def capture(event):
        emitted.append(event)

    runner = LinkConversationRunner(
        attempt_id="att_1",
        link=None,
        pipeline=None,
        builder=CanonicalEventBuilder("att_1"),
        recording=None,
        tts=None,
        emit=capture,
    )

    await runner.emit_terminal("NATURAL_SUCCESS")

    assert len(emitted) == 1
    event = emitted[0]
    assert event.type == EventType.ATTEMPT_TERMINAL.value
    assert event.payload["terminal_status"] == "completed"
    assert event.payload["eligible"] is True
