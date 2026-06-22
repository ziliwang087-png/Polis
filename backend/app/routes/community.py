"""
Community discussion routes.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from psycopg2.errors import UniqueViolation

from app.database import get_db_connection
from app.dependencies import get_current_agent, get_current_owner, get_current_user
from app.models import (
    AgentTaskShareRequest,
    CommunityCommentCreateRequest,
    CommunityCommentListResponse,
    CommunityCommentResponse,
    CommunityLikeResponse,
    CommunityPostCreateRequest,
    CommunityPostCreateResponse,
    CommunityPostListResponse,
    CommunityPostResponse,
)

router = APIRouter(prefix="/community", tags=["community"])
logger = logging.getLogger(__name__)


POST_SELECT = """
    p.id, p.title, p.content, p.author_type, p.author_id, p.category,
    p.likes, p.created_at, p.updated_at,
    CASE
        WHEN p.author_type = 'user' THEN COALESCE(u.display_name, u.username)
        WHEN p.author_type = 'agent' THEN COALESCE(a.display_name, a.name)
        ELSE NULL
    END AS author_name,
    (
        SELECT COUNT(*)
        FROM comments c
        WHERE c.post_id = p.id
    ) AS comment_count
"""


def _liked_by(cur, post_id: UUID, user_id: Optional[UUID]) -> bool:
    if not user_id:
        return False
    cur.execute(
        "SELECT 1 FROM post_likes WHERE post_id = %s AND user_id = %s",
        (str(post_id), str(user_id)),
    )
    return cur.fetchone() is not None


def _post_response(cur, row, current_user_id: Optional[UUID] = None, liked_by_me: Optional[bool] = None) -> CommunityPostResponse:
    """
    构建单个 CommunityPostResponse。
    支持传入预加载的 liked_by_me 以避免 N+1 查询。
    """
    if liked_by_me is None:
        liked_by_me = _liked_by(cur, row["id"], current_user_id)
    
    return CommunityPostResponse(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        author_type=row["author_type"],
        author_id=row["author_id"],
        author_name=row.get("author_name"),
        category=row["category"],
        likes=row.get("likes") or 0,
        comment_count=row.get("comment_count") or 0,
        liked_by_me=liked_by_me,
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )


def _batch_post_responses(cur, post_rows, current_user_id: Optional[UUID] = None) -> List[CommunityPostResponse]:
    """
    批量构建 CommunityPostResponse，消除 N+1 查询。
    一次性查询所有 post 的 liked_by_me 状态。
    """
    if not post_rows:
        return []
    
    # 批量查询 liked_by_me
    likes_by_post = {}
    if current_user_id:
        post_ids = [str(row["id"]) for row in post_rows]
        cur.execute(
            "SELECT post_id FROM post_likes WHERE post_id = ANY(%s::uuid[]) AND user_id = %s",
            (post_ids, str(current_user_id)),
        )
        liked_post_ids = {row["post_id"] for row in cur.fetchall()}
        likes_by_post = {post_id: (post_id in liked_post_ids) for post_id in post_ids}
    
    # 构建所有 CommunityPostResponse
    return [
        _post_response(
            cur,
            row,
            current_user_id=current_user_id,
            liked_by_me=likes_by_post.get(row["id"], False),
        )
        for row in post_rows
    ]


def _optional_user_id(authorization: Optional[str]) -> Optional[UUID]:
    if not authorization:
        return None
    try:
        subject_id, subject_type = get_current_user(authorization)
    except HTTPException:
        return None
    return subject_id if subject_type == "user" else None


@router.post("/posts", response_model=CommunityPostCreateResponse)
def create_post(
    request: CommunityPostCreateRequest,
    user_id: UUID = Depends(get_current_owner),
):
    """Create a user-authored discussion post."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO posts (title, content, author_type, author_id, category)
                VALUES (%s, %s, 'user', %s, %s)
                RETURNING id
                """,
                (request.title, request.content, str(user_id), request.category),
            )
            return CommunityPostCreateResponse(post_id=cur.fetchone()["id"])

    except Exception as exc:
        logger.exception("Community post creation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Community post creation failed",
        )


@router.get("/posts", response_model=CommunityPostListResponse)
def list_posts(
    category: Optional[str] = Query(None, pattern="^(chat|showcase|tech|help)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    """List community posts, optionally filtered by category."""
    current_user_id = _optional_user_id(authorization)
    with get_db_connection() as conn:
        cur = conn.cursor()
        where = ""
        params: list = []
        count_params: list = []
        if category:
            where = "WHERE p.category = %s"
            params.append(category)
            count_params.append(category)

        cur.execute(
            f"""
            SELECT {POST_SELECT}
            FROM posts p
            LEFT JOIN users u ON p.author_type = 'user' AND p.author_id = u.id
            LEFT JOIN agents a ON p.author_type = 'agent' AND p.author_id = a.id
            {where}
            ORDER BY p.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        )
        rows = cur.fetchall()

        cur.execute(
            f"SELECT COUNT(*) AS count FROM posts p {where}",
            tuple(count_params),
        )
        total_row = cur.fetchone() or {"count": len(rows)}

        return CommunityPostListResponse(
            posts=_batch_post_responses(cur, rows, current_user_id),
            total=total_row["count"],
        )


@router.get("/posts/{post_id}", response_model=CommunityPostResponse)
def get_post(
    post_id: UUID,
    authorization: Optional[str] = Header(None),
):
    current_user_id = _optional_user_id(authorization)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {POST_SELECT}
            FROM posts p
            LEFT JOIN users u ON p.author_type = 'user' AND p.author_id = u.id
            LEFT JOIN agents a ON p.author_type = 'agent' AND p.author_id = a.id
            WHERE p.id = %s
            """,
            (str(post_id),),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        return _post_response(cur, row, current_user_id)


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: UUID,
    authorization: Optional[str] = Header(None),
):
    """Delete a post (only author can delete)"""
    subject_id, subject_type = get_current_user(authorization)
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        # Check if post exists and user is the author
        cur.execute(
            "SELECT author_type, author_id FROM posts WHERE id = %s",
            (str(post_id),)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if row["author_type"] != subject_type or str(row["author_id"]) != str(subject_id):
            raise HTTPException(status_code=403, detail="Only author can delete this post")
        
        # Delete post (cascades to comments and likes)
        cur.execute("DELETE FROM posts WHERE id = %s", (str(post_id),))
        conn.commit()
        
        return {"message": "Post deleted successfully"}


@router.post("/posts/{post_id}/comments", response_model=CommunityCommentResponse)
def add_comment(
    post_id: UUID,
    request: CommunityCommentCreateRequest,
    authorization: Optional[str] = Header(None),
):
    subject_id, subject_type = get_current_user(authorization)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM posts WHERE id = %s", (str(post_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")

        cur.execute(
            """
            INSERT INTO comments (post_id, author_type, author_id, content)
            VALUES (%s, %s, %s, %s)
            RETURNING id, post_id, author_type, author_id, content, created_at
            """,
            (str(post_id), subject_type, str(subject_id), request.content),
        )
        row = cur.fetchone()
        author_name = _author_name(cur, subject_type, subject_id)
        return CommunityCommentResponse(**dict(row), author_name=author_name)


@router.get("/posts/{post_id}/comments", response_model=CommunityCommentListResponse)
def list_comments(post_id: UUID):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM posts WHERE id = %s", (str(post_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")

        cur.execute(
            """
            SELECT
                c.id, c.post_id, c.author_type, c.author_id, c.content, c.created_at,
                CASE
                    WHEN c.author_type = 'user' THEN COALESCE(u.display_name, u.username)
                    WHEN c.author_type = 'agent' THEN COALESCE(a.display_name, a.name)
                    ELSE NULL
                END AS author_name
            FROM comments c
            LEFT JOIN users u ON c.author_type = 'user' AND c.author_id = u.id
            LEFT JOIN agents a ON c.author_type = 'agent' AND c.author_id = a.id
            WHERE c.post_id = %s
            ORDER BY c.created_at ASC
            """,
            (str(post_id),),
        )
        return CommunityCommentListResponse(
            comments=[CommunityCommentResponse(**dict(row)) for row in cur.fetchall()]
        )


@router.post("/posts/{post_id}/like", response_model=CommunityLikeResponse)
def like_post(
    post_id: UUID,
    user_id: UUID = Depends(get_current_owner),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM posts WHERE id = %s", (str(post_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")

        try:
            cur.execute(
                """
                INSERT INTO post_likes (post_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (post_id, user_id) DO NOTHING
                """,
                (str(post_id), str(user_id)),
            )
        except UniqueViolation:
            pass

        cur.execute("SELECT COUNT(*) AS count FROM post_likes WHERE post_id = %s", (str(post_id),))
        likes = cur.fetchone()["count"]
        cur.execute("UPDATE posts SET likes = %s WHERE id = %s", (likes, str(post_id)))
        return CommunityLikeResponse(liked=True, likes=likes)


@router.delete("/posts/{post_id}/like", response_model=CommunityLikeResponse)
def unlike_post(
    post_id: UUID,
    user_id: UUID = Depends(get_current_owner),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM posts WHERE id = %s", (str(post_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")

        cur.execute(
            "DELETE FROM post_likes WHERE post_id = %s AND user_id = %s",
            (str(post_id), str(user_id)),
        )
        cur.execute("SELECT COUNT(*) AS count FROM post_likes WHERE post_id = %s", (str(post_id),))
        likes = cur.fetchone()["count"]
        cur.execute("UPDATE posts SET likes = %s WHERE id = %s", (likes, str(post_id)))
        return CommunityLikeResponse(liked=False, likes=likes)


@router.post("/agent/task-share", response_model=CommunityPostCreateResponse)
def share_completed_task(
    request: AgentTaskShareRequest,
    agent_id: UUID = Depends(get_current_agent),
):
    """Let an agent publish a task-completion note."""
    title = f"完成任务：{request.task_title}"
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO posts (title, content, author_type, author_id, category)
                VALUES (%s, %s, 'agent', %s, %s)
                RETURNING id
                """,
                (title, request.summary, str(agent_id), request.category),
            )
            return CommunityPostCreateResponse(post_id=cur.fetchone()["id"])

    except Exception as exc:
        logger.exception("Agent task share failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent task share failed: {exc}",
        )


def _author_name(cur, author_type: str, author_id: UUID) -> Optional[str]:
    if author_type == "user":
        cur.execute(
            "SELECT COALESCE(display_name, username) AS name FROM users WHERE id = %s",
            (str(author_id),),
        )
    else:
        cur.execute(
            "SELECT COALESCE(display_name, name) AS name FROM agents WHERE id = %s",
            (str(author_id),),
        )
    row = cur.fetchone()
    return row["name"] if row else None
