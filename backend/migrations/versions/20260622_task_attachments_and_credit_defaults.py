"""add task attachments and credit defaults

Revision ID: 20260622_task_attachments_credits
Revises: 20260622_messages
Create Date: 2026-06-22
"""

from typing import Union

from alembic import op


revision: str = "20260622_attachments_credits"
down_revision: Union[str, None] = "20260622_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasks "
        "ADD COLUMN IF NOT EXISTS attachments JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute("ALTER TABLE users ALTER COLUMN credit_balance SET DEFAULT 100")


def downgrade() -> None:
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS attachments")
    op.execute("ALTER TABLE users ALTER COLUMN credit_balance SET DEFAULT 0")
