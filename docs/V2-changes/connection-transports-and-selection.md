# Connection transports, selection, and open items

Status: reference / working note (2026-10). Records how the caller decides how to
connect to a target, plus open follow-ups. See also
`caller-migration-to-livekit.md` (§4.2, §14.3) and `provider-integration-datasync.md`.

## 1. Transports (`TargetLink`)

`runtime/livekit/target_links/` — each is a transport-specific connection to the
target; the caller brain is identical across them (`base.py` defines the contract:
`connect`, `incoming_audio`, `send_audio`, `send_dtmf`, `send_control`, `events`,
`close`, `capabilities`).

| slug | file | carries | notes |
|---|---|---|---|
| `room` | `room.py` | WebRTC via a LiveKit room (`livekit.rtc`) | two modes: *caller* (target joins our `ctx.room`) and *external* (`room_mode:"external"` → own `rtc.Room` to a provider's LiveKit, minted url+token) |
| `sip` | `sip.py` | PSTN/SIP: `api.sip.create_sip_participant` + a room media plane | DTMF supported; narrowband |
| `bridge` | `bridge.py` | provider-protocol WebSocket audio | per-provider decoder (`bridge_decoders.py`) + encoder; raw PCM by default |
| `whip` | `whip.py` | raw WebRTC peer connection (WHIP signaling) | `aiortc`; SDP offer → provider session endpoint + ICE trickle; PCM↔Opus resampling |

Registry: `registry.py` (`TargetLinkRegistry`, `get_target_link_registry`), lazy
factories, keyed by slug.

## 2. Static vs per-call endpoints

- **Static** — `endpoint_config` is frozen in the manifest at build time.
- **Per-call** — `endpoint_config` carries `call_setup:"per_call"`; the runtime
  `prepare_target_link()` calls `adapter.start_connection()` at connect time and
  merges the minted config. Tokens are never written into the frozen manifest.

`AgentProviderAdapter.start_connection(account, secrets, agent, revision, *,
transport, sample_rate) -> StartedConnection | None`
(`integrations/base.py`; default `BaseAgentProviderAdapter` returns `None`).
`StartedConnection{endpoint_config, provider_session_id, ephemeral}`.

## 3. Provider → transport map

Provider vocabulary → canonical transport: `_PROVIDER_TO_TARGET_LINK`
(`integrations/base.py`): `webrtc/room→room`, `websocket/ws/bridge→bridge`,
`whip→whip`, `sip/pstn→sip`.

| provider | emitted transport | how |
|---|---|---|
| `retell` | `whip` (per-call) | `POST /v3/create-web-call` → `{call_id, access_token, ice_servers}` |
| `vapi` | `bridge` (per-call) | `POST /call` → `transport.websocketCallUrl` |
| `elevenlabs` | `room` (per-call) | `GET /convai/conversation/token` → LiveKit token; workspace LiveKit URL |
| `livekit` | `room` (per-call) | create room + dispatch agent + caller token, on the target's project |
| `pipecat` | `bridge` (static) | agent endpoint URL |
| custom / manual | `bridge` (static) | `wss://` config |

## 4. How the transport is chosen (who decides)

**Our end, deterministic; the client does not choose today.** Single decision
point at manifest-build time:

1. `AgentProviderAdapter.get_endpoints()` declares possible methods.
2. `services/targets.py::_persist_endpoints` writes them as `agent_endpoint` rows
   (best-effort) on the revision.
3. `orchestration/manifest_service.get_or_create_manifest_for_call_run` →
   `orchestration/target_link.resolve_target_link(session, revision_id)`:
   loads endpoints, normalizes via `target_link_transport()`, returns the first
   match in `TARGET_LINK_PREFERENCE = ("sip", "room", "whip", "bridge")`, else the
   first resolved endpoint, else `default_target_link()` (`room`). Returns
   `{transport, endpoint_config, endpoint_id}`, frozen into
   `manifest.target_snapshot.target_link` (`manifest.py::_target_snapshot`).
4. `runtime/loader.load_attempt_context` → `AttemptBundle.target_link`;
   `runtime/livekit/job.entrypoint` → `prepare_target_link()` (mint) →
   `TargetLinkRegistry.create(transport, endpoint_config, room=ctx.room)`.

Client influence is indirect only: it picks the agent + revision
(`Run.target_revision_id`), and different revisions can carry different endpoints.
No transport field exists on Simulation/Run/RunEvaluator/target schemas.

## 5. To make the transport client-selectable

Keep the decision server-authoritative (validate against what exists):

1. Add `preferred_transport` (or ordered `transport_preference`) to the domain —
   most naturally on `Simulation` (reusable) and/or `Run` (per execution).
2. Thread it into manifest build; let
   `resolve_target_link(session, revision_id, preference=None)` use it, falling
   back to `TARGET_LINK_PREFERENCE`.
3. Expose the revision's available transports (read its `agent_endpoint` rows) so
   the UI can present/validate options.
4. UI picker; the choice flows into the manifest on run/simulation start.

Note: today every adapter emits a single transport, so the preference never
branches — it matters once a provider exposes two methods (e.g. ElevenLabs
room+bridge, or a SIP-reachable target).

## 6. Open items

- **LiveKit deployment selection** — DONE: `LiveKitAdapter.start_connection`
  passes `deployment=revision.provider_revision_id or ""` to
  `CreateAgentDispatchRequest` (the `AgentDispatch` proto has a `deployment`
  field). `AgentTarget.external_agent_id` = agent/dispatch name;
  `AgentTargetRevision.provider_revision_id` = deployment id (revision type
  `DEPLOYMENT`).
  - Remaining: `LiveKitAdapter.list_revisions` returns `[]` — the LiveKit
    control-plane call to *list* deployments isn't wired, so deployments can only
    be imported by id, not discovered/selected in a UI.
- **External provider rooms not reaped locally** — rooms we create on a target's
  LiveKit project (`resona-<ulid>`, returned as `provider_session_id`, persisted in
  `ConnectionSession`) are not deleted by us. We create them with
  `empty_timeout = settings.livekit_target_room_empty_timeout_s` (default 300 s),
  so **LiveKit deletes the room once it's been empty that long** — bounded, not an
  unbounded leak.
  - (A) *done*: timeout hoisted to config; rely on provider self-deletion.
  - (B) deterministic teardown: add an optional `end_connection()` hook the runner
    calls on terminal to `delete_room` on the provider project (resolve account via
    `ConnectionSession` → revision → `AgentTarget` → account).
  - (C) periodic reaper: `watchdog.room_reaper_scan` today only sweeps our own
    `attempt-*` rooms (`LiveKitRoomManager().reap_stale_rooms`); a sibling scan
    could sweep non-terminal `ConnectionSession`s' `resona-*` rooms per project.

## 7. Recent changes (context)

- `prepare_target_link` generalized to mint for `room`, `bridge`, `whip`.
- ElevenLabs switched to WebRTC (`room`); LiveKit target path completed (room +
  dispatch + token); Retell switched to `whip`; `RoomLink` gained external mode +
  connect-before-publish fix; WHIP transport added (`aiortc`, pins `av==17`).

## Sources

- [LiveKit connect / agent dispatch](https://docs.livekit.io/intro/basics/connect/)
- [Retell create web call](https://docs.retellai.com/api-references/create-web-call)
- [Retell client SDK (gateway WHIP transport)](https://github.com/RetellAI/retell-client-js-sdk)
- [ElevenLabs WebSocket/WebRTC](https://elevenlabs.io/docs/eleven-agents/libraries/web-sockets)
