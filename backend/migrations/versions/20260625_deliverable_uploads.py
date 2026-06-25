"""allow task owners to upload deliverables

Revision ID: 20260625_deliverable_uploads
Revises: 20260622_attachments_credits
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260625_deliverable_uploads"
down_revision: Union[str, None] = "20260622_attachments_credits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_submissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            content TEXT,
            deliverable_url VARCHAR(500),
            result_hash VARCHAR(64),
            result_hash_algorithm VARCHAR(20) DEFAULT 'sha256',
            result_size_bytes BIGINT,
            result_mime_type VARCHAR(100),
            evidence_urls JSONB,
            work_log JSONB,
            status VARCHAR(20) DEFAULT 'submitted',
            revision_count INT DEFAULT 0,
            submitted_at TIMESTAMPTZ DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_submissions_task ON task_submissions(task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_submissions_agent ON task_submissions(agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON task_submissions(status)")
    op.execute(
        """
        ALTER TABLE task_deliverables
        ADD COLUMN IF NOT EXISTS uploaded_by_type TEXT NOT NULL DEFAULT 'agent'
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        DROP CONSTRAINT IF EXISTS task_deliverables_uploaded_by_fkey
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        DROP CONSTRAINT IF EXISTS chk_task_deliverables_uploaded_by_type
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        ADD CONSTRAINT chk_task_deliverables_uploaded_by_type
        CHECK (uploaded_by_type IN ('agent', 'user'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE task_deliverables
        SET uploaded_by_type = 'agent'
        WHERE uploaded_by_type <> 'agent'
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        DROP CONSTRAINT IF EXISTS chk_task_deliverables_uploaded_by_type
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        ADD CONSTRAINT task_deliverables_uploaded_by_fkey
        FOREIGN KEY (uploaded_by) REFERENCES agents(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE task_deliverables
        DROP COLUMN IF EXISTS uploaded_by_type
        """
    )
