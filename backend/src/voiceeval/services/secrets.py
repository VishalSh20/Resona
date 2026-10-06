"""Encrypted provider-secret storage.

Provider credentials are encrypted at rest with a deployment master key (a
Fernet key from ``Settings.secret_encryption_key``) and referenced from
``config`` / ``source_config`` via ``secret:`` refs. Plaintext secrets never
live in JSONB configuration.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.config import get_settings
from voiceeval.core.errors import ValidationError
from voiceeval.db.repositories import IntegrationRepository


def _fernet() -> Fernet:
    key = get_settings().secret_encryption_key
    if not key:
        raise ValidationError(
            "secret_encryption_key is not configured; cannot encrypt or decrypt "
            "provider secrets"
        )
    return Fernet(key.encode("utf-8"))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("stored provider secret could not be decrypted") from exc


class SecretService:
    """Resolve/store encrypted integration secrets.

    Exposes ``async resolve(account_id, key)`` so it can be handed to integration
    adapters as their ``SecretResolver`` dependency.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._secrets = IntegrationRepository(session)

    async def store(self, account_id: str, key: str, value: str) -> None:
        await self._secrets.store_secret(account_id, key, encrypt_secret(value))

    async def resolve(self, account_id: str, key: str) -> str:
        secret = await self._secrets.get_secret(account_id, key)
        return decrypt_secret(secret.encrypted_value)
