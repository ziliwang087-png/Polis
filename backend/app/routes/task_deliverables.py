"""
Task deliverable upload/list/delete routes.
"""
import logging
from datetime import datetime
from typing import Optional, Tuple, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import settings
from app.database import get_db_connection
from app.dependencies import get_current_user
from app.services import storage

router = APIRouter(prefix="/tasks/{task_id}/deliverables", tags=["task-deliverables"])
logger = logging.getLogger(__name__)

MAX_DELIVERABLE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".zip",
    ".pdf", ".docx", ".txt", ".md",
    ".png", ".jpg", ".jpeg",
}


class TaskDeliverableResponse(BaseModel):
    id: UUID
    task_id: UUID
    uploaded_by: UUID
    file_name: str
    file_url: str
    file_size: int
    description: Optional[str] = None
    created_at: datetime


CurrentUser = Tuple[UUID, str]


def _ids_equal(left, right) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _extension(filename: str) -> str:
    import pathlib
    return pathlib.Path(filename or "").suffix.lower()


def _ensure_allowed_file(filename: str, size: int):
    if size > MAX_DELIVERABLE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")
    ext = _extension(filename)
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported deliverable file type")


def _load_task(cur, task_id: UUID):
    cur.execute(
        "SELECT id, owner_id, assigned_agent_id, status FROM tasks WHERE id = %s",
        (str(task_id),),
    )
    task = cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _can_view(task, current_user: CurrentUser) -> bool:
    subject_id, subject_type = current_user
    if subject_type == "agent":
        return _ids_equal(task.get("assigned_agent_id"), subject_id)
    return _ids_equal(task.get("owner_id"), subject_id)


def _can_upload(task, current_user: CurrentUser) -> bool:
    subject_id, subject_type = current_user
    return subject_type == "agent" and _ids_equal(task.get("assigned_agent_id"), subject_id)


@router.post("", response_model=TaskDeliverableResponse)
async def upload_deliverable(
    task_id: UUID,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Assigned agent uploads a deliverable file."""
    subject_id, _ = current_user
    try:
        content = await file.read()
        _ensure_allowed_file(file.filename or "deliverable", len(content))

        with get_db_connection() as conn:
            cur = conn.cursor()
            task = _load_task(cur, task_id)
            if not _can_upload(task, current_user):
                raise HTTPException(status_code=403, detail="Only the assigned agent can upload deliverables")
            if task["status"] not in ("in_progress", "submitted"):
                raise HTTPException(status_code=409, detail="Task is not ready for deliverables")

            file_url = storage.upload_bytes(
                data=content,
                filename=file.filename or "deliverable",
                content_type=file.content_type or "application/octet-stream",
                owner_id=subject_id,
                bucket=settings.SUPABASE_DELIVERABLES_BUCKET,
                path_prefix=str(task_id),
            )
            cur.execute(
                """
                INSERT INTO task_deliverables (
                    task_id, uploaded_by, file_name, file_url, file_size, description
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, task_id, uploaded_by, file_name, file_url, file_size, description, created_at
                """,
                (
                    str(task_id),
                    str(subject_id),
                    file.filename or "deliverable",
                    file_url,
                    len(content),
                    description,
                ),
            )
            return TaskDeliverableResponse(**dict(cur.fetchone()))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Deliverable upload failed")
        raise HTTPException(status_code=500, detail=f"Deliverable upload failed: {exc}")


@router.get("", response_model=List[TaskDeliverableResponse])
def list_deliverables(
    task_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List task deliverables for the task owner or assigned agent."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            task = _load_task(cur, task_id)
            if not _can_view(task, current_user):
                raise HTTPException(status_code=403, detail="You cannot view these deliverables")

            cur.execute(
                """
                SELECT id, task_id, uploaded_by, file_name, file_url, file_size, description, created_at
                FROM task_deliverables
                WHERE task_id = %s
                ORDER BY created_at DESC
                """,
                (str(task_id),),
            )
            return [TaskDeliverableResponse(**dict(row)) for row in cur.fetchall()]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Deliverable list failed")
        raise HTTPException(status_code=500, detail=f"Deliverable list failed: {exc}")


@router.delete("/{deliverable_id}")
def delete_deliverable(
    task_id: UUID,
    deliverable_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a deliverable. Allowed for the uploader or task owner."""
    subject_id, _ = current_user
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            task = _load_task(cur, task_id)

            cur.execute(
                "SELECT * FROM task_deliverables WHERE id = %s AND task_id = %s",
                (str(deliverable_id), str(task_id)),
            )
            deliverable = cur.fetchone()
            if not deliverable:
                raise HTTPException(status_code=404, detail="Deliverable not found")
            if not (_ids_equal(task.get("owner_id"), subject_id) or _ids_equal(deliverable.get("uploaded_by"), subject_id)):
                raise HTTPException(status_code=403, detail="You cannot delete this deliverable")

            cur.execute(
                "DELETE FROM task_deliverables WHERE id = %s AND task_id = %s RETURNING *",
                (str(deliverable_id), str(task_id)),
            )
            return {"deleted": bool(cur.fetchone())}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Deliverable delete failed")
        raise HTTPException(status_code=500, detail=f"Deliverable delete failed: {exc}")
