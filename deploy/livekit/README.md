# Self-hosted LiveKit + SIP (local/dev)

Runs the VoiceEval caller's LiveKit server **and** the SIP telephony service
(`livekit-sip`) so the `sip` target transport works locally. Both use
`network_mode: host` (matching LiveKit's own SIP compose) so the SIP server can
advertise a reachable address for RTP.

## Start

```bash
# 1. backend infra — the SIP server reuses redis (host networking = localhost)
docker compose -f backend/docker-compose.yml up -d postgres redis minio

# 2. LiveKit server + SIP service
docker compose -f deploy/livekit/docker-compose.yml up -d

# logs
docker compose -f deploy/livekit/docker-compose.yml logs -f sip
```

The API key/secret live in `livekit.yaml` and are mirrored in the `sip`
service's `SIP_CONFIG_BODY`. They must match `backend/.env`.

## What this gives you

- LiveKit signaling on `ws://localhost:7880` (unchanged).
- The **SIP API** (via redis): `create_sip_outbound_trunk` / `create_sip_participant` —
  exactly what `SipAdapter.provision_account` and `SipLink` call.
- SIP signaling on **5060/udp**, RTP on **10000–20000/udp**.

## Test the path locally (no carrier)

Dial a **local SIP endpoint** (a softphone/SBC on this machine) instead of PSTN:

```bash
# register a SIP integration account pointing at the local endpoint
curl -sX POST localhost:8000/api/v1/integrations/accounts -H 'Content-Type: application/json' -d '{
  "provider_id": "prov_sip", "name": "local-sip",
  "config": {"address": "127.0.0.1:5062", "transport": "udp"},
  "secrets": {"username": "test", "password": "test"}
}'
# then a target with external_agent_id = "sip:agent@127.0.0.1:5062"
```
`provision_account` creates the LiveKit outbound trunk; `SipLink` dials it; media
rides the room.

## Reaching Exotel / PSTN

**This will not work from a laptop.** Exotel sends RTP back to the address the
SIP server advertises; behind NAT that is unroutable — signaling may connect, but
there will be no audio. For real PSTN you need one of:

- a host with a **public IP**: set `sip.use_external_ip: true` (drop
  `use_external_ip: false`), open **5060/udp** + **10000–20000/udp**, and run the
  same two services there; or
- **LiveKit Cloud** (Telephony built in) — no `livekit-sip` needed.

## Switching to LiveKit Cloud

1. Point `backend/.env` at the Cloud project: `LIVEKIT_URL=wss://<proj>.livekit.cloud`
   + its API key/secret.
2. Stop this compose (the Cloud project serves SIP itself).
3. Create the SIP integration account with Exotel's edge address/DID/digest
   (see `backend/scripts/exotel_setup.py`).
