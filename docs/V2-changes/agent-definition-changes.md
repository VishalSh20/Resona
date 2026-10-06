# Voice Agent Target Schema — V1

## 1. Design Principle

The system separates four things:

**Agent Target** — the logical agent we are evaluating.  
**Agent Target Revision** — the exact provider/runtime configuration being evaluated.  
**Agent Endpoint** — how that specific revision can be reached.  
**Connection Session** — one temporary runtime connection during a test.

Provider-specific differences are hidden behind integration adapters.

---

# 2. Integration

An **Integration** represents an authenticated connection to a provider account/project.

### `integration_provider`

Defines the provider itself.

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `slug` | Text | `retell`, `vapi`, `elevenlabs`, `livekit`, `pipecat` |
| `display_name` | Text | Human-readable name |
| `capabilities` | JSONB | Supported config import, transports, sync, etc. |
| `created_at` | Timestamp | |

### `integration_account`

Represents one configured provider account/project.

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `provider_id` | FK | Required |
| `name` | Text | User-defined |
| `config` | JSONB | Non-secret provider configuration |
| `status` | Text | Active/inactive |
| `created_at` | Timestamp | |
| `updated_at` | Timestamp | |

### Secrets

API keys, API secrets and other credentials are stored separately through a secret manager.

Examples:

- Vapi API key
- Retell API key
- ElevenLabs API key
- LiveKit API key + API secret

**Do not store secrets inside ordinary JSONB configuration.**

---

# 3. Agent Target

`AgentTarget` is the stable logical identity of an agent inside our platform.

### `agent_target`

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `provider_id` | FK | Required; an agent belongs to exactly one provider |
| `integration_account_id` | FK | Required; the account through which this agent is accessed |
| `name` | Text | User-defined or imported |
| `created_at` | Timestamp | |
| `updated_at` | Timestamp | |

### Important invariant

An `AgentTarget` has **exactly one provider**.

The provider of its `integration_account` must match `agent_target.provider_id`.

Examples:

```text
AgentTarget
    provider = Vapi
    integration_account = Vishal's Vapi account
```

An agent cannot simultaneously be a Vapi agent and a Retell agent.

---

# 4. Agent Target Revision

A revision is the **exact snapshot of the agent that we are evaluating**.

This is where provider identity and configuration live.

### `agent_target_revision`

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `agent_target_id` | FK | Required |
| `revision_no` | Integer | Required, monotonically increasing |
| `external_agent_id` | Text | Provider/runtime identifier, nullable |
| `agent_url` | Text | Agent's own endpoint when applicable, nullable |
| `description` | Text | Agent description |
| `first_message` | Text | Initial greeting, when available |
| `llm_config` | JSONB | Canonical LLM configuration |
| `stt_config` | JSONB | Canonical STT configuration |
| `tts_config` | JSONB | Canonical TTS configuration |
| `turn_config` | JSONB | Turn-taking/interruption behavior |
| `conversation_config` | JSONB | Other conversation behavior |
| `tools_config` | JSONB | Agent tools |
| `variables_config` | JSONB | Runtime/dynamic variables |
| `knowledge_config` | JSONB | Knowledge/RAG configuration |
| `workflow_config` | JSONB | Workflow/state-machine configuration |
| `handoffs_config` | JSONB | Agent/human handoffs |
| `guardrails_config` | JSONB | Safety/business constraints |
| `canonical_config` | JSONB | Our normalized representation |
| `source_config` | JSONB | Exact provider/runtime configuration fetched/imported |
| `source_version_id` | Text | Provider version when available |
| `source_branch_id` | Text | Provider branch/environment when available |
| `source_updated_at` | Timestamp | Provider-side update time |
| `config_hash` | Text | Hash of the effective configuration |
| `source_kind` | Text | `IMPORTED`, `DECLARED`, `MANIFEST`, `MANUAL` |
| `created_by` | FK | Nullable |
| `created_at` | Timestamp | |

### Why are `external_agent_id` and `agent_url` here?

Because the revision represents the **exact thing being tested**.

For example:

```text
Target:      Customer Support Bot

Revision 17:
    external_agent_id = abc123
    agent_url = null

Revision 18:
    external_agent_id = abc123
    agent_url = null
```

For a custom/Pipecat deployment:

```text
Revision 4:
    external_agent_id = support-prod
    agent_url = wss://agent.example.com/v4/ws

Revision 5:
    external_agent_id = support-prod
    agent_url = wss://agent.example.com/v5/ws
```

This means a historical test still points to the exact revision/endpoints it was run against.

### Important distinction

`agent_url` means the **agent's own address**.

A provider/project URL is not necessarily an agent URL.

For example, a LiveKit project URL belongs to the integration account; the LiveKit agent is selected through its dispatch/agent name.

---

# 5. Canonical vs Source Configuration

Every imported/declared revision keeps two forms of configuration.

### `source_config`

The provider's original configuration, unchanged.

Example:

```json
{
  "... provider-specific fields ...": "..."
}
```

This is used for:

- debugging
- re-importing
- preserving fields we do not understand
- provider-specific behavior

### `canonical_config`

Our normalized representation.

Example:

```json
{
  "llm": {},
  "stt": {},
  "tts": {},
  "turn_taking": {},
  "tools": [],
  "variables": [],
  "knowledge": [],
  "workflow": {}
}
```

The simulation/evaluation layer should consume **`canonical_config`**, not provider-specific schemas.

This prevents the rest of the platform from knowing whether an agent came from Vapi, Retell, ElevenLabs, LiveKit or Pipecat.

---

# 6. Transport

Transport describes **how communication is carried**, not what the agent is.

### `transport_type`

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `slug` | Text | `webrtc`, `websocket`, `sip`, `pstn`, etc. |
| `display_name` | Text | |
| `category` | Text | Media/telephony/messaging/etc. |
| `capabilities` | JSONB | Optional |

V1 only needs:

```text
WEBRTC
WEBSOCKET
```

SIP/PSTN can be added later without changing the agent schema.

---

# 7. Agent Endpoint

An endpoint describes:

> **How do we connect to this specific agent revision using this transport?**

### `agent_endpoint`

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `agent_target_revision_id` | FK | Required |
| `transport_type_id` | FK | Required |
| `connection_config` | JSONB | Transport/provider-specific connection configuration |
| `created_at` | Timestamp | |

A revision can have multiple endpoints.

Example:

```text
ElevenLabs Revision 17
    ├── WebRTC endpoint
    └── WebSocket endpoint
```

The revision stays the same; only the communication mechanism differs.

---

# 8. Connection Session

A session is one **actual runtime connection**.

### `connection_session`

| Field | Type | Notes |
|---|---|---|
| `id` | ULID | Primary key |
| `endpoint_id` | FK | Required |
| `revision_id` | FK | Revision actually used |
| `status` | Text | Created/connecting/connected/terminated/failed |
| `provider_session_id` | Text | Provider call/session ID |
| `runtime_config` | JSONB | Runtime overrides |
| `ephemeral_data` | JSONB | Temporary URL/token/room/etc. |
| `started_at` | Timestamp | |
| `connected_at` | Timestamp | |
| `ended_at` | Timestamp | |
| `error_code` | Text | Nullable |
| `error_message` | Text | Nullable |
| `created_at` | Timestamp | |

Examples of `ephemeral_data`:

- temporary WebRTC token
- signed WebSocket URL
- LiveKit room name
- provider call ID
- temporary session ID

These should **not** be stored on the persistent agent or endpoint.

---

# 9. Relationship Overview

```text
IntegrationProvider
        │
        ▼
IntegrationAccount
        │
        ▼
   AgentTarget
        │
        │ 1 : N
        ▼
AgentTargetRevision
        │
        │ 1 : N
        ▼
  AgentEndpoint
        │
        │
        ▼
ConnectionSession
```

Conceptually:

```text
Integration
    = where/how we authenticate

AgentTarget
    = which logical agent we care about

Revision
    = exactly what that agent looked like

Endpoint
    = how that revision is reachable

Transport
    = how communication travels

Session
    = one actual connection
```

---

# 10. Provider Examples

### Retell

```text
AgentTarget
    provider = Retell

Revision
    external_agent_id = retell_agent_id
    agent_url = null

Endpoint
    transport = WebRTC
```

### Vapi

```text
AgentTarget
    provider = Vapi

Revision
    external_agent_id = assistant_id
    agent_url = null

Endpoints
    ├── WebRTC
    └── WebSocket
```

### ElevenLabs

```text
AgentTarget
    provider = ElevenLabs

Revision
    external_agent_id = agent_id
    source_version_id = version_id

Endpoints
    ├── WebRTC
    └── WebSocket
```

### LiveKit

```text
IntegrationAccount
    provider = LiveKit
    config.url = LiveKit project URL

AgentTarget
    provider = LiveKit

Revision
    external_agent_id = agent/dispatch name
    agent_url = null

Endpoint
    transport = WebRTC
```

### Pipecat

```text
IntegrationAccount
    provider = Pipecat

AgentTarget
    provider = Pipecat

Revision
    external_agent_id = deployment identifier
    agent_url = wss://agent.example.com/ws

Endpoint
    transport = WebSocket
```

The exact fields used by each provider are handled by its integration adapter.

---

# 11. Integration Adapter Contract

Every provider integration implements the same internal interface conceptually:

```text
Provider Adapter

- discover/import target
- fetch agent revision
- normalize provider config
- create connection session
- terminate connection session
```

The adapters translate:

```text
Retell API
Vapi API
ElevenLabs API
LiveKit runtime
Pipecat deployment
```

into the common schema above.

The simulation system never needs provider-specific logic.

---

# 12. V1 Invariants

These should be enforced by the backend:

1. **An AgentTarget belongs to exactly one provider.**

2. **Its IntegrationAccount must use the same provider.**

3. **Every revision belongs to exactly one AgentTarget.**

4. **`external_agent_id` and `agent_url` describe the exact revision being tested.**

5. **A revision may expose multiple endpoints/transports.**

6. **An endpoint uses exactly one transport.**

7. **A connection session refers to the exact revision and endpoint used.**

8. **Persistent provider secrets never live in agent configuration JSON.**

9. **`source_config` preserves the original provider configuration.**

10. **Simulation/evaluation code consumes `canonical_config`, not provider schemas.**

---

# 13. The mental model to keep

```text
WHAT IS THE AGENT?
        ↓
   AgentTarget

WHAT EXACT VERSION?
        ↓
   AgentRevision

HOW DO WE REACH IT?
        ↓
   AgentEndpoint

HOW DOES AUDIO/DATA TRAVEL?
        ↓
     Transport

WHAT HAPPENED THIS TIME?
        ↓
 ConnectionSession
```

This is enough for the V1 integrations and leaves room for SIP, PSTN, custom WebRTC servers, custom WebSockets, future providers, and framework-based agents without changing the fundamental model.