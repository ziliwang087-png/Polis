"""
Task API routes
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from uuid import UUID
from typing import Optional, List
import hashlib
import json
from datetime import datetime
from app.models import (
    TaskCreateRequest, TaskCreateResponse,
    TaskListResponse, TaskDetailResponse,
    TaskApplyRequest, TaskApplyResponse,
    TaskAssignRequest, TaskAssignResponse,
    TaskSubmitRequest, TaskSubmitResponse,
    TaskReviewRequest, TaskReviewResponse,
    AgentTasksResponse
)
from app.database import get_db_connection
from app.dependencies import get_current_owner, get_current_agent
from app.fraud_detection import detect_collusion
import logging

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

@router.post("", response_model=TaskCreateResponse)
def create_task(
    request: TaskCreateRequest,
    owner_id: UUID = Depends(get_current_owner)
):
    """Create a new task (Owner only)"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Convert lists to JSONB
            required_capabilities = request.required_capabilities if request.required_capabilities else []
            
            cur.execute(
                """
                INSERT INTO tasks (
                    owner_id, title, description, category, difficulty,
                    required_capabilities, estimated_hours, reward_points,
                    deadline, deliverable_type
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    owner_id, request.title, request.description, request.category,
                    request.difficulty, required_capabilities, request.estimated_hours,
                    request.reward_points, request.deadline, request.deliverable_type
                )
            )
            result = cur.fetchone()
            task_id = result['id']
            
            logger.info(f"Task created: {task_id} by owner {owner_id}")
            
            return TaskCreateResponse(task_id=task_id)
            
    except Exception as e:
        logger.error(f"Task creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task creation failed"
        )

@router.get("", response_model=List[TaskListResponse])
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None)
):
    """List tasks with optional filters"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            query = "SELECT * FROM tasks WHERE 1=1"
            params = []
            
            if status_filter:
                query += " AND status = %s"
                params.append(status_filter)
            
            if category:
                query += " AND category = %s"
                params.append(category)
            
            query += " ORDER BY created_at DESC"
            
            cur.execute(query, params)
            tasks = cur.fetchall()
            
            return [TaskListResponse(**dict(task)) for task in tasks]
            
    except Exception as e:
        logger.error(f"Task listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task listing failed"
        )

@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task_detail(task_id: UUID):
    """Get task detail with applications, submission, and review"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get task
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            # Get applications
            cur.execute(
                "SELECT * FROM task_applications WHERE task_id = %s ORDER BY applied_at DESC",
                (task_id,)
            )
            applications = cur.fetchall()
            
            # Get submission
            cur.execute(
                "SELECT * FROM task_submissions WHERE task_id = %s ORDER BY submitted_at DESC LIMIT 1",
                (task_id,)
            )
            submission = cur.fetchone()
            
            # Get review
            review = None
            if submission:
                cur.execute(
                    "SELECT * FROM task_reviews WHERE submission_id = %s LIMIT 1",
                    (submission['id'],)
                )
                review = cur.fetchone()
            
            return TaskDetailResponse(
                task=dict(task),
                applications=[dict(app) for app in applications],
                submission=dict(submission) if submission else None,
                review=dict(review) if review else None
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task detail fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task detail fetch failed"
        )

@router.post("/{task_id}/apply", response_model=TaskApplyResponse)
def apply_to_task(
    task_id: UUID,
    request: TaskApplyRequest,
    agent_id: UUID = Depends(get_current_agent)
):
    """Agent applies to a task"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Check task exists and is open
            cur.execute("SELECT status FROM tasks WHERE id = %s", (task_id,))
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if task['status'] != 'open':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task is not open for applications"
                )
            
            # Insert application
            cur.execute(
                """
                INSERT INTO task_applications (
                    task_id, agent_id, cover_letter, estimated_completion_time
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (task_id, agent_id, request.cover_letter, request.estimated_completion_time)
            )
            result = cur.fetchone()
            application_id = result['id']
            
            logger.info(f"Agent {agent_id} applied to task {task_id}")
            
            return TaskApplyResponse(application_id=application_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task application failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task application failed"
        )

@router.post("/{task_id}/assign", response_model=TaskAssignResponse)
def assign_task(
    task_id: UUID,
    request: TaskAssignRequest,
    owner_id: UUID = Depends(get_current_owner)
):
    """Owner assigns task to an agent"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Verify owner owns the task
            cur.execute("SELECT owner_id, status FROM tasks WHERE id = %s", (task_id,))
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if task['owner_id'] != owner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this task"
                )
            
            # Update task
            cur.execute(
                """
                UPDATE tasks 
                SET assigned_agent_id = %s, status = 'in_progress', updated_at = NOW()
                WHERE id = %s
                """,
                (request.agent_id, task_id)
            )
            
            # Update application status
            cur.execute(
                """
                UPDATE task_applications
                SET status = 'accepted', reviewed_at = NOW()
                WHERE task_id = %s AND agent_id = %s
                """,
                (task_id, request.agent_id)
            )
            
            # Reject other applications
            cur.execute(
                """
                UPDATE task_applications
                SET status = 'rejected', reviewed_at = NOW()
                WHERE task_id = %s AND agent_id != %s
                """,
                (task_id, request.agent_id)
            )
            
            logger.info(f"Task {task_id} assigned to agent {request.agent_id}")
            
            return TaskAssignResponse(assigned=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task assignment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task assignment failed"
        )

@router.post("/{task_id}/submit", response_model=TaskSubmitResponse)
def submit_task(
    task_id: UUID,
    request: TaskSubmitRequest,
    agent_id: UUID = Depends(get_current_agent)
):
    """Agent submits task deliverable"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Verify agent is assigned to task
            cur.execute(
                "SELECT assigned_agent_id, status FROM tasks WHERE id = %s",
                (task_id,)
            )
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if task['assigned_agent_id'] != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this task"
                )
            
            # Calculate hash if content provided
            result_hash = None
            if request.deliverable_url:
                result_hash = hashlib.sha256(request.deliverable_url.encode()).hexdigest()
            
            # Convert lists to JSONB
            evidence_urls = request.evidence_urls if request.evidence_urls else []
            work_log = request.work_log if request.work_log else []
            
            # Insert submission
            cur.execute(
                """
                INSERT INTO task_submissions (
                    task_id, agent_id, content, deliverable_url,
                    result_hash, evidence_urls, work_log
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    task_id, agent_id, request.content, request.deliverable_url,
                    result_hash, evidence_urls, work_log
                )
            )
            result = cur.fetchone()
            submission_id = result['id']
            
            # Update task status
            cur.execute(
                """
                UPDATE tasks
                SET status = 'submitted', updated_at = NOW()
                WHERE id = %s
                """,
                (task_id,)
            )
            
            logger.info(f"Task {task_id} submitted by agent {agent_id}")
            
            return TaskSubmitResponse(submission_id=submission_id, result_hash=result_hash)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task submission failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task submission failed"
        )

@router.post("/{task_id}/review", response_model=TaskReviewResponse)
def review_task(
    task_id: UUID,
    request: TaskReviewRequest,
    owner_id: UUID = Depends(get_current_owner)
):
    """Owner reviews task submission"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Verify owner owns the task
            cur.execute(
                "SELECT owner_id, assigned_agent_id FROM tasks WHERE id = %s",
                (task_id,)
            )
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if task['owner_id'] != owner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this task"
                )
            
            # Get submission
            cur.execute(
                "SELECT id, agent_id FROM task_submissions WHERE task_id = %s ORDER BY submitted_at DESC LIMIT 1",
                (task_id,)
            )
            submission = cur.fetchone()
            
            if not submission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No submission found for this task"
                )
            
            # Insert review
            cur.execute(
                """
                INSERT INTO task_reviews (
                    task_id, submission_id, reviewer_id, rating,
                    quality_score, timeliness_score, communication_score,
                    review_text, evidence_verified, verification_notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    task_id, submission['id'], owner_id, request.rating,
                    request.quality_score, request.timeliness_score,
                    request.communication_score, request.review_text,
                    request.evidence_verified, request.verification_notes
                )
            )
            result = cur.fetchone()
            review_id = result['id']
            
            # Update task status
            cur.execute(
                """
                UPDATE tasks
                SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (task_id,)
            )
            
            # Create reputation event
            points = request.rating * 20  # 1-5 rating → 20-100 points
            cur.execute(
                """
                INSERT INTO reputation_events (
                    agent_id, event_type, points, zone, source_id, verifiable
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (submission['agent_id'], 'task_completed', points, 'work', task_id, True)
            )
            
            # Update agent stats
            cur.execute(
                """
                UPDATE agents
                SET 
                    tasks_completed = tasks_completed + 1,
                    work_reputation = work_reputation + %s,
                    reputation_score = reputation_score + %s,
                    average_rating = (
                        SELECT AVG(rating)::DECIMAL(3,2)
                        FROM task_reviews tr
                        JOIN task_submissions ts ON tr.submission_id = ts.id
                        WHERE ts.agent_id = %s
                    )
                WHERE id = %s
                """,
                (points, points, submission['agent_id'], submission['agent_id'])
            )
            
            # Run fraud detection (collusion check)
            try:
                risk_score = detect_collusion(owner_id, submission['agent_id'], task_id)
                if risk_score > 0.7:
                    logger.warning(f"High collusion risk detected: {risk_score:.2f} for task {task_id}")
            except Exception as fraud_err:
                logger.error(f"Fraud detection failed: {fraud_err}")
                # Don't block review on fraud detection failure
            
            logger.info(f"Task {task_id} reviewed with rating {request.rating}")
            
            return TaskReviewResponse(review_id=review_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task review failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task review failed"
        )
