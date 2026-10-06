"""Provision outbound SIP for the caller: Twilio trunk + LiveKit outbound trunk.

Reads credentials from the environment (see ``core/config.py``):

    TWILIO_ACCOUNT_SID        # AC... (required)
    TWILIO_SIP                # Twilio API Key SID (SK...)
    TWILIO_CLIENT_SECRET      # Twilio API Key secret
    TWILIO_SIP_TRUNK_DOMAIN   # optional: existing trunk termination domain
    TWILIO_SIP_USERNAME       # optional: existing SIP credential username
    TWILIO_SIP_PASSWORD       # optional: existing SIP credential password
    TWILIO_FROM_NUMBER        # optional: caller ID (E.164), must be on the trunk

Usage:
    python scripts/sip_setup.py discover          # read-only: list trunks/creds/numbers
    python scripts/sip_setup.py setup             # provision missing pieces + LiveKit trunk
    python scripts/sip_setup.py setup --trunk-sid TK...  # use a specific Twilio trunk

Idempotent: reuses existing trunks, credential lists and numbers.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

import httpx

from voiceeval.core.config import get_settings

# Elastic SIP Trunking lives on its own host; phone numbers stay on the REST API.
TRUNKING_API = "https://trunking.twilio.com/v1"


def _auth() -> tuple[str, str]:
    settings = get_settings()
    if not settings.twilio_account_sid:
        raise SystemExit("TWILIO_ACCOUNT_SID is required (AC...).")
    if not settings.twilio_api_key_sid or not settings.twilio_api_key_secret:
        raise SystemExit("TWILIO_SIP (API Key SID) and TWILIO_CLIENT_SECRET are required.")
    return settings.twilio_api_key_sid, settings.twilio_api_key_secret


def _trunk_client() -> httpx.Client:
    return httpx.Client(base_url=TRUNKING_API, auth=_auth(), timeout=30.0)


def _numbers_client() -> httpx.Client:
    settings = get_settings()
    base = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
    return httpx.Client(base_url=base, auth=_auth(), timeout=30.0)


def _get(client: httpx.Client, path: str, key: str) -> list[dict]:
    response = client.get(path)
    if response.status_code >= 400:
        raise SystemExit(_twilio_error(path, response))
    return response.json().get(key, [])


def _twilio_error(path: str, response: httpx.Response) -> str:
    detail = response.text[:300] if response.text else ""
    hint = ""
    if "Trial account" in detail:
        hint = (
            "\n  -> Elastic SIP Trunking requires a paid Twilio account; "
            "upgrade the account or use another trunk provider (Telnyx/Plivo)."
        )
    return f"Twilio {response.status_code} on {path}: {detail}{hint}"


def list_trunks(client: httpx.Client) -> list[dict]:
    return _get(client, "/Trunks", "trunks")


def trunk_detail(client: httpx.Client, trunk_sid: str) -> dict:
    return client.get(f"/Trunks/{trunk_sid}").raise_for_status().json()


def trunk_credential_lists(client: httpx.Client, trunk_sid: str) -> list[dict]:
    return _get(client, f"/Trunks/{trunk_sid}/CredentialLists", "credential_lists")


def trunk_numbers(client: httpx.Client, trunk_sid: str) -> list[dict]:
    return _get(client, f"/Trunks/{trunk_sid}/PhoneNumbers", "phone_numbers")


def incoming_numbers(client: httpx.Client) -> list[dict]:
    return _get(client, "/IncomingPhoneNumbers.json", "incoming_phone_numbers")


def credential_items(client: httpx.Client, credential_list_sid: str) -> list[dict]:
    return _get(
        client, f"/CredentialLists/{credential_list_sid}/Credentials", "credentials"
    )


def termination_domain(trunk: dict) -> str:
    domain = trunk.get("domain_name") or ""
    if domain.endswith(".pstn.twilio.com"):
        return domain
    return f"{domain}.pstn.twilio.com" if domain else ""


def discover() -> None:
    settings = get_settings()
    with _trunk_client() as tr, _numbers_client() as nums:
        trunks = list_trunks(tr)
        print(f"account {settings.twilio_account_sid}: {len(trunks)} SIP trunk(s)")
        for trunk in trunks:
            sid = trunk["sid"]
            creds = trunk_credential_lists(tr, sid)
            numbers = trunk_numbers(tr, sid)
            print(
                f"  {sid} name={trunk.get('friendly_name')} "
                f"termination={termination_domain(trunk)}\n"
                f"    credential_lists={[c['sid'] for c in creds]}\n"
                f"    numbers={[n.get('phone_number') for n in numbers]}"
            )
            for cl in creds:
                print(
                    f"    users[{cl['sid']}]: "
                    f"{[u['username'] for u in credential_items(tr, cl['sid'])]}"
                )
        print(f"incoming numbers: {[n.get('phone_number') for n in incoming_numbers(nums)][:20]}")


def _ensure_trunk(client: httpx.Client, trunk_sid: str | None) -> dict:
    if trunk_sid:
        return trunk_detail(client, trunk_sid)
    trunks = list_trunks(client)
    if trunks:
        return trunk_detail(client, trunks[0]["sid"])
    print("creating Twilio Elastic SIP trunk ...")
    return client.post("/Trunks", data={"FriendlyName": "voiceeval"}).raise_for_status().json()


def _ensure_credential(client: httpx.Client, trunk_sid: str) -> tuple[str, str]:
    settings = get_settings()
    username = settings.twilio_sip_username or f"voiceeval-{secrets.token_hex(3)}"
    password = settings.twilio_sip_password or secrets.token_urlsafe(16)

    existing = trunk_credential_lists(client, trunk_sid)
    if existing:
        # Reuse the attached credential list; the caller must supply the known
        # password (we cannot read it back from Twilio).
        return username, password
    print("creating credential list + credential ...")
    cl = client.post("/CredentialLists", data={"FriendlyName": "voiceeval"}).raise_for_status().json()
    client.post(
        f"/CredentialLists/{cl['sid']}/Credentials",
        data={"Username": username, "Password": password},
    ).raise_for_status()
    client.post(
        f"/Trunks/{trunk_sid}/CredentialLists",
        data={"CredentialListSid": cl["sid"]},
    ).raise_for_status()
    return username, password


def _ensure_number(client: httpx.Client, trunk_sid: str) -> str:
    settings = get_settings()
    if settings.twilio_from_number:
        with _numbers_client() as nums:
            for n in incoming_numbers(nums):
                if n.get("phone_number") == settings.twilio_from_number:
                    client.post(
                        f"/Trunks/{trunk_sid}/PhoneNumbers",
                        data={"PhoneNumberSid": n["sid"]},
                    ).raise_for_status()
                    return settings.twilio_from_number
        raise SystemExit(f"number {settings.twilio_from_number} not found on the account")
    attached = trunk_numbers(client, trunk_sid)
    if attached:
        return attached[0]["phone_number"]
    with _numbers_client() as nums:
        available = incoming_numbers(nums)
    if not available:
        raise SystemExit("no Twilio phone numbers on the account; buy one first")
    client.post(
        f"/Trunks/{trunk_sid}/PhoneNumbers",
        data={"PhoneNumberSid": available[0]["sid"]},
    ).raise_for_status()
    return available[0]["phone_number"]


def _create_livekit_trunk(domain: str, username: str, password: str, from_number: str) -> str:
    from livekit import api

    settings = get_settings()

    async def _run() -> str:
        client = api.LiveKitAPI(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        try:
            trunk = await client.sip.create_sip_outbound_trunk(
                api.CreateSIPOutboundTrunkRequest(
                    trunk=api.SIPOutboundTrunkInfo(
                        name="twilio",
                        address=domain,
                        numbers=[from_number],
                        auth_username=username,
                        auth_password=password,
                    )
                )
            )
        finally:
            await client.aclose()
        return getattr(trunk, "sip_trunk_id", None) or ""

    return asyncio.run(_run())


def setup(trunk_sid: str | None) -> None:
    settings = get_settings()
    with _trunk_client() as client:
        trunk = _ensure_trunk(client, trunk_sid)
        sid = trunk["sid"]
        domain = settings.twilio_sip_trunk_domain or termination_domain(trunk)
        if not domain:
            raise SystemExit("trunk has no domain; set TWILIO_SIP_TRUNK_DOMAIN")
        username, password = _ensure_credential(client, sid)
        from_number = _ensure_number(client, sid)
        print(f"twilio trunk sid   : {sid}")
        print(f"termination domain : {domain}")
        print(f"credential user    : {username}")
        print(f"from number        : {from_number}")

    lk_trunk_id = _create_livekit_trunk(domain, username, password, from_number)
    print(f"livekit outbound trunk: {lk_trunk_id}")
    print("\nAdd to backend/.env:")
    print(f"  TWILIO_ACCOUNT_SID={settings.twilio_account_sid}")
    print(f"  TWILIO_SIP_TRUNK_DOMAIN={domain}")
    print(f"  TWILIO_SIP_USERNAME={username}")
    print(f"  TWILIO_SIP_PASSWORD={password}")
    print(f"  TWILIO_FROM_NUMBER={from_number}")
    print(f"  LIVEKIT_SIP_OUTBOUND_TRUNK_ID={lk_trunk_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision outbound SIP (Twilio + LiveKit)")
    parser.add_argument("command", choices=["discover", "setup"])
    parser.add_argument("--trunk-sid", default=None)
    args = parser.parse_args()
    if args.command == "discover":
        discover()
    else:
        setup(args.trunk_sid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
