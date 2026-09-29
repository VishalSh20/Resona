"""Target and target-revision persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository


class TargetRepository(Repository):
    async def create_target(
        self,
        name: str,
        *,
        provider_id: str,
        integration_account_id: str,
        external_agent_id: str | None = None,
        agent_url: str | None = None,
    ) -> domain.AgentTarget:
        target = domain.AgentTarget(
            id=new_id(EntityKind.AGENT_TARGET),
            name=name,
            provider_id=provider_id,
            integration_account_id=integration_account_id,
            external_agent_id=external_agent_id,
            agent_url=agent_url,
        )
        self._session.add(target)
        await self._session.flush()
        return target

    async def get_target(self, target_id: str) -> domain.AgentTarget:
        return await self._get(domain.AgentTarget, target_id, name="agent target")

    async def list_targets(self) -> list[domain.AgentTarget]:
        result = await self._session.execute(select(domain.AgentTarget))
        return list(result.scalars().all())

    async def find_by_external(
        self, provider_id: str, external_agent_id: str
    ) -> domain.AgentTarget | None:
        """Find an existing target for a provider by its external agent id.

        Used to make provider-backed target creation idempotent: re-adding the
        same external agent must not mint a duplicate row even when the caller
        presents a different (fresh) integration account.
        """
        result = await self._session.execute(
            select(domain.AgentTarget)
            .where(
                domain.AgentTarget.provider_id == provider_id,
                domain.AgentTarget.external_agent_id == external_agent_id,
            )
            .order_by(domain.AgentTarget.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_revision(
        self,
        target_id: str,
        *,
        source_kind: str,
        canonical_config: dict[str, Any],
        source_config: dict[str, Any],
        config_hash: str,
        description: str | None = None,
        first_message: str | None = None,
        llm_config: dict[str, Any] | None = None,
        stt_config: dict[str, Any] | None = None,
        tts_config: dict[str, Any] | None = None,
        turn_config: dict[str, Any] | None = None,
        conversation_config: dict[str, Any] | None = None,
        tools_config: dict[str, Any] | None = None,
        variables_config: dict[str, Any] | None = None,
        knowledge_config: dict[str, Any] | None = None,
        workflow_config: dict[str, Any] | None = None,
        handoffs_config: dict[str, Any] | None = None,
        guardrails_config: dict[str, Any] | None = None,
        provider_revision_id: str | None = None,
        provider_revision_type: str | None = None,
        revision_label: str | None = None,
        source_branch_id: str | None = None,
        source_updated_at: datetime | None = None,
        revision_no: int | None = None,
        created_by: str | None = None,
    ) -> domain.AgentTargetRevision:
        await self.get_target(target_id)
        if revision_no is None:
            revision_no = await self._next_revision_no(target_id)
        revision = domain.AgentTargetRevision(
            id=new_id(EntityKind.AGENT_TARGET_REVISION),
            agent_target_id=target_id,
            revision_no=revision_no,
            description=description,
            first_message=first_message,
            llm_config=llm_config,
            stt_config=stt_config,
            tts_config=tts_config,
            turn_config=turn_config,
            conversation_config=conversation_config,
            tools_config=tools_config,
            variables_config=variables_config,
            knowledge_config=knowledge_config,
            workflow_config=workflow_config,
            handoffs_config=handoffs_config,
            guardrails_config=guardrails_config,
            canonical_config=canonical_config,
            source_config=source_config,
            provider_revision_id=provider_revision_id,
            provider_revision_type=provider_revision_type,
            revision_label=revision_label,
            source_branch_id=source_branch_id,
            source_updated_at=source_updated_at,
            config_hash=config_hash,
            source_kind=source_kind,
            created_by=created_by,
        )
        self._session.add(revision)
        await self._session.flush()
        return revision

    async def get_revision(self, revision_id: str) -> domain.AgentTargetRevision:
        return await self._get(
            domain.AgentTargetRevision, revision_id, name="agent target revision"
        )

    async def list_revisions(
        self, target_id: str
    ) -> list[domain.AgentTargetRevision]:
        result = await self._session.execute(
            select(domain.AgentTargetRevision)
            .where(domain.AgentTargetRevision.agent_target_id == target_id)
            .order_by(domain.AgentTargetRevision.revision_no)
        )
        return list(result.scalars().all())

    async def find_revision_by_provider(
        self, target_id: str, provider_revision_id: str, source_branch_id: str | None
    ) -> domain.AgentTargetRevision | None:
        result = await self._session.execute(
            select(domain.AgentTargetRevision).where(
                domain.AgentTargetRevision.agent_target_id == target_id,
                domain.AgentTargetRevision.provider_revision_id == provider_revision_id,
                domain.AgentTargetRevision.source_branch_id == source_branch_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_target(
        self,
        target: domain.AgentTarget,
        *,
        name: str | None = None,
        agent_url: str | None = None,
    ) -> domain.AgentTarget:
        if name is not None:
            target.name = name
        if agent_url is not None:
            target.agent_url = agent_url
        await self._session.flush()
        return target

    async def _next_revision_no(self, target_id: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(domain.AgentTargetRevision.revision_no), 0)).where(
                domain.AgentTargetRevision.agent_target_id == target_id
            )
        )
        return int(result.scalar_one()) + 1
