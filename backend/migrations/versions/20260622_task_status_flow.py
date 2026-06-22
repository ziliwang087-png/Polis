"""allow task status flow states

Revision ID: 20260622_task_status_flow
Revises: 20260622_community_posts
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_task_status_flow"
down_revision: Union[str, None] = "20260622_community_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS chk_tasks_status")
    op.execute(
        """
        ALTER TABLE tasks
        ADD CONSTRAINT chk_tasks_status
        CHECK (status IN (
            'open',
            'claimed',
            'in_progress',
            'submitted',
            'completed',
            'cancelled',
            'failed'
        ))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tasks
        SET status = CASE
            WHEN status = 'claimed' THEN 'open'
            WHEN status = 'submitted' THEN 'in_progress'
            WHEN status = 'cancelled' THEN 'failed'
            ELSE status
        END
        WHERE status IN ('claimed', 'submitted', 'cancelled')
        """
    )
    op.execute("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS chk_tasks_status")
    op.execute(
        """
        ALTER TABLE tasks
        ADD CONSTRAINT chk_tasks_status
        CHECK (status IN ('open', 'in_progress', 'completed', 'failed'))
        """
    )
