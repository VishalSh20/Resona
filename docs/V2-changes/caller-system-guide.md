# The Resona caller system — developer guide

How the synthetic caller is spawned, configured, connected to a target agent, run,
and how the aftermath of a call (audio, events, status) is recorded and where.

Scope: the LiveKit-based caller (the current production path) plus the legacy
inline/subprocess `CallRunner`. Governing design doc:
`docs/V2-changes/caller-migration-to-livekit.md`.

---

## 1. What it is

Resona evaluates a **target voice agent** by having a **synthetic caller** phone/
connect to it, hold a goal-directed conversation, and record both ends of the
audio plus every runtime event so the call can be scored.

The caller's "brain" is **deterministic pure logic** (`runtime/caller/`) — the
LLM only realizes language, it never selects actions or mutates state. The brain
is identical across transports; only the audio/connection layer differs.

## 2. Two execution modes

Chosen by `RUNNER_DISPATCH_MODE` → `get_dispatcher()` (`runtime/dispatch.py`):

| mode | dispatcher | caller runtime | target transport |
|---|---|---|---|
| `livekit` | `LiveKitDispatcher` | link-boundary job (`runtime/livekit/job.py`) | TargetLink (room/sip/bridge/whip) |
| `subprocess` | `SubprocessRunnerDispatcher` | legacy `CallRunner` (adapter path) | `TargetAdapter` (fake/websocket) |
| `inline` | `InlineRunnerDispatcher` | legacy `CallRunner`, in-process | adapter path |

**The LiveKit link-boundary path is the current path.** The legacy `CallRunner`
(`runtime/runner.py`) drives the old adapter registry and only records the caller
track; the LiveKit job records caller **and** agent audio plus a stereo mix.

## 3. Component map

| Concern | File |
|---|---|
| Dispatcher (spawn) | `runtime/dispatch.py` (`RunnerDispatcher`, `LiveKitDispatcher`, `SubprocessRunnerDispatcher`, `InlineRunnerDispatcher`, `get_dispatcher`) |
| LiveKit job entrypoint | `runtime/livekit/job.py` (`entrypoint`, `prewarm`, `main`, `_build_tts`) |
| Room + agent dispatch | `runtime/livekit/rooms.py` (`LiveKitRoomManager`, `room_name_for_attempt`) |
| Per-attempt inputs | `runtime/loader.py` (`AttemptBundle`, `load_attempt_context`) |
| Conversation loop | `runtime/livekit/conversation.py` (`LinkConversationRunner`) |
| Caller brain | `runtime/caller/pipeline.py` (`CallerDecisionPipeline`), `runtime/livekit/runtime.py` (`LiveKitCallerRuntime`) |
| Scenario / persona | `runtime/scenario.py`, `runtime/caller/persona.py` |
| Target connection seam | `runtime/livekit/connection_setup.py` (`prepare_target_link`), `runtime/livekit/target_links/*` |
| Recording | `runtime/livekit/recording.py` (`AttemptRecording`), `runtime/media/recorder.py` (`MediaRecorder`, `MediaArtifactRecord`) |
| Persistence | `runtime/livekit/media.py` (`persist_media_records`), `storage/` |
| Telemetry / control | `runtime/telemetry.py` (`RunnerWebSocketClient`), `realtime/runner_ws.py` (`RunnerSession`) |
| Terminal application | `orchestration/terminal.py` (`record_terminal_event`) |
| Execution orchestration | `workers/jobs/execution.py`, `orchestration/executor.py`, `orchestration/manifest_service.py` |
| Watchdog / reaper | `workers/jobs/watchdog.py` (`watchdog_scan`, `room_reaper_scan`) |

---

## 4. Spawning a caller

### 4.1 Control plane → dispatcher

A `Run` is expanded into `CallRun`s (one per evaluator × repetition) and then into
`CallAttempt`s (physical tries). `workers/jobs/execution.py`:

- `execution.run.start` → `begin_run` (queues call runs)
- `execution.call_run.start` → `start_call_run` (freezes the manifest, spawns first attempt)
- `execution.attempt.start` → `start_attempt` then `get_dispatcher().dispatch(attempt.id)`

The dispatcher contract is trivial:

```python
class RunnerDispatcher(Protocol):
    async def dispatch(self, attempt_id: str) -> None: ...
```

### 4.2 LiveKit dispatch (the current path)

`LiveKitDispatcher.dispatch(attempt_id)`:

1. **Admission control** (`runtime/livekit/admission.py`) — acquire a slot keyed by
   target revision (`livekit_max_concurrent_calls` / `_per_target`) before creating a room.
2. **Runner token** — `create_runner_token(runner_id, attempt_id)` (short-lived, attempt-scoped).
3. **Telemetry URL** — `build_stream_url(runner_backend_url, attempt_id, token)` →
   `ws(s)://…/internal/v1/attempts/{attempt_id}/stream?token=…`.
4. **Create room** — `LiveKitRoomManager.create_room("attempt-<id>")`.
5. **Dispatch the caller agent** — `dispatch_agent(room, agent_name=settings.livekit_agent_name,
   metadata=…)`. The job metadata carries **only** `{attempt_id, runner_id, runner_token,
   telemetry_url}` — *never configuration*.

### 4.3 Job entrypoint (what actually runs the call)

`runtime/livekit/job.py`:

- `main()` → `livekit.agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint,
  prewarm_fnc=prewarm, agent_name=settings.livekit_agent_name, ws_url=settings.livekit_url,
  api_key=…, api_secret=…))` — the worker process registers with LiveKit and receives jobs.
- `prewarm(proc)` loads Silero VAD once per worker.
- `entrypoint(ctx)`:
  1. `await ctx.connect()` — joins the caller's own room.
  2. Connects `RunnerWebSocketClient` (telemetry) and registers.
  3. `load_attempt_context(session, attempt_id)` → the `AttemptBundle`.
  4. `prepare_target_link(...)` → resolved link config.
  5. `get_target_link_registry().create(transport, endpoint_config=…, room=ctx.room)` → `link.connect()`.
  6. Builds `LinkConversationRunner` (pipeline + TTS + `AttemptRecording`), `await runner.run()`.
  7. `link.close(RUNNER_SHUTDOWN)`, `recording.finalize()`, `persist_media_records(...)`.

### 4.4 Lifecycle guards

- `watchdog_scan` — reaps dead runner processes for stale attempts.
- `room_reaper_scan` — deletes stale `attempt-*` rooms on our project.
- Terminal handling always deletes the room and releases the admission slot
  (see §8.4).

---

## 5. Configuring a caller

### 5.1 The execution manifest (the source of truth)

At `start_call_run` the control plane freezes an immutable `ExecutionManifest`
(`orchestration/manifest_service.py` → `build_manifest_content`) with snapshots:
`target_snapshot`, `simulation_snapshot`, `run_snapshot`, `evaluator_snapshot`,
`caller_snapshot`, `metric_snapshot`, `judge_snapshot`, `aggregation_snapshot`,
`composite_snapshot`, plus `manifest_hash`. The runner never re-reads mutable config.

`load_attempt_context` (`runtime/loader.py`) reads it into an `AttemptBundle`:

```python
@dataclass(frozen=True)
class AttemptBundle:
    attempt_id; manifest; run_evaluator; call_run
    target_revision; scenario; persona; seed; target_link
```

- `target_snapshot.target_link` → `bundle.target_link` (§6).
- `caller_snapshot.persona_profile` + `seed` → `bundle.persona` (reproducible).

### 5.2 Scenario (`evaluator.v1`)

`build_scenario_from_run_evaluator` parses `RunEvaluator.scenario_config` via
`parse_scenario` (`runtime/scenario.py`):

```
motive.objective, motive.assertions[]{id,type,required,expectation}
facts[]{id,value}
initial_state
behaviour.allowed_actions, behaviour.recovery.max_attempts
stop_conditions, language, persona
```

→ `Scenario(objective, facts, initial_state, assertions, allowed_actions,
max_recovery_attempts, stop_conditions, language, persona)`. Language/persona fall
back to the evaluator's `languages` / `personality`.

### 5.3 Persona

`resolve_persona` prefers the manifest's `persona_profile` (via
`PersonaProfile.from_dict`) for reproducibility, else `PersonaResolver().resolve(...)`.
Resolution order: neutral baseline → trait deltas → scenario overrides → seeded
jitter → clamp. `persona.speaker` (default `"shubh"`) is the Sarvam voice.

### 5.4 Settings / env (`core/config.py`)

- LiveKit: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_AGENT_NAME`,
  `livekit_room_empty_timeout_s`, `livekit_target_room_empty_timeout_s`, room/dispatch timeouts.
- Dispatch: `RUNNER_DISPATCH_MODE`, `runner_backend_url`.
- Admission: `livekit_max_concurrent_calls`, `livekit_max_concurrent_per_target`.
- Caller voice: `SARVAM_API_KEY` (else `DeterministicTTS`).
- `SECRET_ENCRYPTION_KEY` (provider secrets, incl. client-supplied connections).

---

## 6. Connecting to the target agent

### 6.1 Transports (`TargetLink`)

`runtime/livekit/target_links/` — one class per transport, all implementing:

```
connect() · incoming_audio() · send_audio(frame) · send_dtmf(digits) ·
send_control(msg) · events() · close(reason) · capabilities()
```

| slug | class | carries |
|---|---|---|
| `room` | `RoomLink` | WebRTC via a LiveKit room (caller's room, or an external provider room) |
| `sip` | `SipLink` | outbound SIP/PSTN via a LiveKit SIP participant + room media plane |
| `bridge` | `BridgeLink` | provider-protocol WebSocket audio |
| `whip` | `WhipLink` | raw WebRTC (WHIP signaling, `aiortc`) |

Registry: `TargetLinkRegistry` (`registry.py`).

### 6.2 Resolving the link

1. **Manifest build** — `resolve_target_link(session, run.target_revision_id)` reads the
   revision's `agent_endpoint` rows, normalizes each transport via
   `target_link_transport`, picks the first in `TARGET_LINK_PREFERENCE =
   ("sip","room","whip","bridge")`, else the first, else `{"transport":"room"}`. Frozen
   into `target_snapshot.target_link` as `{transport, endpoint_config, endpoint_id}`.
2. **Connect time** — `prepare_target_link(session, raw_link, manifest, target_revision)`
   turns that into a connectable config:
   - **per-call** (`endpoint_config.call_setup == "per_call"`): calls
     `adapter.start_connection(...)` to mint credentials (Vapi `POST /call`; ElevenLabs
     conversation token; LiveKit room+dispatch+caller token). Secrets are resolved
     through `SecretService` and **never frozen into the manifest**.
   - **client-supplied** (`endpoint_config.client_supplied`): pulls the connection's
     secrets from the account (`conn_<name>`) and, for `sip`, provisions the LiveKit
     outbound trunk inline.
   - **static**: passes the frozen config through.

### 6.3 Provider adapters vs client-supplied

- **Provider-backed** targets (retell/vapi/elevenlabs/livekit/pipecat/sip) are handled
  automatically by `AgentProviderAdapter.get_endpoints()` + `start_connection()`
  (`integrations/*`).
- **Client-supplied** connections let the client say *how* to reach an agent:
  `POST /api/v1/targets/{target_id}/connection` with
  `{kind: websocket|webrtc|sip, transport?, config, secrets}` →
  `TargetService.set_connection` writes an `agent_endpoint` (`client_supplied: true`)
  and encrypts secrets as `conn_<name>`. `GET /api/v1/integrations/connectors`
  returns the catalog (which provider supports which kind + field specs).

### 6.4 Capabilities

`link.capabilities()` → `TargetLinkCapabilities(codec, sample_rate, channels,
supports_dtmf, target_speaks_first, provides_monitor_track)`. The recording sample
rate comes from here.

---

## 7. The conversation loop

`LinkConversationRunner` (`runtime/livekit/conversation.py`) is the link-boundary
orchestrator:

- Pumps agent audio: `link.incoming_audio()` → `recording.append_agent(chunk)`.
- Consumes `link.events()`; iterates them into canonical events via
  `CanonicalEventBuilder` and emits them to telemetry.
- Reacts only to completed agent text (`agent.text.final` / `target.transcript.final`)
  → `pipeline.decide(text, assertions=…)` → a `Decision(action, text, language, terminal)`.
- Speaks: `tts.synthesize(SynthesisRequest(text, language, sample_rate))` →
  `recording.append_caller(chunk)` + `link.send_audio(chunk)`, then `link.send_control({"type":"caller.turn.end"})`.
- Terminates on `step.terminal` or `max_agent_turns` (default 32 → `MAX_TURNS`).

Caller TTS (`job._build_tts`): `SarvamBulbulTTS` when `SARVAM_API_KEY` is set, else
`DeterministicTTS` (a fixed-duration tone, for local/test).

---

## 8. Aftermath — what is recorded and where

### 8.1 In-process audio capture

`AttemptRecording` (`runtime/livekit/recording.py`) accumulates two mono PCM tracks
(`caller`, `agent`) via `MediaRecorder` (each immutable, hashed). `finalize()`
returns **three** `MediaArtifactRecord`s:

1. `caller` / `original` — mono, the audio we transmitted;
2. `agent` / `original` — mono, the audio we received;
3. `mixed` / `mixed` — **stereo** (caller=left, agent=right), the human-listenable call.

Chunks at a different rate are resampled to the capture rate before mixing; the
shorter track is zero-padded. Each record is wrapped as a playable `.wav`
(RIFF/WAVE) and carries `sha256`, `size_bytes`, `sample_rate`, `channels`,
`duration_ms`, `clock_domain`.

### 8.2 Object storage + `media_artifact`

`persist_media_records(session, attempt_id, records)` (`runtime/livekit/media.py`):

- Uploads each record to the object store via `store.put(key, data, content_type="audio/wav")`
  with key:

  ```
  media/{attempt_id}/{track}-{representation}-{sha256[:12]}.{ext}
  ```

- Writes one **`media_artifact`** row per representation with `call_attempt_id`,
  `track`, `representation`, `format`, `sample_rate`, `channels`, `duration_ms`,
  `clock_domain`, `object_uri`, `sha256`, `size_bytes`. Commits.

Storage backend is `get_object_store()` (`OBJECT_STORAGE_MODE=local|s3`). Playback
URLs are minted via the storage signing helpers.

### 8.3 Runtime events (the observed record)

Every canonical event from the runner is streamed over the control WebSocket
(`runtime/telemetry.py::RunnerWebSocketClient`) → `realtime/runner_ws.py::RunnerSession`:

- `RuntimeEventIngestor.ingest(envelope)` → append-only **`runtime_event`** row
  (unique per `(call_attempt_id, sequence_no)`; acked back to the runner so it can
  drop the event from its replay buffer).
- `EventMaterializer.materialize(envelope)` builds derived objects — `call_turn`
  (from `turn.*`), `tool_call`, `state_transition` — from `caller.*`/turn events.

Events relevant to the aftermath: `agent.text.final`/`target.transcript.*`,
`turn.*`, `caller.*` (action/state/recovery/terminal), `tool.call.*`,
`connection.*`, `attempt.terminal`.

### 8.4 Terminal handling (status + cleanup)

On `attempt.terminal`, `RunnerSession._apply_terminal` calls
`record_terminal_event` (`orchestration/terminal.py`), which sets the attempt's
`terminal_status` / `termination_reason` / `failure_class` / `eligible_for_evaluation`,
updates the `call_run` (and possibly the `Run`), and returns a `next_attempt_id`
for retries (which is enqueued). Then, **always**:

- delete the LiveKit room (`LiveKitRoomManager.delete_room("attempt-<id>")`) — the
  cross-process hard-cancel that also hangs up any SIP leg;
- release the admission slot.

Attempt/terminal status values: attempt `status ∈ {queued,starting,connecting,running,
terminating,terminal}`; `terminal_status ∈ {completed,failed,timed_out,cancelled}`;
`failure_class ∈ {infrastructure, provider, transport, media, timeout, malformed_stream,
runner_crash, cancelled}`. Call-run `status ∈ {queued,running,completed,
infrastructure_failed,cancelled}`.

### 8.5 Connection session

For provider-backed links with an `endpoint_id`, the job records a
`connection_session` row (`job._start_connection_session` / `_finish_connection_session`):
`connecting → connected (provider_session_id, e.g. a minted room/call id) → terminated`
(or `failed` with `error_message`), plus `started_at`/`connected_at`/`ended_at`.

### 8.6 Media/attempt tables (where things land)

| Table | Holds |
|---|---|
| `call_run` | logical call (status, `selected_attempt_id`, timings) |
| `call_attempt` | physical try (status, terminal_status, failure_class, eligible, versions, timings) |
| `media_artifact` | one row per audio representation + `object_uri` |
| `runtime_event` | append-only canonical event log |
| `call_turn` / `tool_call` / `state_transition` | materialized derived objects |
| `connection_session` | runtime connection lifecycle + provider session id |
| `execution_manifest` | the frozen per-run inputs (incl. `caller_snapshot`) |

---

## 9. Interfaces reference (the extension points)

| Interface | Where | Purpose |
|---|---|---|
| `RunnerDispatcher.dispatch(attempt_id)` | `runtime/dispatch.py` | how an attempt is spawned (subprocess/inline/livekit) |
| `TelemetrySink` (`connect/send_event/heartbeat/next_control/close`) | `runtime/telemetry.py` | runner → backend events + inbound control |
| `TargetLink` (see §6.1) | `runtime/livekit/target_links/base.py` | transport boundary to the target |
| `AgentProviderAdapter` (`get_endpoints`, `start_connection`, `provision_account`, …) | `integrations/base.py` | provider semantics + per-call minting |
| `prepare_target_link(...)` | `runtime/livekit/connection_setup.py` | turn a frozen `target_link` into a connectable config |
| `CallerRuntime` (`start/observe_agent_event/select_action/realize/stream_audio/stop`) | `runtime/caller/runtime.py` | caller brain ↔ framework |
| `CallerDecisionPipeline.decide(text, assertions=…)` | `runtime/caller/pipeline.py` | deterministic turn decision |
| `TTSProvider.synthesize(SynthesisRequest)` | `runtime/providers/base.py` | caller voice |
| `TargetLinkRegistry` / `AgentProviderAdapterRegistry` | `runtime/livekit/target_links/registry.py`, `integrations/registry.py` | resolve by slug |
| `attempt.terminal` event | `runtime/events.py` | the aftermath trigger |

---

## 10. Configuring a caller end-to-end (checklist)

1. Choose a target: provider-backed (create an integration account + target), or a
   client-supplied connection (`POST /targets/{id}/connection`).
2. Ensure the target revision has a resolvable `agent_endpoint` (auto for providers,
   or the client-supplied one).
3. Build a Simulation + Run (evaluator `scenario_config`, languages, personality,
   metrics). The manifest is frozen at call-run start.
4. Set `RUNNER_DISPATCH_MODE=livekit` and the LiveKit + Sarvam settings.
5. Enqueue the run (`execution.run.start`); the dispatcher creates the room, dispatches
   the caller agent, and the job connects the target, runs the loop, records, and
   uploads.
6. Aftermath lands in `media_artifact` (+ object storage), `runtime_event`,
   `connection_session`, and the attempt/run statuses; terminal always cleans up the room.
