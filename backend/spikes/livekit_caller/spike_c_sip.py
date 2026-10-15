"""Spike C — one outbound SIP call (§4.3).

Dispatch the caller first, dial second. Requires a self-hosted LiveKit with an
outbound trunk. Run: ``python spike_c_sip.py``.
"""

from __future__ import annotations

import asyncio
import os


async def main() -> None:
    from livekit import api

    required = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_SIP_OUTBOUND_TRUNK_ID",
        "LIVEKIT_SIP_FROM_NUMBER",
        "SPIKE_TO_NUMBER",
    ]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")

    client = api.SIPServiceClient(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    participant = await client.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name="spike-sip",
            sip_trunk_id=os.environ["LIVEKIT_SIP_OUTBOUND_TRUNK_ID"],
            sip_call_to=os.environ["SPIKE_TO_NUMBER"],
            sip_number=os.environ["LIVEKIT_SIP_FROM_NUMBER"],
            participant_identity="sip-target",
            wait_until_answered=True,
        )
    )
    print("[C] dialed:", getattr(participant, "participant_id", participant))
    print(
        "[C] TODO confirm: call status/status-code mapping (busy/no_answer/declined/"
        "unreachable/trunk-auth); non-speech (ringback/hold/IVR) handling."
    )


if __name__ == "__main__":
    asyncio.run(main())
