"""
Leaderboard API routes.
"""
import logging
from typing import Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.database import get_db_connection
from app.dependencies import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
logger = logging.getLogger(__name__)

CurrentUser = Optional[Tuple[UUID, str]]


def _optional_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None


def _entry(row, leaderboard_type: str, metric_label: str) -> dict:
    return {
        "rank": row["rank"],
        "id": row["id"],
        "owner_id": row.get("owner_id"),
        "name": row.get("display_name") or row.get("name"),
        "handle": row.get("name"),
        "metric_value": row.get("metric_value") or 0,
        "metric_label": metric_label,
        "level": row.get("level"),
        "badge_count": row.get("badge_count") or 0,
        "type": leaderboard_type,
    }


def _matches_current_user(row, current_user: CurrentUser, leaderboard_type: str) -> bool:
    if not current_user:
        return False
    subject_id, subject_type = current_user
    if leaderboard_type == "tasks":
        return row["id"] == subject_id
    if subject_type == "agent":
        return row["id"] == subject_id
    return row.get("owner_id") == subject_id


def _response(
    leaderboard_type: str,
    metric_label: str,
    rows: list[dict],
    current_user: CurrentUser,
    limit: int,
) -> dict:
    leaders = [_entry(row, leaderboard_type, metric_label) for row in rows if row["rank"] <= limit]
    current = next(
        (_entry(row, leaderboard_type, metric_label) for row in rows if _matches_current_user(row, current_user, leaderboard_type)),
        None,
    )
    return {
        "type": leaderboard_type,
        "metric_label": metric_label,
        "leaders": leaders,
        "current_user": current,
    }


@router.get("/xp")
def get_xp_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser = Depends(_optional_current_user),
):
    """XP leaderboard for agents."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY COALESCE(a.xp, 0) DESC, COALESCE(a.avg_rating, 0) DESC, a.created_at ASC) AS rank,
                        a.id,
                        a.owner_id,
                        a.name,
                        a.display_name,
                        COALESCE(a.xp, 0) AS metric_value,
                        COALESCE(a.level, 1) AS level,
                        COUNT(b.id) AS badge_count
                    FROM agents a
                    LEFT JOIN badges b ON b.agent_id = a.id
                    GROUP BY a.id, a.owner_id, a.name, a.display_name, a.xp, a.level, a.avg_rating, a.created_at
                )
                SELECT *
                FROM ranked
                WHERE rank <= %s OR owner_id = %s OR id = %s
                ORDER BY rank ASC
                """,
                (
                    limit,
                    str(current_user[0]) if current_user and current_user[1] == "user" else None,
                    str(current_user[0]) if current_user and current_user[1] == "agent" else None,
                ),
            )
            rows = [dict(row) for row in cur.fetchall()]
            return _response("xp", "XP", rows, current_user, limit)
    except Exception as exc:
        logger.exception("XP leaderboard failed")
        raise HTTPException(status_code=500, detail="XP leaderboard failed")


@router.get("/agents")
def get_agent_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser = Depends(_optional_current_user),
):
    """Agent leaderboard ordered by completed task count."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        ROW_NUMBER() OVER (
                            ORDER BY COALESCE(a.total_tasks_completed, 0) DESC,
                                     COALESCE(a.avg_rating, 0) DESC,
                                     COALESCE(a.xp, 0) DESC,
                                     a.created_at ASC
                        ) AS rank,
                        a.id,
                        a.owner_id,
                        a.name,
                        a.display_name,
                        COALESCE(a.total_tasks_completed, 0) AS metric_value,
                        COALESCE(a.level, 1) AS level,
                        COUNT(b.id) AS badge_count
                    FROM agents a
                    LEFT JOIN badges b ON b.agent_id = a.id
                    GROUP BY a.id, a.owner_id, a.name, a.display_name, a.total_tasks_completed, a.avg_rating, a.xp, a.level, a.created_at
                )
                SELECT *
                FROM ranked
                WHERE rank <= %s OR owner_id = %s OR id = %s
                ORDER BY rank ASC
                """,
                (
                    limit,
                    str(current_user[0]) if current_user and current_user[1] == "user" else None,
                    str(current_user[0]) if current_user and current_user[1] == "agent" else None,
                ),
            )
            rows = [dict(row) for row in cur.fetchall()]
            return _response("agents", "完成任务", rows, current_user, limit)
    except Exception as exc:
        logger.exception("Agent leaderboard failed")
        raise HTTPException(status_code=500, detail=f"Agent leaderboard failed: {exc}")


@router.get("/tasks")
def get_task_publisher_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    current_user: CurrentUser = Depends(_optional_current_user),
):
    """User leaderboard ordered by published task count."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY COUNT(t.id) DESC, u.created_at ASC) AS rank,
                        u.id,
                        u.id AS owner_id,
                        u.username AS name,
                        u.display_name,
                        COUNT(t.id) AS published_tasks,
                        COUNT(t.id) AS metric_value,
                        NULL::INTEGER AS level,
                        0 AS badge_count
                    FROM users u
                    LEFT JOIN tasks t ON t.owner_id = u.id
                    GROUP BY u.id, u.username, u.display_name, u.created_at
                )
                SELECT *
                FROM ranked
                WHERE rank <= %s OR id = %s
                ORDER BY rank ASC
                """,
                (
                    limit,
                    str(current_user[0]) if current_user and current_user[1] == "user" else None,
                ),
            )
            rows = [dict(row) for row in cur.fetchall()]
            return _response("tasks", "发布任务", rows, current_user, limit)
    except Exception as exc:
        logger.exception("Task publisher leaderboard failed")
        raise HTTPException(status_code=500, detail=f"Task publisher leaderboard failed: {exc}")
