"""Adapter mapping + registry tests (pure, no network)."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.integrations.elevenlabs import map_revision as elevenlabs_map
from voiceeval.integrations.registry import get_adapter, known_provider_slugs
from voiceeval.integrations.retell import map_identity, map_revision
from voiceeval.integrations.vapi import map_identity as vapi_identity
from voiceeval.integrations.vapi import map_revision as vapi_map


def test_registry_knows_all_providers():
    assert known_provider_slugs() == {
        "retell",
        "vapi",
        "elevenlabs",
        "livekit",
        "pipecat",
        "sip",
        "custom",
    }


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValidationError):
        get_adapter("does_not_exist")


def test_credential_specs():
    assert [f.key for f in get_adapter("retell").credential_spec()] == ["api_key"]
    assert [f.key for f in get_adapter("vapi").credential_spec()] == ["api_key"]
    assert [f.key for f in get_adapter("elevenlabs").credential_spec()] == [
        "api_key",
        "livekit_url",
    ]
    assert [f.key for f in get_adapter("pipecat").credential_spec()] == ["api_token"]

    sip = {f.key: f for f in get_adapter("sip").credential_spec()}
    assert list(sip) == ["address", "from_number", "transport", "username", "password"]
    assert sip["address"].secret is False and sip["address"].required is True
    assert sip["username"].secret is True and sip["username"].required is False

    livekit = {f.key: f for f in get_adapter("livekit").credential_spec()}
    assert list(livekit) == ["api_key", "api_secret", "url"]
    assert livekit["api_key"].secret is True
    assert livekit["url"].secret is False


def test_retell_maps_identity():
    identity = map_identity({"agent_id": "abc123", "agent_name": "Support"})
    assert identity.external_agent_id == "abc123"
    assert identity.name == "Support"


def test_retell_maps_revision_from_response_engine():
    agent = {"agent_id": "abc", "version": "v3", "version_description": "updated"}
    engine = {
        "general_prompt": "You are helpful",
        "begin_message": "Hello",
        "model": "gpt-4o",
        "tools": [{"name": "lookup"}],
    }
    revision = map_revision(agent, engine)

    assert revision.provider_revision_id == "v3"
    assert revision.provider_revision_type == "AGENT_CONFIGURATION"
    assert revision.description == "updated"
    assert revision.canonical_config.first_message == "Hello"
    assert revision.canonical_config.llm_config == {"model": "gpt-4o"}
    assert revision.canonical_config.tools_config == [{"name": "lookup"}]
    assert revision.raw_config == {"agent": agent, "response_engine": engine}


def test_vapi_maps_identity_and_revision():
    assistant = {
        "id": "a1",
        "name": "Support",
        "latestVersion": "v7",
        "firstMessage": "Hi there",
        "model": {"provider": "openai", "tools": [{"name": "lookup"}]},
        "transcriber": {"provider": "deepgram"},
        "voice": {"provider": "elevenlabs"},
    }
    identity = vapi_identity(assistant)
    assert identity.external_agent_id == "a1"

    revision = vapi_map(assistant)
    assert revision.provider_revision_id == "v7"
    assert revision.canonical_config.first_message == "Hi there"
    assert revision.canonical_config.llm_config == {"provider": "openai"}
    assert revision.canonical_config.tools_config == [{"name": "lookup"}]
    assert revision.canonical_config.stt_config == {"provider": "deepgram"}
    assert revision.canonical_config.tts_config == {"provider": "elevenlabs"}


def test_vapi_extracts_variables_from_message_list():
    assistant = {
        "id": "a1",
        "latestVersion": "v7",
        "firstMessage": "Hi {{first_name}}",
        "model": {
            "provider": "openai",
            "messages": [
                {"role": "system", "content": "Help {{customer_name}} today"},
                {"role": "user", "content": "{{customer_name}} also needs {{account_id}}"},
                "not-a-message",
            ],
        },
    }
    revision = vapi_map(assistant)
    assert revision.canonical_config.variables_config == {
        "first_name": {},
        "customer_name": {},
        "account_id": {},
    }


def test_vapi_description_from_system_message():
    assistant = {
        "id": "a1",
        "latestVersion": "v7",
        "model": {
            "provider": "openai",
            "messages": [
                {"role": "system", "content": "You are a receptionist"},
                {"role": "user", "content": "hi"},
            ],
        },
    }
    revision = vapi_map(assistant)
    assert revision.description == "You are a receptionist"


def test_retell_normalizes_dynamic_variables_to_dict():
    agent = {"agent_id": "abc", "version": "v3"}
    engine = {
        "general_prompt": "Hi",
        "dynamic_variables": [
            {"name": "first_name", "type": "string"},
            "account_id",
        ],
    }
    revision = map_revision(agent, engine)
    assert revision.canonical_config.variables_config == {
        "first_name": {"type": "string"},
        "account_id": {},
    }


def test_elevenlabs_maps_version_and_branch():
    agent = {
        "agent_id": "a1",
        "name": "Support",
        "version_id": "agtvrsn_001",
        "branch_id": "main",
        "conversation_config": {
            "agent": {"prompt": "sys prompt"},
            "asr": {"model": "whisper"},
            "tts": {"model": "eleven"},
        },
    }
    revision = elevenlabs_map(agent)

    assert revision.provider_revision_id == "agtvrsn_001"
    assert revision.branch_id == "main"
    assert revision.canonical_config.stt_config == {"model": "whisper"}
    assert revision.canonical_config.tts_config == {"model": "eleven"}
