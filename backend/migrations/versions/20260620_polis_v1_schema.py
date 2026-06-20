"""polis v1 a2a schema

Revision ID: 20260620_polis_v1
Revises:
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260620_polis_v1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


agent_auth_method = postgresql.ENUM(
    "bearer", "hmac", "none", name="agent_auth_method", create_type=False
)
agent_status = postgresql.ENUM(
    "online", "offline", "busy", name="agent_status", create_type=False
)
job_status = postgresql.ENUM(
    "submitted", "claimed", "working", "completed", "failed", "canceled",
    name="job_status", create_type=False,
)
artifact_type = postgresql.ENUM(
    "text", "file", "json", "image", name="artifact_type", create_type=False
)
job_event_type = postgresql.ENUM(
    "created", "claimed", "progress", "delivered", "rated", "canceled",
    name="job_event_type", create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND (
                    tablename LIKE 'task_%'
                    OR tablename LIKE 'feed_%'
                    OR tablename IN (
                        'agent_follows',
                        'tasks',
                        'owners',
                        'agents',
                        'posts',
                        'comments',
                        'likes',
                        'follows',
                        'reputation_events',
                        'audit_logs',
                        'fraud_detection_logs',
                        'fraud_alerts',
                        'reputation_scores'
                    )
                  )
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
            END LOOP;
        END $$;
        """
    )

    bind = op.get_bind()
    agent_auth_method.create(bind, checkfirst=True)
    agent_status.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)
    artifact_type.create(bind, checkfirst=True)
    job_event_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("websocket_id", sa.String(length=255), nullable=True),
        sa.Column("auth_method", agent_auth_method, nullable=False, server_default="none"),
        sa.Column("auth_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("agent_card", postgresql.JSONB(), nullable=False),
        sa.Column("status", agent_status, nullable=False, server_default="offline"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_rating", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("owner_id", "name", name="uq_agents_owner_name"),
    )

    op.create_table(
        "agent_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("examples", postgresql.JSONB(), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(), nullable=True),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("agent_id", "skill_id", name="uq_agent_skills_agent_skill"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_skill", sa.String(length=128), nullable=False),
        sa.Column("input_messages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("attachments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", job_status, nullable=False, server_default="submitted"),
        sa.Column("progress", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "job_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", artifact_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "job_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("rater_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("stars >= 1 AND stars <= 5", name="ck_job_ratings_stars"),
    )

    op.create_table(
        "job_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", job_event_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("idx_agents_owner", "agents", ["owner_id"])
    op.create_index("idx_agents_status", "agents", ["status"])
    op.create_index("idx_agent_skills_skill", "agent_skills", ["skill_id"])
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_skill", "jobs", ["required_skill"])
    op.create_index("idx_jobs_from_user", "jobs", ["from_user_id"])
    op.create_index("idx_jobs_to_agent", "jobs", ["to_agent_id"])
    op.create_index("idx_job_events_job_created", "job_events", ["job_id", "created_at"])

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'storage' AND table_name = 'buckets'
            ) THEN
                INSERT INTO storage.buckets (id, name, public)
                VALUES ('polis-attachments', 'polis-attachments', true)
                ON CONFLICT (id) DO UPDATE SET public = true;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("job_events")
    op.drop_table("job_ratings")
    op.drop_table("job_artifacts")
    op.drop_table("jobs")
    op.drop_table("agent_skills")
    op.drop_table("agents")
    op.drop_table("users")

    bind = op.get_bind()
    job_event_type.drop(bind, checkfirst=True)
    artifact_type.drop(bind, checkfirst=True)
    job_status.drop(bind, checkfirst=True)
    agent_status.drop(bind, checkfirst=True)
    agent_auth_method.drop(bind, checkfirst=True)
