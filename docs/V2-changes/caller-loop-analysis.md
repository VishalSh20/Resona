# Caller agent — architecture & current behaviour

Scope: the LiveKit link-boundary caller (`runtime/livekit/*`, `runtime/caller/*`,
`runtime/providers/*`, `runtime/media/*`). This document describes **what runs and
in what order**, every node in detail, and the **problems currently observed**. It
does not prescribe changes.

---

## 0. Topology (one line)

```
control plane (Run→CallRun→CallAttempt)
   └─ LiveKitDispatcher ─ creates room + dispatches named agent (metadata only)
        └─ agent worker job.entrypoint
             ├─ load AttemptBundle (frozen manifest)
             ├─ prepare TargetLink (bridge/sip/room/whip)
             ├─ TargetLink.connect()
             ├─ LinkConversationRunner.run()   ← the caller loop
             │     ├─ agent audio → recording + streaming ASR
             │     ├─ provider events → canonical events → telemetry
             │     ├─ brain (analyzer/policy/selector/realizer) → text
             │     └─ TTS → audio → target (and → recording)
             └─ finalize → upload media → terminal → teardown
```

Two asynchronous producers feed one consumer queue:

```
link.incoming_audio() ──┬─► recording.append_agent()          (caller track? no: agent track)
                        └─► asr_queue ─► SarvamStreamingASR ─► agent.text.final (independent_asr) ┐
link.events() ──────────────────────────────────► canonical events (telemetry) + turn text        │
                                                                                                   ▼
                                                                          run() loop: buffer → _respond()
```

---

## 1. Node: control plane → dispatcher

Files: `runtime/dispatch.py` (`LiveKitDispatcher`), `runtime/livekit/rooms.py`,
`runtime/livekit/admission.py`, `workers/jobs/execution.py`.

- A `Run` is expanded to one `CallRun` per `RunEvaluator`; each `CallRun` spawns
  physical `CallAttempt`s. The **simulation handler** gates how many call runs are
  dispatched at once, using a DB tally (`CallRunRepository.count_active`) bounded
  by `livekit_max_concurrent_calls` / `livekit_max_concurrent_per_target`.
- `LiveKitDispatcher.dispatch(attempt_id)`:
  1. `runner_id = runner-id-for(attempt)`; `create_runner_token(runner_id, attempt_id)` (short-lived, attempt-scoped).
  2. `telemetry_url = build_stream_url(runner_backend_url, attempt_id, token)` → `ws://…/internal/v1/attempts/{id}/stream?token=…`.
  3. `LiveKitRoomManager.create_room("attempt-{id}", empty_timeout=settings.livekit_room_empty_timeout_s)`.
  4. `dispatch_agent(room, agent_name=settings.livekit_agent_name, metadata=json{attempt_id, runner_id, runner_token, telemetry_url})`.
- The job metadata carries **only** attempt id, runner id, runner token and the
  telemetry URL — never configuration. The admission controller class still exists
  but is not used on this path; capacity is enforced by the simulation handler.
- There is **no retry** if no agent worker picks up the dispatch (see §11.8).

---

## 2. Node: LiveKit agent worker (process)

File: `runtime/livekit/job.py` (`main`, `prewarm`).

- `main()` → `livekit.agents.cli.run_app(WorkerOptions(...))` with:
  - `entrypoint_fnc=entrypoint`, `prewarm_fnc=prewarm`,
  - `agent_name=settings.livekit_agent_name`, `ws_url=settings.livekit_url`,
    `api_key`/`api_secret`,
  - `num_idle_processes=4` (pool of pre-warmed job processes),
  - `initialize_process_timeout=30.0`, `shutdown_process_timeout=60.0`.
- `prewarm(proc)` (runs once per process, best-effort):
  - loads the Silero VAD into `proc.userdata["vad"]`;
  - imports the heavy modules the job touches (`boto3`/`botocore.client`,
    `asyncpg`, `sarvamai` + both streaming clients, `storage.s3`, the Sarvam
    provider, the target-link classes);
  - builds the object-store client (`store.warm()`);
  - creates the DB engine (`get_engine()`);
  - constructs the TTS provider once (`_build_tts(16000)`).
- The worker registers with the LiveKit server as `agent_name`; jobs are delivered
  per dispatch.

---

## 3. Node: job entrypoint (`entrypoint(ctx)`)

File: `runtime/livekit/job.py`.

Order of operations:

1. Parse `ctx.job.metadata` → `attempt_id`, `runner_id`, `telemetry_url`.
2. `RunnerWebSocketClient` connects (telemetry) with the runner token.
3. Create `CanonicalEventBuilder(attempt_id)` (sequence + clock stamps).
4. `load_attempt_context(session, attempt_id)` → **`AttemptBundle`**:
   `manifest`, `run_evaluator`, `call_run`, `target_revision`, `scenario`,
   `persona`, `seed`, `target_link`. All values come from the **frozen
   `ExecutionManifest`**, never mutable config.
5. `prepare_target_link(session, bundle.target_link, manifest, target_revision)` →
   `PreparedLink(transport, endpoint_config, provider_session_id, endpoint_id)`:
   - **per-call** (`call_setup == "per_call"`): `adapter.start_connection(...)`
     mints credentials (Vapi `POST /call` → `websocketCallUrl`; ElevenLabs token;
     LiveKit room/dispatch). Secrets resolved at connect time, never frozen.
   - **client-supplied**: pulls `conn_<name>` secrets from the account; provisions
     a SIP outbound trunk inline for `sip`.
   - **static**: passes the frozen config through.
6. Build the target link: `get_target_link_registry().create(transport, endpoint_config=…, room=ctx.room)`.
7. `_start_connection_session(...)` (records a `connection_session` row when the
   endpoint has an id), `await link.connect()`; emit lifecycle `connecting` then
   `running`; on connect failure emit a terminal (`CONNECTION_FAILURE`).
8. Build the caller side (details §5–§8):
   - `recording = AttemptRecording(sample_rate=link.capabilities().sample_rate)`;
   - `pipeline_runtime = LiveKitCallerRuntime(bundle.scenario, bundle.persona)`
     which constructs `CallerDecisionPipeline(... realizer=Realizer(model=get_generation_model(), validator=OutputValidator(max_chars=160)))`;
   - `tts = _build_tts(recording.sample_rate, speaker=bundle.persona.speaker)`;
   - `asr_factory = _build_asr(bundle, recording)` (None without `SARVAM_API_KEY`);
   - `LinkConversationRunner(attempt_id, link, pipeline, builder, recording, tts, emit, asr_factory=…)`.
9. `reason = await runner.run()` (the loop, §9).
10. `recording.finalize()` → upload (`persist_media_records`, bounded 60 s).
11. Emit `attempt.terminal` (classified) **after** upload.
12. Teardown: `link.close()`, `_finish_connection_session("terminated")`, `telemetry.close()`.

---

## 4. Node: TargetLink (`BridgeLink`) + protocol decode

Files: `runtime/livekit/target_links/base.py`, `bridge.py`, `audio.py`,
`bridge_decoders.py`, `runtime/adapters/websocket.py`.

- `TargetLink` contract: `connect`, `incoming_audio`, `send_audio`, `send_dtmf`,
  `send_control`, `events`, `close`, `capabilities`.
- `TargetLinkCapabilities(codec, sample_rate, channels, supports_dtmf,
  target_speaks_first, provides_monitor_track)`. For the Vapi `bridge`:
  `codec=pcm_s16le`, `sample_rate=16000`, `channels=1`, `target_speaks_first=True`.
- `BridgeLink` wraps a `WebSocketAdapter(sample_rate, decoder=VapiDecoder, encoder=RawPcmEncoder)`:
  - `connect()`: build the connection from `endpoint_config` and open the websocket;
    start `_demux()`.
  - `_demux()`: reads `connection.receive()`; frames whose type ends with
    `media.chunk` **and carry bytes** go to the `_audio` queue, **everything else**
    goes to the `_events` queue.
  - `incoming_audio()`: `while connected: yield await self._audio.get()`.
  - `send_audio(frame)`: `connection.send_audio(frame)` (raw PCM over the socket).
  - `events()`: `while connected: yield await self._events.get()`.
- `FrameDecoder` (`adapters/websocket.py`): binary websocket messages are sliced
  into **640-byte (20 ms @16 kHz)** audio frames; text messages are JSON — a
  message with a `frames` array yields one frame per element, otherwise one
  control frame.
- `VapiDecoder` (`bridge_decoders.py`) mapping (the provider does **not** nest under
  `payload`; fields are top-level):
  | Vapi message | → canonical |
  |---|---|
  | binary frame | `agent.media.chunk` (provider_raw, `{data, bytes}`) |
  | `transcript` role=assistant, `transcriptType=partial` | `target.transcript.interim` |
  | `transcript` role=assistant, final | `target.transcript.final` (`{text, provider: vapi}`) |
  | `transcript` role=user | ignored |
  | `speech-update` status=started/stopped | `agent.speech.start` / `agent.speech.end` |
  | `audio` (base64) | `agent.media.chunk` (base64 fallback) |
  | `hang` | `connection.closed` |
  | `conversation-update`, `status-update`, others | ignored |

  Note: the provider's own caption is `target.transcript.final`, deliberately **not**
  the decision trigger; our ASR is the trigger.

---

## 5. Node: caller audio capture (pump + recording)

Files: `runtime/livekit/conversation.py` (`_pump_agent_audio`),
`runtime/livekit/recording.py` (`AttemptRecording`),
`runtime/media/recorder.py` (`MediaRecorder`).

- `_pump_agent_audio()`: `async for chunk in link.incoming_audio():` →
  `recording.append_agent(chunk)` and, when ASR is active,
  `self._asr_queue.put_nowait(chunk)`.
- `AttemptRecording(sample_rate=link.capabilities().sample_rate)` holds **two
  independent** `MediaRecorder`s: `caller` and `agent`. `append_caller` is called
  from `_speak`; `append_agent` from the pump. Each tracker resamples to the
  capture rate if needed.
- `MediaRecorder.append(chunk)`: updates a running sha256, extends a byte buffer,
  adds `size_bytes`, and adds `chunk.duration_ms` (or a byte-derived duration) to
  `_duration_ms`. **It stores no timestamps and inserts no silence.**
- `AttemptRecording.finalize()` → `[caller(mono wav), agent(mono wav), mixed(stereo wav)]`:
  - `_stereo_record` calls `interleave_stereo(caller_bytes, agent_bytes)`, which
    zero-pads the shorter buffer to the longer length and places caller on the
    left channel, agent on the right, from sample 0.

---

## 6. Node: our target ASR (`_asr_loop` + `SarvamStreamingASR`)

Files: `runtime/livekit/conversation.py` (`_asr_loop`),
`runtime/providers/sarvam.py` (`SarvamStreamingASR`).

- Created when `SARVAM_API_KEY` is set and passed as `asr_factory` to the runner.
- `_asr_loop(out_queue)` runs inside `async with self._asr_factory() as asr:` with
  two concurrent sub-tasks:
  - `_pump(asr)`: pulls audio chunks from `self._asr_queue` and calls `asr.push(chunk)`;
  - `_read(asr)`: `async for text in asr.transcripts():` logs and pushes a raw
    `agent.text.final` with `source="independent_asr"` and `payload={"text": text}`
    into the main `queue`.
- `SarvamStreamingASR`:
  - `__aenter__`: `client.speech_to_text_streaming.connect(language_code=normalize_bcp47(language), model=saaras:v4, sample_rate=str(16000), input_audio_codec="pcm_s16le", high_vad_sensitivity="false", flush_signal="true", api_subscription_key=…)`.
  - `push(chunk)`: base64-encodes raw PCM and sends a streaming audio message
    (per-message `encoding` is fixed to `audio/wav` by the SDK model; the real
    format is declared at connect).
  - `transcripts()`: reads messages, skips `events`, yields `data.transcript`.
  - `__aexit__`: flush + close + release the httpx client.
- Fail-safe: if `_asr_loop` raises, it sets `self._asr_active = False` so the loop
  falls back to provider captions (see §9 turn-signal selection).

---

## 7. Node: provider-event reader

File: `runtime/livekit/conversation.py` (`_reader`).

- `async for raw in self._link.events(): queue.put_nowait(raw)`.
- This is the same `queue` the ASR writes to. Provider captions and our ASR results
  therefore interleave in one FIFO.

---

## 8. Node: telemetry (runner → backend)

Files: `runtime/telemetry.py` (`RunnerWebSocketClient`),
`realtime/runner_ws.py` (`RunnerSession`), `realtime/event_ingestion.py`,
`realtime/materializer.py`.

- `RunnerWebSocketClient`: register, periodic heartbeat, `send_event(envelope)`
  with a bounded unacked replay buffer, `next_control()` for inbound control.
- Backend `RunnerSession.handle`: parse → `RuntimeEventIngestor.ingest` (append-only
  `runtime_event`, unique per `(attempt, sequence)`) → `EventMaterializer.materialize`
  (`turn.*`→`call_turn`, `caller.*`→`state_transition`, `tool.*`→`tool_call`) →
  on `attempt.terminal`, `record_terminal_event` (status/retry/completion) and
  room deletion + admission bookkeeping.

---

## 9. Node: the main loop (`LinkConversationRunner.run`)

File: `runtime/livekit/conversation.py`.

Setup: start `_pump_agent_audio`; create `pending: list[str]`, `assertions: list[str]`,
a local `queue`; start `_reader`; if `_asr_active`, set `_asr_queue` and start `_asr_loop`.

Loop iteration:
1. `raw = await asyncio.wait_for(queue.get(), timeout=self._turn_silence_s)` (2.5 s).
2. On **`TimeoutError`**: if `pending` is non-empty → `_respond(pending, assertions)`;
   if it returns True → break; else continue.
3. Otherwise build a `CanonicalEvent` from the raw item and `emit()` it to telemetry.
4. If `_asr_active` and the event is a provider caption (`target.transcript.final`)
   → log as `TARGET(provider)` and `continue` (not a trigger).
5. If `_is_turn_event(canonical)` → log, dedupe against `_last_agent_text`, append to
   `pending`; collect `assertions` from the payload.
6. Else if the event is `agent.speech.end`/`target.speech.end` and `pending` is
   non-empty → `_respond(pending, assertions)`.

`_is_turn_event(canonical)`:
- ASR active → `canonical.type == agent.text.final AND canonical.source == "independent_asr"`.
- ASR inactive → `agent.text.final` (any source) OR `target.transcript.final`.

`_respond(pending, assertions) -> bool`:
1. `text = " ".join(pending).strip(); pending.clear()`.
2. `step = await self._pipeline.decide(text, assertions=…)`.
3. `logger.info("[dialog] CALLER >> …")`.
4. if `step.text`: `_speak(step.text, step.language)`.
5. `link.send_control({"type":"caller.turn.end","turn_id": f"turn-{n}"})`.
6. if `step.terminal or self._turns >= self._max_agent_turns (32)` → set
   `terminal_reason` and return True.

Teardown (`finally`): cancel `reader`, `asr_task`, `agent_audio_task`.

Notes on the boundary:
- The trigger is **event silence** (no canonical event for 2.5 s), and/or a
  provider `speech.end` event — not the target's audio actually finishing.
- `_respond` speaks immediately; there is no check of whether the target is still
  producing audio.

---

## 10. Node: the brain (`CallerDecisionPipeline` and friends)

Files: `runtime/caller/pipeline.py`, `analyzer.py`, `turn_analyzer.py`,
`policy.py`, `state.py`, `actions.py`, `language.py`, `realizer.py`,
`interruption.py`; `runtime/livekit/runtime.py` (`LiveKitCallerRuntime`).

`LiveKitCallerRuntime.__init__` builds the pipeline:
`CallerDecisionPipeline(scenario, persona, realizer=Realizer(model=get_generation_model(), validator=OutputValidator(max_chars=160)), rng=…)`.
Internally the pipeline also builds `TargetAnalyzer()` (no model), `ActionSelector`
over `scenario.allowed_actions`, `PolicyEngine(scenario)`,
`LanguageController.from_scenario(scenario.language)`, `InterruptionPlanner(persona)`,
`PersonaDynamics(persona)`, and `ScenarioState.initial(…)`.

`decide(target_text, *, assertions=…)`:
1. **`TargetAnalyzer.analyze`** → `TurnReading(kind, fact_key, is_question,
   is_repeat, confidence, requires_clarification)`. Rule path
   (`turn_analyzer.py`): similarity vs previous → `REPEAT`; regex classes
   `HOLD_TRANSFER_CLOSING`, `DISCLAIMER`, `ERROR_APOLOGY`, `CONFIRMATION_REQUEST`,
   `FACT_REQUEST`; `?`/question-words → `QUESTION`; ≥45 words → `MONOLOGUE`; else
   `STATEMENT`. The optional structured LLM step is disabled because the analyzer's
   model is `None`.
2. **`PolicyEngine.observe(state, CallerObservation(kind="agent_text", text,
   assertions))`** → state mutations. Only assertion ids present in
   `observation.assertions` that are in the scenario mutate
   `known_information.assertions.satisfied`; `last_agent_text` is stored. Free text
   never satisfies an assertion.
3. **`PersonaDynamics.update(reading)`** — irritation/patience/engagement move on
   repeat/monologue/apology/question; decay over time.
4. **`ActionSelector.select(state, required_satisfied, recovery_requested)`**
   (`actions.py`, deterministic priority):
   `terminal_status set → END_CALL`; `required_satisfied && acknowledged → END_CALL`;
   `required_satisfied → ACKNOWLEDGE_RESOLUTION`; `recovery_requested → RECOVER`;
   `turn_count == 0 → PRESENT_PROBLEM`; `not authentication_state →
   PROVIDE_INFORMATION`; else `CLARIFY`.
5. **`LanguageController.language_for_turn(turn)`** (code-switch to secondary on odd
   turns when set) and `realize(action, …)` → deterministic template text (used as
   the fallback).
6. **`Realizer.realize(action, persona, allowed_facts, language, objective,
   agent_message, recent_turns, fallback)`**: if it has a model, builds
   system = persona card (`style_card`) + objective + "Reply in {language}",
   user = "The agent just said: {agent_message}" + action + allowed facts + recent
   utterances + "ONE short sentence (≤~15 words)". Validates via `OutputValidator`
   (`max_chars=160`, no AI disclosure, no forbidden facts, profanity ceiling); one
   retry, then the template fallback. Exceptions fall through to the fallback.
7. Returns `Decision(action, text, language, terminal, terminal_reason, reading,
   record)`.

`InterruptionPlanner` (`interruption.py`) implements `should_yield`,
`is_false_interruption`, `barge_in_trigger`, `should_barge_in`, `overlap_mode`
(`cooperative`/`competitive`/`cut-off`) and `effective_yield_threshold_ms`. The
pipeline exposes `decide_barge_in(...)`; `LiveKitCallerRuntime` does not call it.

---

## 11. Node: TTS + send

Files: `runtime/livekit/conversation.py` (`_speak`),
`runtime/providers/sarvam.py` (`SarvamBulbulTTS`), `providers/deterministic.py`.

- `_speak(text, language)` builds `SynthesisRequest(text, language,
  sample_rate=recording.sample_rate)` and `async for chunk in tts.synthesize(request):`
  → `recording.append_caller(chunk)` and `await link.send_audio(chunk)`.
- `SarvamBulbulTTS.synthesize`: opens `text_to_speech_streaming.connect(model="bulbul:v3",
  send_completion_event="true")`, `configure(target_language_code=normalize_bcp47(...),
  speaker=…, speech_sample_rate=…, output_audio_codec="linear16")`, `convert(text)`,
  `flush()`, then yields base64-decoded `AudioOutput` chunks until `final`/timeout.
- Without `SARVAM_API_KEY`, `DeterministicTTS` emits a fixed-duration tone.

---

## 12. Node: aftermath / storage

Files: `runtime/livekit/media.py`, `runtime/livekit/recording.py`,
`storage/s3.py`, `orchestration/terminal.py`.

- `persist_media_records(session, attempt_id, records)`: uploads each record
  **concurrently** (`asyncio.gather` → `asyncio.to_thread(store.put)`) with key
  `media/{attempt_id}/{track}-{representation}-{sha256[:12]}.wav`, then writes one
  `media_artifact` row per representation and commits.
- `S3ObjectStore`: boto3 client (`max_pool_connections=32`, `connect_timeout=5`,
  `read_timeout=20`, 2 retries), warmed in `prewarm`; presigned playback URLs.
- `_emit_terminal` (classified via `terminal_payload`) is sent **after** the upload,
  because `attempt.terminal` causes the control plane to delete the room.
- Backend: `record_terminal_event` → attempt/run status, retry policy, judges →
  aggregation; room deleted, slot freed.

---

## 13. Config inventory (effective values)

| Element | Class / key | Value |
|---|---|---|
| Capture rate | `AttemptRecording.sample_rate` | `link.capabilities().sample_rate` = 16000 |
| Caller TTS | `SarvamBulbulTTS` | `bulbul:v3`, `linear16`, sample_rate = capture rate, speaker `persona.speaker` (`shubh`) |
| Target ASR (ours) | `SarvamStreamingASR` | `saaras:v4`, `pcm_s16le`, `high_vad_sensitivity=false`, language = scenario `primary` |
| Realizer | `OpenAICompatibleProvider` | provider `openrouter`, model `openai/gpt-4o-mini`, **non-streaming**, `max_chars=160` |
| Analyzer | `TargetAnalyzer` | model `None` (rules only) |
| Brain | `CallerDecisionPipeline` | actions from scenario |
| Loop | `LinkConversationRunner` | `turn_silence_s=2.5`, `max_agent_turns=32` |
| Worker | `WorkerOptions` | `num_idle_processes=4`, `initialize_process_timeout=30`, `shutdown_process_timeout=60` |
| Room | `LiveKitRoomManager.create_room` | `empty_timeout=settings.livekit_room_empty_timeout_s` (300) |

---

## 14. Problems currently observed

### 14.1 No floor control / no yield / no barge-in in the live path
`LinkConversationRunner` and `LiveKitCallerRuntime` never consult
`InterruptionPlanner` (`should_yield`, `should_barge_in`) and never call
`pipeline.decide_barge_in`. The caller speaks immediately on `_respond()`
regardless of whether the target is still speaking.

### 14.2 The turn boundary is event-silence, not audio-silence
`_respond()` fires on `turn_silence_s` of no canonical events, or on a provider
`speech.end`. It is not tied to the target's audio actually finishing (the ASR can
endpoint while target audio is still buffered/playing, and `speech-update` timing
is independent of the audio). The caller can therefore start speaking over the
target.

### 14.3 Two producers, one queue
Provider events (`_reader`) and ASR transcripts (`_asr_loop`) push into the same
`asyncio.Queue`; the flush decision uses wall-clock silence of that queue. A brief
gap in the provider event stream can flush a partial turn while the ASR is still
emitting.

### 14.4 The recording is not time-aligned
- `AttemptRecording` keeps two independent `MediaRecorder`s and mixes them with
  `interleave_stereo`, which zero-pads the shorter buffer and overlays both from
  sample 0. Neither track contains the silence when that side was not talking, so
  the stereo mix overlays speech-only tracks — both sides appear to talk over each
  other.
- `MediaRecorder.append` stores no timestamps and inserts no silence; `duration_ms`
  is the **sum of appended chunk durations**, not elapsed call time (e.g. one call:
  caller 109 s vs agent 309 s).
- `clock_domain="runner_monotonic"` is a static label; there is no per-chunk clock,
  so `runtime_event.monotonic_ms` cannot be mapped to WAV offsets.

### 14.5 The realizer LLM is non-streaming
`OpenAICompatibleProvider.generate` performs a single blocking POST; no audio can
begin until the full completion returns, so the reply lands abruptly and late.

### 14.6 Assertions are effectively never satisfied
`PolicyEngine` only mutates assertions from ids present in an observation payload;
target agents do not send assertion ids. Unless a scenario pre-satisfies its
required assertions, the selector never reaches `END_CALL`, so calls run to
`max_agent_turns` (`MAX_TURNS`).

### 14.7 Provider caption and ASR duplicate the same content
Both `TARGET(provider)` (from Vapi `transcript`) and `TARGET(asr)` (our ASR) are
produced and logged for the same utterance; only the ASR drives decisions. They are
different lengths/segmentations, which is visible in the logs.

### 14.8 Dispatch can silently no-op
`LiveKitDispatcher.dispatch` creates the room and dispatches the named agent once;
if no agent worker is registered at that instant (e.g. right after a worker
restart), the job is never picked up and the attempt remains `starting` with no
terminal. There is no retry.

### 14.9 Room lifetime vs call length
The room is created with `empty_timeout=settings.livekit_room_empty_timeout_s`.
When that elapses while a call is in progress, LiveKit closes the room
(`IDLE_TIMEOUT`), the job is cancelled, and (depending on timing) the upload is
aborted.

### 14.10 Upload races job shutdown
The job emits `attempt.terminal` only after the upload, but the upload itself can
still be cancelled by the job's shutdown grace if the object store is slow or DNS
flaky; the terminal path also kills the room, so ordering matters.

### 14.11 Long dead air per turn
Because the caller's utterances were long and the realizer non-streaming, the
target sits silent between turns; the agent track is therefore mostly silence
(measured 69% silent, gaps of 17–39 s) even though audio is captured continuously.

### 14.12 Audio-from-provider is all-or-nothing per branch
`VapiDecoder` handles binary audio frames and a base64 `audio` message; there is no
sampling-rate handling for the base64 branch beyond an optional field, and no
resampling there (the capture path resamples to the capture rate, the decoder does
not set a rate for base64 audio).
