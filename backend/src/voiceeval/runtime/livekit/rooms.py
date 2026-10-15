"""LiveKit room lifecycle and explicit agent dispatch (§4.1).

The control plane creates a room per attempt, issues an **explicit named-agent
dispatch** (so the caller job never auto-joins arbitrary rooms), and always
deletes the room on any terminal state. Room deletion is also the cross-process
hard-cancel path (§10).
"""

from __future__ import annotations

from typing import Any

from voiceeval.core.config import get_settings
from voiceeval.core.errors import DependencyUnavailableError, ValidationError


def room_name_for_attempt(attempt_id: str) -> str:
    return f"attempt-{attempt_id}"


def _import_api() -> Any:
    try:
        from livekit import api  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional SDK
        raise DependencyUnavailableError(
            "livekit-api is not installed; LiveKit room management is unavailable"
        ) from exc
    return api


class LiveKitRoomManager:
    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        settings = get_settings()
        self._url = url or settings.livekit_url
        self._api_key = api_key or settings.livekit_api_key
        self._api_secret = api_secret or settings.livekit_api_secret
        self._empty_timeout_s = settings.livekit_room_empty_timeout_s
        self._max_participants = settings.livekit_room_max_participants

    def _require(self) -> None:
        if not (self._url and self._api_key and self._api_secret):
            raise ValidationError(
                "LiveKit is not configured (livekit_url/api_key/api_secret)"
            )

    def _client(self, api: Any) -> Any:
        return api.LiveKitAPI(
            url=self._url, api_key=self._api_key, api_secret=self._api_secret
        )

    async def create_room(
        self, room_name: str, *, empty_timeout_s: int | None = None
    ) -> None:
        self._require()
        api = _import_api()
        async with self._client(api) as client:
            await client.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=empty_timeout_s or self._empty_timeout_s,
                    max_participants=self._max_participants,
                )
            )

    async def delete_room(self, room_name: str) -> None:
        self._require()
        api = _import_api()
        async with self._client(api) as client:
            await client.room.delete_room(api.DeleteRoomRequest(room=room_name))

    async def dispatch_agent(
        self, room_name: str, *, agent_name: str, metadata: str
    ) -> str:
        self._require()
        api = _import_api()
        async with self._client(api) as client:
            dispatch = await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=agent_name, room=room_name, metadata=metadata
                )
            )
        return getattr(dispatch, "id", "")

    async def list_rooms(self, prefix: str = "attempt-") -> list[str]:
        self._require()
        api = _import_api()
        async with self._client(api) as client:
            response = await client.room.list_rooms(api.ListRoomsRequest())
        return [
            room.name for room in getattr(response, "rooms", []) if room.name.startswith(prefix)
        ]

    async def reap_stale_rooms(
        self, *, prefix: str = "attempt-", older_than_s: int
    ) -> list[str]:
        """Delete rooms older than the max attempt duration plus grace (§4.1)."""
        self._require()
        api = _import_api()
        deleted: list[str] = []
        async with self._client(api) as client:
            response = await client.room.list_rooms(api.ListRoomsRequest())
            for room in getattr(response, "rooms", []):
                if not room.name.startswith(prefix):
                    continue
                if int(getattr(room, "creation_time", 0)) and _age_s(room) > older_than_s:
                    await client.room.delete_room(api.DeleteRoomRequest(room=room.name))
                    deleted.append(room.name)
        return deleted


def _age_s(room: Any) -> int:
    import time

    creation = int(getattr(room, "creation_time", 0) or 0)
    return max(0, int(time.time()) - creation)


__all__ = ["LiveKitRoomManager", "room_name_for_attempt"]
