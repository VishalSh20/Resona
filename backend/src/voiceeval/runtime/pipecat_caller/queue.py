"""Claim queued call attempts from the database for the pipecat caller.

The pipecat caller is the sole consumer of websocket-transport attempts. The
claim is a ``SELECT ... FOR UPDATE SKIP LOCKED`` so several supervisor processes
can poll the same queue without ever double-running an attempt.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.models import domain
from voiceeval.db.models import runtime
from voiceeval.domain.enums import AttemptStatus


def _transport_is_websocket(allowed: Sequence[str]):
    snapshot = domain.ExecutionManifest.target_snapshot
    return snapshot["target_link"]["transport"].astext.in_(list(allowed))


def pending_attempts_statement(limit: int, allowed_transports: Sequence[str]):
    """The ``SELECT ... FOR UPDATE SKIP LOCKED`` that claims queued attempts."""
    return (
        select(runtime.CallAttempt)
        .join(
            domain.ExecutionManifest,
            runtime.CallAttempt.execution_manifest_id == domain.ExecutionManifest.id,
        )
        .where(runtime.CallAttempt.status == AttemptStatus.QUEUED.value)
        .where(_transport_is_websocket(allowed_transports))
        .order_by(runtime.CallAttempt.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True, of=runtime.CallAttempt)
    )


async def claim_pending_attempts(
    session: AsyncSession,
    limit: int,
    *,
    allowed_transports: Sequence[str],
) -> list[runtime.CallAttempt]:
    """Return up to ``limit`` queued websocket attempts, locked for this caller."""
    if limit <= 0 or not allowed_transports:
        return []
    result = await session.execute(
        pending_attempts_statement(limit, allowed_transports)
    )
    return list(result.scalars().all())


__all__ = ["claim_pending_attempts", "pending_attempts_statement"]
