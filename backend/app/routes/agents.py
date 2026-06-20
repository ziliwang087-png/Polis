"""
Agent API routes
"""
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List, Dict, Any
from pydantic import BaseModel
from app.models import AgentTasksResponse
from app.database import get_db_connection
import logging

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


class AgentApplicationsResponse(BaseModel):
    applications: List[Dict[str, Any]]


@router.get("/{agent_id}/applications", response_model=AgentApplicationsResponse)
def get_agent_applications(agent_id: UUID):
    """Return tasks this agent has applied to (joined with task info)."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    a.id              AS application_id,
                    a.task_id,
                    a.cover_letter,
                    a.estimated_completion_time,
                    a.status          AS application_status,
                    a.applied_at,
                    t.id              AS task_id_dup,
                    t.title,
                    t.description,
                    t.category,
                    t.difficulty,
                    t.reward_points,
                    t.status          AS task_status,
                    t.deadline,
                    t.cover_emoji,
                    t.cover_gradient,
                    t.skills_required,
                    t.assigned_agent_id,
                    o.display_name    AS owner_display_name,
                    o.avatar_gradient AS owner_avatar_gradient
                FROM task_applications a
                JOIN tasks t  ON t.id = a.task_id
                LEFT JOIN owners o ON o.id = t.owner_id
                WHERE a.agent_id = %s
                ORDER BY a.applied_at DESC
                """,
                (str(agent_id),),
            )
            rows = cur.fetchall()
            return AgentApplicationsResponse(
                applications=[dict(row) for row in rows]
            )
    except Exception as e:
        logger.error(f"Agent applications fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent applications fetch failed",
        )

@router.get("/{agent_id}/tasks", response_model=AgentTasksResponse)
def get_agent_tasks(agent_id: UUID):
    """Get task history for an agent"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Verify agent exists
            cur.execute("SELECT id FROM agents WHERE id = %s", (str(agent_id),))
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
                (str(agent_id), str(agent_id))
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
