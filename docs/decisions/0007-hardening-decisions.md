# 0007 — Hardening, security and observability decisions (Prompt 8)

Prompt 8 is a review-and-harden pass. This document records the decisions taken
where the six source documents left room for interpretation, plus the findings
of the security and observability reviews. It does not rewrite the source docs.

See [`../requirements-matrix.md`](../requirements-matrix.md) for the full
requirement → implementation → test trace.

## 1. Control-plane authentication is now enforced

**Decision.** Every `/api/v1` route requires a `user`-scope bearer JWT, applied
at router level (`dependencies=[require_user_dep]`). The only unauthenticated
HTTP surface is `GET /api/v1/media/blob`, which is authorised by its short-lived
HMAC signature + expiry instead of a session.

**Why.** Prompts 3 and 7 deferred "v1 auth" and "global auth on result routes".
`require_user` existed but was dead code. The design treats the endpoint surface
and result/forensics APIs as operator-only, so leaving them open is the largest
security gap. The WebSockets were already authenticated (runner token for the
control channel, user JWT for the live channel).

**Token issuance.** No public signup. Operators mint tokens out of band with
`uv run python -m voiceeval.auth.cli --sub <id> [--scope runner --attempt <id>]`
(`auth/jwt.py::create_user_token`). Following the Prompt 1 rule, this is a CLI,
not a network endpoint or identity UX.

**Trade-off.** Manual local use now needs a token. This is the intended security
posture; the CLI keeps it one command.

## 2. Signed media blob stays public by design

The media blob is fetched by browsers/audio players via a signed URL, which
cannot carry a bearer token. It is split into its own unauthenticated router
(`api/routes/results.py::blob_router`) so it never inherits the bearer
requirement, while every other result route is protected. Authorisation is the
HMAC signature + expiry (`storage/signing.py`), matching the "short-lived signed
URL" contract for both local and S3 modes.

## 3. Idempotency hardening

**Decisions.**
- The reserve remains a **409 on duplicate** (Prompt 3 semantics, unchanged).
- The request body hash is now persisted (`request_hash`), so reusing a key with
  a *different* body is reported distinctly. Bodyless actions
  (prepare/execute/cancel/resume/freeze/approve/validate) use the key alone as
  identity.
- The SELECT-then-INSERT race is closed: the DB `UNIQUE(key)` violation is
  caught and translated to a clean `ConflictError` (409) instead of surfacing as
  an integrity error (500).
- The reservation is flushed inside the request transaction, so a failed
  operation rolls the key back with it and does not permanently burn the key.

**Deliberately not done.** Full response *replay* (returning the stored response
for a repeated request) is out of scope for v1: it adds response-caching
semantics the product does not yet need. The `response_*` columns remain for a
future replay implementation. This is the least-complex choice that preserves
the documented invariant ("the same request must not create duplicate logical
repetitions").

## 4. Immutability: database triggers, not just convention

The design requires immutability "beyond application convention". Prompt 2
created service-level guards but three of them (manifests, runtime events,
original media) had no reaching code path. Migration `0004` adds a
`BEFORE UPDATE OR DELETE` trigger to `runtime_event`, `execution_manifest` and
`media_artifact` that raises.

Derived, rebuildable tables (turns, tool calls, state transitions, metric
results, aggregates) are deliberately **not** locked — they are projections that
may be replaced on reprocessing. Evaluator-revision and benchmark-version
immutability stays at the service layer because their status transitions are
legitimate `UPDATE`s; a blanket trigger would break the state machines.

`alembic check` confirms triggers are invisible to autogenerate, so the schema
still matches the metadata.

## 5. Observability: tracing initialised and spans at the documented points

**Findings before hardening.** `init_tracing()` was never called; no span
existed anywhere; worker/runner logs carried null correlation ids.

**Decisions.**
- `init_tracing()` runs at app import (`main.py`), ARQ worker startup and the
  runner CLI. It is idempotent (guards against overriding the tracer provider).
- A single `span(name, **attrs)` context manager (`observability/tracing.py`)
  replaces ad-hoc tracing. Spans are attached at the documented paths: API
  request (middleware), ARQ job handlers, orchestrator plan/run/dispatch, target
  connection, caller execution, metric computation, judge invocation and
  aggregation.
- The API request middleware prefers the real OTel trace id, falling back to an
  upstream `X-Trace-ID` or the request id.
- `plan_id`/`run_id`/`attempt_id` are contextvars in `core/logging.py` and are
  bound via `bind_execution_context(...)` in the metric engine, judge engine,
  aggregation engine, orchestrator jobs and the runner, so every structured log
  line in those scopes is correlated.

**Not done.** The `opentelemetry-instrumentation-fastapi` auto-instrumentation is
deliberately not enabled; an explicit `api.request` span in the middleware gives
deterministic ordering without double-spanning. Auto-instrumentation can replace
it later.

## 6. Motive assertions get an explicit state and a conversation oracle

**Gap.** `AssertionState` did not exist (assertions jumped straight to a
verdict), and `OracleType.CONVERSATION_EVIDENCE` was declared in the precedence
tuple but never produced.

**Decisions.**
- `AssertionState` (PENDING / SUPPORTED_BY_EVIDENCE / SATISFIED / CONTRADICTED /
  UNSATISFIED / NO_OBSERVABLE_EVIDENCE / UNKNOWN) models the documented
  assertion lifecycle (SM §12). `assertion_state(verdict, oracle)` maps a
  verdict + oracle onto it: strong oracles terminate the assertion, an LLM-only
  verdict only reaches "supported", conflicts are `UNKNOWN`, and no firing oracle
  is `NO_OBSERVABLE_EVIDENCE`.
- The LLM judge now lands in `CONVERSATION_EVIDENCE` when it grounds a verdict in
  conversation evidence, and in `LLM_INFERENCE` when it is a bare
  interpretation — making the precedence tier real. This preserves the "judge
  never outranks a stronger deterministic oracle" invariant.

## 7. Testing strategy (kept intentionally simple)

`pytest` + `pytest-asyncio` + `httpx.ASGITransport` and fakes. No Testcontainers
or integration framework. New coverage added in this pass:

- `test_api_auth.py` — REST authentication/authorization (401/403), the public
  signed blob, request validation, error envelope, idempotency-header
  requirement, authorized reads (session stubbed, no DB).
- `test_workers.py` — deterministic ARQ job identities for every enqueue helper,
  the eligibility gate, aggregation triggering and registered job functions.
- `test_observability.py` — log context fields/restoration, span trace ids,
  idempotent tracer init.
- `test_idempotency.py` — request-hash binding, key reuse, the concurrent
  duplicate path (IntegrityError → 409).
- `test_judges.py` — assertion-state mapping, state/conversation oracle tiers.

The live-database immutability behaviour is verified out of band (manual trigger
check against Docker Postgres) because the unit suite is DB-free by design.

## 8. Security review summary

| Check | Result |
|---|---|
| No secrets in `endpoint_config` | Pass — `find_raw_secrets` rejects them; references allowed. |
| JWT validation (issuer, expiry, signature, scope) | Pass — `auth/jwt.py`, `test_jwt.py`. |
| Runner token scoping + attempt isolation | Pass — `authenticate_runner` binds scope + attempt; WS rejects mismatches. |
| Authorization on plan/run/attempt/result access | **Fixed** — bearer required on all routes. |
| Signed media URLs | Pass — HMAC + expiry; blob route is signature-authorised, not bearer. |
| Provider payload treated as untrusted | Pass — judge prompt fences untrusted data. |
| LLM judge injection defense | Pass — trusted/untrusted separation, strict output schema. |
| No secret committed | Pass — `.env` gitignored; `.env.example` has placeholders. |

## 9. Observability review summary

| Path | request_id | trace_id | plan/run/attempt | span |
|---|---|---|---|---|
| API request | ✅ | ✅ (OTel) | via route scope | `api.request` |
| ARQ job | ✅ (contextvar) | ✅ | ✅ bound | `worker.*` |
| Orchestrator plan/run/attempt | ✅ | ✅ | ✅ bound | `orchestration.*` |
| Target connection | ✅ | ✅ | ✅ bound | `runtime.target.connect` |
| Caller execution | ✅ | ✅ | ✅ bound | `runtime.caller.execute` |
| Metric computation | ✅ | ✅ | ✅ bound | `metrics.compute` |
| Judge invocation | ✅ | ✅ | ✅ bound | `judge.evaluate` |
| Aggregation | ✅ | ✅ | ✅ bound | `aggregation.*` |

Secrets are never logged: the structured logger emits only the documented fields
plus exception text; provider keys are read from settings and never attached to
spans or log records.
