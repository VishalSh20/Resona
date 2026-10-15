

## Which files matter

| Status | Files | Why |
|---|---|---|
| Live and central | `conversation.py`, `job.py`, `recording.py`, `bridge_decoders.py` (Vapi part), `failure.py` | Behaviour and measurement |
| Live, secondary | `media.py`, `rooms.py` | Shutdown and room-lifetime problems |
| Not wired in | `session.py`, `lifecycle.py`, `event_mapping.py`, `tts_fallback.py`, `admission.py`, most of `runtime.py` | See below |
| Irrelevant here | `connection_setup.py` | Fine for this problem |

The unwired files are the spec of what you meant to build: a LiveKit audio pipeline, a lifecycle machine with stall and wall-clock timeouts, floor/overlap/barge-in events, and a TTS fallback chain. What actually runs dropped all four. Concretely:

- **VAD:** Silero is loaded in `prewarm` and never read.
- **`runtime.py`:** only `.pipeline` is used from it.
- **Seed:** `bundle.seed` is loaded and never passed on.
- **Clock:** the runner's `clock` parameter is stored and never used. The runner literally has no clock.

**Still needed, in order of value:**
1. One bad call: the `[dialog]` log lines with timestamps, its `runtime_event` rows, and the three WAVs. This is the highest value per byte.
2. `runtime/caller/*` (pipeline, policy, state, actions, realizer, persona, interruption, rng, turn_analyzer, language), to verify the repetition causes.
3. `target_links/bridge.py` and `adapters/websocket.py`, for send pacing, close handling, queue bounds, and what `send_control` does on the wire.
4. `providers/sarvam.py` and `providers/base.py`, for the ASR and TTS internals.
5. `events.py` and `telemetry.py`, for timestamp stamping and backpressure.
6. `media/recorder.py`, `media/audio.py`, and `llm/providers.py`.

## Findings

### A. Turn-taking core (`conversation.py`)
Beyond what I said before (deaf while speaking, timer resets on any event, speech-end race):

- **Stale transcripts replay as new turns.** While `_respond` is awaiting the LLM and TTS, nobody drains the queue. Late ASR segments of the utterance you're answering pile up, then land in `pending` and fire a second reply 2.5 s later, to a fragment you already answered. This is a big source of your repetition.
  - **Fix:** tag every transcript segment with the audio offset where it ended, and keep a "floor epoch" that increments when the caller starts speaking. Segments that ended before the epoch started are history, not triggers.
- **No initiative.** `pending` empty plus silence means waiting forever. The code also never reads `capabilities().target_speaks_first`, so a target that waits for the caller deadlocks.
  - **Fix:** add a silence-initiative policy ("hello?", then "are you there?", then give up) and an opening policy that depends on the capability flag.
- **Exact-string dedupe** (`_last_agent_text`) drops legitimate repeats like "Okay." and does nothing for near-duplicates. A target repeating itself is a signal for the brain, not noise to filter.

### B. Output path
- **The target is evaluated under unrealistic conditions.** Burst-sending TTS means the target receives a 4 s sentence in about 300 ms, then nothing. Targets whose endpointing runs on wall-clock or audio-silence see a strange stream. That perturbs the *target's* turn-taking, so your scores are contaminated, which matters more than the caller merely looking bad.
- **Silence is never sent.** Many target stacks only endpoint when they receive silence frames. A user stream with gaps instead of silence can cause late or missed target responses (verify per provider).
  - **Fix for both:** send a continuous, real-time-paced 20 ms stream. TTS audio when speaking, silence otherwise, via a cancellable playout buffer.
- **A TTS blip kills the call.** `_build_tts` returns the raw Sarvam provider, so `tts_fallback.py` is never used. An exception in `_speak` escapes `run()` and the call ends as `JOB_CRASH`. Wrap TTS failure as a retry or fallback, and classify it as `TTS_FAILURE` only after the fallback is exhausted.
- **Cold first turn.** The ASR socket is opened inside `run()` and TTS per utterance, both after `link.connect()`. The target's greeting audio queues up and reaches ASR late, so your first reply is slow. Open ASR and TTS sockets in parallel with the link connect, and keep the TTS socket for the whole call.
- **Truncated ending.** The pump is cancelled right after the goodbye is *sent*, so the target's reply to your goodbye is never recorded. Judges can't see how the target ended the call. Keep listening for a tail of a few seconds after playout completes, then hang up.

### C. Input path / ASR
- **Language pinned to `scenario.language.primary`.** Your `LanguageController` code-switches on odd turns, but the ASR can't follow. Mismatch produces garbage text, which feeds the CLARIFY loop. Check whether Sarvam can run auto-detect for your case (`session.py` uses `"unknown"`).
- **Verify what `saaras:v4` outputs.** Historically Sarvam's "saaras" line translated to English and "saarika" transcribed. If yours translates, the language fidelity and the code-switch signal are gone.
- **ASR-side speech signals are thrown away.** `transcripts()` skips `events` messages. Check the SDK for VAD signals (something like `vad_signals`, with start/end-of-speech messages). You are not enabling them, and they are exactly the signal you're missing.
- **Silent degradation.**
  - The ASR queue is unbounded, so lag is invisible and grows.
  - A mid-call ASR failure permanently flips the trigger to provider captions, which changes semantics with no reconnect.
  - There is no watchdog for "target audio present but no transcript for N s".
  - **Fix:** reconnect with backoff, a lag metric, and a watchdog.
- **Wasted traffic.** Continuous silence is streamed to ASR. A local VAD gate (speech plus padding) cuts cost and gives you the speech/silence signal anyway.

### D. Supervision and termination
This is probably what's causing your 17-39 s gaps and 300 s calls.

- **Target hang-up is never handled.**
  - `VapiDecoder` emits `connection.closed` on `hang`, and `run()` ignores it.
  - `TARGET_HUNG_UP` as the default reason is unreachable, because `run()` only returns via `_respond`.
  - After a hang-up with empty `pending`, the loop spins on 2.5 s timeouts until the room dies. With non-empty `pending`, `send_audio` into a closed socket raises and you get `JOB_CRASH`.
  - I can't confirm what `BridgeLink` does on socket close without `bridge.py`.
- **`lifecycle.py` is not used.** It defines a 10 s conversation-stall timeout, a 15 s first-audio timeout, and a 180 s wall clock, and none of them run. A 10 s stall check would have caught your 17-39 s gaps. `TARGET_SILENT`, `CONVERSATION_STALL`, `STT_FAILURE`, and `TTS_FAILURE` exist in `failure.py` and nothing emits them.
- **Your room may be on a 300 s fuse (hypothesis).** In link-boundary mode the room contains only the agent job and no human participant. As I recall, LiveKit does not count agent participants toward keeping a room alive, so `empty_timeout=300` could close the room mid-call regardless of activity. Your 309 s agent track fits that. Verify against LiveKit server logs and docs.
  - **Fix:** set `empty_timeout` above max call plus upload grace, and use `reap_stale_rooms` (which you already have) for cleanup.
- **Caller failures are counted as target results.** `MAX_TURNS` is classified as an eligible, completed target outcome, and `LOOP` is ambiguous. With assertions never satisfied, most calls hit `MAX_TURNS`, so caller bugs flow into target scores as valid samples.
  - **Fix:** a "caller-degraded" class that is ineligible or flagged, set when the cap is hit without goal progress, or when the self-repetition or response-latency health metrics breach thresholds.
- **Terminal ordering.** "Upload before terminal, because terminal deletes the room" couples two unrelated things. Split into `attempt.ended` (status computed, room left alone) and `media.uploaded`, with the room deleted on the second or after a grace timeout. Also persist PCM to disk incrementally during the call, so a shutdown loses the tail rather than everything.

### E. Time and measurement
- **Timestamps are wrong exactly when it matters.** Provider and ASR events carry `monotonic_ms=0`, so (assuming the builder stamps "now" when it's None, which `events.py` would confirm) they're stamped when `run()` dequeues them. Anything that arrived during `_speak` is stamped seconds late. Stamp at the source (the reader and the ASR callback) and attach audio offsets.
- **Recording, a correction to my earlier read.** Your own numbers (agent track 309 s, 69% silent) mean the agent track is continuous, because Vapi streams silence. Only the caller track is speech-only. So the stereo overlay is wrong mainly on one side. Fixing the output path (continuous paced stream) fixes most of it. For the rest:
  - anchor `t0` at link connect, because audio from before `run()` starts is currently appended in a burst;
  - make the caller track exactly what playout sent, including truncation;
  - guard providers that only send audio while speaking by inserting gap silence from the wall clock;
  - check whether `Resampler` has state, since one instance is shared by both tracks. It's dormant at 16 k but will bite SIP at 8 k or WebRTC at 48 k.
- **`emit()` is awaited inside the loop.** If `telemetry.send_event` ever blocks on acks, turn handling stalls. Make it fire-and-forget with a bounded queue. I need `telemetry.py` to confirm.

### F. Brain wiring
- `LiveKitCallerRuntime(bundle.scenario, bundle.persona)` gets no `rng`, though `bundle.seed` exists. Unless the pipeline seeds itself elsewhere, runs aren't reproducible, which defeats an eval platform.
- The realizer is told "ONE short sentence (≤~15 words)" with `max_chars=160`. That is fine for latency, but combined with a constant action it yields the clipped, repetitive speech you describe.
- The Retell and Pipecat decoders alias `transcript` to `agent.text.final`. If those providers send accumulated transcripts (as I believe Retell does, though I'm not sure of the wire format), the ASR-fallback path would replay the whole history each update.

## Fix order

1. **Supervision (cheap, immediate).** Hang-up handling, stall and wall-clock timeouts (wire the machine you already wrote), room timeout, and the `MAX_TURNS` classification. Do this first because it stops bad data from entering your scores.
2. **Clock and measurement.** Source stamping, audio offsets, `t0`, continuous caller track. Log per turn: target VAD end, ASR final, decide start, LLM first token, TTS first chunk, first audio sent.
3. **Paced, cancellable playout plus persistent TTS socket.**
4. **Perception.** Local VAD and ASR speech signals, then the endpointing policy from last turn.
5. **Controller.** Floor states, epochs, initiative, and both interruption directions, emitting the floor and barge-in events you already defined in `event_mapping.py`.
6. **Brain.** Belief state, disclosed-facts ledger, and caller-owned termination.

**AgentSession or your own controller?** I still lean towards owning the controller, borrowing Silero VAD and possibly the turn-detector model. Your `session.py` shows you once planned the AgentSession route and abandoned it. Its knobs (endpointing delays, interruption minimums) are global defaults, while you need per-persona, seeded, replayable timing.

**How you'll know it's fixed:** track these per attempt.
- the distribution of target-end to caller-start gap, with p50 around 0.6-1.2 s
- caller self-overlap ratio
- caller repetition rate
- percentage of calls ending at `MAX_TURNS` (should be near zero)
- ASR lag
- LLM time to first token

Send the files in the "still needed" list, or just one bad call's logs plus WAVs, and I can turn this into specific, verified changes.