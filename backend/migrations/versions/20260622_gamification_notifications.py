"""add gamification and notifications tables

Revision ID: 20260622_gamification
Revises: 20260622_task_mvp
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_gamification"
down_revision: Union[str, None] = "20260622_task_mvp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 扩展 agents 表 - 添加游戏化字段
    op.execute("""
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1,
        ADD COLUMN IF NOT EXISTS total_tasks_completed INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS total_tasks_failed INTEGER DEFAULT 0
    """)

    # 2. 创建 notifications 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(64) NOT NULL,
            title VARCHAR(256) NOT NULL,
            message TEXT NOT NULL,
            link VARCHAR(512),
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(user_id, read)")

    # 3. 创建 task_ratings 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_ratings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(task_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_ratings_agent ON task_ratings(agent_id)")

    # 4. 创建 badges 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            badge_type VARCHAR(64) NOT NULL,
            earned_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(agent_id, badge_type)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_badges_agent ON badges(agent_id)")

    # 5. 创建触发器 - 自动更新 agent 平均评分
    op.execute("""
        CREATE OR REPLACE FUNCTION update_agent_rating()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE agents
            SET avg_rating = (
                SELECT AVG(rating)::DECIMAL(3,2)
                FROM task_ratings
                WHERE agent_id = NEW.agent_id
            )
            WHERE id = NEW.agent_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS task_ratings_update_agent ON task_ratings
    """)

    op.execute("""
        CREATE TRIGGER task_ratings_update_agent
        AFTER INSERT OR UPDATE ON task_ratings
        FOR EACH ROW
        EXECUTE FUNCTION update_agent_rating()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS task_ratings_update_agent ON task_ratings")
    op.execute("DROP FUNCTION IF EXISTS update_agent_rating()")
    op.execute("DROP TABLE IF EXISTS badges")
    op.execute("DROP TABLE IF EXISTS task_ratings")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("""
        ALTER TABLE agents
        DROP COLUMN IF EXISTS xp,
        DROP COLUMN IF EXISTS level,
        DROP COLUMN IF EXISTS total_tasks_completed,
        DROP COLUMN IF EXISTS total_tasks_failed
    """)
