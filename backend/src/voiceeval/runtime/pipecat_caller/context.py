"""Resolve a prepared attempt into the naive caller's runtime inputs.

Everything is read from the immutable execution manifest through the shared
:func:`voiceeval.runtime.loader.load_attempt_context`, so the pipecat caller
takes exactly the same "details" as the LiveKit caller: scenario, persona,
target link and seed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ValidationError
from voiceeval.runtime.loader import load_attempt_context
from voiceeval.runtime.pipecat_caller.call_context import CallScript
from voiceeval.runtime.pipecat_caller.settings import PipecatCallerSettings


@dataclass(frozen=True)
class CallerContext:
    attempt_id: str
    script: CallScript
    target_ws_url: str
    target_headers: dict[str, str]
    target_protocol: str
    target_speaks_first: bool
    in_sample_rate: int
    out_sample_rate: int
    greet_first: bool
    language: str


#: Adapters that speak the voiceeval raw-PCM/JSON websocket protocol.
_VOICE_EVAL_ADAPTERS = frozenset({"fake", "websocket"})


def resolve_protocol(
    target_link: dict, endpoint: dict, settings: PipecatCallerSettings
) -> str:
    """Pick the wire protocol: explicit target choice, else adapter, else default."""
    explicit = endpoint.get("protocol")
    if explicit:
        return str(explicit)
    if str(target_link.get("adapter_name") or "") in _VOICE_EVAL_ADAPTERS:
        return "voiceeval"
    return settings.protocol


async def load_caller_context(
    session: AsyncSession,
    attempt_id: str,
    settings: PipecatCallerSettings,
) -> CallerContext:
    bundle = await load_attempt_context(session, attempt_id)

    target_link = bundle.target_link
    transport = str(target_link.get("transport") or "")
    if transport not in settings.allowed_transports:
        raise ValidationError(
            f"pipecat caller only dials {settings.allowed_transports} targets, "
            f"got {transport!r}"
        )
    endpoint = dict(target_link.get("endpoint_config") or {})
    url = endpoint.get("url")
    if not url:
        raise ValidationError(
            f"target link '{transport}' has no 'url' in its endpoint_config"
        )
    headers = {
        str(key): str(value) for key, value in (endpoint.get("headers") or {}).items()
    }

    return CallerContext(
        attempt_id=attempt_id,
        script=CallScript.from_scenario(
            bundle.scenario, bundle.persona, greet_first=settings.greet_first
        ),
        target_ws_url=str(url),
        target_headers=headers,
        target_protocol=resolve_protocol(target_link, endpoint, settings),
        target_speaks_first=bool(endpoint.get("target_speaks_first", True)),
        in_sample_rate=settings.in_sample_rate,
        out_sample_rate=settings.out_sample_rate,
        greet_first=settings.greet_first,
        language=settings.language,
    )


__all__ = ["CallerContext", "load_caller_context", "resolve_protocol"]
