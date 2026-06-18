"""
Agent API routes
"""
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List, Dict, Any
from app.models import AgentTasksResponse
from app.database import get_db_connection
import logging

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.get("/{agent_id}/tasks", response_model=AgentTasksResponse)
def get_agent_tasks(agent_id: UUID):
    """Get task history for an agent"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Verify agent exists
            cur.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            
            # Get tasks
            cur.execute(
                """
                SELECT 
                    t.*,
                    ts.submitted_at,
                    tr.rating,
                    tr.review_text
                FROM tasks t
                LEFT JOIN task_submissions ts ON t.id = ts.task_id AND ts.agent_id = %s
                LEFT JOIN task_reviews tr ON ts.id = tr.submission_id
                WHERE t.assigned_agent_id = %s
                ORDER BY t.created_at DESC
                """,
                (agent_id, agent_id)
            )
            tasks = cur.fetchall()
            
            return AgentTasksResponse(tasks=[dict(task) for task in tasks])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent tasks fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent tasks fetch failed"
        )
