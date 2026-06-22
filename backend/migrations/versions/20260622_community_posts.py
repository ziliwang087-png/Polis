"""add community discussion tables

Revision ID: 20260622_community_posts
Revises: 20260622_gamification
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260622_community_posts"
down_revision: Union[str, None] = "20260622_gamification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(256) NOT NULL,
            content TEXT NOT NULL,
            author_type VARCHAR(16) NOT NULL,
            author_id UUID NOT NULL,
            category VARCHAR(64) NOT NULL,
            likes INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS title VARCHAR(256)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_type VARCHAR(16)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS author_id UUID")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS category VARCHAR(64)")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS likes INTEGER DEFAULT 0")
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'posts' AND column_name = 'agent_id'
            ) THEN
                UPDATE posts
                SET
                    title = COALESCE(title, LEFT(content, 120), 'Untitled'),
                    author_type = COALESCE(author_type, 'agent'),
                    author_id = COALESCE(author_id, agent_id),
                    category = COALESCE(category, 'chat'),
                    likes = COALESCE(likes, like_count, 0)
                WHERE title IS NULL
                   OR author_type IS NULL
                   OR author_id IS NULL
                   OR category IS NULL
                   OR likes IS NULL;
                ALTER TABLE posts ALTER COLUMN agent_id DROP NOT NULL;
            ELSE
                UPDATE posts
                SET
                    title = COALESCE(title, LEFT(content, 120), 'Untitled'),
                    author_type = COALESCE(author_type, 'user'),
                    category = COALESCE(category, 'chat'),
                    likes = COALESCE(likes, 0)
                WHERE title IS NULL
                   OR author_type IS NULL
                   OR category IS NULL
                   OR likes IS NULL;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE posts ALTER COLUMN title SET NOT NULL")
    op.execute("ALTER TABLE posts ALTER COLUMN author_type SET NOT NULL")
    op.execute("ALTER TABLE posts ALTER COLUMN author_id SET NOT NULL")
    op.execute("ALTER TABLE posts ALTER COLUMN category SET NOT NULL")
    op.execute("ALTER TABLE posts ALTER COLUMN likes SET DEFAULT 0")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_type, author_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            author_type VARCHAR(16) NOT NULL,
            author_id UUID NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS author_type VARCHAR(16)")
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS author_id UUID")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'comments' AND column_name = 'agent_id'
            ) THEN
                UPDATE comments
                SET
                    author_type = COALESCE(author_type, 'agent'),
                    author_id = COALESCE(author_id, agent_id)
                WHERE author_type IS NULL OR author_id IS NULL;
                ALTER TABLE comments ALTER COLUMN agent_id DROP NOT NULL;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE comments ALTER COLUMN author_type SET NOT NULL")
    op.execute("ALTER TABLE comments ALTER COLUMN author_id SET NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_likes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(post_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_post_likes_post ON post_likes(post_id)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_post_likes()
        RETURNS TRIGGER AS $$
        DECLARE affected_post_id UUID;
        BEGIN
            affected_post_id := COALESCE(NEW.post_id, OLD.post_id);
            UPDATE posts
            SET likes = (SELECT COUNT(*) FROM post_likes WHERE post_id = affected_post_id)
            WHERE id = affected_post_id;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS post_likes_update_count ON post_likes")
    op.execute(
        """
        CREATE TRIGGER post_likes_update_count
        AFTER INSERT OR DELETE ON post_likes
        FOR EACH ROW
        EXECUTE FUNCTION update_post_likes()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS post_likes_update_count ON post_likes")
    op.execute("DROP FUNCTION IF EXISTS update_post_likes()")
    op.execute("DROP TABLE IF EXISTS post_likes")
    op.execute("DROP TABLE IF EXISTS comments")
    op.execute("DROP TABLE IF EXISTS posts")
