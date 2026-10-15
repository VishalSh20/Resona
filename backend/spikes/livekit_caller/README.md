# Phase 0 spike — LiveKit caller (not shipped)

Sandbox for the three de-risking checks in `docs/V2-changes/caller-migration-to-livekit.md` §14.0.
Nothing here is imported by the application.

## Setup

Create a scratch venv (or add a `[dependency-groups] spike` group) with the
versions you intend to pin:

```bash
python -m venv .venv-spike && . .venv-spike/bin/activate
pip install livekit-agents livekit-api livekit-plugins-sarvam livekit-plugins-silero
```

Required env: `SARVAM_API_KEY`; for the SIP spike also `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_SIP_OUTBOUND_TRUNK_ID`,
`LIVEKIT_SIP_FROM_NUMBER`, and a destination number.

## Scripts

| Script | Check | Pass criteria |
|---|---|---|
| `spike_a_sarvam.py` | Sarvam bilingual STT/TTS inside `AgentSession` (§9.3) | `bulbul:v3` streaming works; `bulbul:v4-flash` present in the pinned plugin (else custom wrapper); 24 kHz WebRTC + 8 kHz narrowband both produce audio; raw-PCM (not WAV container); `pace` range validated |
| `spike_b_talkover.py` | Caller talks over the target without self-cut-off (§8.3) | Per-speech interruption control keeps the caller speaking over target audio, then re-enables |
| `spike_c_sip.py` | One outbound SIP call (§4.3) | Caller dispatched first, dial second; SIP status mapped; no greeting into an empty room |

## Exit criteria

Do not start Phase 1 until `spike_b` and either the `spike_a` plugin path or a
custom Sarvam wrapper are proven. Record resolved package versions in
`docs/V2-changes/livekit-caller-spike.md`.
