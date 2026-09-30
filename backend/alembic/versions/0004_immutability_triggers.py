"""Database-level immutability guards.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30

The design contract forbids mutation of raw runtime events, execution
manifests and media artifacts. Prompt 2 encoded that with an application-level
guard; this migration adds the database-level backstop the contract asks for
("do not rely only on application convention").

Three append-only tables get a BEFORE UPDATE OR DELETE trigger that raises:

  * ``runtime_event``      — raw evidence is append-only.
  * ``execution_manifest`` — the execution contract is immutable.
  * ``media_artifact``     — captured/derived media rows are immutable.

Derived tables (turns, tool calls, state transitions, metric results, …) are
deliberately NOT locked: they are rebuildable projections and may be replaced.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IMMUTABLE_TABLES = ("runtime_event", "execution_manifest", "media_artifact")

_BLOCK_FUNCTION = """
CREATE OR REPLACE FUNCTION voiceeval_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'table % is immutable; % is not permitted', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_BLOCK_FUNCTION)
    for table in _IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION voiceeval_block_mutation();
            """
        )


def downgrade() -> None:
    for table in _IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table};")
    op.execute("DROP FUNCTION IF EXISTS voiceeval_block_mutation();")
