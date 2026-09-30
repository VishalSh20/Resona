# Runtime execution decisions (Prompt 6)

## 1. Transport, provider semantics and evaluation semantics are three layers

`AgentConnection` is transport only (connect / send audio / receive observations
/ close). A `TargetAdapter` owns provider semantics: config validation,
capability snapshot, and turning a provider observation into a canonical event.
The runner and caller own evaluation semantics. A websocket *message* is decoded
into zero or more frames (`FrameDecoder`) and each frame into zero or more
observations (`ProviderProtocolDecoder`), so neither "1 message = 1 audio frame"
nor "1 message = 1 turn" is ever assumed.

## 2. The adapter registry now holds factories, not just names

Prompt 3 only needed to know whether an adapter existed. Prompt 6 needs to
instantiate it, so `AdapterRegistry.register(name, version, factory)` now stores
a factory and `create()` builds the adapter. `ensure_exists` keeps rejecting
unknown adapters at target-revision creation. `fake@1.0.0` and `websocket@1.0.0`
are registered; WebRTC is intentionally **not** registered.

## 3. WebRTC is an interface and validation contract, not a transport

`WebRTCAdapter` models signaling URL/method, ICE servers, codecs, authentication
and audio tracks, and validates them. `build_connection` raises
`ConnectionFailedError` rather than pretending generic WebRTC compatibility, so a
WebRTC target cannot silently execute. This preserves "do not implement WebRTC
media transport yet" without over-claiming.

## 4. Canonical events are built by the runner, media timestamps by the producer

`CanonicalEventBuilder` owns the strictly increasing per-attempt `sequence` and
the runner-monotonic stamp. The TTS component assigns the media timestamp (which
advances by frame duration). Wall clock, runner monotonic and media timeline are
kept distinct and are never assumed equal.

## 5. The caller's opening turn is the first agent-observed turn

The runner groups agent events per agent turn and only asks the caller to act on
`turn.end`, so one agent turn produces exactly one caller turn. The caller starts
by stating the problem (`turn_count == 0`), then volunteers information, then
recovers, then acknowledges and ends. Action selection is a deterministic
priority order, never an LLM decision.

## 6. Normal success requires all required assertions *and* caller acknowledgement

The caller emits `caller.terminal` with `NATURAL_SUCCESS` only when every required
motive assertion is satisfied and the caller has acknowledged resolution.
Otherwise the terminal reason is `IRRECOVERABLE_OBJECTIVE_FAILURE`. Recovery
exhaustion is a **semantic** result (eligible for evaluation, no retry), while a
connection failure is a retryable `transport` failure.

## 7. Stop conditions use documented precedence and are configuration, not constants

`StopConditionEngine` records candidate decisions and returns the strongest by
`NATURAL_SUCCESS > RECOVERY_EXHAUSTED > IRRECOVERABLE_OBJECTIVE_FAILURE >
CONVERSATION_STALL > WALL_CLOCK_TIMEOUT > CONNECTION_FAILURE`. The stall and
wall-clock budgets come from settings (10s / 180s, capped at 300s) and are
snapshotted into the manifest. Cancellation is driven by a control command and is
kept out of the evaluation precedence list.

## 8. Terminal outcomes are applied by the backend on `attempt.terminal`

The runner does not write to the database for the terminal transition; it emits
an `attempt.terminal` canonical event. The runner control WebSocket ingests it and
calls `record_terminal_event`, which applies the retry policy through the
orchestrator (infrastructure failure with budget remaining spawns the next
attempt on the same `CallRun`; semantic outcomes finalize it). Retry attempts are
enqueued best-effort.

## 9. Dispatch is a process boundary; inline dispatch is the local/fake path

`SubprocessRunnerDispatcher` (default) spawns `python -m voiceeval.runtime` with
a short-lived, attempt-scoped runner token; `InlineRunnerDispatcher` runs the
same `CallRunner` in-process with a telemetry sink that feeds the ingestion path
directly. The runner resolves everything it needs from the immutable manifest and
the referenced evaluator revision, never from mutable config.

## 10. Pipecat is integrated at a narrow seam; the in-process path is the default

Pipecat 1.12 runs pipelines through a worker/bus runtime and stamps frame
identifiers at push time, and meaningful execution needs real transports, which
v1 does not have. `CallerSpeechProcessor` is a real Pipecat `FrameProcessor`
wrapping the `TTSProvider`; `build_caller_pipeline` composes the graph; and
`PipecatCallerRuntime` exposes the same interface as `CallerController` with
`use_pipecat=False` by default. Frame translation (`to_audio_frame` /
`from_audio_frame`) is pure and unit-tested. Running the caller on a transported
Pipecat pipeline is deferred until a transport exists; the decision is explicit
rather than a false claim of integration.

## 11. Provider secrets are never hardcoded; Sarvam uses the official SDK

Sarvam Bulbul TTS and Saaras ASR are implemented behind `TTSProvider` /
`ASRProvider` using the official `sarvamai` SDK as the streaming transport
(models `bulbul:v3` / `saaras:v4`). The SDK is the vendor-recommended client and
handles the WebSocket framing; notably its Python per-message helper accepts only
WAV, so caller PCM is wrapped in a minimal RIFF/WAVE container
(`pcm_to_wav`) before transcription. TTS requests `linear16` at the target sample
rate so audio drops straight into `AudioChunk` with no transcoding, and ASR
accumulates endpointed segments into one consolidated transcript.

Without `SARVAM_API_KEY` the providers raise a configuration error instead of
synthesizing silence. Verified live: TTS returned 16 kHz linear16 PCM and ASR
transcribed it. The deterministic providers still back the local/test runtime, so
an end-to-end call needs no credentials.

## 12. OpenAI is configured but unused in Prompt 6

`OPENAI_API_KEY` exists in configuration but nothing in the runtime reads it. The
caller is deterministic by design (the LLM must not own scenario state), so the
key is reserved for later prompts (e.g. judge/realization in Prompt 7) rather than
being wired into execution now.
