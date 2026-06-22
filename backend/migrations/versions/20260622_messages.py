"""add private messages

Revision ID: 20260622_messages
Revises: 20260622_task_deliverables
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_messages"
down_revision: Union[str, None] = "20260622_task_deliverables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(receiver_id, read)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages")
