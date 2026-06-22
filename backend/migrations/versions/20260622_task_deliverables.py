"""add task deliverables

Revision ID: 20260622_task_deliverables
Revises: 20260622_task_status_flow
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_task_deliverables"
down_revision: Union[str, None] = "20260622_task_status_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_deliverables (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            uploaded_by UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            file_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            file_size BIGINT,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_deliverables_task ON task_deliverables(task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_deliverables_uploaded_by ON task_deliverables(uploaded_by)")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'storage' AND table_name = 'buckets'
            ) THEN
                INSERT INTO storage.buckets (id, name, public)
                VALUES ('task-deliverables', 'task-deliverables', true)
                ON CONFLICT (id) DO UPDATE SET public = true;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_deliverables")
