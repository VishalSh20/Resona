# VoiceEval Design Pack v0.3

## What changed from v0.2

This revision was re-reviewed against the full Product Scope and then stress-tested around the runtime.

### Major hardening

1. **CallRun vs CallAttempt**
   - Three repetitions remain three statistical samples.
   - Infrastructure retries become attempts and do not inflate aggregates.

2. **Execution Manifest**
   - Target, evaluator, benchmark, caller, metric, judge, aggregation, and runtime versions are frozen into one immutable execution contract.

3. **WebRTC is modeled correctly**
   - Signaling, SDP, ICE, STUN/TURN, media negotiation, and connection lifecycle are explicit.
   - "Generic WebRTC" now requires a documented signaling contract.

4. **Audio provenance**
   - Original media and analysis-normalized media are separate artifacts.
   - Media timestamps and runner monotonic time are distinct.

5. **Transcript provenance**
   - Caller reference text, provider transcript, and independent ASR are explicitly different.

6. **Motive truth**
   - Typed assertions and oracle precedence separate objective evidence from LLM inference.

7. **Small-sample statistics**
   - With 3 repetitions, P95 is retained in the schema but intentionally not presented as a stable statistic.

8. **Composite coverage**
   - Missing metrics no longer silently alter the meaning of the overall score.
   - Critical metric availability and coverage are explicit.

9. **Judge hardening**
   - Rubric versions, strict output schemas, reason codes, evidence references, and prompt-injection boundaries are explicit.

10. **Caller reproducibility**
    - Seeds remain useful, but the system no longer pretends external LLM/TTS components are necessarily bitwise deterministic.
    - Actual caller action traces and realized utterances are retained.

## Files

- `01-architecture.md`
- `02-domain-schema.md`
- `03-runtime-event-schema.md`
- `04-evaluation-result-schema.md`
- `05-state-machines-validation.md`
- `README.md`

## Source relationship

The Product Scope remains the functional baseline: generated/validated editable evaluators, WebSocket/WebRTC execution, stateful synthetic callers, complete call artifacts, capability-dependent tool evaluation, three repetitions, hybrid deterministic + model judging, versioned benchmark runs, and forensic dashboards. fileciteturn0file0L1326-L1359

This pack adds implementation constraints needed to keep those requirements trustworthy under retries, stochastic models, black-box providers, missing observability, and post-hoc reprocessing.
