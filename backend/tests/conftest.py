"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from voiceeval.main import app
from voiceeval.runtime.scenario import parse_scenario


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# A canonical `evaluator.v1`-shaped scenario used by the runtime tests: the
# caller must verify their identity and get their objective fulfilled.
SCENARIO_CONTENT = {
    "motive": {
        "objective": "Get help with my account",
        "assertions": [
            {"id": "authentication_complete", "type": "state", "required": True},
            {"id": "objective_fulfilled", "type": "state", "required": True},
        ],
    },
    "facts": [{"id": "account_id", "value": "AC-1234"}],
    "initial_state": {"authenticated": False},
    "behaviour": {
        "allowed_actions": [
            "present_problem",
            "provide_information",
            "clarify",
            "recover",
            "acknowledge_resolution",
            "end_call",
        ],
        "recovery": {"max_attempts": 2},
    },
    "language": {"primary": "en-IN"},
}


@pytest.fixture
def scenario():
    return parse_scenario(SCENARIO_CONTENT)
