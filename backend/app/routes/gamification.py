"""
Gamification API routes - Agent stats and leaderboard
"""
from fastapi import APIRouter, HTTPException, status, Query
from uuid import UUID
from typing import Optional, List
from app.database import get_db_connection
import logging

router = APIRouter(prefix="/gamification", tags=["gamification"])
logger = logging.getLogger(__name__)


@router.get("/agent/{agent_id}/stats")
def get_agent_stats(agent_id: UUID):
    """获取 Agent 的游戏化统计数据"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 获取 Agent 基础统计
            cur.execute(
                """
                SELECT
                    id, name, xp, level,
                    total_tasks_completed, total_tasks_failed,
                    avg_rating
                FROM agents
                WHERE id = %s
                """,
                (str(agent_id),)
            )
            agent = cur.fetchone()

            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )

            # 获取徽章
            cur.execute(
                """
                SELECT badge_type, earned_at
                FROM badges
                WHERE agent_id = %s
                ORDER BY earned_at DESC
                """,
                (str(agent_id),)
            )
            badges = [dict(b) for b in cur.fetchall()]

            # 计算成功率
            total = agent['total_tasks_completed'] + agent['total_tasks_failed']
            success_rate = (agent['total_tasks_completed'] / total * 100) if total > 0 else 0

            # 获取最近评分
            cur.execute(
                """
                SELECT rating, comment, created_at
                FROM task_ratings
                WHERE agent_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (str(agent_id),)
            )
            recent_ratings = [dict(r) for r in cur.fetchall()]

            return {
                "agent_id": agent['id'],
                "name": agent['name'],
                "level": agent['level'],
                "xp": agent['xp'],
                "xp_to_next_level": (agent['level'] * 100) - agent['xp'],
                "total_tasks_completed": agent['total_tasks_completed'],
                "total_tasks_failed": agent['total_tasks_failed'],
                "success_rate": round(success_rate, 2),
                "avg_rating": float(agent['avg_rating']) if agent['avg_rating'] else None,
                "badges": badges,
                "recent_ratings": recent_ratings
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent stats failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Get agent stats failed"
        )


@router.get("/leaderboard")
def get_leaderboard(
    period: str = Query("all", pattern="^(week|month|all)$"),
    limit: int = Query(10, ge=1, le=100)
):
    """获取排行榜"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 根据时间范围构建查询
            time_filter = ""
            if period == "week":
                time_filter = "AND tr.created_at >= NOW() - INTERVAL '7 days'"
            elif period == "month":
                time_filter = "AND tr.created_at >= NOW() - INTERVAL '30 days'"

            # 获取排行榜数据
            cur.execute(
                f"""
                SELECT
                    a.id,
                    a.name,
                    a.level,
                    a.xp,
                    a.total_tasks_completed,
                    a.avg_rating,
                    COUNT(tr.id) as period_tasks,
                    AVG(tr.rating)::DECIMAL(3,2) as period_avg_rating,
                    (
                        SELECT COUNT(*)
                        FROM badges b
                        WHERE b.agent_id = a.id
                    ) as badge_count
                FROM agents a
                LEFT JOIN task_ratings tr ON tr.agent_id = a.id {time_filter}
                WHERE a.total_tasks_completed > 0
                GROUP BY a.id, a.name, a.level, a.xp, a.total_tasks_completed, a.avg_rating
                ORDER BY a.xp DESC, a.avg_rating DESC
                LIMIT %s
                """,
                (limit,)
            )
            leaderboard = cur.fetchall()

            return {
                "period": period,
                "leaders": [dict(row) for row in leaderboard]
            }

    except Exception as e:
        logger.error(f"Get leaderboard failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Get leaderboard failed"
        )


@router.get("/badges")
def list_badge_types():
    """列出所有徽章类型和获得条件"""
    return {
        "badges": [
            {
                "type": "first_task",
                "name": "新手上路",
                "description": "完成第一个任务",
                "icon": "🎯"
            },
            {
                "type": "five_star_streak",
                "name": "五星连胜",
                "description": "连续获得 5 个五星好评",
                "icon": "⭐"
            },
            {
                "type": "veteran",
                "name": "老手",
                "description": "完成 10 个任务",
                "icon": "🏆"
            }
        ]
    }
