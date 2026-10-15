"""Target-protocol control signalling.

The generic websocket target only advances its script when the caller signals the
end of a caller turn (``{"type": "caller.turn.end"}``). Pipecat gives us that
boundary as the end of our own synthesized speech, so this processor forwards one
control message downstream to the output transport per spoken turn.
"""

from __future__ import annotations

from pipecat.frames.frames import Frame, OutputTransportMessageFrame, TTSStoppedFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

CALLER_TURN_END = "caller.turn.end"


class CallerTurnEndProcessor(FrameProcessor):
    """Emit ``caller.turn.end`` after each of the caller's spoken turns."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSStoppedFrame):
            await self.push_frame(
                OutputTransportMessageFrame(message={"type": CALLER_TURN_END}),
                direction,
            )
        await self.push_frame(frame, direction)


__all__ = ["CALLER_TURN_END", "CallerTurnEndProcessor"]
