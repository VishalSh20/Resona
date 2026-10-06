"""SIP provider adapter.

A SIP target is dialed through a LiveKit **outbound trunk** on our own project
(the SIP participant joins the caller's room). The trunk carries the remote SIP
server's address and, when it requires auth, a username/password — i.e. the
target's transport credentials, not a per-call secret.

Because the trunk is persistent (one per account, not per call), it is created
once at account setup (:meth:`SipAdapter.provision_account`) and its id is cached
in the account's non-secret ``config``. The revision's endpoint is therefore
static: it just names the destination (``to_number`` / ``sip_uri``) to dial.
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import get_settings
from voiceeval.core.errors import (
    DependencyUnavailableError,
    ResourceNotFoundError,
    ValidationError,
)
from voiceeval.db.models.domain import IntegrationAccount
from voiceeval.integrations.base import (
    PROVIDER_REVISION_TYPE_DEPLOYMENT,
    BaseAgentProviderAdapter,
    CanonicalAgentRevision,
    CredentialField,
    ProviderAgentIdentity,
    ProviderEndpoint,
    ProviderRevision,
    ProviderRevisionSummary,
    SecretResolver,
)

ADDRESS_CONFIG = "address"
FROM_NUMBER_CONFIG = "from_number"
TRANSPORT_CONFIG = "transport"
TRUNK_ID_CONFIG = "livekit_trunk_id"
USERNAME_SECRET = "username"
PASSWORD_SECRET = "password"

#: transport name -> LiveKit ``SIPTransport`` proto value.
_TRANSPORT_CODES = {"auto": 0, "udp": 1, "tcp": 2, "tls": 3}


def _transport_code(name: Any) -> int:
    return _TRANSPORT_CODES.get(str(name or "auto").lower(), 0)


def _import_api() -> Any:
    try:
        from livekit import api  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        raise DependencyUnavailableError(
            "livekit-api is not installed; the 'sip' target is unavailable"
        ) from exc
    return api


async def ensure_outbound_trunk(
    *,
    name: str,
    address: str,
    username: str | None,
    password: str | None,
    from_number: str | None,
    transport: str = "auto",
) -> str | None:
    """Create (or reuse) a LiveKit outbound trunk toward a SIP server.

    Used both when provisioning a ``sip`` integration account and when a client
    supplies a trunk inline. Idempotent by ``name``.
    """
    settings = get_settings()
    if not (
        settings.livekit_url
        and settings.livekit_api_key
        and settings.livekit_api_secret
    ):
        raise ValidationError(
            "LiveKit is not configured; cannot provision the SIP outbound trunk"
        )
    api = _import_api()
    async with api.LiveKitAPI(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    ) as client:
        list_fn = getattr(client.sip, "list_outbound_trunk", None) or getattr(
            client.sip, "list_sip_outbound_trunk"
        )
        existing = await list_fn(api.ListSIPOutboundTrunkRequest())
        for trunk in getattr(existing, "items", None) or []:
            if getattr(trunk, "name", None) == name:
                return getattr(trunk, "sip_trunk_id", None)

        create_fn = getattr(client.sip, "create_outbound_trunk", None) or getattr(
            client.sip, "create_sip_outbound_trunk"
        )
        trunk = await create_fn(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name=name,
                    address=address,
                    numbers=[from_number] if from_number else [],
                    auth_username=username or "",
                    auth_password=password or "",
                    transport=_transport_code(transport),
                )
            )
        )
    return getattr(trunk, "sip_trunk_id", None)


async def _try_resolve(
    secrets: SecretResolver, account_id: str, key: str
) -> str | None:
    try:
        return await secrets.resolve(account_id, key)
    except ResourceNotFoundError:
        return None


class SipAdapter(BaseAgentProviderAdapter):
    provider_slug = "sip"

    CREDENTIAL_SPEC = (
        CredentialField(
            key=ADDRESS_CONFIG, label="SIP address (host/domain)", secret=False
        ),
        CredentialField(
            key=FROM_NUMBER_CONFIG,
            label="From number / caller ID",
            secret=False,
            required=False,
        ),
        CredentialField(
            key=TRANSPORT_CONFIG,
            label="Transport (auto|udp|tcp|tls)",
            secret=False,
            required=False,
        ),
        CredentialField(key=USERNAME_SECRET, label="SIP username", required=False),
        CredentialField(key=PASSWORD_SECRET, label="SIP password", required=False),
    )

    def credential_spec(self):
        return list(self.CREDENTIAL_SPEC)

    async def validate_connection(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> None:
        if not (account.config or {}).get(ADDRESS_CONFIG):
            raise ValidationError("sip account requires an 'address'")

    async def provision_account(
        self, account: IntegrationAccount, secrets: SecretResolver
    ) -> dict[str, Any]:
        """Create (or reuse) the LiveKit outbound trunk for this SIP account."""
        config = account.config or {}
        address = config.get(ADDRESS_CONFIG)
        if not address:
            return {}
        username = await _try_resolve(secrets, account.id, USERNAME_SECRET)
        password = await _try_resolve(secrets, account.id, PASSWORD_SECRET)
        trunk_id = await ensure_outbound_trunk(
            name=f"resona-sip-{account.id}",
            address=address,
            username=username,
            password=password,
            from_number=config.get(FROM_NUMBER_CONFIG),
            transport=config.get(TRANSPORT_CONFIG) or "auto",
        )
        return {TRUNK_ID_CONFIG: trunk_id}

    async def validate_agent_reference(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return self._identity(external_agent_id)

    async def get_agent_identity(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderAgentIdentity:
        return self._identity(external_agent_id)

    @staticmethod
    def _identity(external_agent_id: str) -> ProviderAgentIdentity:
        # The "agent id" for a SIP target is the destination we dial.
        return ProviderAgentIdentity(
            external_agent_id=external_agent_id,
            name=external_agent_id,
            agent_url=None,
        )

    @staticmethod
    def _revision(provider_revision_id: str | None) -> ProviderRevision:
        return ProviderRevision(
            provider_revision_id=provider_revision_id,
            provider_revision_type=PROVIDER_REVISION_TYPE_DEPLOYMENT,
            raw_config={},
            canonical_config=CanonicalAgentRevision(),
            revision_label=provider_revision_id,
        )

    async def get_current_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> ProviderRevision:
        return self._revision(None)

    async def list_revisions(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
    ) -> list[ProviderRevisionSummary]:
        return []

    async def get_revision(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        external_agent_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> ProviderRevision:
        return self._revision(provider_revision_id)

    def normalize_revision(self, revision: ProviderRevision) -> CanonicalAgentRevision:
        return revision.canonical_config

    async def get_endpoints(
        self,
        account: IntegrationAccount,
        secrets: SecretResolver,
        agent: ProviderAgentIdentity,
        revision: ProviderRevision,
    ) -> list[ProviderEndpoint]:
        """A static SIP endpoint: the destination plus the provisioned trunk id.

        The trunk itself holds the credentials, so nothing secret is stored in
        (or frozen with) the endpoint.
        """
        config = account.config or {}
        connection: dict[str, Any] = {
            "provider": "sip",
            "to_number": agent.external_agent_id,
            "trunk_id": config.get(TRUNK_ID_CONFIG),
            "from_number": config.get(FROM_NUMBER_CONFIG),
            "address": config.get(ADDRESS_CONFIG),
        }
        return [
            ProviderEndpoint(
                transport="sip",
                connection_config={
                    key: value for key, value in connection.items() if value is not None
                },
            )
        ]
