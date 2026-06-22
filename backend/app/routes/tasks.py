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
    TaskCompleteRequest, TaskFailRequest, TaskStatusResponse,
    TaskApplyRequest, TaskApplyResponse,
    TaskAssignRequest, TaskAssignResponse,
    TaskSubmitRequest, TaskSubmitResponse,
    TaskReviewRequest, TaskReviewResponse,
    AgentTasksResponse
)
from app.database import get_db_connection
from app.dependencies import get_current_owner, get_current_agent, get_current_user
from app.fraud_detection import detect_collusion
from app.services import anti_fraud as anti_fraud_svc
from app.routes.notifications import create_notification
import logging

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

XP_REWARD_ON_ACCEPT = 50


TASK_LIST_COLUMNS = """
    t.id, t.owner_id, t.title, t.description, t.category, t.difficulty,
    t.reward_points, t.status, t.created_at, t.updated_at, t.completed_at,
    t.deadline, t.assigned_agent_id, t.estimated_hours, t.deliverable_type,
    t.required_capabilities, t.verification_required
"""


def _task_status_response(row) -> TaskStatusResponse:
    return TaskStatusResponse(
        id=row["id"],
        status=row["status"],
        assigned_agent_id=row.get("assigned_agent_id"),
        updated_at=row.get("updated_at"),
        completed_at=row.get("completed_at"),
    )


def _ids_equal(left, right) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _award_task_acceptance(conn, agent_id: UUID):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE agents
        SET
            xp = xp + %s,
            level = FLOOR((xp + %s) / 100.0) + 1,
            total_tasks_completed = total_tasks_completed + 1
        WHERE id = %s
        RETURNING xp, level, total_tasks_completed
        """,
        (XP_REWARD_ON_ACCEPT, XP_REWARD_ON_ACCEPT, str(agent_id)),
    )
    agent_stats = cur.fetchone()
    if agent_stats:
        logger.info(
            "Agent %s gained %s XP, now level %s with %s XP",
            agent_id,
            XP_REWARD_ON_ACCEPT,
            agent_stats["level"],
            agent_stats["xp"],
        )
    _check_and_award_badges(conn, agent_id)


@router.post("", response_model=TaskCreateResponse)
def create_task(
    request: TaskCreateRequest,
    owner_id: UUID = Depends(get_current_owner)
):
    """Create a new task (Owner only)"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # required_capabilities 列是 JSONB —— 用 psycopg2.extras.Json 包一下，
            # 否则 psycopg2 会把 list 当成 text[] 数组传过去，引发类型不匹配。
            from psycopg2.extras import Json
            required_capabilities = request.required_capabilities or []
            reward_points = request.budget if request.budget is not None else request.reward_points
            difficulty = request.priority or request.difficulty

            cur.execute(
                """
                INSERT INTO tasks (
                    owner_id, title, description, category, difficulty,
                    required_capabilities, estimated_hours, reward_points,
                    deadline, deliverable_type, assigned_agent_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    str(owner_id), request.title, request.description, request.category,
                    difficulty, Json(required_capabilities), request.estimated_hours,
                    reward_points, request.deadline, request.deliverable_type, None
                )
            )
            result = cur.fetchone()
            task_id = result['id']

            logger.info(f"Task created: {task_id} by owner {owner_id}")

            return TaskCreateResponse(task_id=task_id)

    except Exception as e:
        logger.error(f"Task creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task creation failed: {str(e)}"
        )

@router.get("", response_model=List[TaskListResponse])
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None)
):
    """List tasks with optional filters."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            query = f"""
                SELECT {TASK_LIST_COLUMNS}
                FROM tasks t
                WHERE 1=1
            """
            params = []

            if status_filter:
                query += " AND t.status = %s"
                params.append(status_filter)

            if category:
                query += " AND t.category = %s"
                params.append(category)

            query += " ORDER BY t.created_at DESC"

            cur.execute(query, params)
            tasks = cur.fetchall()

            return [TaskListResponse(**dict(task)) for task in tasks]

    except Exception as e:
        logger.error(f"Task listing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task listing failed"
        )


@router.get("/pending", response_model=List[TaskListResponse])
def pending_tasks(agent_id: UUID = Depends(get_current_agent)):
    """Return open tasks visible to the polling agent."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT {TASK_LIST_COLUMNS}
                FROM tasks t
                WHERE t.status = 'open'
                ORDER BY
                    CASE t.difficulty
                        WHEN 'urgent' THEN 0
                        WHEN 'normal' THEN 1
                        WHEN 'low' THEN 2
                        ELSE 1
                    END,
                    t.created_at ASC
                """,
                (),
            )
            return [TaskListResponse(**dict(task)) for task in cur.fetchall()]

    except Exception as e:
        logger.error(f"Pending task fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pending task fetch failed",
        )


@router.post("/{task_id}/claim", response_model=TaskStatusResponse)
def claim_task(
    task_id: UUID,
    agent_id: UUID = Depends(get_current_agent),
):
    """Agent claims an open task."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id, owner_id, title FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if task["status"] != "open":
                raise HTTPException(status_code=409, detail="Task is not open")
            assigned_agent_id = task.get("assigned_agent_id")
            if assigned_agent_id and not _ids_equal(assigned_agent_id, agent_id):
                raise HTTPException(status_code=403, detail="Task is reserved for another agent")

            cur.execute(
                """
                UPDATE tasks
                SET assigned_agent_id = %s, status = 'claimed', updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at, owner_id, title
                """,
                (str(agent_id), str(task_id)),
            )
            updated_task = cur.fetchone()

            # 通知任务发布者
            create_notification(
                conn,
                updated_task['owner_id'],
                'task_accepted',
                '任务已被接受',
                f'您的任务「{updated_task["title"]}」已被 Agent 接受',
                f'/tasks/{task_id}'
            )

            return _task_status_response(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task claim failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task claim failed",
        )


@router.post("/{task_id}/start", response_model=TaskStatusResponse)
def start_task(
    task_id: UUID,
    agent_id: UUID = Depends(get_current_agent),
):
    """Assigned agent starts a claimed task."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id, owner_id, title FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if not _ids_equal(task.get("assigned_agent_id"), agent_id):
                raise HTTPException(status_code=403, detail="You are not assigned to this task")
            if task["status"] != "claimed":
                raise HTTPException(status_code=409, detail="Task is not claimed")

            cur.execute(
                """
                UPDATE tasks
                SET status = 'in_progress', updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at
                """,
                (str(task_id),),
            )
            updated_task = cur.fetchone()

            logger.info(f"Task {task_id} started by agent {agent_id}")
            return _task_status_response(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task start failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task start failed",
        )


@router.post("/{task_id}/complete", response_model=TaskStatusResponse)
def complete_task(
    task_id: UUID,
    request: TaskCompleteRequest,
    agent_id: UUID = Depends(get_current_agent),
):
    """Deprecated: agents submit work; owners accept submitted work."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Agents cannot complete tasks directly. Submit deliverables, then the task owner accepts them.",
    )


@router.post("/{task_id}/accept", response_model=TaskStatusResponse)
def accept_task(
    task_id: UUID,
    owner_id: UUID = Depends(get_current_owner),
):
    """Owner accepts a submitted task and marks it completed."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id, owner_id, title FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if not _ids_equal(task.get("owner_id"), owner_id):
                raise HTTPException(status_code=403, detail="You don't own this task")
            if task["status"] != "submitted":
                raise HTTPException(status_code=409, detail="Task is not submitted")

            cur.execute(
                """
                UPDATE tasks
                SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at
                """,
                (str(task_id),),
            )
            updated_task = cur.fetchone()

            if task.get("assigned_agent_id"):
                _award_task_acceptance(conn, task["assigned_agent_id"])

            create_notification(
                conn,
                task["owner_id"],
                "task_completed",
                "任务已验收",
                f"任务「{task['title']}」已验收通过",
                f"/tasks/{task_id}",
            )

            logger.info(f"Task {task_id} accepted by owner {owner_id}")
            return _task_status_response(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task acceptance failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task acceptance failed",
        )


@router.post("/{task_id}/request-revision", response_model=TaskStatusResponse)
def request_revision_task(
    task_id: UUID,
    owner_id: UUID = Depends(get_current_owner),
):
    """Owner sends a submitted task back to in-progress."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id, owner_id, title FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if not _ids_equal(task.get("owner_id"), owner_id):
                raise HTTPException(status_code=403, detail="You don't own this task")
            if task["status"] != "submitted":
                raise HTTPException(status_code=409, detail="Task is not submitted")

            cur.execute(
                """
                UPDATE tasks
                SET status = 'in_progress', updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at
                """,
                (str(task_id),),
            )
            updated_task = cur.fetchone()

            logger.info(f"Task {task_id} sent back for revision by owner {owner_id}")
            return _task_status_response(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task revision request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task revision request failed",
        )


@router.post("/{task_id}/cancel", response_model=TaskStatusResponse)
def cancel_task(
    task_id: UUID,
    owner_id: UUID = Depends(get_current_owner),
):
    """Owner cancels a task that is not completed."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id, owner_id, title FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if not _ids_equal(task.get("owner_id"), owner_id):
                raise HTTPException(status_code=403, detail="You don't own this task")
            if task["status"] == "completed":
                raise HTTPException(status_code=409, detail="Completed tasks cannot be cancelled")

            cur.execute(
                """
                UPDATE tasks
                SET status = 'cancelled', updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at
                """,
                (str(task_id),),
            )
            updated_task = cur.fetchone()

            logger.info(f"Task {task_id} cancelled by owner {owner_id}")
            return _task_status_response(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task cancellation failed",
        )


@router.post("/{task_id}/fail", response_model=TaskStatusResponse)
def fail_task(
    task_id: UUID,
    request: TaskFailRequest,
    agent_id: UUID = Depends(get_current_agent),
):
    """Agent marks an in-progress task as failed."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, status, assigned_agent_id FROM tasks WHERE id = %s FOR UPDATE",
                (str(task_id),),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            if not _ids_equal(task.get("assigned_agent_id"), agent_id):
                raise HTTPException(status_code=403, detail="You are not assigned to this task")
            if task["status"] != "in_progress":
                raise HTTPException(status_code=409, detail="Task is not in progress")

            cur.execute(
                """
                UPDATE tasks
                SET status = 'failed', updated_at = NOW()
                WHERE id = %s
                RETURNING id, status, assigned_agent_id, updated_at, completed_at
                """,
                (str(task_id),),
            )
            logger.info(f"Task {task_id} failed by agent {agent_id}: {request.error}")
            return _task_status_response(cur.fetchone())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task failure update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task failure update failed",
        )


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task_detail(task_id: UUID):
    """Get task detail with applications, submission, and review"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get task
            cur.execute("SELECT * FROM tasks WHERE id = %s", (str(task_id),))
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            # Get applications (safely handle if table doesn't exist or is empty)
            applications = []
            try:
                cur.execute(
                    "SELECT * FROM task_applications WHERE task_id = %s ORDER BY applied_at DESC",
                    (str(task_id),)
                )
                applications = cur.fetchall()
            except Exception as app_err:
                logger.warning(f"Failed to fetch applications: {app_err}")
            
            # Get submission (safely handle if table doesn't exist or is empty)
            submission = None
            try:
                cur.execute(
                    "SELECT * FROM task_submissions WHERE task_id = %s ORDER BY submitted_at DESC LIMIT 1",
                    (str(task_id),)
                )
                submission = cur.fetchone()
            except Exception as sub_err:
                logger.warning(f"Failed to fetch submission: {sub_err}")
            
            # Get review (safely handle if table doesn't exist or is empty)
            review = None
            if submission:
                try:
                    cur.execute(
                        "SELECT * FROM task_reviews WHERE submission_id = %s LIMIT 1",
                        (submission['id'],)
                    )
                    review = cur.fetchone()
                except Exception as rev_err:
                    logger.warning(f"Failed to fetch review: {rev_err}")
            
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
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task detail fetch failed: {str(e)}"
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
            cur.execute("SELECT status FROM tasks WHERE id = %s", (str(task_id),))
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
                (str(task_id), str(agent_id), request.cover_letter, request.estimated_completion_time)
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
            cur.execute("SELECT owner_id, status FROM tasks WHERE id = %s", (str(task_id),))
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
                SET assigned_agent_id = %s, status = 'claimed', updated_at = NOW()
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
                (str(task_id),)
            )
            task = cur.fetchone()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            if not _ids_equal(task['assigned_agent_id'], agent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this task"
                )
            if task["status"] != "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Task is not in progress"
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
                (str(task_id),)
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
                (str(task_id),)
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
            
            # Run fraud detection (collusion check + 5 anti-fraud rules)
            try:
                risk_score = detect_collusion(owner_id, submission['agent_id'], task_id)
                if risk_score > 0.7:
                    logger.warning(f"High collusion risk detected: {risk_score:.2f} for task {task_id}")
            except Exception as fraud_err:
                logger.error(f"Fraud detection failed: {fraud_err}")
                # Don't block review on fraud detection failure

            # New: 5-rule anti_fraud service + reputation_scores refresh
            try:
                triggered = anti_fraud_svc.check_review_for_fraud(
                    conn, owner_id, submission['agent_id'], task_id
                )
                if triggered:
                    logger.warning(
                        "anti_fraud rules triggered for task %s by owner %s: %s",
                        task_id, owner_id,
                        [a.rule_name for a in triggered],
                    )
            except Exception as af_err:
                logger.error(f"anti_fraud service failed: {af_err}")
            
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


@router.post("/{task_id}/rate")
def rate_task(
    task_id: UUID,
    rating: int = Query(..., ge=1, le=5),
    comment: Optional[str] = None,
    user_id: UUID = Depends(get_current_user)
):
    """用户给已完成的任务评分"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 验证任务存在且已完成
            cur.execute(
                "SELECT owner_id, assigned_agent_id, status FROM tasks WHERE id = %s",
                (str(task_id),)
            )
            task = cur.fetchone()

            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )

            if task['status'] != 'completed':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task is not completed yet"
                )

            if task['owner_id'] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this task"
                )

            if not task['assigned_agent_id']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Task has no assigned agent"
                )

            agent_id = task['assigned_agent_id']

            # 插入评分（如果已存在则更新）
            cur.execute(
                """
                INSERT INTO task_ratings (task_id, user_id, agent_id, rating, comment)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE
                SET rating = EXCLUDED.rating, comment = EXCLUDED.comment
                RETURNING id
                """,
                (str(task_id), str(user_id), str(agent_id), rating, comment)
            )
            result = cur.fetchone()

            # 更新 agent 游戏化数据
            xp_gain = rating * 20  # 1星=20XP, 5星=100XP
            cur.execute(
                """
                UPDATE agents
                SET
                    xp = xp + %s,
                    level = FLOOR((xp + %s) / 100.0) + 1,
                    total_tasks_completed = total_tasks_completed + 1
                WHERE id = %s
                RETURNING xp, level
                """,
                (xp_gain, xp_gain, str(agent_id))
            )
            agent_result = cur.fetchone()

            # 创建通知给 agent owner
            cur.execute("SELECT owner_id FROM agents WHERE id = %s", (str(agent_id),))
            agent_owner = cur.fetchone()
            if agent_owner:
                create_notification(
                    conn,
                    agent_owner['owner_id'],
                    'task_rated',
                    f'任务获得 {rating} 星评价',
                    f'您的 Agent 完成的任务获得了 {rating} 星评价，获得 {xp_gain} XP！',
                    f'/tasks/{task_id}'
                )

            # 检查徽章
            _check_and_award_badges(conn, agent_id)

            logger.info(f"Task {task_id} rated {rating} stars, agent {agent_id} gained {xp_gain} XP")

            return {
                "success": True,
                "rating_id": result['id'],
                "xp_gained": xp_gain,
                "agent_xp": agent_result['xp'],
                "agent_level": agent_result['level']
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task rating failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task rating failed"
        )


def _check_and_award_badges(conn, agent_id: UUID):
    """检查并授予徽章"""
    cur = conn.cursor()

    # 徽章 1: 首次完成任务
    cur.execute(
        "SELECT total_tasks_completed FROM agents WHERE id = %s",
        (str(agent_id),)
    )
    agent = cur.fetchone()
    if agent and agent['total_tasks_completed'] == 1:
        cur.execute(
            """
            INSERT INTO badges (agent_id, badge_type)
            VALUES (%s, %s)
            ON CONFLICT (agent_id, badge_type) DO NOTHING
            """,
            (str(agent_id), 'first_task')
        )

    # 徽章 2: 连续 5 个 5 星评价
    cur.execute(
        """
        SELECT COUNT(*) as count
        FROM (
            SELECT rating
            FROM task_ratings
            WHERE agent_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        ) recent
        WHERE rating = 5
        """,
        (str(agent_id),)
    )
    result = cur.fetchone()
    if result and result['count'] == 5:
        cur.execute(
            """
            INSERT INTO badges (agent_id, badge_type)
            VALUES (%s, %s)
            ON CONFLICT (agent_id, badge_type) DO NOTHING
            """,
            (str(agent_id), 'five_star_streak')
        )

    # 徽章 3: 完成 10 个任务
    if agent and agent['total_tasks_completed'] >= 10:
        cur.execute(
            """
            INSERT INTO badges (agent_id, badge_type)
            VALUES (%s, %s)
            ON CONFLICT (agent_id, badge_type) DO NOTHING
            """,
            (str(agent_id), 'veteran')
        )
