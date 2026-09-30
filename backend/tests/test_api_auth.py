"""Control-plane API authentication/authorization tests.

The whole ``/api/v1`` surface requires a user JWT; the only unauthenticated
endpoint is the signed media blob. These tests exercise missing/invalid/wrong-
scope tokens, the error envelope, request validation, the idempotency-header
requirement and the authorization happy path — without a database (the session
dependency is overridden with a stub).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from voiceeval.api.dependencies import get_session_dep
from voiceeval.auth.jwt import create_runner_token, create_user_token
from voiceeval.main import app


class _Scalars:
    def all(self):
        return []


class _Result:
    def scalars(self):
        return _Scalars()

    def scalar_one_or_none(self):
        return None

    def scalar_one(self):
        return 0

    def first(self):
        return None


class _StubSession:
    """Just enough session for read-only endpoints that return empty lists."""

    async def execute(self, stmt):
        return _Result()

    def add(self, obj):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def get(self, model, id_):
        return None


@pytest.fixture
async def anon_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def authed_client():
    async def _stub_session():
        yield _StubSession()

    app.dependency_overrides[get_session_dep] = _stub_session
    token = create_user_token("operator@example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()


# --- authentication ----------------------------------------------------------


async def test_missing_token_is_401_with_envelope(anon_client):
    response = await anon_client.get("/api/v1/targets")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "message" in body["error"]
    assert "request_id" in body["error"]


async def test_invalid_token_is_401(anon_client):
    response = await anon_client.get(
        "/api/v1/targets", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_runner_scope_is_forbidden_on_user_routes(anon_client):
    token = create_runner_token("runner-1", "att_1")
    response = await anon_client.get(
        "/api/v1/targets", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/targets",
        "/api/v1/benchmarks",
        "/api/v1/simulations",
        "/api/v1/simulations/sim_1",
        "/api/v1/runs/run_1",
        "/api/v1/runs/run_1/evaluators",
    ],
)
async def test_every_control_plane_surface_requires_auth(anon_client, path):
    response = await anon_client.get(path)
    assert response.status_code == 401


@pytest.mark.skip(
    reason="deferred: the signed media-blob route is re-mounted in the results pass"
)
async def test_signed_media_blob_is_public(anon_client):
    # No bearer token, but also no signature query params -> a validation error,
    # never 401. The signature/expiry authorises the request instead.
    response = await anon_client.get("/api/v1/media/blob")
    assert response.status_code == 422
    assert response.status_code != 401


async def test_authorized_read_succeeds(authed_client):
    response = await authed_client.get("/api/v1/targets")
    assert response.status_code == 200
    assert response.json() == []


# --- request validation ------------------------------------------------------


async def test_invalid_body_is_422(authed_client):
    response = await authed_client.post("/api/v1/targets", json={})
    assert response.status_code == 422


async def test_missing_idempotency_key_is_400(authed_client):
    response = await authed_client.post(
        "/api/v1/targets/agt_1/revisions",
        json={"provider_revision_id": "v4", "branch_id": None},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_idempotency_key_present_is_accepted(authed_client):
    # A valid key passes the dependency; the stub session then reports the
    # referenced target as missing, so we get a domain 404, not a 400.
    response = await authed_client.post(
        "/api/v1/targets/agt_1/revisions",
        json={"provider_revision_id": "v4", "branch_id": None},
        headers={"Idempotency-Key": "key-1"},
    )
    assert response.status_code == 404
