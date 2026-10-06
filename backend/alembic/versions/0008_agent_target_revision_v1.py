"""Redefine the agent target/revision model (V1) and add integration tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03

Breaks ``agent_target`` / ``agent_target_revision`` into the V1 model from
``docs/V2-changes/agent-definition-changes.md``:

    IntegrationProvider -> IntegrationAccount -> AgentTarget
        -> AgentTargetRevision -> AgentEndpoint -> ConnectionSession

``agent_target`` now points at a provider and an integration account instead of
carrying a free-text ``provider`` / ``description``. ``agent_target_revision``
now holds provider identity + configuration (``external_agent_id``, ``agent_url``,
``source_config``, ``canonical_config``, ...) instead of the transport/adapter/
endpoint/capability fields, which move to ``transport_type`` / ``agent_endpoint``.

Breaking and non-additive: the two target tables are dropped and recreated.
``simulation.agent_target_id`` and ``run.target_revision_id`` are re-wired to the
recreated tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- detach the surviving tables from the tables being rebuilt ----------
    op.drop_constraint(
        "simulation_agent_target_id_fkey", "simulation", type_="foreignkey"
    )
    op.drop_constraint("run_target_revision_id_fkey", "run", type_="foreignkey")

    op.drop_table("agent_target_revision")
    op.drop_table("agent_target")

    # --- integration + transport reference tables ---------------------------
    op.create_table(
        "integration_provider",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_integration_provider_slug"),
    )
    op.bulk_insert(
        sa.table(
            "integration_provider",
            sa.column("id", sa.String),
            sa.column("slug", sa.Text),
            sa.column("display_name", sa.Text),
            sa.column("capabilities", postgresql.JSONB),
        ),
        [
            {"id": "prov_retell", "slug": "retell", "display_name": "Retell", "capabilities": {}},
            {"id": "prov_vapi", "slug": "vapi", "display_name": "Vapi", "capabilities": {}},
            {"id": "prov_elevenlabs", "slug": "elevenlabs", "display_name": "ElevenLabs", "capabilities": {}},
            {"id": "prov_livekit", "slug": "livekit", "display_name": "LiveKit", "capabilities": {}},
            {"id": "prov_pipecat", "slug": "pipecat", "display_name": "Pipecat Cloud", "capabilities": {}},
        ],
    )
    op.create_table(
        "integration_account",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["integration_provider.id"]),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_integration_account_status"
        ),
    )
    op.create_index(
        "ix_integration_account_provider", "integration_account", ["provider_id"]
    )
    op.create_table(
        "integration_secret",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("integration_account_id", sa.String(64), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["integration_account_id"],
            ["integration_account.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "integration_account_id", "key", name="uq_integration_secret_account_key"
        ),
    )
    op.create_index(
        "ix_integration_secret_account", "integration_secret", ["integration_account_id"]
    )
    op.create_table(
        "transport_type",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_transport_type_slug"),
    )

    # --- agent target + revision (V1) ---------------------------------------
    op.create_table(
        "agent_target",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("integration_account_id", sa.String(64), nullable=False),
        sa.Column("external_agent_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("agent_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["integration_provider.id"]),
        sa.ForeignKeyConstraint(
            ["integration_account_id"], ["integration_account.id"]
        ),
        sa.UniqueConstraint(
            "integration_account_id",
            "external_agent_id",
            name="uq_agent_target_account_external_id",
        ),
    )
    op.create_index("ix_agent_target_provider", "agent_target", ["provider_id"])
    op.create_index(
        "ix_agent_target_account", "agent_target", ["integration_account_id"]
    )
    op.create_table(
        "agent_target_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_target_id", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("first_message", sa.Text(), nullable=True),
        sa.Column("llm_config", postgresql.JSONB(), nullable=True),
        sa.Column("stt_config", postgresql.JSONB(), nullable=True),
        sa.Column("tts_config", postgresql.JSONB(), nullable=True),
        sa.Column("turn_config", postgresql.JSONB(), nullable=True),
        sa.Column("conversation_config", postgresql.JSONB(), nullable=True),
        sa.Column("tools_config", postgresql.JSONB(), nullable=True),
        sa.Column("variables_config", postgresql.JSONB(), nullable=True),
        sa.Column("knowledge_config", postgresql.JSONB(), nullable=True),
        sa.Column("workflow_config", postgresql.JSONB(), nullable=True),
        sa.Column("handoffs_config", postgresql.JSONB(), nullable=True),
        sa.Column("guardrails_config", postgresql.JSONB(), nullable=True),
        sa.Column("canonical_config", postgresql.JSONB(), nullable=False),
        sa.Column("source_config", postgresql.JSONB(), nullable=False),
        sa.Column("provider_revision_id", sa.Text(), nullable=True),
        sa.Column("provider_revision_type", sa.String(32), nullable=True),
        sa.Column("revision_label", sa.Text(), nullable=True),
        sa.Column("source_branch_id", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_target_id"], ["agent_target.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "agent_target_id", "revision_no", name="uq_target_rev_no"
        ),
        sa.UniqueConstraint(
            "agent_target_id", "config_hash", name="uq_target_rev_config_hash"
        ),
        sa.UniqueConstraint(
            "agent_target_id",
            "provider_revision_id",
            "source_branch_id",
            name="uq_target_rev_provider",
        ),
        sa.CheckConstraint(
            "source_kind IN ('IMPORTED', 'MANUAL')",
            name="ck_target_rev_source_kind",
        ),
        sa.CheckConstraint(
            "provider_revision_type IN ('AGENT_CONFIGURATION', 'DEPLOYMENT')",
            name="ck_target_rev_type",
        ),
    )
    op.create_index(
        "ix_target_rev_target_revno",
        "agent_target_revision",
        ["agent_target_id", "revision_no"],
    )

    op.create_table(
        "agent_endpoint",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_target_revision_id", sa.String(64), nullable=False),
        sa.Column("transport_type_id", sa.String(64), nullable=False),
        sa.Column("connection_config", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_target_revision_id"],
            ["agent_target_revision.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["transport_type_id"], ["transport_type.id"]),
    )
    op.create_index(
        "ix_agent_endpoint_revision", "agent_endpoint", ["agent_target_revision_id"]
    )
    op.create_table(
        "connection_session",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("endpoint_id", sa.String(64), nullable=False),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'created'")),
        sa.Column("provider_session_id", sa.Text(), nullable=True),
        sa.Column("runtime_config", postgresql.JSONB(), nullable=True),
        sa.Column("ephemeral_data", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["endpoint_id"], ["agent_endpoint.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["agent_target_revision.id"]),
        sa.CheckConstraint(
            "status IN ('created','connecting','connected','terminated','failed')",
            name="ck_connection_session_status",
        ),
    )
    op.create_index("ix_connection_session_endpoint", "connection_session", ["endpoint_id"])
    op.create_index("ix_connection_session_revision", "connection_session", ["revision_id"])

    # --- re-wire the surviving tables ---------------------------------------
    op.create_foreign_key(
        "simulation_agent_target_id_fkey",
        "simulation",
        "agent_target",
        ["agent_target_id"],
        ["id"],
    )
    op.create_foreign_key(
        "run_target_revision_id_fkey",
        "run",
        "agent_target_revision",
        ["target_revision_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "simulation_agent_target_id_fkey", "simulation", type_="foreignkey"
    )
    op.drop_constraint("run_target_revision_id_fkey", "run", type_="foreignkey")

    op.drop_table("connection_session")
    op.drop_table("agent_endpoint")
    op.drop_table("agent_target_revision")
    op.drop_table("agent_target")
    op.drop_table("transport_type")
    op.drop_table("integration_secret")
    op.drop_table("integration_account")
    op.drop_table("integration_provider")

    # --- recreate the pre-V1 target tables ----------------------------------
    op.create_table(
        "agent_target",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "agent_target_revision",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_target_id", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("adapter_name", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("endpoint_config", postgresql.JSONB(), nullable=False),
        sa.Column("capability_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_target_id"], ["agent_target.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "agent_target_id", "revision_no", name="uq_target_rev_no"
        ),
        sa.UniqueConstraint(
            "agent_target_id", "config_hash", name="uq_target_rev_config_hash"
        ),
        sa.CheckConstraint(
            "transport IN ('websocket', 'webrtc')", name="ck_target_rev_transport"
        ),
    )
    op.create_index(
        "ix_target_rev_target_revno",
        "agent_target_revision",
        ["agent_target_id", "revision_no"],
    )

    op.create_foreign_key(
        "simulation_agent_target_id_fkey",
        "simulation",
        "agent_target",
        ["agent_target_id"],
        ["id"],
    )
    op.create_foreign_key(
        "run_target_revision_id_fkey",
        "run",
        "agent_target_revision",
        ["target_revision_id"],
        ["id"],
    )
