"""Spike A — Sarvam bilingual STT/TTS in AgentSession (§9.3).

Run: ``python spike_a_sarvam.py``. Requires ``SARVAM_API_KEY`` and the LiveKit
plugins installed. This is a sandbox probe; it is not imported by the app.
"""

from __future__ import annotations

import asyncio
import os


async def main() -> None:
    from livekit.plugins import sarvam

    if not os.environ.get("SARVAM_API_KEY"):
        raise SystemExit("SARVAM_API_KEY is required")

    for sample_rate in (24_000, 8_000):
        tts = sarvam.TTS(
            model="bulbul:v3",
            speaker="shubh",
            target_language_code="hi-IN",
            speech_sample_rate=sample_rate,
        )
        # Bilingual/code-mixed input; confirm the model renders both languages.
        request_text = "नमस्ते, my account number is AC-1234, कृपया मदद कीजिए।"
        chunks = 0
        async for _chunk in tts.synthesize(request_text):
            chunks += 1
        print(f"[A] sample_rate={sample_rate} chunks={chunks}")

    # STT: confirm code-mix / language-unknown mode and 8 kHz telephony input.
    stt = sarvam.STT(model="saaras:v4", language="unknown")
    print("[A] STT constructed:", type(stt).__name__)
    print(
        "[A] TODO confirm: v4-flash present in plugin; pace range; PCM (not WAV) "
        "output; streaming error handling."
    )


if __name__ == "__main__":
    asyncio.run(main())
