"""HTTP tests for the AI generation + run-configuration surface.

Workflow A is exercised end-to-end with a static generation model; Workflow B
and the run lifecycle are exercised through request validation and the
not-found path using a stubbed session (no database).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from voiceeval.api.dependencies import get_session_dep
from voiceeval.auth.jwt import create_user_token
from voiceeval.llm import (
    StaticDecisionModel,
    StaticGenerationModel,
    set_decision_model,
    set_generation_model,
)
from voiceeval.main import app

_PREFERENCES_RESPONSES = [
    '{"objectives":["resolve"],"behavioral_requirements":["handle frustration"],'
    '"failure_modes":[],"task_characteristics":[],"language_requirements":["hi"],'
    '"caller_stressors":["impatience"],"knowledge_dependence":"high",'
    '"temporal_sensitivity":"low","ambiguity_flags":[]}',
    '{"items": ['
    '{"metric":"task_completion","reason":"goal resolution"},'
    '{"metric":"hallucination","reason":"grounding"}'
    "]}",
    '{"items": [{"personality":"IMPATIENT","reason":"pressure"}]}',
]


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


@pytest.fixture(autouse=True)
def _reset_models():
    yield
    set_generation_model(None)
    set_decision_model(None)


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


# --- Workflow A: simulation preferences -------------------------------------


async def test_simulation_preferences_requires_auth(anon_client):
    response = await anon_client.post(
        "/api/v1/generation/simulation-preferences",
        json={
            "description": "handle blocked cards",
            "available_metrics": ["task_completion"],
            "available_personalities": ["IMPATIENT"],
        },
    )
    assert response.status_code == 401


async def test_simulation_preferences_selects_via_llm(authed_client):
    set_generation_model(StaticGenerationModel(list(_PREFERENCES_RESPONSES)))

    response = await authed_client.post(
        "/api/v1/generation/simulation-preferences",
        json={
            "description": "Handle blocked cards with frustrated callers.",
            "available_metrics": ["task_completion", "hallucination", "ttfa"],
            "available_personalities": ["IMPATIENT", "SUPPORTIVE"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["metrics"]) == {"task_completion", "hallucination"}
    assert body["personalities"] == ["IMPATIENT"]


async def test_simulation_preferences_unknown_metric_is_400(authed_client):
    response = await authed_client.post(
        "/api/v1/generation/simulation-preferences",
        json={
            "description": "anything",
            "available_metrics": ["not_a_metric"],
            "available_personalities": ["IMPATIENT"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- Workflow B: generate evaluators for a run ------------------------------


async def test_generate_evaluators_requires_workflow_spec(authed_client):
    response = await authed_client.post(
        "/api/v1/runs/run_1/evaluators/generate",
        json={},
        headers={"Idempotency-Key": "key-1"},
    )
    assert response.status_code == 422


async def test_generate_evaluators_missing_run_is_404(authed_client):
    response = await authed_client.post(
        "/api/v1/runs/run_1/evaluators/generate",
        json={"workflow_spec": {}},
        headers={"Idempotency-Key": "key-2"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# --- Run lifecycle: mark ready ----------------------------------------------


async def test_mark_run_ready_missing_run_is_404(authed_client):
    response = await authed_client.post("/api/v1/runs/run_1/ready")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# --- Simulation creation route smoke ----------------------------------------


async def test_create_simulation_missing_target_is_404(authed_client):
    response = await authed_client.post(
        "/api/v1/simulations",
        json={
            "name": "Credit Card Support",
            "agent_target_id": "agt_1",
            "target_revision_id": "targetrev_1",
            "languages": ["en", "hi"],
            "call_ambience": ["QUIET"],
            "metric_set": ["task_completion"],
            "personalities": ["IMPATIENT"],
            "evaluator_count": 2,
        },
        headers={"Idempotency-Key": "key-3"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_create_simulation_rejects_bad_evaluator_count(authed_client):
    response = await authed_client.post(
        "/api/v1/simulations",
        json={
            "name": "Bad",
            "agent_target_id": "agt_1",
            "target_revision_id": "targetrev_1",
            "languages": ["en"],
            "call_ambience": ["QUIET"],
            "metric_set": ["task_completion"],
            "personalities": ["IMPATIENT"],
            "evaluator_count": 0,
        },
        headers={"Idempotency-Key": "key-4"},
    )
    assert response.status_code == 422
