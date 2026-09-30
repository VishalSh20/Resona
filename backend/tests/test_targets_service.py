"""Target service integration-flow tests (fakes, no database/network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voiceeval.integrations.base import (
    PROVIDER_REVISION_TYPE_CONFIGURATION,
    CanonicalAgentRevision,
    ProviderAgentIdentity,
    ProviderRevision,
    ProviderRevisionSummary,
)
from voiceeval.services.targets import TargetService


def _obj(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


class _FakeTargets:
    def __init__(self) -> None:
        self.targets: list[SimpleNamespace] = []
        self.revisions: list[SimpleNamespace] = []

    async def create_target(self, name, *, provider_id, integration_account_id, external_agent_id=None, agent_url=None):
        target = _obj(
            id=f"agt_{len(self.targets) + 1}",
            name=name,
            provider_id=provider_id,
            integration_account_id=integration_account_id,
            external_agent_id=external_agent_id,
            agent_url=agent_url,
        )
        self.targets.append(target)
        return target

    async def find_by_external(self, provider_id, external_agent_id):
        for target in self.targets:
            if (
                target.provider_id == provider_id
                and target.external_agent_id == external_agent_id
            ):
                return target
        return None

    async def get_target(self, target_id: str):
        for target in self.targets:
            if target.id == target_id:
                return target
        raise ValueError(f"target {target_id} not found")

    async def create_revision(self, target_id, *, source_kind, canonical_config, source_config, config_hash, revision_no=None, **fields):
        if revision_no is None:
            revision_no = await self._next_revision_no(target_id)
        revision = _obj(
            id=f"targetrev_{len(self.revisions) + 1}",
            agent_target_id=target_id,
            revision_no=revision_no,
            source_kind=source_kind,
            canonical_config=canonical_config,
            source_config=source_config,
            config_hash=config_hash,
            **fields,
        )
        self.revisions.append(revision)
        return revision

    async def get_revision(self, revision_id: str):
        for revision in self.revisions:
            if revision.id == revision_id:
                return revision
        raise ValueError(f"revision {revision_id} not found")

    async def list_revisions(self, target_id: str):
        return [r for r in self.revisions if r.agent_target_id == target_id]

    async def find_revision_by_provider(self, target_id, provider_revision_id, source_branch_id):
        for revision in self.revisions:
            if (
                revision.agent_target_id == target_id
                and revision.provider_revision_id == provider_revision_id
                and revision.source_branch_id == source_branch_id
            ):
                return revision
        return None

    async def update_target(self, target, *, name=None, agent_url=None):
        if name is not None:
            target.name = name
        if agent_url is not None:
            target.agent_url = agent_url
        return target

    async def _next_revision_no(self, target_id: str) -> int:
        existing = [r.revision_no for r in self.revisions if r.agent_target_id == target_id]
        return (max(existing) if existing else 0) + 1


class _FakeIntegrations:
    def __init__(self) -> None:
        self.provider = _obj(id="prov_1", slug="retell")
        self.account = _obj(id="acct_1", provider_id="prov_1")

    async def get_provider(self, provider_id: str):
        return self.provider

    async def get_account(self, account_id: str):
        return self.account


class _FakeAdapter:
    provider_slug = "retell"

    def __init__(self) -> None:
        self.identity = ProviderAgentIdentity(
            external_agent_id="agent_123", name="Support Agent"
        )
        self.current = ProviderRevision(
            provider_revision_id="v7",
            provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
            raw_config={"agent": {"id": "agent_123"}},
            canonical_config=CanonicalAgentRevision(),
        )

    async def get_agent_identity(self, account, secrets, external_agent_id):
        return self.identity

    async def get_current_revision(self, account, secrets, external_agent_id):
        return self.current

    async def list_revisions(self, account, secrets, external_agent_id):
        return [
            ProviderRevisionSummary(provider_revision_id="v8"),
            ProviderRevisionSummary(provider_revision_id="v7"),
        ]

    async def get_revision(self, account, secrets, external_agent_id, provider_revision_id, *, branch_id=None):
        return ProviderRevision(
            provider_revision_id=provider_revision_id,
            provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
            raw_config={"agent": {"id": external_agent_id, "version": provider_revision_id}},
            canonical_config=CanonicalAgentRevision(),
            branch_id=branch_id,
        )

    def normalize_revision(self, revision):
        return revision.canonical_config


class _FakeSecrets:
    async def resolve(self, account_id, key):
        return "fake-secret-value"


def _service(monkeypatch, *, adapter=None):
    targets = _FakeTargets()
    integrations = _FakeIntegrations()
    adapter = adapter or _FakeAdapter()
    monkeypatch.setattr(
        "voiceeval.services.targets.get_adapter", lambda slug: adapter
    )
    service = TargetService(session=None, secrets=_FakeSecrets())
    service._targets = targets
    service._integrations = integrations
    return service, targets, integrations, adapter


async def test_manual_create_target(monkeypatch):
    service, targets, _, _ = _service(monkeypatch)

    target, revision = await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_1",
        name="Custom Agent",
    )

    assert target.name == "Custom Agent"
    assert target.external_agent_id is None
    assert revision.revision_no == 1
    assert revision.source_kind == "MANUAL"
    assert revision.provider_revision_id is None


async def test_provider_backed_create_imports_initial_revision(monkeypatch):
    service, targets, _, _ = _service(monkeypatch)

    target, revision = await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_1",
        external_agent_id="agent_123",
    )

    assert target.name == "Support Agent"
    assert target.external_agent_id == "agent_123"
    assert revision.revision_no == 1
    assert revision.source_kind == "IMPORTED"
    assert revision.provider_revision_id == "v7"


async def test_provider_backed_create_dedupes_by_external_id(monkeypatch):
    service, targets, _, _ = _service(monkeypatch)

    first_target, first_revision = await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_1",
        external_agent_id="agent_123",
    )

    # Re-adding the same external agent under a different account must reuse the
    # existing target instead of minting a duplicate agent row.
    second_target, second_revision = await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_2",
        external_agent_id="agent_123",
    )

    assert second_target.id == first_target.id
    assert second_revision.id == first_revision.id
    assert len(targets.targets) == 1  # no duplicate agent row


async def test_import_revision_is_deduplicated(monkeypatch):
    service, targets, _, _ = _service(monkeypatch)
    await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_1",
        external_agent_id="agent_123",
    )
    target = targets.targets[0]

    first = await service.import_revision(target.id, "v8")
    second = await service.import_revision(target.id, "v8")

    assert first.id == second.id
    assert len(targets.revisions) == 2  # initial + one imported


async def test_sync_target_is_idempotent(monkeypatch):
    service, targets, _, adapter = _service(monkeypatch)
    await service.create_target(
        provider_id="prov_1",
        integration_account_id="acct_1",
        external_agent_id="agent_123",
    )
    target = targets.targets[0]

    # current provider revision ("v7") was already imported at create time.
    first = await service.sync_target(target.id)
    second = await service.sync_target(target.id)

    assert first.provider_revision_id == "v7"
    assert first.id == second.id
    assert len(targets.revisions) == 1  # no duplicate

    # a new current provider revision appears -> sync imports it once.
    adapter.current = ProviderRevision(
        provider_revision_id="v8",
        provider_revision_type=PROVIDER_REVISION_TYPE_CONFIGURATION,
        raw_config={"agent": {"id": "agent_123"}},
        canonical_config=CanonicalAgentRevision(),
    )
    third = await service.sync_target(target.id)
    assert third.provider_revision_id == "v8"
    assert len(targets.revisions) == 2
