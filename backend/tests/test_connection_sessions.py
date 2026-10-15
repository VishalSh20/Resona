"""ConnectionSession persistence: create/update transitions (fake session, no DB)."""

from __future__ import annotations

from voiceeval.db.repositories import IntegrationRepository


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def get(self, model, id_):
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == id_:
                return obj
        return None


async def test_create_connection_session_tracks_lifecycle():
    repo = IntegrationRepository(_FakeSession())

    connection = await repo.create_connection_session(
        endpoint_id="endpoint_1", revision_id="targetrev_1", status="connecting"
    )
    assert connection.id.startswith("conn_")
    assert connection.status == "connecting"
    assert connection.connected_at is None

    connected = await repo.update_connection_session(
        connection.id, status="connected", provider_session_id="call_9"
    )
    assert connected.status == "connected"
    assert connected.provider_session_id == "call_9"
    assert connected.connected_at is not None

    ended = await repo.update_connection_session(connection.id, status="terminated")
    assert ended.status == "terminated"
    assert ended.provider_session_id == "call_9"  # not cleared
    assert ended.ended_at is not None


async def test_create_connection_session_connected_sets_connected_at():
    repo = IntegrationRepository(_FakeSession())
    connection = await repo.create_connection_session(
        endpoint_id="endpoint_1", revision_id="targetrev_1", status="connected"
    )
    assert connection.connected_at is not None
