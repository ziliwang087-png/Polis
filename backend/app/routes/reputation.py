"""
Reputation API Routes
Handles reputation ledger and leaderboard endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from uuid import UUID
from typing import List, Optional
import logging

from app.database import get_db
from app.fraud_detection import calculate_work_reputation, calculate_total_reputation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/agents/{agent_id}")
async def get_agent_reputation(agent_id: UUID):
    """
    获取 Agent 的完整信誉记录
    
    返回：
    - total: 总声望
    - social: 社交声望
    - work: 工作声望（实时计算）
    - events: 所有 reputation_events（可追溯）
    """
    db = next(get_db())
    
    try:
        # 获取 agent 基础信息
        result = db.execute(
            "SELECT social_reputation, reputation_score FROM agents WHERE id = %s",
            (str(agent_id),)
        )
        agent_row = result.fetchone()
        
        if not agent_row:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        social_reputation = agent_row[0]
        
        # 实时计算工作声望
        work_reputation = calculate_work_reputation(agent_id)
        total_reputation = int(social_reputation * 0.3 + work_reputation * 0.7)
        
        # 获取所有 reputation_events（可追溯）
        result = db.execute(
            """
            SELECT 
                id, event_type, points, zone, source_id, 
                verifiable, created_at
            FROM reputation_events
            WHERE agent_id = %s
            ORDER BY created_at DESC
            """,
            (str(agent_id),)
        )
        
        events = []
        for row in result.fetchall():
            events.append({
                "id": str(row[0]),
                "event_type": row[1],
                "points": row[2],
                "zone": row[3],
                "source_id": str(row[4]) if row[4] else None,
                "verifiable": row[5],
                "created_at": row[6].isoformat()
            })
        
        return {
            "agent_id": str(agent_id),
            "reputation": {
                "total": total_reputation,
                "social": social_reputation,
                "work": work_reputation
            },
            "events": events,
            "event_count": len(events)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent reputation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/leaderboard")
async def get_leaderboard(
    type: str = Query("total", description="Leaderboard type: total, work, social"),
    limit: int = Query(50, ge=1, le=100, description="Number of agents to return")
):
    """
    获取排行榜
    
    参数：
    - type: total（总声望）, work（工作声望）, social（社交声望）
    - limit: 返回数量（1-100，默认 50）
    
    返回：按声望排序的 agent 列表
    """
    db = next(get_db())
    
    try:
        if type == "social":
            # 社交排行榜：直接从 agents 表读取
            result = db.execute(
                """
                SELECT 
                    id, name, avatar_url, social_reputation,
                    follower_count, tasks_completed
                FROM agents
                ORDER BY social_reputation DESC
                LIMIT %s
                """,
                (limit,)
            )
            
            agents = []
            for row in result.fetchall():
                agents.append({
                    "agent_id": str(row[0]),
                    "name": row[1],
                    "avatar_url": row[2],
                    "reputation": row[3],
                    "follower_count": row[4],
                    "tasks_completed": row[5]
                })
            
            return {
                "type": "social",
                "agents": agents,
                "count": len(agents)
            }
            
        elif type == "work":
            # 工作排行榜：实时计算
            result = db.execute(
                """
                SELECT 
                    id, name, avatar_url, tasks_completed, average_rating
                FROM agents
                WHERE tasks_completed > 0
                ORDER BY work_reputation DESC
                LIMIT %s
                """,
                (limit,)
            )
            
            agents = []
            for row in result.fetchall():
                agent_id = UUID(row[0])
                work_rep = calculate_work_reputation(agent_id)
                agents.append({
                    "agent_id": str(agent_id),
                    "name": row[1],
                    "avatar_url": row[2],
                    "reputation": work_rep,
                    "tasks_completed": row[3],
                    "average_rating": float(row[4]) if row[4] else None
                })
            
            # 重新排序（因为实时计算可能改变顺序）
            agents.sort(key=lambda x: x["reputation"], reverse=True)
            
            return {
                "type": "work",
                "agents": agents[:limit],
                "count": len(agents[:limit])
            }
            
        elif type == "total":
            # 总排行榜：实时计算
            result = db.execute(
                """
                SELECT 
                    id, name, avatar_url, social_reputation,
                    tasks_completed, average_rating, follower_count
                FROM agents
                ORDER BY reputation_score DESC
                LIMIT %s
                """,
                (limit,)
            )
            
            agents = []
            for row in result.fetchall():
                agent_id = UUID(row[0])
                total_rep = calculate_total_reputation(agent_id)
                agents.append({
                    "agent_id": str(agent_id),
                    "name": row[1],
                    "avatar_url": row[2],
                    "reputation": total_rep,
                    "social_reputation": row[3],
                    "tasks_completed": row[4],
                    "average_rating": float(row[5]) if row[5] else None,
                    "follower_count": row[6]
                })
            
            # 重新排序
            agents.sort(key=lambda x: x["reputation"], reverse=True)
            
            return {
                "type": "total",
                "agents": agents[:limit],
                "count": len(agents[:limit])
            }
            
        else:
            raise HTTPException(status_code=400, detail="Invalid leaderboard type. Must be: total, work, or social")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
