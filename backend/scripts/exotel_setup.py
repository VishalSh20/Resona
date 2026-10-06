"""Provision an Exotel SIP trunk for the LiveKit caller (outbound PSTN).

Exotel requires three API steps before LiveKit can dial through it:

    1. Create trunk           POST /v2/accounts/{sid}/trunks
    2. Map phone number (DID) POST /v2/accounts/{sid}/trunks/{trunk_sid}/phone-numbers
    3. Digest credentials     POST /v2/accounts/{sid}/trunks/{trunk_sid}/credentials

The digest username/password must match the LiveKit outbound trunk's auth, which
``SipAdapter.provision_account`` creates from the SIP integration account config.

Reads credentials from the environment (see ``core/config.py``):

    EXOTEL_ACCOUNT_SID      # e.g. vishhh1
    EXOTEL_ACCOUNT_REGION   # India | Singapore (informational)
    EXOTEL_SUBDOMAIN        # api.in.exotel.com (India) | api.exotel.com (Singapore)
    EXOTEL_API_KEY
    EXOTEL_API_TOKEN
    EXOTEL_TRUNK_NAME       # optional, default "voiceeval"
    EXOTEL_SIP_USERNAME     # optional; generated if absent
    EXOTEL_SIP_PASSWORD     # optional; generated if absent
    EXOTEL_SIP_TRANSPORT    # optional, tls (default) | tcp
    EXOTEL_FROM_NUMBER      # DID in E.164, must already belong to the account

Usage:
    python scripts/exotel_setup.py discover   # list existing trunks
    python scripts/exotel_setup.py setup      # create missing pieces, print config
"""

from __future__ import annotations

import argparse
import base64
import secrets
import sys

import httpx

from voiceeval.core.config import get_settings

#: SIP edge port per transport (Exotel: 443 TLS / 5070 TCP).
_EDGE_PORTS = {"tls": 443, "tcp": 5070, "udp": 5070, "auto": 5060}


def _auth_header() -> str:
    settings = get_settings()
    if not (settings.exotel_api_key and settings.exotel_api_token):
        raise SystemExit("EXOTEL_API_KEY and EXOTEL_API_TOKEN are required.")
    raw = f"{settings.exotel_api_key}:{settings.exotel_api_token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _require_settings() -> None:
    settings = get_settings()
    if not settings.exotel_account_sid:
        raise SystemExit("EXOTEL_ACCOUNT_SID is required.")
    if not settings.exotel_subdomain:
        raise SystemExit("EXOTEL_SUBDOMAIN is required.")


def _api(path: str) -> str:
    settings = get_settings()
    return f"https://{settings.exotel_subdomain}/v2/accounts/{settings.exotel_account_sid}{path}"


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        timeout=30.0,
    )


def _payload(response: httpx.Response) -> dict:
    """Unwrap Exotel's ``{response: {data: {...}}}`` envelope."""
    response.raise_for_status()
    body = response.json()
    if isinstance(body, dict) and "response" in body:
        inner = body["response"]
        if isinstance(inner, dict):
            return inner.get("data") or inner
        if isinstance(inner, list) and inner:
            first = inner[0]
            return (first.get("data") if isinstance(first, dict) else first) or {}
    return body if isinstance(body, dict) else {}


def _list_trunks(client: httpx.Client) -> list[dict]:
    body = client.get(_api("/trunks")).json()
    inner = body.get("response") if isinstance(body, dict) else None
    if isinstance(inner, list):
        return [item.get("data", item) for item in inner if isinstance(item, dict)]
    if isinstance(inner, dict) and isinstance(inner.get("data"), list):
        return inner["data"]
    return []


def discover() -> None:
    _require_settings()
    with _client() as client:
        trunks = _list_trunks(client)
        print(f"{len(trunks)} trunk(s):")
        for trunk in trunks:
            print(
                f"  {trunk.get('trunk_sid') or trunk.get('sid')} "
                f"name={trunk.get('trunk_name') or trunk.get('name')}"
            )


def _ensure_trunk(client: httpx.Client) -> str:
    settings = get_settings()
    for trunk in _list_trunks(client):
        if (trunk.get("trunk_name") or trunk.get("name")) == settings.exotel_trunk_name:
            trunk_sid = trunk.get("trunk_sid") or trunk.get("sid")
            if trunk_sid:
                print(f"reusing trunk {trunk_sid}")
                return trunk_sid
    print("creating trunk ...")
    data = _payload(
        client.post(
            _api("/trunks"),
            json={
                "trunk_name": settings.exotel_trunk_name,
                "nso_code": "ANY-ANY",
                "domain_name": f"{settings.exotel_account_sid}.pstn.exotel.com",
            },
        )
    )
    trunk_sid = data.get("trunk_sid") or data.get("sid")
    if not trunk_sid:
        raise SystemExit(f"trunk created but no trunk_sid in response: {data}")
    return trunk_sid


def _ensure_number(client: httpx.Client, trunk_sid: str) -> str:
    settings = get_settings()
    if not settings.exotel_from_number:
        raise SystemExit("EXOTEL_FROM_NUMBER (an Exophone in E.164) is required.")
    _payload(
        client.post(
            _api(f"/trunks/{trunk_sid}/phone-numbers"),
            json={"phone_number": settings.exotel_from_number, "mode": "pstn"},
        )
    )
    return settings.exotel_from_number


def _ensure_credentials(client: httpx.Client, trunk_sid: str) -> tuple[str, str]:
    settings = get_settings()
    username = settings.exotel_sip_username or f"voiceeval-{secrets.token_hex(3)}"
    password = settings.exotel_sip_password or secrets.token_urlsafe(18)
    _payload(
        client.post(
            _api(f"/trunks/{trunk_sid}/credentials"),
            json={
                "user_name": username,
                "password": password,
                "friendly_name": "voiceeval-livekit",
            },
        )
    )
    return username, password


def _edge_address(transport: str) -> str:
    settings = get_settings()
    port = _EDGE_PORTS.get(transport.lower(), 443)
    return f"{settings.exotel_account_sid}.pstn.exotel.com:{port}"


def setup() -> None:
    _require_settings()
    settings = get_settings()
    transport = settings.exotel_sip_transport
    with _client() as client:
        trunk_sid = _ensure_trunk(client)
        from_number = _ensure_number(client, trunk_sid)
        username, password = _ensure_credentials(client, trunk_sid)

    address = _edge_address(transport)
    print(f"\nexotel trunk sid : {trunk_sid}")
    print(f"edge address     : {address}  (transport={transport})")
    print(f"from number      : {from_number}")
    print(f"digest user      : {username}")
    print(
        "\nRegister the SIP integration account:\n"
        "  POST /api/v1/integrations/accounts\n"
        "  {\n"
        '    "provider_id": "prov_sip",\n'
        '    "name": "Exotel",\n'
        f'    "config": {{"address": "{address}", "from_number": "{from_number}", '
        f'"transport": "{transport}"}},\n'
        f'    "secrets": {{"username": "{username}", "password": "{password}"}}\n'
        "  }\n"
    )
    print("Then create a target with external_agent_id = the PSTN number to dial.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Exotel SIP for LiveKit")
    parser.add_argument("command", choices=["discover", "setup"])
    args = parser.parse_args()
    if args.command == "discover":
        discover()
    else:
        setup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
