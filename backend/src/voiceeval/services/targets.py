"""Agent target + revision domain operations.

Implements the provider-integration flow on top of the shared
``AgentProviderAdapter`` interface. Provider-specific API knowledge never lives
here: ``create``, ``discover``, ``import_revision`` and ``sync`` all resolve an
adapter by ``IntegrationProvider.slug`` and work only against the common
interface.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ConflictError, ValidationError
from voiceeval.db.models import domain
from voiceeval.db.repositories import IntegrationRepository, TargetRepository
from voiceeval.integrations.base import (
    CLIENT_CONNECTION_KINDS,
    CanonicalAgentRevision,
    ProviderAgentIdentity,
    ProviderRevision,
    ProviderRevisionSummary,
    SecretResolver,
)
from voiceeval.integrations.registry import get_adapter
from voiceeval.services.secrets import SecretService

_SECRET_HINT_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "credential",
    "authorization",
    "private_key",
)

_SOURCE_KINDS = {"IMPORTED", "MANUAL"}

#: transport slug → (display name, category) for ``transport_type`` seeding.
_TRANSPORT_META = {
    "room": ("LiveKit Room", "webrtc"),
    "sip": ("SIP", "pstn"),
    "bridge": ("Protocol Bridge", "websocket"),
    "whip": ("WHIP", "webrtc"),
    "webrtc": ("WebRTC", "webrtc"),
    "websocket": ("WebSocket", "websocket"),
}


class _InlineSecretResolver:
    """Resolves secrets from a caller-supplied dict, never from storage."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets

    async def resolve(self, account_id: str, key: str) -> str:
        if key not in self._secrets:
            raise ValidationError(f"missing required secret '{key}'")
        return self._secrets[key]


def _is_secret_reference(value: Any) -> bool:
    if isinstance(value, dict) and ("$ref" in value or "secret_ref" in value):
        return True
    if isinstance(value, str) and (
        value.startswith("secret:")
        or value.startswith("secrets.")
        or value.startswith("$ref:")
    ):
        return True
    return False


def find_raw_secrets(config: Any, prefix: str = "config") -> list[str]:
    """Return paths in ``config`` that hold raw secrets instead of references."""
    found: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}"
                key_lower = key.lower()
                is_secret_key = any(frag in key_lower for frag in _SECRET_HINT_FRAGMENTS)
                if is_secret_key and not _is_secret_reference(value):
                    found.append(child_path)
                walk(value, child_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(config, prefix)
    return found


def compute_target_config_hash(
    *,
    first_message: str | None,
    llm_config: dict[str, Any] | None,
    stt_config: dict[str, Any] | None,
    tts_config: dict[str, Any] | None,
    turn_config: dict[str, Any] | None,
    conversation_config: dict[str, Any] | None,
    tools_config: dict[str, Any] | None,
    variables_config: dict[str, Any] | None,
    knowledge_config: dict[str, Any] | None,
    workflow_config: dict[str, Any] | None,
    handoffs_config: dict[str, Any] | None,
    guardrails_config: dict[str, Any] | None,
    canonical_config: dict[str, Any],
    source_config: dict[str, Any],
    provider_revision_id: str | None,
    source_branch_id: str | None,
    source_kind: str,
) -> str:
    """Derive a stable hash over the revision-defining configuration fields."""
    payload = {
        "first_message": first_message,
        "llm_config": llm_config or {},
        "stt_config": stt_config or {},
        "tts_config": tts_config or {},
        "turn_config": turn_config or {},
        "conversation_config": conversation_config or {},
        "tools_config": tools_config or {},
        "variables_config": variables_config or {},
        "knowledge_config": knowledge_config or {},
        "workflow_config": workflow_config or {},
        "handoffs_config": handoffs_config or {},
        "guardrails_config": guardrails_config or {},
        "canonical_config": canonical_config or {},
        "source_config": source_config or {},
        "provider_revision_id": provider_revision_id,
        "source_branch_id": source_branch_id,
        "source_kind": source_kind,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TargetService:
    def __init__(
        self, session: AsyncSession, *, secrets: SecretResolver | None = None
    ) -> None:
        self._session = session
        self._targets = TargetRepository(session)
        self._integrations = IntegrationRepository(session)
        self._secrets: SecretResolver = secrets or SecretService(session)

    # -- creation ------------------------------------------------------------

    async def create_target(
        self,
        *,
        provider_id: str,
        integration_account_id: str,
        name: str | None = None,
        external_agent_id: str | None = None,
        agent_url: str | None = None,
        description: str | None = None,
        first_message: str | None = None,
        llm_config: dict[str, Any] | None = None,
        stt_config: dict[str, Any] | None = None,
        tts_config: dict[str, Any] | None = None,
        turn_config: dict[str, Any] | None = None,
        conversation_config: dict[str, Any] | None = None,
        tools_config: dict[str, Any] | None = None,
        variables_config: dict[str, Any] | None = None,
        knowledge_config: dict[str, Any] | None = None,
        workflow_config: dict[str, Any] | None = None,
        handoffs_config: dict[str, Any] | None = None,
        guardrails_config: dict[str, Any] | None = None,
    ) -> tuple[domain.AgentTarget, domain.AgentTargetRevision]:
        account = await self._integrations.get_account(integration_account_id)
        if account.provider_id != provider_id:
            raise ValidationError(
                "integration account does not belong to the target's provider"
            )
        provider = await self._integrations.get_provider(provider_id)

        if external_agent_id is not None:
            adapter = get_adapter(provider.slug)
            existing = await self._targets.find_by_external(
                provider.id, external_agent_id
            )
            if existing is not None:
                return await self._reuse_or_import_revision(
                    existing, account, adapter, external_agent_id
                )
            return await self._create_provider_backed(
                provider, account, adapter, external_agent_id
            )

        if not name:
            raise ValidationError("name is required for a manual agent target")

        canonical = CanonicalAgentRevision(
            first_message=first_message,
            llm_config=llm_config,
            stt_config=stt_config,
            tts_config=tts_config,
            turn_config=turn_config,
            conversation_config=conversation_config,
            tools_config=tools_config,
            variables_config=variables_config,
            knowledge_config=knowledge_config,
            workflow_config=workflow_config,
            handoffs_config=handoffs_config,
            guardrails_config=guardrails_config,
        )
        target = await self._targets.create_target(
            name=name,
            provider_id=provider_id,
            integration_account_id=integration_account_id,
            external_agent_id=None,
            agent_url=agent_url,
        )
        revision = await self._persist_revision(
            target,
            source_kind="MANUAL",
            canonical=canonical,
            source_config={},
            provider_revision_id=None,
            provider_revision_type=None,
            revision_label=None,
            source_branch_id=None,
            description=description,
            source_updated_at=None,
        )
        return target, revision

    async def _create_provider_backed(
        self,
        provider: domain.IntegrationProvider,
        account: domain.IntegrationAccount,
        adapter,
        external_agent_id: str,
    ) -> tuple[domain.AgentTarget, domain.AgentTargetRevision]:
        identity = await adapter.get_agent_identity(
            account, self._secrets, external_agent_id
        )
        target = await self._targets.create_target(
            name=identity.name,
            provider_id=provider.id,
            integration_account_id=account.id,
            external_agent_id=identity.external_agent_id,
            agent_url=identity.agent_url,
        )
        current = await adapter.get_current_revision(
            account, self._secrets, external_agent_id
        )
        canonical = adapter.normalize_revision(current)
        revision = await self._persist_imported_revision(target, current, canonical)
        await self._persist_endpoints(account, adapter, identity, current, revision.id)
        return target, revision

    async def _reuse_or_import_revision(
        self,
        target: domain.AgentTarget,
        account: domain.IntegrationAccount,
        adapter,
        external_agent_id: str,
    ) -> tuple[domain.AgentTarget, domain.AgentTargetRevision]:
        """Return an existing target + its latest revision (import when absent).

        Keeps provider-backed target creation idempotent by external agent id: when
        the same external agent is re-added under a different (fresh) integration
        account, we reuse the existing target instead of minting a duplicate row —
        the cause of the agent list growing one entry per re-provision.
        """
        revisions = await self._targets.list_revisions(target.id)
        if revisions:
            return target, revisions[-1]

        current = await adapter.get_current_revision(
            account, self._secrets, external_agent_id
        )
        canonical = adapter.normalize_revision(current)
        revision = await self._persist_imported_revision(target, current, canonical)
        identity = ProviderAgentIdentity(
            external_agent_id=target.external_agent_id or "",
            name=target.name,
            agent_url=target.agent_url,
        )
        await self._persist_endpoints(account, adapter, identity, current, revision.id)
        return target, revision

    # -- discovery / import / sync ------------------------------------------

    async def preview_target(
        self,
        *,
        provider_id: str,
        external_agent_id: str,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
    ) -> tuple[ProviderAgentIdentity, ProviderRevision]:
        """Fetch + normalize the current provider revision without persisting.

        Used by the frontend to preview agent details before committing to an
        account + target. Secrets are resolved inline and never stored.
        """
        provider = await self._integrations.get_provider(provider_id)
        adapter = get_adapter(provider.slug)
        account = SimpleNamespace(id="preview", config=config or {})
        resolver = _InlineSecretResolver(secrets or {})
        identity = await adapter.get_agent_identity(
            account, resolver, external_agent_id
        )
        current = await adapter.get_current_revision(
            account, resolver, external_agent_id
        )
        return identity, current

    async def discover_revisions(
        self, target_id: str
    ) -> list[tuple[ProviderRevisionSummary, bool]]:
        target, _account, adapter = await self._load_target_and_adapter(target_id)
        candidates = await adapter.list_revisions(
            _account, self._secrets, target.external_agent_id
        )
        result: list[tuple[ProviderRevisionSummary, bool]] = []
        for candidate in candidates:
            already = (
                await self._targets.find_revision_by_provider(
                    target_id, candidate.provider_revision_id, candidate.branch_id
                )
                is not None
            )
            result.append((candidate, already))
        return result

    async def import_revision(
        self,
        target_id: str,
        provider_revision_id: str,
        *,
        branch_id: str | None = None,
    ) -> domain.AgentTargetRevision:
        target, account, adapter = await self._load_target_and_adapter(target_id)
        existing = await self._targets.find_revision_by_provider(
            target_id, provider_revision_id, branch_id
        )
        if existing is not None:
            return existing

        provider_revision = await adapter.get_revision(
            account,
            self._secrets,
            target.external_agent_id,
            provider_revision_id,
            branch_id=branch_id,
        )
        canonical = adapter.normalize_revision(provider_revision)
        revision = await self._persist_imported_revision(
            target, provider_revision, canonical
        )
        identity = ProviderAgentIdentity(
            external_agent_id=target.external_agent_id or "",
            name=target.name,
            agent_url=target.agent_url,
        )
        await self._persist_endpoints(
            account, adapter, identity, provider_revision, revision.id
        )
        return revision

    async def sync_target(self, target_id: str) -> domain.AgentTargetRevision:
        target, account, adapter = await self._load_target_and_adapter(target_id)
        identity = await adapter.get_agent_identity(
            account, self._secrets, target.external_agent_id
        )
        await self._targets.update_target(
            target, name=identity.name, agent_url=identity.agent_url
        )

        current = await adapter.get_current_revision(
            account, self._secrets, target.external_agent_id
        )
        existing = await self._targets.find_revision_by_provider(
            target_id, current.provider_revision_id, current.branch_id
        )
        if existing is not None:
            # Refresh the reachable endpoints for an already-imported revision:
            # a revision can exist without its endpoint rows (e.g. it was
            # imported before endpoint persistence, or discovery failed), which
            # would leave it unrunnable.
            await self._persist_endpoints(
                account, adapter, identity, current, existing.id
            )
            return existing

        canonical = adapter.normalize_revision(current)
        revision = await self._persist_imported_revision(target, current, canonical)
        await self._persist_endpoints(account, adapter, identity, current, revision.id)
        return revision

    # -- read ----------------------------------------------------------------

    async def get_target(self, target_id: str) -> domain.AgentTarget:
        return await self._targets.get_target(target_id)

    async def list_targets(self) -> list[domain.AgentTarget]:
        return await self._targets.list_targets()

    async def get_revision(self, revision_id: str) -> domain.AgentTargetRevision:
        return await self._targets.get_revision(revision_id)

    async def list_revisions(
        self, target_id: str
    ) -> list[domain.AgentTargetRevision]:
        return await self._targets.list_revisions(target_id)

    # -- client-supplied connection -----------------------------------------

    async def set_connection(
        self,
        target_id: str,
        *,
        kind: str,
        transport: str | None = None,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
        revision_id: str | None = None,
    ) -> domain.AgentTargetRevision:
        """Attach a client-supplied connection to a target revision.

        ``kind`` is the client vocabulary (``websocket``/``webrtc``/``sip``);
        ``transport`` optionally overrides the TargetLink slug (e.g. ``whip``
        instead of ``room`` for webrtc). Non-secret ``config`` is stored on the
        endpoint (frozen into the manifest); ``secrets`` are encrypted on the
        target's integration account as ``conn_<name>``.
        """
        target = await self._targets.get_target(target_id)
        if revision_id is not None:
            revision = await self._targets.get_revision(revision_id)
        else:
            revisions = await self._targets.list_revisions(target_id)
            if not revisions:
                raise ValidationError(f"agent target '{target_id}' has no revision")
            revision = revisions[-1]

        slug = transport or CLIENT_CONNECTION_KINDS.get(kind)
        if slug is None:
            raise ValidationError(
                f"unknown connection kind '{kind}'; expected one of "
                f"{sorted(CLIENT_CONNECTION_KINDS)}"
            )
        config = dict(config or {})
        self._validate_connection(slug, config)

        display, category = _TRANSPORT_META.get(slug, (slug, "other"))
        transport_type = await self._integrations.ensure_transport_type(
            slug, display, category
        )
        await self._integrations.upsert_endpoint(
            agent_target_revision_id=revision.id,
            transport_type_id=transport_type.id,
            connection_config={**config, "client_supplied": True},
        )
        for name, value in (secrets or {}).items():
            await self._secrets.store(
                target.integration_account_id, f"conn_{name}", value
            )
        return revision

    @staticmethod
    def _validate_connection(slug: str, config: dict[str, Any]) -> None:
        if slug in {"bridge", "room", "whip"} and not config.get("url"):
            raise ValidationError(f"'{slug}' connection requires 'url' in config")
        if slug == "sip":
            if not config.get("address"):
                raise ValidationError("'sip' connection requires 'address' in config")
            if not (config.get("to_number") or config.get("sip_uri")):
                raise ValidationError(
                    "'sip' connection requires 'to_number' or 'sip_uri' in config"
                )

    # -- internals -----------------------------------------------------------

    async def _load_target_and_adapter(self, target_id: str):
        target = await self._targets.get_target(target_id)
        if target.external_agent_id is None:
            raise ValidationError(
                f"agent target '{target_id}' is manual and has no provider agent to sync"
            )
        account = await self._integrations.get_account(target.integration_account_id)
        provider = await self._integrations.get_provider(target.provider_id)
        adapter = get_adapter(provider.slug)
        return target, account, adapter

    async def _persist_endpoints(
        self,
        account: domain.IntegrationAccount,
        adapter,
        identity: ProviderAgentIdentity,
        provider_revision: ProviderRevision,
        revision_id: str,
    ) -> int:
        """Resolve a provider's reachable endpoints into ``transport_type`` +
        ``agent_endpoint`` rows (the integrations → TargetLink hand-off, §14.3).

        Endpoint discovery is best-effort: a provider that exposes no stable
        endpoint (or a discovery error) must not fail the config import.
        """
        try:
            endpoints = await adapter.get_endpoints(
                account, self._secrets, identity, provider_revision
            )
        except Exception:
            return 0
        stored = 0
        for endpoint in endpoints:
            display, category = _TRANSPORT_META.get(
                endpoint.transport, (endpoint.transport, "other")
            )
            transport_type = await self._integrations.ensure_transport_type(
                endpoint.transport, display, category
            )
            await self._integrations.upsert_endpoint(
                agent_target_revision_id=revision_id,
                transport_type_id=transport_type.id,
                connection_config=dict(endpoint.connection_config or {}),
            )
            stored += 1
        return stored

    async def _persist_imported_revision(
        self,
        target: domain.AgentTarget,
        provider_revision: ProviderRevision,
        canonical: CanonicalAgentRevision,
    ) -> domain.AgentTargetRevision:
        return await self._persist_revision(
            target,
            source_kind="IMPORTED",
            canonical=canonical,
            source_config=provider_revision.raw_config,
            provider_revision_id=provider_revision.provider_revision_id,
            provider_revision_type=provider_revision.provider_revision_type,
            revision_label=provider_revision.revision_label,
            source_branch_id=provider_revision.branch_id,
            description=provider_revision.description,
            source_updated_at=provider_revision.source_updated_at,
        )

    async def _persist_revision(
        self,
        target: domain.AgentTarget,
        *,
        source_kind: str,
        canonical: CanonicalAgentRevision,
        source_config: dict[str, Any],
        provider_revision_id: str | None,
        provider_revision_type: str | None,
        revision_label: str | None,
        source_branch_id: str | None,
        description: str | None,
        source_updated_at: datetime | None,
    ) -> domain.AgentTargetRevision:
        if source_kind not in _SOURCE_KINDS:
            raise ValidationError(f"source_kind must be one of {sorted(_SOURCE_KINDS)}")

        canonical_dict = canonical.as_dict()
        secrets = find_raw_secrets(canonical_dict, prefix="canonical_config")
        if source_kind == "MANUAL":
            secrets += find_raw_secrets(source_config, prefix="source_config")
        if secrets:
            raise ValidationError(
                "agent configuration must not contain raw secrets; use secret "
                f"references instead (found: {', '.join(secrets)})"
            )

        config_hash = compute_target_config_hash(
            first_message=canonical.first_message,
            llm_config=canonical.llm_config,
            stt_config=canonical.stt_config,
            tts_config=canonical.tts_config,
            turn_config=canonical.turn_config,
            conversation_config=canonical.conversation_config,
            tools_config=canonical.tools_config,
            variables_config=canonical.variables_config,
            knowledge_config=canonical.knowledge_config,
            workflow_config=canonical.workflow_config,
            handoffs_config=canonical.handoffs_config,
            guardrails_config=canonical.guardrails_config,
            canonical_config=canonical_dict,
            source_config=source_config,
            provider_revision_id=provider_revision_id,
            source_branch_id=source_branch_id,
            source_kind=source_kind,
        )

        try:
            return await self._targets.create_revision(
                target.id,
                source_kind=source_kind,
                canonical_config=canonical_dict,
                source_config=source_config,
                description=description,
                first_message=canonical.first_message,
                llm_config=canonical.llm_config,
                stt_config=canonical.stt_config,
                tts_config=canonical.tts_config,
                turn_config=canonical.turn_config,
                conversation_config=canonical.conversation_config,
                tools_config=canonical.tools_config,
                variables_config=canonical.variables_config,
                knowledge_config=canonical.knowledge_config,
                workflow_config=canonical.workflow_config,
                handoffs_config=canonical.handoffs_config,
                guardrails_config=canonical.guardrails_config,
                provider_revision_id=provider_revision_id,
                provider_revision_type=provider_revision_type,
                revision_label=revision_label,
                source_branch_id=source_branch_id,
                source_updated_at=source_updated_at,
                config_hash=config_hash,
            )
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "a target revision with this configuration already exists",
                code="CONFIG_ALREADY_EXISTS",
            ) from exc
