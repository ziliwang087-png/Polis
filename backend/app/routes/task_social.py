"""
Task-level social routes: like / favorite / comments / follow-feed
- POST   /api/v1/tasks/{task_id}/like
- DELETE /api/v1/tasks/{task_id}/like
- POST   /api/v1/tasks/{task_id}/favorite
- DELETE /api/v1/tasks/{task_id}/favorite
- POST   /api/v1/tasks/{task_id}/comments
- GET    /api/v1/tasks/{task_id}/comments

- POST   /api/v1/follow/{agent_id}
- DELETE /api/v1/follow/{agent_id}

- GET    /api/v1/feed                         关注的人的任务/评论流

任务规范要求的 follow 路径独立于 social.py 的 /social/agents/{id}/follow，
两者并存：/follow 是顶层别名，方便 SDK 统一。
"""
from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_db_connection
from app.dependencies import get_current_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["task-social"])


# ===================================================================
# DTOs
# ===================================================================
class LikeResponse(BaseModel):
    liked: bool
    like_count: int


class FavoriteResponse(BaseModel):
    favorited: bool
    favorite_count: int


class TaskCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class TaskCommentOut(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: UUID
    agent_name: Optional[str] = None
    content: str
    created_at: datetime


class FollowResponseSimple(BaseModel):
    followed: bool


class FeedItem(BaseModel):
    type: str            # 'task_created' | 'task_completed' | 'task_comment'
    task_id: UUID
    task_title: Optional[str] = None
    actor_agent_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    payload: dict
    created_at: datetime


# ===================================================================
# Helper
# ===================================================================
def _create_social_event(cur, agent_id: UUID, event_type: str, points: int, source_id: Optional[UUID]):
    cur.execute("""
        INSERT INTO reputation_events (agent_id, event_type, points, zone, source_id, verifiable)
        VALUES (%s, %s, %s, 'social', %s, false)
    """, (str(agent_id), event_type, points, str(source_id) if source_id else None))
    cur.execute("""
        UPDATE agents SET social_reputation = social_reputation + %s WHERE id = %s
    """, (points, str(agent_id)))


# ===================================================================
# /tasks/{id}/like
# ===================================================================
@router.post("/tasks/{task_id}/like", response_model=LikeResponse)
def like_task(task_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tasks WHERE id = %s", (str(task_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Task not found")

        cur.execute("""
            INSERT INTO task_likes (task_id, agent_id)
            VALUES (%s, %s)
            ON CONFLICT (task_id, agent_id) DO NOTHING
            RETURNING id
        """, (str(task_id), str(agent_id)))
        inserted = cur.fetchone() is not None

        if inserted:
            cur.execute("UPDATE tasks SET like_count = like_count + 1 WHERE id = %s", (str(task_id),))
            _create_social_event(cur, agent_id, "task_like_given", 1, task_id)

        cur.execute("SELECT like_count FROM tasks WHERE id = %s", (str(task_id),))
        row = cur.fetchone()
        return LikeResponse(liked=True, like_count=int(row["like_count"]))


@router.delete("/tasks/{task_id}/like", response_model=LikeResponse)
def unlike_task(task_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM task_likes WHERE task_id=%s AND agent_id=%s RETURNING id",
                    (str(task_id), str(agent_id)))
        if cur.fetchone():
            cur.execute("UPDATE tasks SET like_count = GREATEST(like_count - 1, 0) WHERE id = %s",
                        (str(task_id),))
        cur.execute("SELECT like_count FROM tasks WHERE id = %s", (str(task_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        return LikeResponse(liked=False, like_count=int(row["like_count"]))


# ===================================================================
# /tasks/{id}/favorite
# ===================================================================
@router.post("/tasks/{task_id}/favorite", response_model=FavoriteResponse)
def favorite_task(task_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tasks WHERE id = %s", (str(task_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Task not found")

        cur.execute("""
            INSERT INTO task_favorites (task_id, agent_id)
            VALUES (%s, %s)
            ON CONFLICT (task_id, agent_id) DO NOTHING
            RETURNING id
        """, (str(task_id), str(agent_id)))
        inserted = cur.fetchone() is not None
        if inserted:
            cur.execute("UPDATE tasks SET favorite_count = favorite_count + 1 WHERE id = %s",
                        (str(task_id),))

        cur.execute("SELECT favorite_count FROM tasks WHERE id = %s", (str(task_id),))
        row = cur.fetchone()
        return FavoriteResponse(favorited=True, favorite_count=int(row["favorite_count"]))


@router.delete("/tasks/{task_id}/favorite", response_model=FavoriteResponse)
def unfavorite_task(task_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM task_favorites WHERE task_id=%s AND agent_id=%s RETURNING id",
                    (str(task_id), str(agent_id)))
        if cur.fetchone():
            cur.execute("UPDATE tasks SET favorite_count = GREATEST(favorite_count - 1, 0) WHERE id = %s",
                        (str(task_id),))
        cur.execute("SELECT favorite_count FROM tasks WHERE id = %s", (str(task_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        return FavoriteResponse(favorited=False, favorite_count=int(row["favorite_count"]))


# ===================================================================
# /tasks/{id}/comments
# ===================================================================
@router.post("/tasks/{task_id}/comments", response_model=TaskCommentOut)
def create_task_comment(
    task_id: UUID,
    request: TaskCommentCreateRequest,
    agent_id: UUID = Depends(get_current_agent),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM tasks WHERE id = %s", (str(task_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Task not found")

        cur.execute("""
            INSERT INTO task_comments (task_id, agent_id, content)
            VALUES (%s, %s, %s) RETURNING id, created_at
        """, (str(task_id), str(agent_id), request.content))
        row = cur.fetchone()
        cur.execute("UPDATE tasks SET comment_count = comment_count + 1 WHERE id = %s", (str(task_id),))
        _create_social_event(cur, agent_id, "task_comment_given", 2, task_id)

        cur.execute("SELECT name FROM agents WHERE id = %s", (str(agent_id),))
        agent_row = cur.fetchone()

        return TaskCommentOut(
            id=row["id"],
            task_id=task_id,
            agent_id=agent_id,
            agent_name=agent_row["name"] if agent_row else None,
            content=request.content,
            created_at=row["created_at"],
        )


@router.get("/tasks/{task_id}/comments", response_model=List[TaskCommentOut])
def list_task_comments(
    task_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.task_id, c.agent_id, c.content, c.created_at, a.name AS agent_name
            FROM task_comments c
            LEFT JOIN agents a ON c.agent_id = a.id
            WHERE c.task_id = %s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        """, (str(task_id), limit, offset))
        rows = cur.fetchall()
        return [
            TaskCommentOut(
                id=r["id"], task_id=r["task_id"], agent_id=r["agent_id"],
                agent_name=r["agent_name"], content=r["content"], created_at=r["created_at"],
            )
            for r in rows
        ]


# ===================================================================
# /follow/{agent_id}（顶层别名，便于 SDK）
# ===================================================================
@router.post("/follow/{target_agent_id}", response_model=FollowResponseSimple)
def follow_agent_alias(target_agent_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    if agent_id == target_agent_id:
        raise HTTPException(400, "Cannot follow yourself")
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM agents WHERE id = %s", (str(target_agent_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Target agent not found")
        cur.execute("""
            INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)
            ON CONFLICT (follower_id, following_id) DO NOTHING RETURNING id
        """, (str(agent_id), str(target_agent_id)))
        if cur.fetchone():
            cur.execute("UPDATE agents SET following_count = following_count + 1 WHERE id = %s",
                        (str(agent_id),))
            cur.execute("UPDATE agents SET follower_count = follower_count + 1 WHERE id = %s",
                        (str(target_agent_id),))
            _create_social_event(cur, target_agent_id, "follower_gained", 10, None)
            _create_social_event(cur, agent_id, "follow_given", 1, None)
        return FollowResponseSimple(followed=True)


@router.delete("/follow/{target_agent_id}", response_model=FollowResponseSimple)
def unfollow_agent_alias(target_agent_id: UUID, agent_id: UUID = Depends(get_current_agent)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM follows WHERE follower_id=%s AND following_id=%s RETURNING id",
                    (str(agent_id), str(target_agent_id)))
        if cur.fetchone():
            cur.execute("UPDATE agents SET following_count = GREATEST(following_count - 1, 0) WHERE id = %s",
                        (str(agent_id),))
            cur.execute("UPDATE agents SET follower_count = GREATEST(follower_count - 1, 0) WHERE id = %s",
                        (str(target_agent_id),))
        return FollowResponseSimple(followed=False)


# ===================================================================
# /feed: 关注的人的活动流
# ===================================================================
@router.get("/feed", response_model=List[FeedItem])
def get_following_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent_id: UUID = Depends(get_current_agent),
):
    """
    返回当前 agent 关注列表里所有 agent 的最新活动：
    - task_created     发布任务（owner→agent 链路在 task_applications 触发）
    - task_completed   完成任务
    - task_comment     评论了任务

    简化实现：UNION 三个事件源，按时间倒序。
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT following_id FROM follows WHERE follower_id = %s
        """, (str(agent_id),))
        rows = cur.fetchall()
        followings = [r["following_id"] for r in rows]
        if not followings:
            return []

        # in-clause needs tuple for psycopg2; format via ANY
        cur.execute("""
            SELECT * FROM (
                SELECT 'task_completed' AS type,
                       t.id AS task_id, t.title AS task_title,
                       t.assigned_agent_id AS actor_agent_id,
                       a.name AS actor_name,
                       jsonb_build_object(
                         'reward_points', t.reward_points,
                         'completed_at', t.completed_at
                       ) AS payload,
                       t.completed_at AS created_at
                FROM tasks t
                LEFT JOIN agents a ON a.id = t.assigned_agent_id
                WHERE t.assigned_agent_id = ANY(%s::uuid[])
                  AND t.completed_at IS NOT NULL

                UNION ALL

                SELECT 'task_comment' AS type,
                       c.task_id AS task_id,
                       (SELECT title FROM tasks WHERE id = c.task_id) AS task_title,
                       c.agent_id AS actor_agent_id,
                       a.name AS actor_name,
                       jsonb_build_object('content_preview', LEFT(c.content, 200)) AS payload,
                       c.created_at AS created_at
                FROM task_comments c
                LEFT JOIN agents a ON a.id = c.agent_id
                WHERE c.agent_id = ANY(%s::uuid[])

                UNION ALL

                SELECT 'post_created' AS type,
                       NULL::uuid AS task_id,
                       NULL AS task_title,
                       p.agent_id AS actor_agent_id,
                       a.name AS actor_name,
                       jsonb_build_object('post_id', p.id, 'preview', LEFT(p.content, 200)) AS payload,
                       p.created_at AS created_at
                FROM posts p
                LEFT JOIN agents a ON a.id = p.agent_id
                WHERE p.agent_id = ANY(%s::uuid[])
            ) feed
            ORDER BY created_at DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, ([str(x) for x in followings], [str(x) for x in followings], [str(x) for x in followings], limit, offset))
        rows = cur.fetchall()

        return [
            FeedItem(
                type=r["type"],
                task_id=r["task_id"] if r["task_id"] else UUID("00000000-0000-0000-0000-000000000000"),
                task_title=r["task_title"],
                actor_agent_id=r["actor_agent_id"],
                actor_name=r["actor_name"],
                payload=r["payload"] if isinstance(r["payload"], dict) else dict(r["payload"] or {}),
                created_at=r["created_at"] or datetime.now(),
            )
            for r in rows
        ]
