# Prompt 6 — CallRunner + Target Adapters + Pipecat Caller: Progress

## Status: Complete

The realtime execution runtime is implemented: a disposable `CallRunner` that
connects to a target through a versioned adapter, drives the deterministic caller
loop, normalizes provider observations into canonical runtime events, evaluates
stop conditions after every event, records media, and streams telemetry to the
backend over the runner control WebSocket (whose terminal event the backend now
applies to the attempt/run). A deterministic fake target server makes the whole
path exercisable end-to-end with no third-party provider and no database.

## What was built

### Target adapters (`runtime/adapters/`)
- `base.TargetAdapter` — config validation, capability snapshot, connection
  construction, and observation -> canonical translation.
- `websocket.py` — `FrameDecoder` (a message may yield many frames), abstract
  `ProviderProtocolDecoder`, `JsonProviderProtocolDecoder` (media aliases +
  base64 byte counting), `WebSocketTransport` (`AgentConnection` over
  `websockets`, plus `send_control`), and `WebSocketAdapter`.
- `fake.py` — `FakeTargetServer` (real `websockets` server, deterministic
  scripted conversation with audio/text/turns/tool calls), `FakeScript`,
  `FakeTargetAdapter`, and public `agent_turn` / `tool_turn` builders.
- `webrtc.py` — `WebRTCAdapter` with a full config-validation contract
  (signaling, SDP, ICE, codecs, auth, audio tracks) and execution that fails
  loudly instead of faking compatibility.
- `registry.py` — now stores adapter factories; `create()` instantiates,
  `ensure_exists()` still rejects unknown adapters.

### Caller runtime (`runtime/caller/`)
- `state.ScenarioState` (pre-existing) is the authoritative state; every mutation
  goes through `apply`, increments `state_version` and returns a transition.
- `policy.PolicyEngine` — converts agent observations into explicit state
  mutations (assertions, tool results, language) and owns recovery counting.
- `actions.ActionSelector` — deterministic priority order over allowed actions.
- `language.LanguageController` — language/script selection, deterministic
  code-switching, templated realization.
- `controller.CallerController` — the caller loop: observed output -> policy ->
  action -> realization -> TTS -> audio, emitting caller state/action/utterance
  and turn events. Interface: `start`, `observe_agent_event`, `select_action`,
  `realize`, `stream_audio`, `stop`.
- `runtime.CallerRuntime` — the protocol the runner depends on.
- `pipecat_caller.py` — `CallerSpeechProcessor` (real Pipecat `FrameProcessor`
  wrapping a `TTSProvider`), `build_caller_pipeline`, `PipecatCallerRuntime`, and
  pure frame translation helpers.

### Providers (`runtime/providers/`)
- `base` — `TTSProvider` / `ASRProvider` protocols, `SynthesisRequest`,
  `Transcript` (with provenance).
- `deterministic` — reproducible in-process TTS/ASR for local runs and tests.
- `sarvam` — `SarvamBulbulTTS` / `SarvamSaarasASR` built on the official
  `sarvamai` SDK (models `bulbul:v3` / `saaras:v4`). TTS requests `linear16` PCM
  at the target rate; ASR wraps caller PCM in a WAV container (`pcm_to_wav`) and
  consolidates endpointed segments. Credentials from config; fails fast without a
  key.

### Media (`runtime/media/`)
- `audio` — `AudioSource`, `Resampler` (s16le), energy-based `VAD`.
- `recorder` — `MediaRecorder` (content hash, size, duration) and
  `MediaArtifactRecord`; originals are immutable (finalize once, no late appends).
- `tts` — `TTS` component that emits canonical caller media/speech/audible events
  and assigns media timestamps.
- `db/repositories/media.py` — `MediaArtifactRepository` for original captures.

### Stop conditions (`runtime/stop_conditions.py`)
- `StopConditionEngine` with documented precedence, a sticky decision, retained
  evidence event id, and stall / wall-clock checks. Mapping to
  `AttemptTerminalStatus` / `AttemptFailureClass` / eligibility.

### Runner + telemetry
- `runner.CallRunner` — lifecycle (STARTING -> CONNECTING -> RUNNING ->
  TERMINATING), adapter connection, per-agent-turn caller response, canonical
  event emission, stop evaluation, media finalization, and a terminal
  `attempt.terminal` event.
- `telemetry` — `TelemetrySink` protocol, `RecordingTelemetrySink`, and the real
  `RunnerWebSocketClient` (register / heartbeat / runtime.event / control).
- `loader.build_runner_for_attempt` — resolves an attempt from the immutable
  manifest + evaluator revision into a `CallRunner`.
- `dispatch` — `SubprocessRunnerDispatcher` (default) and
  `InlineRunnerDispatcher`; `cli.main` / `python -m voiceeval.runtime` entrypoint.
- `realtime/local_telemetry.LocalTelemetrySink` — feeds the ingestion path
  in-process for inline runs.

### Wiring
- `workers/jobs/execution.py` — `execution_attempt_start` now dispatches the
  runner (replacing the Prompt-4 placeholder).
- `realtime/runner_ws.py` — an ingested `attempt.terminal` event is applied via
  `orchestration/terminal.record_terminal_event`, which applies the retry policy
  and enqueues a retry attempt when the failure is infrastructure.
- `core/config.py` — added `RUNNER_BACKEND_URL` for dispatched runners.

## Verification (all passing)
```bash
uv run pytest          # 202 passed (132 prior + 70 new runtime/provider tests)
```
Deterministic end-to-end (fake target through `CallRunner`):
- outcome `NATURAL_SUCCESS`, terminal `completed`, `eligible=True`, 164 events,
  4 agent turns, 4 caller turns, caller audio delivered to the target, one
  original caller media artifact (sha256 recorded).
- required canonical events present: connection.ready, caller.state.initialized,
  caller.action.selected, caller.utterance.realized, agent.text.final,
  tool.call.start/result, turn.start/end, caller.terminal, attempt.terminal.
- sequences strictly increasing and unique per attempt; all events carry the
  attempt id.
- replaying the recorded events through `EventMaterializer` materializes caller
  and agent turns, the `verify_identity` tool call, and caller state transitions.
- failure paths verified: recovery exhaustion -> `RECOVERY_EXHAUSTED`
  (semantic, eligible), unreachable target -> `CONNECTION_FAILURE` (transport,
  retryable), silent target -> `CONVERSATION_STALL` (timed out), control
  `attempt.cancel` -> `CANCELLED`.

No migration is needed: the runtime uses existing `runtime_event`, `call_turn`,
`tool_call`, `state_transition` and `media_artifact` tables.

Live provider verification (with `SARVAM_API_KEY` set):
- `SarvamBulbulTTS` synthesized a phrase to 16 kHz `linear16` PCM (~50–70 KB,
  several chunks) over the Bulbul `v3` streaming socket.
- `SarvamSaarasASR` transcribed that audio back to text (`saaras:v4`), confirming
  auth, config, codec and framing in both directions.
- OpenAI is configured but intentionally unused in Prompt 6 (the caller is
  deterministic by design).

## Decisions
`docs/decisions/0005-runtime-decisions.md` — three-layer separation, adapter
factories, WebRTC-not-executed, event/clock provenance, turn-grouped caller
loop, natural-success rule, precedence + config timeouts, terminal-on-ingest,
process dispatch, Pipecat seam, Sarvam fail-fast.

## Deferred to later prompts
- Prompt 7: metric/judge/aggregation registries and result computation
  (`metric.computed`, `judge.completed`, `aggregate.updated`, `composite.updated`).
- Pipecat execution over a real transport (the pipeline graph and processor are
  built and tested; v1 runs the in-process caller).
- Endpoint secret-reference resolution at dispatch time (config validation
  already forbids raw secrets; a secret store plug-in lands later).
- Async (ARQ-queued) materialization to replace the v1 synchronous path.

## What you may still need to do
- Run the inline path against live Postgres (`InlineRunnerDispatcher`) or start
  the runner container to exercise the dispatched path end-to-end; neither is
  covered by the unit suite (which is DB-free by design).
