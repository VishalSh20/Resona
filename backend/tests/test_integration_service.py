"""Integration account-creation flow tests (fakes, no database)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.services.integrations import IntegrationService


def _obj(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


class _FakeRepo:
    def __init__(self, provider: SimpleNamespace) -> None:
        self.provider = provider
        self.accounts: list[SimpleNamespace] = []

    async def get_provider(self, provider_id: str):
        return self.provider

    async def create_account(self, provider_id, name, *, config=None, status="active"):
        account = _obj(
            id=f"acct_{len(self.accounts) + 1}",
            provider_id=provider_id,
            name=name,
            config=config or {},
            status=status,
        )
        self.accounts.append(account)
        return account


class _FakeSecrets:
    def __init__(self) -> None:
        self.stored: list[tuple[str, str, str]] = []

    async def store(self, account_id: str, key: str, value: str) -> None:
        self.stored.append((account_id, key, value))


def _service(slug: str):
    provider = _obj(id=f"prov_{slug}", slug=slug)
    repo = _FakeRepo(provider)
    secrets = _FakeSecrets()
    service = IntegrationService(session=None, secrets=secrets)
    service._integrations = repo
    return service, repo, secrets


async def test_create_livekit_account_stores_two_secrets_and_url():
    service, repo, secrets = _service("livekit")

    account = await service.create_account(
        provider_id="prov_livekit",
        name="Vishal's LiveKit",
        config={"url": "wss://project.livekit.cloud"},
        secrets={"api_key": "key", "api_secret": "secret"},
    )

    assert account.config == {"url": "wss://project.livekit.cloud"}
    assert {key for _, key, _ in secrets.stored} == {"api_key", "api_secret"}


async def test_create_pipecat_account_requires_only_token():
    service, repo, secrets = _service("pipecat")

    account = await service.create_account(
        provider_id="prov_pipecat",
        name="Pipecat",
        secrets={"api_token": "tok"},
    )

    assert account.id == "acct_1"
    assert [key for _, key, _ in secrets.stored] == ["api_token"]


async def test_create_account_rejects_missing_secret():
    service, _, _ = _service("livekit")

    with pytest.raises(ValidationError):
        await service.create_account(
            provider_id="prov_livekit",
            name="LiveKit",
            config={"url": "wss://x"},
            secrets={"api_key": "key"},
        )


async def test_create_account_rejects_missing_config():
    service, _, _ = _service("livekit")

    with pytest.raises(ValidationError):
        await service.create_account(
            provider_id="prov_livekit",
            name="LiveKit",
            secrets={"api_key": "key", "api_secret": "secret"},
        )
