"""Judge-definition and judge-execution persistence."""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import results
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import JudgeExecutionStatus


class JudgeRepository(Repository):
    async def create_definition(
        self,
        *,
        judge_key: str,
        version: str,
        kind: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        rubric_version: str | None = None,
        output_schema_version: str | None = None,
        config: dict | None = None,
    ) -> results.JudgeDefinition:
        definition = results.JudgeDefinition(
            id=new_id(EntityKind.JUDGE),
            judge_key=judge_key,
            version=version,
            kind=kind,
            provider=provider,
            model=model,
            prompt_hash=prompt_hash,
            rubric_version=rubric_version,
            output_schema_version=output_schema_version,
            config=config,
        )
        self._session.add(definition)
        await self._session.flush()
        return definition

    async def get_definition(self, definition_id: str) -> results.JudgeDefinition:
        return await self._get(
            results.JudgeDefinition, definition_id, name="judge definition"
        )

    async def find_definition(
        self, judge_key: str, version: str
    ) -> results.JudgeDefinition | None:
        result = await self._session.execute(
            select(results.JudgeDefinition)
            .where(results.JudgeDefinition.judge_key == judge_key)
            .where(results.JudgeDefinition.version == version)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_create_definition(
        self,
        *,
        judge_key: str,
        version: str,
        kind: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        rubric_version: str | None = None,
        output_schema_version: str | None = None,
        config: dict | None = None,
    ) -> results.JudgeDefinition:
        existing = await self.find_definition(judge_key, version)
        if existing is not None:
            return existing
        return await self.create_definition(
            judge_key=judge_key,
            version=version,
            kind=kind,
            provider=provider,
            model=model,
            prompt_hash=prompt_hash,
            rubric_version=rubric_version,
            output_schema_version=output_schema_version,
            config=config,
        )

    async def list_definitions(self) -> list[results.JudgeDefinition]:
        result = await self._session.execute(select(results.JudgeDefinition))
        return list(result.scalars().all())

    async def create_execution(
        self,
        *,
        call_run_id: str,
        judge_definition_id: str,
        input_hash: str | None = None,
        call_attempt_id: str | None = None,
        rubric_version: str | None = None,
    ) -> results.JudgeExecution:
        execution = results.JudgeExecution(
            id=new_id(EntityKind.JUDGE),
            call_run_id=call_run_id,
            call_attempt_id=call_attempt_id,
            judge_definition_id=judge_definition_id,
            input_hash=input_hash,
            rubric_version=rubric_version,
            status=JudgeExecutionStatus.PENDING.value,
        )
        self._session.add(execution)
        await self._session.flush()
        return execution

    async def get_execution(self, execution_id: str) -> results.JudgeExecution:
        return await self._get(
            results.JudgeExecution, execution_id, name="judge execution"
        )

    async def update_execution(
        self,
        execution: results.JudgeExecution,
        *,
        status: str,
        raw_output: dict | None = None,
        parsed_output: dict | None = None,
        latency_ms: int | None = None,
        input_hash: str | None = None,
        evidence_coverage: float | None = None,
        needs_human_review: bool | None = None,
        alignment_conflict: bool | None = None,
        media_validation: dict | None = None,
    ) -> results.JudgeExecution:
        execution.status = status
        if raw_output is not None:
            execution.raw_output = raw_output
        if parsed_output is not None:
            execution.parsed_output = parsed_output
        if latency_ms is not None:
            execution.latency_ms = latency_ms
        if input_hash is not None:
            execution.input_hash = input_hash
        if evidence_coverage is not None:
            execution.evidence_coverage = evidence_coverage
        if needs_human_review is not None:
            execution.needs_human_review = needs_human_review
        if alignment_conflict is not None:
            execution.alignment_conflict = alignment_conflict
        if media_validation is not None:
            execution.media_validation = media_validation
        await self._session.flush()
        return execution

    async def list_executions(self, call_run_id: str) -> list[results.JudgeExecution]:
        result = await self._session.execute(
            select(results.JudgeExecution).where(
                results.JudgeExecution.call_run_id == call_run_id
            )
        )
        return list(result.scalars().all())
