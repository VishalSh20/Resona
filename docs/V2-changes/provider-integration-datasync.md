

## Common adapter contract

```ts
interface AgentProviderAdapter {
  getTarget(input): Promise<AgentTargetData>;

  getRevision(input): Promise<AgentRevisionData>;
}
```

Every adapter should produce:

```ts
{
  externalAgentId,
  agentUrl,
  name,
  description,
  firstMessage,
  llmConfig,
  sttConfig,
  ttsConfig,
  turnConfig,
  conversationConfig,
  toolsConfig,
  variablesConfig,
  knowledgeConfig,
  workflowConfig,
  handoffsConfig,
  guardrailsConfig,
  sourceVersionId,
  sourceBranchId,
  sourceUpdatedAt,
  sourceConfig,
  canonicalConfig
}
```

---

# 1. Retell Adapter

Retell is a **two-level import**: first retrieve the agent, then retrieve whatever response engine that agent points to. The current agent API is `GET https://api.retellai.com/get-agent/{agent_id}`, authenticated with `Authorization: Bearer <API_KEY>`. [Retell AI](https://docs.retellai.com/api-references/get-agent?utm_source=chatgpt.com)

### Retrieval

```text
GET /get-agent/{agent_id}?version={version}
        │
        └── response_engine
              │
              ├── retell-llm
              │      ↓
              │   GET /get-retell-llm/{llm_id}
              │
              └── conversation-flow
                     ↓
                  GET /get-conversation-flow/{flow_id}
```

The important design point is that the **agent response alone may not contain the actual prompt/tools/workflow**; those live in the referenced response engine.

### Mapping

```text
agent.agent_id
    → external_agent_id

agent.agent_name
    → name

agent.version
    → source_version_id

agent.version_description
    → description

agent.response_engine
    → determines secondary retrieval
```

From the Retell LLM / Conversation Flow resource:

```text
begin_message
    → first_message

model / model_temperature
    → llm_config

voice_id / voice_model / voice_speed / voice_temperature
    → tts_config

stt configuration
    → stt_config

responsiveness / interruption settings
    → turn_config / conversation_config

tools
    → tools_config

knowledge_base_ids
    → knowledge_config

states / nodes / transitions
    → workflow_config

dynamic variables
    → variables_config
```

### `source_config`

Store:

```json
{
  "agent": { "...": "..." },
  "response_engine": { "...": "..." }
}
```

### `canonical_config`

Normalize the merged result into your common schema.

### Version

Retell also exposes an agent-version listing endpoint, so a sync/import adapter can discover provider revisions rather than inventing them.  

---

# 2. Vapi Adapter

Vapi is simpler: assistant configuration is largely available from the assistant resource itself.

### Retrieval

```http
GET https://api.vapi.ai/assistant/{assistant_id}
Authorization: Bearer <VAPI_API_KEY>
```

Vapi's documented response includes `transcriber`, `model`, `voice`, `firstMessage`, call behavior, tools-related model configuration, transport configurations, metadata, and `latestVersion`. [Vapi](https://docs.vapi.ai/api-reference/assistants/get?utm_source=chatgpt.com)

For discovery:

```http
GET https://api.vapi.ai/assistant
Authorization: Bearer <VAPI_API_KEY>
```

This lists assistants for the authenticated organization. [Vapi](https://docs.vapi.ai/api-reference/assistants/list?explorer=true\&utm_source=chatgpt.com)

### Mapping

```text
assistant.id
    → external_agent_id

assistant.name
    → name

assistant.updatedAt
    → source_updated_at

assistant.latestVersion
    → source_version_id

assistant.firstMessage
    → first_message

assistant.model
    → llm_config

assistant.transcriber
    → stt_config

assistant.voice
    → tts_config

assistant.firstMessage*
assistant.endCall*
assistant.voicemail*
assistant.maxDuration*
etc.
    → conversation_config

assistant.model.tools
    → tools_config

assistant.transportConfigurations
    → transport-related source_config
       NOT agent semantics

assistant.*
    → source_config
```

For dynamic variables, inspect prompt/message/tool fields for Vapi variable references such as `{{name}}` and normalize those into `variables_config`.

### Important

Don't copy `transportConfigurations` into the agent's semantic `canonical_config` as though transport were part of the agent. Preserve it in `source_config`; our `AgentEndpoint` handles actual transport.

---

# 3. ElevenLabs Adapter

This one maps almost directly to our revision schema.

### Retrieval

```http
GET https://api.elevenlabs.io/v1/convai/agents/{agent_id}
xi-api-key: <API_KEY>
```

Optional:

```text
?version_id=<version>
?branch_id=<branch>
```

ElevenLabs now explicitly supports retrieving an agent at a particular version or branch. [ElevenLabs](https://elevenlabs.io/docs/eleven-agents/api-reference/agents/get?utm_source=chatgpt.com)

For version metadata:

```http
GET /v1/convai/agents/{agent_id}/versions/{version_id}
xi-api-key: <API_KEY>
```

which returns version/branch metadata. [ElevenLabs](https://elevenlabs.io/docs/eleven-agents/api-reference/agents/versions/get?utm_source=chatgpt.com)

### Mapping

```text
agent.agent_id
    → external_agent_id

agent.name
    → name

agent.version_id
    → source_version_id

agent.branch_id
    → source_branch_id

agent.conversation_config.agent
    → agent behavior (preserved in source_config)

agent.conversation_config.asr
    → stt_config

agent.conversation_config.turn
    → turn_config

agent.conversation_config.tts
    → tts_config

agent.conversation_config.conversation
    → conversation_config

agent.conversation_config.vad
    → turn_config / conversation_config

agent.workflow
    → workflow_config

agent.procedures
    → tools_config / workflow_config

agent.platform_settings
    → conversation_config / provider extensions

agent.*
    → source_config
```

The current Get Agent response explicitly contains `conversation_config`, ASR, turn, TTS, conversation settings, VAD, workflow, procedures, metadata, platform settings, version and branch information. [ElevenLabs](https://elevenlabs.io/docs/eleven-agents/api-reference/agents/get?utm_source=chatgpt.com)

### Canonical config

This is probably the easiest adapter:

```text
ElevenLabs response
       ↓
field-by-field normalization
       ↓
CanonicalAgentRevision
```

No secondary config request is normally necessary.

---

# 4. LiveKit Adapter

This one is fundamentally different.

There is **no provider API that returns the agent's application-level prompt/LLM/STT/TTS/tools configuration**.

LiveKit's agent identity is the dispatch name, and dispatch routes a job to the deployed agent server. [LiveKit Docs](https://docs.livekit.io/agents/server/agent-dispatch/?utm_source=chatgpt.com)

### Retrieval

For V1:

```text
USER PROVIDES
    LIVEKIT_URL
    API_KEY
    API_SECRET
    AGENT_NAME
```

Optional runtime verification/discovery:

```http
POST https://<LIVEKIT_URL>/twirp/livekit.AgentDispatchService/CreateDispatch
Authorization: Bearer <roomAdmin JWT>
Content-Type: application/json
```

```json
{
  "agent_name": "support-agent",
  "room": "verification-room"
}
```

The AgentDispatchService uses Twirp POST endpoints and a signed `roomAdmin` token. [LiveKit Docs](https://docs.livekit.io/reference/agents/agent-dispatch-service-api/?utm_source=chatgpt.com)

### Mapping

Since there is no agent-config retrieval:

```text
user.agent_name
    → external_agent_id

user-provided name
    → name

LIVEKIT_URL
    → integration_account.config.url

agent_name
    → revision.external_agent_id

deployment
    → source_version_id
       OR provider extension

dispatch metadata
    → source_config
```

And:

```text
llm_config
stt_config
tts_config
tools_config
workflow_config
knowledge_config
```

remain unavailable unless the customer provides a **manifest/config endpoint**.

### Source kind

```text
source_kind = DECLARED
```

rather than `IMPORTED`.

That's the honest representation.

---

# 5. Pipecat Adapter

Pipecat has no universal provider-side `GET agent configuration` API.

For **self-hosted Pipecat**, the application is the source of truth. The framework provides transports such as SmallWebRTC, rather than a central agent registry. [Pipecat](https://docs.pipecat.ai/api-reference/server/services/transport/small-webrtc?utm_source=chatgpt.com)

### Self-hosted retrieval

User supplies:

```text
agent name / deployment identifier
agent URL
transport
optional auth
```

Example:

```text
agent_url = https://agent.example.com/api/offer
```

for SmallWebRTC.

### Mapping

```text
user.agent_name
    → external_agent_id

user.agent_name
    → name

user.agent_url
    → agent_url

user-provided endpoint metadata
    → source_config
```

Everything else is:

```text
llm_config         → unavailable
stt_config         → unavailable
tts_config         → unavailable
tools_config       → unavailable
workflow_config    → unavailable
knowledge_config   → unavailable
```

unless your customer's Pipecat application exposes a manifest/config endpoint.

---

## Pipecat Cloud

This is better because Pipecat Cloud has a control-plane API.

Conceptually:

```http
GET https://api.pipecat.daily.co/v1/agents/{agentName}
Authorization: Bearer <PIPECAT_CLOUD_TOKEN>
```

The response describes the deployed agent, deployment IDs/revisions and runtime/deployment information.

### Mapping

```text
agent.name
    → external_agent_id

agent.name
    → name

activeDeploymentId
    → source_version_id

deployment / manifest
    → source_config

deployment endpoint
    → agent_url / endpoint config
```

But again:

```text
Pipecat Cloud deployment metadata
                ≠
application's actual prompt/LLM/TTS/tools
```

The latter lives inside the deployed Pipecat application.

---

# Final adapter matrix

| Provider | Retrieval | Config depth | Mapping strategy |
|---|---|---|---|
| **Retell** | `GET agent` → follow response engine → `GET LLM/Flow` | High | Merge agent + response engine, normalize |
| **Vapi** | `GET assistant` | High | Direct field mapping |
| **ElevenLabs** | `GET agent?version_id&branch_id` | Very high | Direct nested mapping |
| **LiveKit** | Dispatch/runtime API + user declaration | Low | Declare identity/runtime, don't fabricate config |
| **Pipecat** | User endpoint / Pipecat Cloud deployment API | Low–medium | Import deployment metadata; semantic config only via manifest |

### The adapter implementation pattern

```text
                 Provider Adapter
                       │
          ┌────────────┴────────────┐
          │                         │
     retrieve source           resolve identity
          │                         │
          └────────────┬────────────┘
                       ▼
                ProviderSnapshot
                       │
                       ▼
                Mapping Layer
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      source_config       canonical_config
             │                   │
             └─────────┬─────────┘
                       ▼
              AgentTargetRevision
```

The key is that **the retrieval code and mapping code should be separate inside each adapter**. For example:

```ts
RetellAdapter
  ├── retrieveAgent()
  ├── retrieveResponseEngine()
  └── mapToRevision()

VapiAdapter
  ├── retrieveAssistant()
  └── mapToRevision()

ElevenLabsAdapter
  ├── retrieveAgent()
  └── mapToRevision()

LiveKitAdapter
  ├── resolveDispatchTarget()
  └── mapToRevision()

PipecatAdapter
  ├── resolveDeployment()
  └── mapToRevision()
```

That keeps the provider API mess isolated to the adapter and keeps your database model clean.