"""User and role persistence for credential authentication."""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.ids import new_plain_ulid
from voiceeval.db.models.support import User, UserRole
from voiceeval.db.repositories.base import Repository


class UserRepository(Repository):
    async def create_user(
        self,
        *,
        email: str | None = None,
        username: str | None = None,
        password_hash: str | None = None,
        is_active: bool = True,
    ) -> User:
        user = User(
            id=new_plain_ulid(),
            email=email,
            username=username,
            password_hash=password_hash,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_user(self, user_id: str) -> User:
        return await self._get(User, user_id, name="user")

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username).limit(1)
        )
        return result.scalar_one_or_none()

    async def add_role(self, user_id: str, role: str) -> UserRole:
        user_role = UserRole(id=new_plain_ulid(), user_id=user_id, role=role)
        self._session.add(user_role)
        await self._session.flush()
        return user_role

    async def list_roles(self, user_id: str) -> list[str]:
        result = await self._session.execute(
            select(UserRole.role).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())
