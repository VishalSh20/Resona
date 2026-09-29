# VoiceEval — Runtime/Event Schema v0.3 (Strengthened)

## 1. Runtime principle

The runtime has four evidence layers:

```text
1. Raw provider events
2. Canonical normalized events
3. Derived events
4. Evaluation evidence
```

Never destroy layer 1 when creating layer 2.

---

## 2. Canonical event envelope

```json
{
  "event_id": "evt_01J...",
  "call_attempt_id": "att_01J...",
  "sequence": 184,
  "type": "agent.audible.start",
  "source": "derived",

  "monotonic_ms": 12420,
  "wall_clock": "2026-09-29T12:35:22.420Z",
  "media_timestamp": 918273,

  "turn_id": "turn_17",

  "payload": {},
  "provider_event_id": "abc-123"
}
```

Required:

```text
event_id
call_attempt_id
sequence
type
source
monotonic_ms
wall_clock
payload
```

Optional:

```text
media_timestamp
turn_id
provider_event_id
```

---

## 3. Event source classes

```text
provider_raw
provider_normalized
runtime
derived
caller
metric
```

Example:

```text
provider_raw:
  exact provider websocket message/event

provider_normalized:
  canonical event created by adapter

derived:
  VAD-derived `agent.audible.start`

caller:
  synthetic caller state/action event
```

---

## 4. Connection events

```text
connection.requested
connection.signaling.start
connection.signaling.offer
connection.signaling.answer
connection.ice.candidate
connection.ice.connected
connection.ready
connection.warning
connection.error
connection.closed
```

For WebSocket:

```text
connection.ws.open
connection.ws.message
connection.ws.error
connection.ws.close
```

For WebRTC:

```text
connection.rtc.peer_created
connection.rtc.ice_state_changed
connection.rtc.connection_state_changed
connection.rtc.track_received
```

WebRTC requires signaling outside the WebRTC API and commonly relies on STUN/TURN through ICE for peer connectivity. citeturn826333search0turn826333search2

---

## 5. Media events

### Caller

```text
caller.media.start
caller.media.chunk
caller.media.end

caller.speech.start
caller.speech.end
caller.audible.start
caller.audible.end
```

### Agent

```text
agent.media.start
agent.media.chunk
agent.media.end

agent.speech.start
agent.speech.end
agent.audible.start
agent.audible.end
```

Do not equate `media.start` and `audible.start`.

---

## 6. Text events

```text
agent.text.first
agent.text.delta
agent.text.final
```

Optional caller-side observations:

```text
caller.transcript.observed
caller.language.detected
```

---

## 7. Turn events

```text
turn.start
turn.end
turn.interrupted
turn.overlapped
```

A turn is a derived semantic object and may be revised after late-arriving provider events.

Therefore:

```text
raw events = append-only
turn materialization = rebuildable
```

---

## 8. Language events

```text
caller.language.detected
caller.code_switch.detected

agent.language.detected
agent.code_switch.detected
```

Example:

```json
{
  "type": "caller.code_switch.detected",
  "payload": {
    "from": "hi",
    "to": "en",
    "segment_ms": [6400, 8120],
    "confidence": 0.93
  }
}
```

---

## 9. Tool events

```text
tool.call.start
tool.call.args
tool.call.result
tool.call.end
```

Example:

```json
{
  "type": "tool.call.end",
  "payload": {
    "tool_name": "unblock_card",
    "status": "succeeded",
    "duration_ms": 912
  }
}
```

---

## 10. Caller decision events

```text
caller.state.initialized
caller.action.selected
caller.utterance.realized
caller.interruption.scheduled
caller.recovery.used
caller.assertion.updated
caller.terminal
```

Example:

```json
{
  "type": "caller.action.selected",
  "payload": {
    "action": "correct_misunderstanding",
    "state_version": 17,
    "recovery_count": 1
  }
}
```

---

## 11. State versioning

Every caller state has a version:

```text
state_version = 0
      ↓
state_version = 1
      ↓
state_version = 2
```

Store state transitions rather than only the final state.

Example:

```json
{
  "state_version": 7,
  "patch": [
    {
      "path": "/authenticated",
      "from": false,
      "to": true
    }
  ]
}
```

This helps explain why a caller selected a later action.

---

## 12. Call turn schema

```json
{
  "id": "turn_17",
  "call_attempt_id": "att_01J...",
  "sequence_no": 17,

  "speaker": "caller",

  "start_ms": 12420,
  "end_ms": 15810,

  "reference_text": "Mera card block ho gaya hai",
  "observed_text": null,

  "reference_language_profile": {
    "dominant": "hinglish",
    "languages": ["hi", "en"]
  },

  "observed_language_profile": null,

  "transcript_source": "caller_reference",
  "transcript_confidence": 1.0,

  "reference_audio_artifact_id": "media_...",
  "observed_audio_artifact_id": null
}
```

For an agent turn:

```json
{
  "speaker": "agent",
  "reference_text": null,
  "observed_text": "Sure, I can help you replace the card.",
  "transcript_source": "provider"
}
```

---

## 13. Transcript provenance

```text
caller_reference
provider_target_input
provider_target_output
independent_asr
human
unknown
```

This resolves the WER ambiguity.

### Correct interpretation

```text
agent_input_wer
=
compare caller reference
against target agent's exposed input transcript
```

If target input transcript is unavailable:

```text
agent_input_wer = NOT_AVAILABLE
```

An independent ASR can produce:

```text
independent_asr_wer
```

but that must never be renamed to target-agent WER.

---

## 14. Media artifact

```json
{
  "id": "media_01J...",
  "call_attempt_id": "att_01J...",
  "track": "agent",
  "representation": "original",

  "format": "webm",
  "codec": "opus",
  "sample_rate": 48000,
  "channels": 1,

  "duration_ms": 183420,
  "clock_domain": "media",

  "object_uri": "s3://voiceeval/...",
  "sha256": "...",
  "size_bytes": 9384721
}
```

Possible representations:

```text
original
analysis
clip
mixed
```

Original artifacts are immutable.

---

## 15. Audio clock model

Store:

```text
runner monotonic timestamp
media/RTP timestamp when available
wall-clock timestamp
```

Never assume those clocks are identical.

For WebRTC, RTP timestamps are part of the media timing information exposed by the WebRTC stack. citeturn826333search1

---

## 16. TTFA event sequence

Ideal timeline:

```text
caller.audible.end       8200 ms
        ↓
target processing
        ↓
agent.media.start        8810 ms
agent.audible.start      8920 ms
```

Then:

```text
TTFA = 8920 - 8200 = 720 ms
```

The `agent.audible.start` event should be derived using the configured audio activity detector.

---

## 17. TTFT event sequence

```text
caller.audible.end       8200 ms
agent.text.first         8680 ms
```

Then:

```text
TTFT = 480 ms
```

Only compute this if the target text stream is actually exposed.

---

## 18. Interruption event sequence

```text
agent.audible.start      12000 ms
caller.speech.start      15000 ms
agent.audible.end        15310 ms
```

Then:

```text
interruption_latency = 310 ms
```

The evaluator should additionally record:

```json
{
  "interruption_detected": true,
  "agent_stopped": true,
  "caller_continued": true
}
```

---

## 19. Ordering guarantees

Within an attempt:

```text
sequence strictly increases
```

`monotonic_ms` is:

```text
non-decreasing
```

But late provider events may arrive after later events.

Therefore processing should use:

```text
append-only raw event log
+
normalization/materialization step
```

Never make the database row order itself the source of truth.

---

## 20. Deduplication

When a provider has stable event IDs:

```text
UNIQUE(source, provider_event_id)
```

When it does not:

use an adapter-specific deduplication strategy such as:

```text
event type
timestamp bucket
payload hash
sequence/window context
```

Do not assume provider event IDs exist.

---

## 21. Runtime terminal event

Every attempt has exactly one terminal runtime event:

```json
{
  "type": "attempt.terminal",
  "payload": {
    "status": "completed",
    "termination_reason": "NATURAL_SUCCESS"
  }
}
```

This event is immutable after finalization.

---

## 22. Runtime invariants

1. Raw provider evidence is append-only.
2. Canonical events are rebuildable from raw evidence where possible.
3. Event sequences never repeat within an attempt.
4. Media artifacts are immutable.
5. A logical run cannot produce multiple aggregate samples.
6. A retry creates a new attempt, not a new repetition.
7. Missing events are explicit.
8. Timestamps always declare their clock basis.
9. Provider transcript and independent ASR transcript remain distinguishable.
10. Agent utterances are data, not instructions to evaluation components.
