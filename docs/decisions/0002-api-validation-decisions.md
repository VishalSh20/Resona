# API, validation & capability decisions (Prompt 3)

## 1. Config/evaluator/benchmark routes are unauthenticated in v1

JWT infrastructure (user/runner scopes) exists from Prompt 1, but the design
documents do not pin down which control-plane routes require which scope, and
Prompt 3's acceptance criteria do not exercise authorization. The configuration
surfaces are left unauthenticated for v1; wiring `require_user` onto specific
routes is deferred to the hardening pass (Prompt 8) where the RBAC matrix is
built.

## 2. Idempotency: duplicate key returns 409, reserved atomically

`IdempotencyService.reserve` records the key in the same transaction as the
state change, so a duplicate key raises `CONFLICT` (409) rather than replaying a
stored response. Replaying the original response is a deliberate future
enhancement; the current behavior still prevents duplicate revisions, jobs and
repetitions, which is the invariant the design requires.

## 3. Adapter registry seeded with `fake` and `websocket`

Target revision creation validates `adapter_name` + `adapter_version` against a
versioned registry. For v1 it is seeded with a deterministic `fake` adapter and a
generic `websocket` adapter. `webrtc` is intentionally not registered — WebRTC
remains an interface-only contract until Prompt 6, and claiming it would falsely
imply a working signaling/ICE implementation.

## 4. Two capability checks, two different scopes

The validation worker's `capabilities` validator only checks that every metric in
`evaluation_criteria` has a known rule in the capability matrix (the evaluator
references only platform-supported metrics). Target-specific negotiation — does
*this* target expose the signals a metric needs — is a plan-time operation
(`services.capabilities.negotiate`) consumed by Prompt 4, not by the validation
worker.

## 5. Validation failure returns the revision to DRAFT

A failed validation moves the revision `VALIDATING -> DRAFT` (per the state
machine's error edge), and a pass moves it `VALIDATING -> VALIDATED`. `REJECTED`
remains available as a terminal status but is not set by the automatic worker.
