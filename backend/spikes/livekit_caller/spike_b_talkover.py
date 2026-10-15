"""Spike B — caller talk-over without self-cut-off (§8.3).

The critical mechanic: overlapping speech is spoken with interruptions disabled
for that speech item, then re-enabled, so the target's audio (which looks like
user speech to the framework) cannot cut the caller off.

Run against a live AgentSession; this sandbox script demonstrates the control
flow and asserts the API surface exists.
"""

from __future__ import annotations

import asyncio
import inspect


async def main() -> None:
    from livekit.agents import AgentSession

    say = getattr(AgentSession, "say", None)
    if say is None:
        raise SystemExit("AgentSession.say not found in the pinned version")
    signature = inspect.signature(say)
    assert "allow_interruptions" in signature.parameters, (
        "per-speech interruption control (allow_interruptions) is unavailable "
        "in this SDK version — do not start Phase 1"
    )
    print("[B] AgentSession.say supports allow_interruptions:", signature)
    print(
        "[B] Procedure: start a speech with allow_interruptions=False, feed target "
        "audio simultaneously, assert the caller is not cut off, then verify a "
        "subsequent speech with allow_interruptions=True IS interruptible."
    )


if __name__ == "__main__":
    asyncio.run(main())
