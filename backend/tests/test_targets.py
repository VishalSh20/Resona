"""Target config-hash, secret-detection and adapter-registry tests."""

from __future__ import annotations

import pytest

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.adapters import get_adapter_registry
from voiceeval.services.targets import (
    compute_target_config_hash,
    find_raw_secrets,
)


def _revision_args(**overrides):
    args = {
        "source_kind": "MANUAL",
        "first_message": None,
        "llm_config": {},
        "stt_config": {},
        "tts_config": {},
        "turn_config": {},
        "conversation_config": {},
        "tools_config": {},
        "variables_config": {},
        "knowledge_config": {},
        "workflow_config": {},
        "handoffs_config": {},
        "guardrails_config": {},
        "canonical_config": {"llm": {"model": "gpt-4o"}},
        "source_config": {"provider": "fake"},
        "provider_revision_id": None,
        "source_branch_id": None,
    }
    args.update(overrides)
    return args


def test_config_hash_is_deterministic():
    assert compute_target_config_hash(**_revision_args()) == compute_target_config_hash(
        **_revision_args()
    )


def test_config_hash_changes_with_config():
    a = compute_target_config_hash(**_revision_args())
    b = compute_target_config_hash(
        **_revision_args(canonical_config={"llm": {"model": "gpt-4o-mini"}})
    )
    assert a != b


def test_find_raw_secrets_detects_plain_value():
    secrets = find_raw_secrets({"url": "wss://x", "api_key": "sk-123"})
    assert "config.api_key" in secrets


def test_find_raw_secrets_allows_reference():
    secrets = find_raw_secrets({"api_key": {"$ref": "secret:acme/key"}})
    assert secrets == []


def test_find_raw_secrets_allows_secret_scheme_string():
    secrets = find_raw_secrets({"authorization": "secret:acme/token"})
    assert secrets == []


def test_adapter_registry_rejects_unknown():
    with pytest.raises(ValidationError):
        get_adapter_registry().ensure_exists("acme_ws", "2.1.0")


def test_adapter_registry_accepts_known():
    info = get_adapter_registry().ensure_exists("fake", "1.0.0")
    assert info.name == "fake"
