"""ULID-style identifiers with domain prefixes.

Externally visible entities use a short domain prefix (``agt_``, ``run_`` ...)
followed by a lowercase ULID. The prefix makes an identifier self-describing;
the ULID provides a lexicographically sortable, time-ordered unique component.

The mapping is the single source of truth for which prefix belongs to which
entity kind, so callers never hand-concatenate strings.
"""

from __future__ import annotations

from enum import StrEnum

import ulid

from voiceeval.core.errors import ValidationError


class EntityKind(StrEnum):
    INTEGRATION_PROVIDER = "prov"
    INTEGRATION_ACCOUNT = "acct"
    INTEGRATION_SECRET = "isecret"
    TRANSPORT_TYPE = "transport"
    AGENT_TARGET = "agt"
    AGENT_TARGET_REVISION = "targetrev"
    AGENT_ENDPOINT = "endpoint"
    CONNECTION_SESSION = "conn"
    SIMULATION = "sim"
    RUN = "run"
    RUN_EVALUATOR = "runeval"
    CALL_RUN = "callrun"
    TEST_DESCRIPTOR = "td"
    TEST_DESCRIPTOR_REVISION = "tdrev"
    EVALUATOR = "eval"
    EVALUATOR_REVISION = "evalrev"
    BENCHMARK = "bench"
    BENCHMARK_VERSION = "benchver"
    PLAN = "plan"
    PLAN_ITEM = "planitem"
    MANIFEST = "manifest"
    ATTEMPT = "att"
    TURN = "turn"
    EVENT = "evt"
    MEDIA = "media"
    TOOL = "tool"
    STATE = "state"
    METRIC = "metric"
    JUDGE = "judge"
    EVIDENCE = "evidence"
    LEDGER = "ledger"
    PROBE = "probe"
    FINDING = "finding"
    JOB = "job"


# Prefix -> kind reverse map for parsing/validation.
_KIND_BY_PREFIX: dict[str, EntityKind] = {str(kind.value): kind for kind in EntityKind}


def new_id(kind: EntityKind) -> str:
    """Return a new externally visible identifier for ``kind``."""
    return f"{kind.value}_{ulid.new().str}"


def new_plain_ulid() -> str:
    """Return a bare ULID for entities without a documented domain prefix."""
    return ulid.new().str


def kind_of(value: str) -> EntityKind | None:
    prefix = value.split("_", 1)[0]
    return _KIND_BY_PREFIX.get(prefix)


def ensure_kind(value: str, kind: EntityKind) -> str:
    """Validate that ``value`` carries the expected ``kind`` prefix."""
    actual = kind_of(value)
    if actual is not kind:
        raise ValidationError(
            f"identifier '{value}' is not a valid {kind.value}_ identifier"
        )
    return value
