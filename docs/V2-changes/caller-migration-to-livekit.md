# VoiceEval Synthetic Caller on LiveKit: Design

Status: draft v1 · Scope: design only, no code · Persona set: 14 traits (see §7)

---

## 0. Summary

The caller becomes a **LiveKit Agents job**: one room and one job process per call attempt. LiveKit's `AgentSession` supplies the audio pipeline (VAD, STT, TTS, playout, interruption mechanics). Everything that makes the caller *behave like a person* lives in a thin layer **we own**:

1. A deterministic conversation brain (the existing scenario state machine and action selector, kept as is).
2. A persona engine that turns a personality enum into timing and behavior parameters.
3. A floor-control and interruption planner that decides when to talk, when to yield and when to barge in.

The LLM only analyzes the target's utterance and phrases the caller's reply. It never picks actions or owns state. This is your existing design rule and it stays.

**Key decisions**

| # | Decision | Why |
|---|---|---|
| D1 | One room + one job process per attempt, explicit dispatch by agent name | Config isolation per session (2–20 different configs), crash isolation, simple cleanup |
| D2 | A `TargetLink` abstraction with three implementations: room participant (WebRTC), SIP participant, protocol bridge (WebSocket / provider-specific) | Caller brain is identical across transports; connectivity differences are confined to adapters |
| D3 | Keep the backend runner WebSocket and the event ingestion/materialization path unchanged | Telemetry, retries and persistence already work; only the producer changes |
| D4 | Take over "when to reply and what to say" from the framework; keep its turn detection and playout as *signals* | Framework default is a helpful assistant that replies after every turn, which is the opposite of a persona |
| D5 | All stochastic behavior comes from a per-attempt seeded RNG, with every draw logged | Evaluations must be reproducible and explainable |
| D6 | The language layer outputs language-tagged segments; the TTS adapter decides how to render them | Isolates the bilingual and Sarvam-specific details |

**What migration to LiveKit does and doesn't fix.** It should fix connectivity (SIP, room-based WebRTC), multi-session management and give you VAD and turn handling out of the box. It does **not** by itself make the caller human. That comes from the behavior layer in §6–§8, which would be needed on any framework. WebSocket and provider-specific WebRTC targets also still need custom adapters.

---

## 1. Goals and constraints

- Caller behaves like a plausible human in timing, interruption, hesitation, emotion and language.
- Caller drives a **scenario objective** and can be asked to probe specific target behaviors (e.g. "does the target handle being interrupted during a confirmation read-back?").
- Single-lingual or bilingual (Indic + English, code-switching) per config, using Sarvam Bulbul TTS streaming.
- Connects to targets over WebRTC, WebSocket or SIP.
- 2–20 concurrent attempts, each with different config.
- Reproducible: same (scenario, persona, seed) gives the same *decisions*. Audio and target responses will still vary.
- The caller is also a **measurement instrument**. Every overlap, yield and latency it produces must be timestamped precisely, because those become evaluation metrics for the target.

Non-goals for v1: video, speech-to-speech realtime LLMs (they remove our control over action selection and the Sarvam voice), caller-side acoustic echo cancellation (the caller listens to the target's track directly, never to a microphone, so it can't hear itself).

---

## 2. What stays, what changes, what is new

Based on your trace of the current system:

| Area | Disposition |
|---|---|
| `CallerRuntime` protocol (`runtime/caller/runtime.py`) | **Stays.** New `LiveKitCallerRuntime` implements it; Pipecat/Controller variants remain as alternates |
| Scenario parsing, `ScenarioState`, `policy`, `ActionSelector`, `LanguageController` | **Stay**, assuming they are framework-independent pure logic (verify, since they were written against the Pipecat/controller loop) |
| Manifest snapshot, `CALLER_POLICY_VERSION`, `ExecutionManifest` | **Stay.** Add the resolved persona profile and seed to the snapshot |
| Runner WebSocket, ingestion, materializer, terminal/retry logic | **Stay** (see §10 for three small cautions) |
| `CallRunner.run` loop over `connection.receive()` | **Shrinks.** `AgentSession` owns the media loop. The runner becomes job entrypoint, lifecycle and telemetry |
| `runtime/media/*` (tts, audio, recorder), Pipecat pieces | **Replaced** by the `AgentSession` pipeline and track recording |
| `runtime/providers/sarvam.py` | **Replaced** by the LiveKit Sarvam plugin, or a thin custom TTS/STT wrapper if the plugin lags the API (§9) |
| Dispatcher (`runtime/dispatch.py`: subprocess/inline) | **New mode `livekit`** alongside the existing two |
| Transport adapters (`runtime/adapters/`) | **Reshaped** into `TargetLink` implementations |
| `integrations/` ↔ `runtime/adapters/` hand-off | **Still needs to be built** and is the main blocker for real provider targets |

New components: `TargetLink` + adapters, `FloorTracker`, `InterruptionPlanner`, `PersonaResolver`, `TurnAnalyzer`, `LiveKitDispatcher`, `FailureClassifier`, heartbeat watchdog (backend).

---

## 3. Architecture

```
 Backend (existing)                               LiveKit
 ┌──────────────────────────────┐   create room   ┌──────────────────┐
 │ ExecutionOrchestrator        │───────────────▶ │ LiveKit server   │
 │  └ LiveKitDispatcher (new)   │   dispatch job  │  rooms / SFU     │
 │ Runner WS /internal/v1/...   │◀── telemetry ───│  SIP service     │
 │ Ingestor → Materializer      │                 │  egress          │
 └──────────────────────────────┘                 └───────┬──────────┘
            ▲                                             │ job assigned
            │ events (existing WS protocol)               ▼
 ┌──────────┴───────────────────────────────────────────────────────────┐
 │ Caller job process (one per attempt)                                  │
 │                                                                       │
 │  L4  Control & telemetry   EventEmitter · stop conditions · recorder  │
 │  L3  Production            SpeechPlanner → TTS (Sarvam) → playout     │
 │  L2  Cognition             ScenarioState · Persona · Policy ·         │
 │                            ActionSelector · InterruptionPlanner ·     │
 │                            LLM (analyze + realize only)               │
 │  L1  Perception            VAD · STT · FloorTracker · TurnAnalyzer    │
 │  L0  TargetLink            room participant | SIP | protocol bridge   │
 └──────────────────────────────────────────────────────────────────────┘
                                   │ audio
                                   ▼
                      Target agent (any provider)
```

Control flow per target utterance: **L1** detects speech and end of turn → **L2** analyzes it, updates state, selects an action, and the planner decides timing → **L3** phrases and speaks it → **L4** emits events.

---

## 4. Call lifecycle and connectivity

### 4.1 Dispatch flow (all transports)

1. Orchestrator creates the attempt and the room (`attempt-<id>`, short empty timeout, participant cap).
2. Dispatcher issues an **explicit agent dispatch** (named agent, so the caller job never auto-joins arbitrary rooms). Job metadata carries only `attempt_id` and a short-lived `runner` token. The job fetches the scenario and manifest from the backend; metadata is not a config channel.
3. Job starts, connects the runner WebSocket, sends `runner.register`. The dispatcher waits for this with a timeout. No registration means infra failure and retry.
4. Job builds persona, resolves seed, warms TTS and STT connections, loads `TargetLink`.
5. Job calls `TargetLink.connect()`. This is the only transport-specific step.
6. On answer / first audio, the lifecycle machine moves to conversing.
7. On any terminal state the job emits `attempt.terminal`, flushes telemetry, and the dispatcher **always deletes the room** (this also hangs up any SIP leg). A reaper sweeps `attempt-*` rooms older than max duration plus grace.

### 4.2 Transports

| Target type | `TargetLink` | How audio flows | Notes |
|---|---|---|---|
| Target is a LiveKit participant (same project) | RoomLink | Both in the same room; framework room I/O | Simplest path. Target agent dispatched explicitly by us if we own it |
| Target on a different LiveKit server | RoomLink (external) | Caller opens a second connection to the target's URL with a supplied token | Needs custom I/O, since `ctx.room` belongs to our project |
| Phone number / SIP URI | SipLink | Outbound SIP participant created through the outbound trunk | Needs a third-party SIP trunk provider; LiveKit-provided numbers don't support outbound. Narrowband audio, DTMF available |
| WebSocket audio target (generic, Twilio-style media streams, provider sockets) | BridgeLink | Adapter speaks the target's protocol, converts codec and sample rate, and exposes audio in/out to the session through custom audio input/output | Reuses `adapters/websocket.py` and `fake.py` ideas |
| Provider WebRTC not based on LiveKit (e.g. Daily-style) | BridgeLink | Provider SDK or an aiortc-style client behind the same adapter contract | Check per provider. Some providers hand out LiveKit-compatible join tokens, which makes them RoomLink |

**Adapter contract** (small on purpose): `connect` · `incoming_audio()` · `send_audio(frame)` · `send_dtmf(digits)` · `events()` (provider-native events passed through as `provider_raw` / `provider_normalized`) · `close(reason)` · `capabilities` (codec, sample rate, supports DTMF, target speaks first?).

**For BridgeLink, the room still exists.** The job publishes the target's audio into the room as a monitor track. This keeps recording, live listen-in and egress uniform across all transports. Metrics are computed in-process at the audio boundary, never from the egress copy.

**Who speaks first.** On outbound calls the callee normally greets first, so the caller waits and only prompts ("hello?") after a persona-dependent greeting timeout.

### 4.3 SIP specifics

- Dispatch the caller first, dial second. The target's greeting must not play to an empty room.
- Watch the SIP participant's call status and the SIP status code on failure. Map them: busy, no answer, declined, unreachable, trunk auth failure are different terminal reasons (§4.5).
- Handle non-speech audio: ringback, hold music and IVR prompts keep VAD "speaking" continuously. The `FloorTracker` needs a **non-speech/music/hold classifier** (STT confidence and content plus audio-activity pattern) so these don't count as turns or false interruptions.
- Voicemail detection is a lifecycle branch, not a conversation.
- Check telephony regulations for your region before running outbound PSTN tests; provider-side WebRTC/WebSocket paths avoid most of this.

### 4.4 Connection state machine (macro lifecycle)

```
INIT → DISPATCHED → REGISTERED → DIALING/CONNECTING → RINGING ─▶ ANSWERED
                                                                   │
                         ┌─────────────── IVR_NAVIGATION ◀─────────┤ (optional)
                         │                                         │
                         └──────────────▶ CONVERSING ◀─────────────┘
                                              │
                                  CLOSING (goodbye) → ENDED
Failure exits from any state: NO_ANSWER · BUSY · REJECTED · VOICEMAIL ·
TARGET_SILENT · TRANSPORT_LOST · TARGET_HUNG_UP · TIMEOUT · CANCELLED · INTERNAL_ERROR
```

Every phase has its own timeout (dispatch, register, dial, ring, first audio, conversation stall, wall clock). Existing `conversation_stall_ms` and `wall_clock_timeout_ms` map to the last two.

### 4.5 Failure taxonomy: infra failure vs. target outcome

This distinction matters most for an evaluator, because retries should only happen for failures that are not the target's fault.

| Class | Examples | Action |
|---|---|---|
| Infrastructure | dispatch/registration timeout, trunk auth failure, transport lost with no target-side end event, our STT/TTS hard failure, job crash | Retry via existing retry policy (`max_attempts_per_run`) |
| Environment/degraded | high packet loss, STT confidence collapse | Complete, but flag attempt as **degraded** so evaluators don't blame the target |
| Target outcome | no answer, busy, declined, hung up mid-call, silent after greeting, loops, voicemail | Valid result; recorded, not retried |

Attempts are **not resumable**. If the job dies, the attempt is an infra failure and a new attempt is created (see sequence caveat in §10).

---

## 5. Perception layer (L1)

- **VAD** on the target's audio (Silero via the framework). Loaded once per worker process at prewarm.
- **STT** on the target's audio only. Streaming with interim results; interim text feeds early analysis and barge-in decisions.
- **End-of-turn signals**: VAD silence plus the framework's semantic turn detector, with persona-tuned endpointing delays. Indic-language coverage of the turn detector model is unverified, so test early. Fallback: VAD plus fixed endpointing plus STT end-of-speech.
- **FloorTracker** (ours): fuses the above into the floor state (§8.1) and keeps per-turn stats: words so far, speech duration, pauses, estimated completeness.
- **TurnAnalyzer** (ours): produces a structured reading of the target's utterance: is it a question, a request for a fact (which one), a confirmation request, a disclaimer or monologue, a repeat of an earlier message, an error or apology, hold/transfer/closing. Runs on debounced interim text while the target is still talking, so the result is ready by end of turn. Rules handle common cases; a small LLM structured call handles the rest.
- **Quality probes**: connection stats (loss, jitter, RTT) and STT confidence feed the degraded flag.

---

## 6. Conversation brain (L2)

### 6.1 Three state machines, deliberately separate

1. **Call lifecycle** (§4.4): transport-level.
2. **Floor state** (§8.1): who is speaking right now; changes in tens of milliseconds.
3. **Scenario and persona state**: what the caller is trying to achieve and how it feels.
   - Scenario: objective progress, facts revealed/withheld, assertions, `initial_state`, mutations (existing `ScenarioState.apply`).
   - Persona dynamics: `irritation` (0–1), `patience_budget`, `engagement`. Triggers raise or lower them: the target repeating itself, long silences, wrong answers, being put on hold, being asked to repeat. They decay over time.

### 6.2 Decision pipeline per target turn

```
interim/final text ─▶ TurnAnalyzer ─▶ ScenarioState.apply ─▶ PersonaDynamics.update
                                                                   │
        ActionSelector (deterministic, allowed_actions) ◀──────────┘
                  │ action + constraints
                  ▼
        InterruptionPlanner / timing (§8)  ─▶  Realizer (LLM) ─▶ validator ─▶ speech
```

**Actions** (subset enabled per scenario via `allowed_actions`): answer, provide fact, ask question, confirm, deny, request repeat, clarify, change topic, express frustration, escalate (ask for a human), stay silent, send DTMF, wait on hold, switch language, interrupt, end call.

### 6.3 The LLM's two bounded jobs

- **Analyze**: structured output only, no free text to the caller.
- **Realize**: given the action, persona style card, language plan, the *facts allowed this turn* (never the full fact sheet) and recent turns, write the utterance. Streamed straight into TTS.
- **Output validator** before speech: length cap, language check, no forbidden facts revealed, no breaking character ("as an AI..."). One regeneration, then a template fallback.

### 6.4 How the framework is used

- Keep from the framework: audio I/O, VAD, STT/TTS plumbing, playout tracking, per-speech interruptibility, explicit speech calls, interrupt calls.
- Take over: the default behavior where every completed user turn triggers a reply. Intercept at the "user turn completed" point (or use manual turn control), route to the decision pipeline, and speak only when the pipeline says so. Exact hook names vary by SDK version, so confirm against the pinned version in the spike.
- Pin the SDK version. Turn handling options have changed across 1.x releases.

---

## 7. Persona system

The 14 personas (Supportive, Concise, Verbose, Abusive, Interruptor, Impatient, Confused, Skeptical, Cooperative, Uncooperative, Hesitant, Repetitive, Emotional, Demanding) are treated as **composable traits**, not mutually exclusive archetypes. Each trait is a set of deltas on the parameter groups below. A caller carries **1 to 3** traits.

A persona is a resolved, versioned profile of orthogonal parameters, snapshotted into the manifest:

| Group | Parameters |
|---|---|
| Voice | speaker, pace, base loudness |
| Temperament | patience, irritability, agreeableness, hostility ceiling |
| Turn-taking | response latency distribution, endpointing delay, `overlap_tendency`, `yield_threshold`, `floor_hold_cap`, barge-in triggers enabled |
| Speech style | utterance length, disfluency/filler rate, formality, backchannel rate |
| Cooperation | gives info freely / only if asked twice / evasive / changes mind |
| Cognition | mishears or asks to repeat at some rate, goes off-topic at some rate |
| Language | primary, secondary, mixing mode (none / code-switch / alternating), switch triggers |
| Environment | quiet / street / call-centre / car ambient; line quality |

Resolution order: **enum default profile → scenario overrides → seeded jitter**. Jitter keeps every call from sounding identical while remaining reproducible.

**Trait mapping.** Traits fall on three axes: *stance* (how it treats the target), *style* (how it talks) and *turn-taking* (how it handles the floor).

| Axis | Trait | Behavior deltas | What it stresses in the target |
|---|---|---|---|
| Stance | Supportive | Agreeable, thanks and encourages ("take your time"), warm backchannels, yields fast, irritation gain very low | Baseline happy path; checks the target doesn't over-talk a friendly caller |
| Stance | Cooperative | Gives requested facts promptly, follows instructions, confirms readily | Baseline task completion |
| Stance | Uncooperative | Withholds facts until asked 2+ times, answers off-target, pushes back on the process | Persistence, alternate flows, graceful failure |
| Stance | Skeptical | Challenges claims, "are you sure?", asks for proof, withholds sensitive facts until justified, re-asks to test consistency | Verification flows, consistency, honesty about limits |
| Stance | Demanding | States requirements and deadlines, rejects the first offer, insists on outcomes, asks for a manager | Boundary-holding, policy adherence, escalation handling |
| Stance | Abusive | Irritation gain very high, rude and sarcastic, profanity only if configured, rarely yields, demands escalation | De-escalation, policy compliance, not retaliating |
| Style | Concise | One short sentence, answers only what was asked, low filler | Slot filling from minimal input |
| Style | Verbose | Long utterances, extra detail, tangents, holds the floor | Extraction from long turns; target must not cut it off or lose the point |
| Style | Hesitant | Long mid-sentence pauses, fillers, self-corrections, trailing off, high-variance latency, yields at once | Target endpointing: does it cut in during pauses? |
| Style | Repetitive | Restates the same point or question several times, loops back | Consistent answers; target must not loop or lose patience |
| Style | Confused | Asks to repeat or clarify, misunderstands and restates wrongly, partial info, slow latency | Clarification and rephrasing ability |
| Style | Emotional | Affect swings (anxious, upset, happy) shown in wording, pace and pauses; may code-switch when upset | Empathy handling, escalation triggers |
| Turn-taking | Interruptor | High overlap tendency, early-answer barge-in, competitive overlap, long floor-hold cap | Barge-in handling, recovery after being cut off |
| Turn-taking | Impatient | Short endpointing delay and latency, low monologue patience, early "get to the point", small patience budget | Latency tolerance, brevity of the target's turns |

**Composition rules**

- **At most 3 traits per caller**, enforced at config validation.
- **Contradictory pairs are rejected at config validation:** Concise + Verbose, Cooperative + Uncooperative, Supportive + Abusive, Interruptor + Hesitant.
- Traits have no intensity levels. Each is applied at its fixed strength: the deltas are added to a neutral baseline (a plain, mildly cooperative adult) and clamped. Seeded jitter is applied last.
- For evaluation matrices, run **single-trait baselines first**, then combinations, so a failure can be attributed to a trait.
- Two details specific to this set: the caller's own Repetitive behavior must be excluded from the loop-detection stop condition (§8.5), which only watches the target; and Hesitant/Emotional pauses *inside* an utterance are planned by the speech planner (§9.4), because the caller must not end its own turn during a planned pause.

Parameter values for each trait are **starting points to tune by listening tests**, not measured values.

**Hostility guardrail.** Abusive (and Demanding or Impatient) simulate difficult customers within a defined ceiling: rude, sarcastic, insulting in a generic way, with profanity only when the scenario enables it. No slurs, threats of violence or harassment of protected groups. The ceiling is a persona parameter and the output validator enforces it.

---

## 8. Turn-taking and interruption (core)

### 8.1 Floor model

States: `SILENCE`, `TARGET_SPEAKING`, `CALLER_SPEAKING`, `OVERLAP`, `TARGET_PAUSED` (gap inside a target turn), `CALLER_PLANNING`.

Inputs: target VAD, interim transcript, end-of-turn probability, caller playout position.

Floor events emitted: `floor.taken`, `floor.yielded`, `overlap.start`, `overlap.end`, `barge_in.attempted`, `barge_in.succeeded`, `barge_in.ignored`.

### 8.2 When the target interrupts the caller (caller yields)

- Yield if the target speaks ≥ `min_duration` **and** ≥ `min_words` (STT-confirmed), scaled by persona `yield_threshold`.
- Short noise or a one-word "okay" from the target is a **false interruption**: pause, then resume if the target goes quiet within the timeout.
- Hold-the-floor personas speak with interruptions disabled for the first N seconds of an utterance, then re-enable.
- After yielding, the caller's context contains only the words **actually played** plus an interrupted marker, using the playout-aligned text. This maps naturally to `reference_text` (intended) vs `observed_text` (played) on the materialized turn.
- Then a persona-dependent choice: respond to what the target said, repeat/resume, or abandon the sentence.

Adaptive (model-based) interruption handling is a LiveKit Cloud-hosted feature. Self-hosted setups fall back to VAD-based interruption. For this use case that is acceptable: its main benefit is filtering a *user's* backchannel, and target agents rarely backchannel. (This is an inference; confirm in testing.)

### 8.3 When the caller interrupts the target (barge-in)

The framework models users interrupting the agent, not the reverse, so this is our logic. Triggers, all rule-based and persona-gated:

| Trigger | Condition |
|---|---|
| Monologue impatience | Target turn exceeds `patience_ms` (scaled by irritation) |
| Early answer | Analyzer says the question is already complete and end-of-turn probability is high; start with a negative gap |
| Repetition / redundancy | Target asks something already answered, or repeats a disclaimer |
| Scripted test | Scenario asks for a barge-in at a specific point (after N words, during a confirmation read-back, during a specific state) |
| Emotional | Irritation above threshold |

**Mechanics**
- Choose the cut-in point at a clause boundary when word timing is available; otherwise approximate from interim transcript arrival.
- Overlap modes: **cooperative** (short interjection), **competitive** (hold the floor until the target stops), **cut-off** (take the floor, don't relent).
- `floor_hold_cap` bounds how long the caller talks over the target before yielding or escalating.
- **Self-interruption suppression (critical).** While the caller talks over the target, the target's audio looks like user speech to the framework and would cut the caller off. Overlapping speech must therefore be spoken with interruptions disabled for that speech item (the framework supports per-speech control), then re-enabled.
- **Observation window.** After every barge-in, measure and log: time for target to stop, whether it resumed, whether it ignored us, whether it talked over us. These are the evaluation metrics.

### 8.4 Backchannels and fillers

- **Backchannels** ("hmm", "okay", "haan") use short pre-synthesized, cached clips per speaker and language; no TTS round-trip. **Off by default in strict-eval scenarios**, because they can cause the target to stop speaking and contaminate the result. Enable when the scenario tests exactly that.
- **Fillers** mask slow generation: if planning exceeds a threshold, play a cached filler first. Rate is persona-controlled; never exceed a cap.

### 8.5 Silence and stall handling

- Escalating prompts if the target goes silent ("hello?", "are you there?"), then hang up when the persona's patience budget is exhausted.
- Distinguish silence from target thinking using persona thresholds. Target tool-call latency is unobservable from outside.
- **Hold/IVR substate**: no replies while the target is detected as playing hold music or an IVR menu; DTMF as needed; patience budget still drains.
- **Loop detection**: target repeats the same message N times → end with a "loop" outcome.

### 8.6 Timing

- Response latency = max(technical readiness, persona-sampled latency). The caller must **never respond faster than the persona's floor**, and the sampled delay is applied deliberately.
- Longer, more variable pauses for hard questions; shorter for yes/no.
- Endpointing delay per persona: patient personas wait longer after the target stops, impatient ones less. Prefer semantic end-of-turn detection to avoid answering inside a target's mid-sentence pause (a common source of robotic or rude behavior).
- Optional speculative generation may be used later, but only for the *realization* of the predicted action, discarded if the target keeps talking.

### 8.7 Determinism and explainability

Per-attempt seed drives every random choice (latency draw, filler use, barge-in jitter, persona jitter). Each decision is logged with its inputs and draws (`caller.decision` events carrying trigger, draw values, chosen action). A failed evaluation can be explained and replayed at the decision level.

---

## 9. Speech production and bilingual behavior (L3)

### 9.1 Language layer

Config: `primary`, optional `secondary`, `mixing` (none / code-switch / alternating), `mix_ratio`, `switch_triggers`.

`LanguageController.realize` outputs **language-tagged segments**: `[(text, lang)]`. The TTS adapter either renders them as one call (if the model handles mixed text well) or as consecutive calls with the **same speaker**. Voice identity stays consistent across languages.

Switch triggers: the target asks for another language, the target replies in the wrong language, or persona-driven (e.g. emotional code-switch). "Does the target answer in the caller's language?" is a first-class assertion.

### 9.2 STT for bilingual

- Single-lingual: fixed language code.
- Bilingual: auto-detect or code-mix mode (the Sarvam docs show a language-unknown setting for the Saaras STT). Test accuracy on code-mixed speech and on 8 kHz telephony audio specifically.

### 9.3 Sarvam TTS: facts and risks (verified against docs and issues, Oct 2026)

- LiveKit's plugin docs recommend `bulbul:v3` and say to set the target language code explicitly.
- The API accepts **`bulbul:v4-flash`**, not `bulbul:v4`. A plugin PR adds `v4-flash`; **check that your pinned plugin version includes it**. If not, wrap Sarvam's streaming API in a small custom TTS adapter.
- Streaming supports only 8000, 16000, 22050 and 24000 Hz. Higher rates are REST-only. Use 24 kHz for WebRTC and 8 kHz for narrowband SIP to avoid pointless resampling.
- `pace` valid range differs by model. Validate at config time, not at call time.
- Reported issues: intermittent unrecoverable streaming errors, and a WAV-codec issue (raw PCM returned without a header). Use PCM or MP3 as appropriate and **do not rely on the WAV container path**.
- **Resilience plan**: wrap TTS in a fallback adapter (streaming → REST sentence-chunked → alternate provider for the same language). Warm the connection before the first utterance. An utterance that fails mid-stream is emitted as `caller.tts_error` and retried once.
- **Check Sarvam plan limits on concurrent streaming connections**: 20 simultaneous calls is within what you plan to run.

### 9.4 Production polish

- Pace and prosody come from persona; avoid extremes.
- Intra-utterance pauses (Hesitant, Emotional) are planned by the speech planner as silence between segments, not left to the TTS.
- Optional ambient audio (street, office, car) mixed into the caller's outgoing audio for realism and robustness testing; this is an `environment` setting, separate from personality.
- Optional narrowband encoding to mimic phone lines when the transport isn't SIP.

---

## 10. Telemetry and event mapping

Keep the runner WebSocket protocol and the append-only ingestion/materialization path exactly as is. Map the session's events to canonical events:

| Source | Canonical |
|---|---|
| Target speech start/end (VAD) | `target.speech.start/end` (with media timestamp) |
| Interim/final transcript | `target.transcript.interim/final` |
| Caller speech created / playout started / finished | `turn.start` / `turn.end` (intended vs played text) |
| Caller agent-state changes | `caller.state.*` (meaningful states only) |
| False interruption | `caller.false_interruption` |
| Floor events | `floor.*` |
| Decision log | `caller.decision` |
| STT/TTS/LLM latency metrics | metric events |
| Provider-native events (BridgeLink) | `provider_raw` / `provider_normalized` with `provider_event_id` for dedup |
| Terminal | `attempt.terminal` with failure class (§4.5) |

**Three cautions from the pasted backend code**

1. **Every event type starting with `caller.` is materialized into a state transition** (`EventMaterializer.materialize`). Don't emit high-frequency or purely informational events under that prefix, or the state-transition table will bloat. Use `floor.*`, `target.*`, `metric.*` for those. Consider moving `caller.decision` to its own prefix.
2. **Ingestion drops any event whose sequence number repeats within an attempt.** Safe for at-least-once resend, but a restarted runner that resets its counter would have its events silently discarded. Use a single monotonic sequence allocator per attempt, with a bounded local buffer that replays unacknowledged events after a WebSocket reconnect. Never resume an attempt in a new process.
3. **No dead-runner detection.** The WebSocket handler acknowledges heartbeats but nothing times out a silent runner. A crashed job would leave the attempt hanging until the wall-clock limit. Add a backend heartbeat watchdog that classifies it as an infra failure and triggers retry.

Also note: the connection registry used for cancel/terminate is process-local. If the API runs multiple processes, a cancel request may reach a process the runner isn't connected to. Use room deletion through the LiveKit API as the cross-process hard-cancel path, with `attempt.cancel` over the WebSocket as the graceful path (say goodbye, then end).

Timestamps: record `monotonic_ms` at the audio boundary, relative to attempt start, and fill `media_timestamp` for alignment against recordings. Keep per-track recordings (target and caller separated) for post-hoc overlap analysis.

---

## 11. Scale and operations (2–20 concurrent)

- One job process per attempt, so each attempt has its own persona, language, TTS and STT config; a crash in one doesn't affect others.
- Sizing rule of thumb from LiveKit's docs: a 4-core / 8 GB agent server handles roughly 10–25 concurrent jobs depending on components. For 20 concurrent, plan **two workers** rather than one, and prewarm VAD and turn-detector models per process. Local VAD inference across many calls is CPU-bound in Python, so scale by processes.
- Use a custom load function based on active jobs. A known issue: worker load updates lag by about half a second, so two near-simultaneous dispatches can both land on a worker meant to be capped. Stagger dispatch from the backend queue or accept a small overshoot.
- **Admission control in the orchestrator** (the real bottleneck is usually outside LiveKit):
  - per-target concurrency (a target agent may support few simultaneous calls)
  - per-SIP-trunk channel and call-rate limits
  - Sarvam concurrent stream limits
  - LLM provider rate limits
- Idempotent dispatch: the attempt's DB state guards against double start on retry.
- Observability: per-attempt trace of lifecycle phases with timings; dashboards for time-to-register, time-to-answer, TTS error rate, degraded-attempt rate.
- Cost levers: cached backchannels/fillers, small model for analysis, streaming realization.

---

## 12. Testing and validating "human-like"

| Layer | How |
|---|---|
| Brain and state machines | Pure unit tests with a fake clock and scripted target text. Run the whole policy at text speed with audio disabled |
| Floor/interruption logic | Replay recorded target audio traces through VAD + FloorTracker; assert event sequences |
| End to end | Deterministic fake target (existing `fake` adapter) plus a reference LiveKit agent; golden decision traces per (scenario, persona, seed) |
| Transports | One real target per transport (room, SIP, WebSocket) in CI-lite smoke runs |
| Concurrency | Soak test at 20 concurrent mixed personas; watch worker load, TTS errors, event loss |
| Humanness | Distribution checks (response latency, overlap rate, utterance length, filler rate) against targets set per persona, plus blind listening tests comparing builds |
| Regression | Version the persona profiles and policy; any change bumps the policy version recorded in the manifest |

---

## 13. Risks and open questions

**Risks**

1. Sarvam streaming reliability and plugin lag behind the API (§9.3). Mitigation: fallback adapter and a spike.
2. Semantic turn-detector coverage for Indic languages is unverified. Fallback: VAD-based endpointing.
3. Talk-over mechanics (§8.3) depend on per-speech interruption control behaving correctly under noisy VAD. Spike first.
4. Hold music, IVR and ringback confusing perception on SIP.
5. Provider-specific WebRTC and WebSocket targets: each adapter is real engineering, and adapter count drives schedule.
6. Pre-existing gap: provider integrations return empty endpoints, so no real target can be called until the hand-off is built.
7. Self-hosted vs. LiveKit Cloud: affects adaptive interruption, SIP and egress availability and operations.

**Open questions for you**

1. Which target providers, in priority order, and which transport each exposes.
2. LiveKit Cloud or self-hosted LiveKit? Which SIP trunk provider?
3. Which LLM for analyze/realize (latency matters more than quality for analysis)?
4. May the caller ever admit to being an AI (scenario-level override)?
5. Recording and consent requirements for the calls and the stored audio.
6. Maximum hostility level you want for the harshest persona.

---

## 14. Migration plan

0. **Spike (~1 week):** test Sarvam bilingual STT/TTS in `AgentSession` (incl. 8 kHz), caller talk-over without self-cut-off, and one outbound SIP call.
1. **Core caller:** `LiveKitCallerRuntime`, dispatcher, lifecycle machine, room and SIP links, event mapping, failure classifier, heartbeat watchdog, one simple persona.
2. **Behavior:** floor tracker, interruption planner, persona resolver, turn analyzer, seeded decision log, backchannels/fillers, full persona set.
3. **Bridges:** WebSocket and provider-specific adapters, plus the `integrations/` → adapter hand-off.
4. **Scale:** admission control, 20-call soak test, humanness tuning.

Keep the Pipecat runtime selectable until phase 2 passes the humanness checks.

---

## Sources

- LiveKit turn handling options and interruption tuning: https://docs.livekit.io/agents/logic/turns/tuning/ · https://docs.livekit.io/reference/agents/turn-handling-options/
- Adaptive interruption (LiveKit Cloud only): https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling.md · https://livekit.com/blog/turn-detection-and-interruption-handling
- Agent speech (per-speech interruptions, `say`, `generate_reply`): https://docs.livekit.io/agents/multimodality/audio/
- Self-hosted deployment, load balancing, prewarm: https://docs.livekit.io/deploy/custom/deployments.md · https://docs.livekit.io/agents/server/options.md
- Load threshold lag issue: https://github.com/livekit/agents/issues/4884
- Outbound SIP: https://docs.livekit.io/telephony/making-calls/outbound-calls.md · https://docs.livekit.io/agents/quickstarts/outbound-calls/ · https://docs.livekit.io/telephony/testing/
- Track egress to WebSocket: https://docs.livekit.io/transport/media/ingress-egress/egress/track.md
- Sarvam TTS plugin: https://docs.livekit.io/agents/models/tts/sarvam.md · v4-flash PR https://github.com/livekit/agents/pull/7335 · param/sample-rate issue https://github.com/livekit/agents/issues/6774 · WAV issue https://github.com/livekit/agents/issues/5267 · streaming error report https://github.com/livekit/agents/issues/5620
- Sarvam + LiveKit STT/TTS example: https://docs.sarvam.ai/api/integration/build-voice-agent-with-live-kit