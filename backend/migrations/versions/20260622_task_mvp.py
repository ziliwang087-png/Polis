"""add task mvp table

Revision ID: 20260622_task_mvp
Revises: 20260621_stale_claim_reaped
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_task_mvp"
down_revision: Union[str, None] = "20260621_stale_claim_reaped"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            difficulty VARCHAR(20),
            required_capabilities JSONB,
            estimated_hours INT,
            reward_points INT NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            assigned_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
            deadline TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP,
            deliverable_type VARCHAR(50),
            verification_required BOOLEAN DEFAULT TRUE,
            CONSTRAINT chk_tasks_status
                CHECK (status IN ('open', 'in_progress', 'completed', 'failed'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
